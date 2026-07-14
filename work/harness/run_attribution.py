#!/usr/bin/env python3
"""Attribution testing — per-recommendation KB-faithfulness (EXPERIMENTS.md Exp 5 & 6).

WHAT THIS MEASURES
  For each recommendation the system makes, is it *grounded in the knowledge base* (KB) or produced
  from the model's *parametric* (pre-trained) memory? We answer it causally, by occlusion/ablation:
    1. Baseline: run the full pipeline on a query  ->  the set of options the model recommends.
    2. For each recommended option r, ABLATE r's KB signal (see modes) and re-run the pipeline.
    3. attribution(r) = 1 if r is NO LONGER recommended  -> KB-FAITHFUL   (the KB caused the rec)
                      = 0 if r is STILL recommended       -> PARAMETRIC   (model knew it anyway)
  faithfulness_rate = mean attribution over every recommendation across the test set.

ABLATION MODES (which slice of r's KB signal we remove -> isolates *where* the grounding lives)
  --mode combined     blank r's option-guidance fields AND drop r from the worked examples (both)
  --mode description  blank only r's guidance fields (description / when_to_use / when_not_to_use and
                      neutralise priority_by_use_case)         -> isolates the option-catalogue text
  --mode examples     drop r only from the few-shot demonstrations -> isolates in-context imitation
  Contrasting the three decomposes the KB's influence into its catalogue-text vs worked-example
  channels (Exp 6 6a: examples-only 56% vs description-only 26% vs combined 79%).

DETERMINISM (critical — see EXPERIMENTS.md Exp 6)
  temp=0 is NOT deterministic on this Apple Metal / MoE stack: under concurrency, batched float
  reductions make the SAME prompt drift by several options. The appear/disappear signal would then
  be sampling noise rather than the ablation effect. So reproducible runs require **--concurrency 1
  and a fixed --seed**; the baselines saved with each result let you audit cross-run / cross-mode
  identity. A mean +/- SD over the metric is obtained by varying --seed across runs (the metric is
  deterministic per seed), not by repeated sampling.

LEAVE-ONE-OUT
  For a scored *synthetic* query, its own gold example is removed from the retrieval corpus (no
  answer leakage). *Real* forum queries carry no gold example (ground_truth_id absent) -> the full
  corpus is used and there is nothing to leave out.

Usage (env vars select the KB / example set / test set / results dir; see CLAUDE.md):
  VEP_OPTIONS_FILE=… VEP_EXAMPLES_FILE=… VEP_TESTSET_FILE=… VEP_RESULTS_DIR=… \
    python run_attribution.py --model gemma4:26b --queries 0 --mode combined --concurrency 1 --seed 42
"""
import argparse
import copy
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Reuse the real pipeline: prompt assembly + parsing + checker live in the demo's vep_assistant,
# and the LLM call + ground-truth helpers live in evaluate. We import them so attribution scores
# the EXACT code path the product uses (no re-implementation that could drift from it).
DEMO = Path(__file__).resolve().parents[2] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va           # noqa: E402
import evaluate as ev                # noqa: E402
from openai import OpenAI            # noqa: E402

# The 7 project use cases — used only to neutralise an option's per-use-case priority map on ablation.
USE_CASES = ["rare_disease_germline", "somatic_cancer", "regulatory_noncoding",
             "population_genetics", "structural_variants", "non_human", "quick_lookup"]


def ablate_options(catalogue, r, do_guidance):
    """Remove the *reasons to pick* option r from the option catalogue (the 'description' channel).

    We blank r's free-text guidance and flatten its priorities to 'optional', but DELIBERATELY keep
    r's id / cli_flag / species_restriction intact so the option is still listable in the prompt.
    Rationale: if we dropped r entirely, its 'disappearance' from the output could just mean "no
    longer offered" rather than "no longer justified by the KB" — we want to measure the latter.
    Returns the catalogue unchanged when do_guidance is False (so 'examples' mode is a no-op here).
    """
    if not do_guidance:
        return catalogue
    cat = copy.deepcopy(catalogue)           # deepcopy: never mutate the shared KB across tasks
    for o in cat:
        if o["id"] == r:
            o["description"] = ""
            o["when_to_use"] = ""
            o["when_not_to_use"] = ""
            o["priority_by_use_case"] = {uc: "optional" for uc in USE_CASES}
    return cat


