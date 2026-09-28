#!/usr/bin/env python3
"""Latency benchmark for the FULL local inference path: prose prompt -> LLM -> parser -> checker.

Measures what a user actually waits for, per prompt, broken into stages so you can see where the time
goes (spoiler: the local LLM dominates; retrieval/parse/check are sub-millisecond). Uses the same
OpenAI-compatible streaming call the deployed assistant uses, so the wall-clock numbers are the real ones.

Metrics per run:
  build_ms   prompt assembly (retrieval + compress the KB/examples into the system prompt) — CPU
  ttft_s     time to FIRST token (prefill: the model reading the ~big all-examples prompt)
  gen_s      first token -> last token (decode)
  out_tok    completion tokens (from the API's usage; else counted from stream chunks)
  tok_s      out_tok / gen_s  — decode throughput
  parse_ms   extract the ✓/✗ [source:] decisions — CPU
  check_ms   deterministic constraint checker (species/conflict/dependency) — CPU
  total_s    end-to-end wall clock
  n_on       options the config ends up enabling

  # deployed model, default prompt set, 1 warmup + 3 timed runs each
  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json VEP_EXAMPLES_FILE=data/simulated_gold_examples.json \
      python evidence/legacy_superseded/use_cases/bench_latency.py --model gemma4:26b --runs 3

  # compare models (the speed/quality trade) on the same prompts
  ... python evidence/legacy_superseded/use_cases/bench_latency.py --models gemma4:e4b,gemma4:12b,gemma4:26b --runs 3

  # compare retrieval modes (prompt size vs speed) and/or your own prompts
  ... python evidence/legacy_superseded/use_cases/bench_latency.py --modes keyword,all --prompts my_prompts.txt --json out.json
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va          # noqa: E402
from openai import OpenAI           # noqa: E402

DEFAULT_PROMPTS = [
    ("quick-lookup",   "what does this variant do"),
    ("rare-disease",   "germline exome variants from a rare-disease trio, human GRCh38, coding"),
    ("somatic-cancer", "somatic point mutations from a tumour-normal pair, want driver assessment"),
    ("structural",     "human germline structural variants and CNVs from whole-genome sequencing"),
    ("regulatory",     "non-coding variants in regulatory regions, human, assessing gene-expression impact"),
    ("non-human",      "mouse knockout study, small coding variants, just need the consequence type"),
    ("long-clinical",  "I have human germline whole-exome data from a paediatric cohort with suspected "
                       "Mendelian disease; I need pathogenicity assessment across coding variants, "
                       "cross-referenced with clinical databases and population allele frequencies, "
                       "reported on the community-standard transcripts for diagnostic interpretation"),
]


def timed_stream(client, model, system_prompt, user_msg, max_tokens):
    """Stream the completion, timing TTFT and decode; return (text, ttft, gen, out_tok)."""
    t0 = time.perf_counter()
    ttft = None
    text, n_chunks = "", 0
    usage_tok = None
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_msg}],
        max_tokens=max_tokens, stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                text += delta
                n_chunks += 1
        if getattr(chunk, "usage", None):
            usage_tok = chunk.usage.completion_tokens
    end = time.perf_counter()
    if ttft is None:                       # empty generation
        ttft = end - t0
    gen = max(end - t0 - ttft, 1e-6)
    return text, ttft, gen, (usage_tok if usage_tok else n_chunks)


def run_one(client, model, prompt, catalogue, corpus, aliases, mode, max_tokens):
    t = time.perf_counter()
    system_prompt = va.build_system_prompt(catalogue, corpus, prompt, retrieval_mode=mode)
    build_ms = (time.perf_counter() - t) * 1000
    prompt_chars = len(system_prompt)

    text, ttft, gen, out_tok = timed_stream(client, model, system_prompt, prompt, max_tokens)

    t = time.perf_counter()
    enabled, disabled = va.extract_recommendations(text, aliases)
    parse_ms = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    va.check_and_fix_violations(set(enabled), set(disabled), catalogue, prompt)
    check_ms = (time.perf_counter() - t) * 1000

    return {
        "build_ms": build_ms, "prompt_chars": prompt_chars, "ttft_s": ttft, "gen_s": gen,
        "out_tok": out_tok, "tok_s": out_tok / gen, "parse_ms": parse_ms, "check_ms": check_ms,
        "total_s": build_ms / 1000 + ttft + gen + (parse_ms + check_ms) / 1000, "n_on": len(enabled),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="single model (shorthand for --models)")
    ap.add_argument("--models", default="gemma4:26b", help="comma-separated models to compare")
    ap.add_argument("--modes", default="all", help="retrieval modes: bare,keyword,all,semantic")
    ap.add_argument("--prompts", help="file of prompts (one per line); default = built-in set")
    ap.add_argument("--runs", type=int, default=3, help="timed runs per cell (median reported)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--json", help="write full results JSON here")
    args = ap.parse_args()

    models = [args.model] if args.model else [m.strip() for m in args.models.split(",") if m.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if args.prompts:
        prompts = [(f"p{i+1}", l.strip()) for i, l in enumerate(Path(args.prompts).read_text().splitlines())
                   if l.strip()]
    else:
        prompts = DEFAULT_PROMPTS

    catalogue, corpus = va.load_knowledge_base()
    aliases = va.build_option_aliases(catalogue)
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")

    print(f"catalogue={len(catalogue)} options, corpus={len(corpus)} examples | "
          f"models={models} modes={modes} | {len(prompts)} prompts x {args.runs} runs "
          f"(+1 warmup/model)\n")

    all_results = []
    for model in models:
        for mode in modes:
            print(f"### {model}  ·  retrieval={mode}")
            print(f"{'prompt':16s} {'in(ch)':>7s} {'TTFT':>7s} {'gen':>7s} {'out':>5s} "
                  f"{'tok/s':>6s} {'cpu(ms)':>8s} {'TOTAL':>7s} {'on':>3s}")
            print("-" * 78)
            warm = False
            model_tok_s, model_total = [], []
            for label, prompt in prompts:
                if not warm:                          # warm up the model (excludes load_duration)
                    try:
                        run_one(client, model, prompt, catalogue, corpus, aliases, mode, 256)
                    except Exception as e:
                        print(f"  (warmup failed: {e}); is '{model}' pulled and Ollama up?"); break
                    warm = True
                runs = []
                for _ in range(args.runs):
                    try:
                        runs.append(run_one(client, model, prompt, catalogue, corpus, aliases,
                                            mode, args.max_tokens))
                    except Exception as e:
                        print(f"  {label:14s} ERROR: {e}"); break
                if not runs:
                    continue
                med = {k: statistics.median(r[k] for r in runs) for k in runs[0]}
                cpu = med["build_ms"] + med["parse_ms"] + med["check_ms"]
                model_tok_s.append(med["tok_s"]); model_total.append(med["total_s"])
                print(f"{label:16s} {med['prompt_chars']:7.0f} {med['ttft_s']:6.2f}s "
                      f"{med['gen_s']:6.2f}s {med['out_tok']:5.0f} {med['tok_s']:6.1f} "
                      f"{cpu:7.1f}  {med['total_s']:6.2f}s {med['n_on']:3.0f}")
                all_results.append({"model": model, "mode": mode, "prompt": label,
                                    "prompt_text": prompt, "runs": runs, "median": med})
            if model_tok_s:
                print("-" * 78)
                print(f"{'MEDIAN':16s} {'':7s} {'':7s} {'':7s} {'':5s} "
                      f"{statistics.median(model_tok_s):6.1f} {'':8s} "
                      f"{statistics.median(model_total):6.2f}s")
                print(f"  decode throughput ~{statistics.median(model_tok_s):.0f} tok/s; "
                      f"end-to-end median {statistics.median(model_total):.1f}s "
                      f"(CPU stages — retrieval+parse+check — are <1% of that)\n")

    if args.json and all_results:
        Path(args.json).write_text(json.dumps(all_results, indent=2))
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
