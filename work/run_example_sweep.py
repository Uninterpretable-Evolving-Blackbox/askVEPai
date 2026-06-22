#!/usr/bin/env python3
"""Example-count sweep: isolate the CORPUS-SIZE effect on all-examples vs selective retrieval.

Test set = all 20 queries (leave-one-out). For each query we subsample the corpus
(the other 19 examples) to size N, STRATIFIED across use cases, then compare:
  keyword (top-2 of N)  vs  all-examples (all N)  vs  semantic (top-2 of N + top-10 options)
across N. bare (no corpus) is computed once (N-independent).

If all-examples' lead over keyword shrinks / goes negative as N grows -> corpus-size
crossover (all-examples wins only because the corpus is small). If it holds -> it doesn't.

Usage:
  python run_example_sweep.py --models qwen2.5:3b,gemma4:e4b --ns 2,5,10,15,19 --runs 2
"""
import argparse
import os
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va           # noqa: E402
import evaluate as ev                # noqa: E402
from openai import OpenAI            # noqa: E402

COND_MODE = {"keyword": "keyword", "all": "all", "semantic": "semantic"}


def stratified_subsample(pool, n, seed):
    """Pick n examples from pool, spread across use_case_category, deterministically."""
    if n >= len(pool):
        return list(pool)
    by_uc = defaultdict(list)
    for e in pool:
        by_uc[e["use_case_category"]].append(e)
    rng = random.Random(seed)
    for uc in by_uc:
        rng.shuffle(by_uc[uc])
    ucs = sorted(by_uc)
    rng.shuffle(ucs)
    picked, i = [], 0
    while len(picked) < n and any(by_uc[u] for u in ucs):
        uc = ucs[i % len(ucs)]
        if by_uc[uc]:
            picked.append(by_uc[uc].pop())
        i += 1
    return picked


def main():
    # Sweep driver: build every (query, N, condition) prompt once, then fan the
    # LLM calls out across a thread pool and tabulate Enable F1 per corpus size N.
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen2.5:3b,gemma4:e4b")
    ap.add_argument("--ns", default="2,5,10,15,19")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",")]
    Ns = [int(x) for x in args.ns.split(",")]
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    vep_options, examples = va.load_knowledge_base()
    option_aliases = va.build_option_aliases(vep_options)
    test_queries = ev.TEST_QUERIES
    qtext = {t["id"]: t["query"] for t in test_queries}
    gts = {t["id"]: ev.get_ground_truth(examples, t["ground_truth_id"]) for t in test_queries}
    print(f"examples={len(examples)} options={len(vep_options)} queries={len(test_queries)} "
          f"models={models} Ns={Ns} runs={args.runs} concurrency={args.concurrency}")

    # Pre-build prompts (single-threaded; semantic uses the embedding model)
    bare_prompts = {t["id"]: ev.BARE_SYSTEM_PROMPT for t in test_queries}
    np_prompts = {}
    for t in test_queries:
        pool = [e for e in examples if e["id"] != t["ground_truth_id"]]   # leave-one-out
        for N in Ns:
            # seed offset by N so each corpus size gets a distinct-but-deterministic draw
            corpus = stratified_subsample(pool, N, seed=args.seed + N)
            for cond in ("keyword", "all", "semantic"):
                np_prompts[(t["id"], N, cond)] = va.build_system_prompt(
                    vep_options, corpus, t["query"], retrieval_mode=COND_MODE[cond])
    print("Prompts built. Firing...")

    rdir = Path(os.environ.get("VEP_RESULTS_DIR", DEMO / "results"))
    rdir.mkdir(parents=True, exist_ok=True)
    combined = ["# Example-count sweep — all-examples vs selective retrieval, by corpus size N\n",
                "Real system: 58 options, 20 LOO test queries. Enable F1 (mean over queries x runs).\n"]

    for model in models:
        tasks = []   # (key, prompt, qid, run);  key=("bare",0) or (cond,N)
        for t in test_queries:
            qid = t["id"]
            for r in range(args.runs):
                # bare is N-independent: scored once per (query, run), keyed ("bare", 0)
                tasks.append((("bare", 0), bare_prompts[qid], qid, r))
                for N in Ns:
                    for cond in ("keyword", "all", "semantic"):
                        tasks.append(((cond, N), np_prompts[(qid, N, cond)], qid, r))

        results = defaultdict(list)
        t0, done = time.time(), [0]

        def work(task):
            key, prompt, qid, r = task
            cat, en, dis = gts[qid]
            score = ev._run_condition(client, model, prompt, qtext[qid], option_aliases,
                                      en, dis, cat, vep_options, args.temperature, args.seed + r, str(key))
            return key, score

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            for fut in as_completed([ex.submit(work, tk) for tk in tasks]):
                key, score = fut.result()
                results[key].append(score)
                done[0] += 1
                if done[0] % 20 == 0 or done[0] == len(tasks):
                    print(f"  [{model}] {done[0]}/{len(tasks)}  {time.time()-t0:.0f}s")

        def f1(key):
            # mean Enable F1 over all (query x run) scores collected under this key.
            # None-safe: enable_f1 is None when undefined (no model output) — skip, don't sum None.
            vals = [x["enable_f1"] for x in results.get(key, []) if x["enable_f1"] is not None]
            return sum(vals) / len(vals) if vals else 0.0
        bare = f1(("bare", 0))

        lines = [f"\n## {model}\n", "| N (corpus) | bare | keyword | all-ex | semantic | all−kw |",
                 "|---|---|---|---|---|---|"]
        print(f"\n=== {model} (Enable F1 by corpus size N) ===")
        print(f"{'N':>3} {'bare':>5} {'keyword':>8} {'all-ex':>7} {'semantic':>9} {'all−kw':>7}")
        for N in Ns:
            kw, al, se = f1(("keyword", N)), f1(("all", N)), f1(("semantic", N))
            lines.append(f"| {N} | {bare:.0%} | {kw:.0%} | {al:.0%} | {se:.0%} | {al-kw:+.0%} |")
            print(f"{N:>3} {bare:>4.0%} {kw:>7.0%} {al:>6.0%} {se:>8.0%} {al-kw:>+6.0%}")
        combined += lines
        (rdir / f"example_sweep_{model.replace('/', '_').replace(':', '_')}.md").write_text("\n".join(lines))

    (rdir / "example_sweep_combined.md").write_text("\n".join(combined))
    print(f"\nWrote {rdir}/example_sweep_combined.md")


if __name__ == "__main__":
    main()