def ablate_examples(corpus, r, do_examples):
    """Drop option r from every worked example's recommended_options (the 'examples' channel).

    This deletes the few-shot demonstration that "queries like this enable r" — i.e. the in-context
    imitation signal — while leaving the option's catalogue entry untouched. No-op when do_examples
    is False (so 'description' mode does not touch the demonstrations).
    """
    if not do_examples:
        return corpus
    exs = copy.deepcopy(corpus)              # deepcopy: isolate this task's ablation from others
    for e in exs:
        e["recommended_options"].pop(r, None)
    return exs


def run_one(client, model, opts, corpus, query, aliases, seed=42):
    """One greedy pass of the real pipeline -> the set of option ids the model enables.

    prompt assembly (all-examples condition) -> LLM (temp=0, fixed seed) -> parse. We discard the
    'disabled' set; attribution is defined on what the model ENABLES. retrieval_mode='all' is held
    fixed across the whole experiment (no retrieval filtering is the studied condition).
    """
    sp = va.build_system_prompt(opts, corpus, query, retrieval_mode="all")
    resp = ev.call_llm(client, model, sp, query, temperature=0.0, seed=seed)
    enabled, _ = va.extract_recommendations(resp, aliases)
    return enabled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--queries", type=int, default=0, help="0=all; else a stratified subset of this size")
    ap.add_argument("--mode", default="combined", choices=["combined", "description", "examples"])
    ap.add_argument("--concurrency", type=int, default=4, help="USE 1 for deterministic/reproducible runs")
    ap.add_argument("--seed", type=int, default=42, help="fixed seed; determinism requires --concurrency 1")
    ap.add_argument("--tag", default="", help="optional suffix for output filenames (e.g. 'real', 's123')")
    args = ap.parse_args()
    # Which channel(s) each mode ablates (see module docstring).
    do_guidance = args.mode in ("combined", "description")
    do_examples = args.mode in ("combined", "examples")

    # Ollama's OpenAI-compatible endpoint. load_knowledge_base()/TEST_QUERIES honour the VEP_* env vars,
    # so the same code scores either the demo KB or the expanded 58-option catalogue (see CLAUDE.md).
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    catalogue, examples = va.load_knowledge_base()
    aliases = va.build_option_aliases(catalogue)      # free-text -> canonical option id mapping (for the parser)
    tqs = ev.TEST_QUERIES
    # Ground-truth lookup per query — only used below for stratified subsetting. Guarded with .get so
    # real queries (no ground_truth_id) yield None instead of raising.
    gts = {t["id"]: (ev.get_ground_truth(examples, t.get("ground_truth_id")) if t.get("ground_truth_id") else None) for t in tqs}

    if args.queries and args.queries < len(tqs):          # stratified subset: one query per use case first,
        by_uc = defaultdict(list)                         # then top up in order until we hit the requested size
        for t in tqs:
            by_uc[gts[t["id"]][0]].append(t)
        sel = [by_uc[uc][0] for uc in sorted(by_uc)]
        for t in tqs:
            if len(sel) >= args.queries:
                break
            if t not in sel:
                sel.append(t)
        tqs = sel[:args.queries]

    def loo(t):
        # Leave-one-out: drop this query's own gold example from the corpus (no answer leakage).
        # For real queries ground_truth_id is absent -> nothing matches -> full corpus is used.
        return [e for e in examples if e["id"] != t.get("ground_truth_id")]

    print(f"model={args.model} queries={len(tqs)} mode={args.mode} seed={args.seed} concurrency={args.concurrency} (greedy temp=0)")
    t0 = time.time()

    # Phase 1 — BASELINES on the full (un-ablated) KB: what does the model recommend per query?
    # These define R_full, the recommendation set we then probe. Saved to the result JSON so cross-mode
    # / cross-seed baseline identity can be audited (the determinism check).
    baselines = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(run_one, client, args.model, catalogue, loo(t), t["query"], aliases, args.seed): t for t in tqs}
        for f in as_completed(futs):
            t = futs[f]
            baselines[t["id"]] = f.result()
    print(f"baselines done ({time.time()-t0:.0f}s); recs/query="
          f"{[len(baselines[t['id']]) for t in tqs]}")

    # Phase 2 — one ABLATION run per (query, recommended option r): re-run with r's KB signal removed.
    tasks = [(t["id"], t["query"], t.get("ground_truth_id"), r)
             for t in tqs for r in sorted(baselines[t["id"]])]
    print(f"ablation runs: {len(tasks)}")
    results, raw, done = defaultdict(dict), [], [0]       # results[qid][r] = attribution (0/1); raw = full log

    def work(task):
        qid, query, gtid, r = task
        corpus = [e for e in examples if e["id"] != gtid]     # same LOO corpus as the baseline
        en = run_one(client, args.model,
                     ablate_options(catalogue, r, do_guidance),    # ablate r in the catalogue (if mode says so)
                     ablate_examples(corpus, r, do_examples), query, aliases, args.seed)  # ...and/or in examples
        # attribution = 1 if r vanished after ablation (KB-faithful), 0 if it survived (parametric).
        return qid, r, (0 if r in en else 1), sorted(en)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for f in as_completed([ex.submit(work, tk) for tk in tasks]):
            qid, r, attr, en = f.result()
            results[qid][r] = attr
            raw.append({"query_id": qid, "option": r, "attribution": attr, "ablated_enabled": en})
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(tasks):
                print(f"  {done[0]}/{len(tasks)} ({time.time()-t0:.0f}s)")

    # Aggregate: overall faithfulness, and per-option means (which options are KB-driven vs parametric).
    all_attr = [a for d in results.values() for a in d.values()]
    faith = sum(all_attr) / len(all_attr) if all_attr else 0.0
    by_opt = defaultdict(list)
    for d in results.values():
        for r, a in d.items():
            by_opt[r].append(a)

    # Persist: a summary JSON (+ baselines for the determinism audit) and a per-recommendation raw log
    # (used downstream to slice real-query results by provenance/use-case). --tag keeps modes/seeds/real
    # runs in separate files so nothing is overwritten.
    rdir = Path(os.environ.get("VEP_RESULTS_DIR", DEMO / "results")) / "attribution"
    rdir.mkdir(parents=True, exist_ok=True)
    safe = args.model.replace("/", "_").replace(":", "_")
    suffix = f"_{args.tag}" if args.tag else ""
    json.dump({"faithfulness_rate": faith, "mode": args.mode, "seed": args.seed,
               "concurrency": args.concurrency, "n_recs": len(all_attr),
               "per_option": {r: sum(v) / len(v) for r, v in by_opt.items()},
               "per_query": {q: sum(d.values()) / len(d) for q, d in results.items()},
               "baselines": {t["id"]: sorted(baselines[t["id"]]) for t in tqs}},
              open(rdir / f"{safe}_{args.mode}{suffix}.json", "w"), indent=2)
    with open(rdir / f"{safe}_{args.mode}{suffix}_raw.jsonl", "w") as fr:
        for x in raw:
            fr.write(json.dumps(x) + "\n")

    print(f"\n=== Attribution ({args.mode}): faithfulness_rate = {faith:.0%} over {len(all_attr)} recs ===")
    print("most PARAMETRIC (recommended regardless of KB — low faithful):")
    for r, v in sorted(by_opt.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[:10]:
        print(f"  {r:18s} faithful={sum(v)/len(v):.0%} (n={len(v)})")
    print(f"saved -> {rdir}/{safe}_{args.mode}{suffix}.json")


if __name__ == "__main__":
    main()
