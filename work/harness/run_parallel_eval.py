#!/usr/bin/env python3
"""Parallel leave-one-out evaluation driver for the real-project system.

Saturates the GPU by firing many LLM requests concurrently (Ollama serves up to
OLLAMA_NUM_PARALLEL at once). Reuses vep_assistant + evaluate scoring/report code;
only the eval loop is parallelised.

Reads the same env vars as the demo eval:
  VEP_OPTIONS_FILE, VEP_EXAMPLES_FILE, VEP_TESTSET_FILE, VEP_RESULTS_DIR, OLLAMA_BASE_URL

Usage:
  python run_parallel_eval.py --model gemma4:12b --runs 3 --concurrency 4
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# import the demo modules (vep_assistant imports by name, so add its dir to path)
DEMO = Path(__file__).resolve().parents[2] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va          # noqa: E402
import evaluate as ev               # noqa: E402
from openai import OpenAI           # noqa: E402

COND_KEY = {"bare": "without_kb", "keyword": "with_kb",
            "all": "with_kb_all", "semantic": "with_kb_semantic",
            "noex": "with_kb_noex"}
COND_MODE = {"keyword": "keyword", "all": "all", "semantic": "semantic"}


def main():
    # Pipeline: build LOO prompts per (query, condition) -> fan LLM calls out across
    # a thread pool -> aggregate with evaluate.generate_report -> write md + raw jsonl.
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--conditions", default="bare,keyword,all,semantic",
                    help="comma list from: bare,keyword,all,semantic")
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    for must in ("bare", "keyword"):           # generate_report needs these baselines
        if must not in conds:
            conds.insert(0, must)

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")

    vep_options, training_examples = va.load_knowledge_base()
    option_aliases = va.build_option_aliases(vep_options)
    test_queries = ev.TEST_QUERIES   # honours VEP_TESTSET_FILE

    print(f"Model={args.model}  examples={len(training_examples)}  options={len(vep_options)}  "
          f"queries={len(test_queries)}  conditions={conds}  runs={args.runs}  concurrency={args.concurrency}")

    # --- pre-build prompts (single-threaded; semantic uses the embedding model) ---
    gts, prompts = {}, {}
    for t in test_queries:
        qid, query, gtid = t["id"], t["query"], t["ground_truth_id"]
        gts[qid] = ev.get_ground_truth(training_examples, gtid)
        loo = [e for e in training_examples if e["id"] != gtid]
        for c in conds:
            if c == "bare":
                prompts[(qid, c)] = ev.BARE_SYSTEM_PROMPT
            elif c == "noex":
                # docs-only ablation: full 58-option catalogue + output contract + rules but ZERO
                # in-context examples. Isolates the golden-examples contribution as the single changed
                # variable vs the `all` condition (same options/format/checker; examples 19 -> 0).
                prompts[(qid, c)] = va.build_system_prompt(vep_options, [], query, retrieval_mode="all")
            else:
                prompts[(qid, c)] = va.build_system_prompt(vep_options, loo, query,
                                                           retrieval_mode=COND_MODE[c])
    print("Prompts built. Firing LLM calls...")

    # --- parallel LLM calls ---
    tasks = [(t, c, r) for t in test_queries for c in conds for r in range(args.runs)]
    results = {}                      # (qid, cond) -> [score dicts]
    t0 = time.time()
    done = [0]

    raw_log = []   # per-call raw outputs, so new metrics can be back-applied without re-running

    def work(task):
        t, c, r = task
        cat, en, dis = gts[t["id"]]
        score = ev._run_condition(client, args.model, prompts[(t["id"], c)], t["query"],
                                  option_aliases, en, dis, cat, vep_options,
                                  args.temperature, args.seed + r, c)
        raw_log.append({                       # list.append is atomic under the GIL
            "model": args.model, "query_id": t["id"], "query": t["query"],
            "condition": c, "run": r, "seed": args.seed + r, "use_case": cat,
            "enabled": sorted(score.get("enabled_found", [])),
            "disabled": sorted(score.get("disabled_found", [])),
            "gt_enabled": sorted(en), "gt_disabled": sorted(dis),
            "response": score.get("_response", ""),
        })
        return (t["id"], c), score

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for fut in as_completed([ex.submit(work, tk) for tk in tasks]):
            # collected in the main thread as futures complete -> no lock needed
            key, score = fut.result()
            results.setdefault(key, []).append(score)
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(tasks):
                el = time.time() - t0
                print(f"  {done[0]}/{len(tasks)} calls  {el:.0f}s  ({done[0]/el:.2f} calls/s)")

    # --- aggregate + report (reuse evaluate.generate_report) ---
    all_results = {"model": args.model, "num_runs": args.runs, "base_seed": args.seed,
                   "temperature": args.temperature, "queries": []}
    for t in test_queries:
        cat, en, dis = gts[t["id"]]
        entry = {"id": t["id"], "query": t["query"], "source": t.get("source", "simulated"),
                 "gt_category": cat}
        for c in conds:
            entry[COND_KEY[c]] = ev.aggregate_scores(results[(t["id"], c)])
        all_results["queries"].append(entry)

    report = ev.generate_report(all_results)
    rdir = Path(os.environ.get("VEP_RESULTS_DIR", DEMO / "results"))
    rdir.mkdir(parents=True, exist_ok=True)
    safe = args.model.replace("/", "_").replace(":", "_")
    (rdir / f"evaluation_results_{safe}.md").write_text(report)

    # raw per-call outputs -> enables back-applying new metrics with no re-run
    rawdir = rdir / "raw"
    rawdir.mkdir(parents=True, exist_ok=True)
    with open(rawdir / f"{safe}.jsonl", "w") as rf:
        for rec in raw_log:
            rf.write(json.dumps(rec) + "\n")
    print(f"Raw outputs -> {rawdir}/{safe}.jsonl ({len(raw_log)} calls)")

    # compact summary to stdout
    n = len(all_results["queries"])
    def avg(key, metric):
        # None-safe (evaluate now returns None for undefined metrics): skip them, don't sum None.
        return ev._safe_mean([q.get(key, q["without_kb"])[metric] for q in all_results["queries"]]) or 0
    print(f"\n=== {args.model} ({time.time()-t0:.0f}s) ===")
    for c in conds:
        k = COND_KEY[c]
        print(f"  {c:9s} Enable F1={avg(k,'enable_f1'):.0%}  "
              f"prio-wtd F1={avg(k,'enable_f1_weighted'):.0%}  cite={avg(k,'citation_rate'):.0%}")
    print(f"Report -> {rdir}/evaluation_results_{safe}.md")


if __name__ == "__main__":
    main()
