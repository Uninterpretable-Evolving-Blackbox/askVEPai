#!/usr/bin/env python3
"""Example-ORDER sensitivity experiment for Ask VEPai.

Question (from Agarwal et al. 2024, "Many-Shot In-Context Learning", §4.7):
    does the ORDER of the in-context examples change the score, even when the
    SET of examples is held fixed?  The paper evaluated 10 random orderings of a
    fixed 50-example set on MATH and found large, inconsistent variance.

This script reproduces that protocol for our task. It changes EXACTLY ONE
variable -- the order in which the reference examples are shown -- and holds the
model, KB, example set, prompt template, temperature and LLM sampling seed
fixed. The unit of analysis is one ORDERING (one shuffle seed); we report
mean +- SD of the leave-one-out, priority-weighted Enable F1 ACROSS orderings.

Design (matches CLAUDE.md experiment discipline):
  * Same harness primitives as run_parallel_eval.py: reuses vep_assistant +
    evaluate scoring/report code; only the example order varies.
  * Leave-one-out is preserved: the scored example is never in the prompt.
  * Conditions: `all` (all LOO examples shown) and/or `semantic` (top-k
    semantically-retrieved examples shown). For `all`, a shuffle seed defines ONE
    global permutation of the example set (paper-style). For `semantic`, it
    permutes the order of the top-k retrieved examples per query.
  * GREEDY by default (temperature=0.0), mirroring the paper. With greedy each
    ordering is one deterministic data point, so the N orderings ARE the
    replicates (report mean +- SD over them). If you raise temperature, pass
    --runs >1 to average sampling noise WITHIN each ordering so the across-ordering
    SD still reflects order, not decoding noise.

Honesty: the 20-example gold set is SIMULATED. Any spread reported here is
directional evidence about order-sensitivity of THIS pipeline, not a benchmark.

Env vars (same as the demo eval): VEP_OPTIONS_FILE, VEP_EXAMPLES_FILE,
VEP_TESTSET_FILE, VEP_RESULTS_DIR, OLLAMA_BASE_URL.

Usage:
  # all-examples, 10 orderings, greedy (recommended baseline)
  python work/run_order_sensitivity.py --model gemma4:26b --conditions all --shuffles 10

  # compare all vs semantic; show enough semantic examples for order to matter
  python work/run_order_sensitivity.py --model gemma4:26b \
      --conditions all,semantic --semantic-topk 8 --shuffles 10 --concurrency 4
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va          # noqa: E402
import evaluate as ev               # noqa: E402
from openai import OpenAI           # noqa: E402

# Metrics we summarise per ordering. enable_f1_weighted is the project headline
# (priority-weighted, leave-one-out); the others are reported for context.
SUMMARY_METRICS = ["enable_f1_weighted", "enable_recall_weighted", "enable_f1"]


def _ordering_for_all(training_examples, shuffle_seed):
    """One global permutation of the FULL example set for this shuffle seed.

    Returns a list of example dicts. Per query we later drop the LOO example,
    preserving the induced order of the rest -- i.e. a single coherent ordering
    of the set, exactly as in the paper's fixed-set/varied-order protocol.
    """
    perm = list(training_examples)
    random.Random(shuffle_seed).shuffle(perm)
    return perm


def _build_prompts(vep_options, training_examples, test_queries, conds,
                   shuffle_seeds, semantic_topk, include_baseline):
    """Single-threaded prompt construction (semantic uses the embedding model).

    Returns:
        prompts: {(cond, ordering_label, qid): system_prompt}
        gts:     {qid: (use_case, gt_enabled, gt_disabled)}
        ordering_labels: {cond: [labels...]}  (str labels; "default" + shuffle ids)
    """
    gts = {}
    prompts = {}
    ordering_labels = {c: [] for c in conds}

    for t in test_queries:
        gts[t["id"]] = ev.get_ground_truth(training_examples, t["ground_truth_id"])

    for c in conds:
        labels = []
        if include_baseline:
            labels.append("default")
        labels += [f"s{seed}" for seed in shuffle_seeds]
        ordering_labels[c] = labels

    for c in conds:
        for label in ordering_labels[c]:
            # Resolve the shuffle seed (None => natural/default order).
            seed = None if label == "default" else int(label[1:])

            # For `all`, precompute one global permutation per ordering.
            global_perm = (None if (c != "all" or seed is None)
                           else _ordering_for_all(training_examples, seed))

            for t in test_queries:
                qid, query, gtid = t["id"], t["query"], t["ground_truth_id"]
                loo = [e for e in training_examples if e["id"] != gtid]

                if c == "all":
                    if seed is None:
                        ordered = loo                     # natural file order
                    else:
                        ordered = [e for e in global_perm if e["id"] != gtid]
                    prompt = va.build_system_prompt(
                        vep_options, loo, query, retrieval_mode="all",
                        examples_override=ordered)

                elif c == "semantic":
                    retrieved = [ex for _, ex in va.retrieve_examples_semantic(
                        loo, query, vep_options, top_k=semantic_topk)]
                    if seed is None:
                        ordered = retrieved               # natural similarity order
                    else:
                        ordered = list(retrieved)
                        # per-(seed,query) permutation so different queries get
                        # genuinely different orderings under the same shuffle seed
                        random.Random(f"{seed}:{qid}").shuffle(ordered)
                    prompt = va.build_system_prompt(
                        vep_options, loo, query, retrieval_mode="semantic",
                        examples_override=ordered)
                else:
                    raise ValueError(f"unsupported condition: {c}")

                prompts[(c, label, qid)] = prompt

    return prompts, gts, ordering_labels


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--conditions", default="all",
                    help="comma list from: all,semantic (default: all)")
    ap.add_argument("--shuffles", type=int, default=10,
                    help="number of random orderings to test (default: 10, as in the paper)")
    ap.add_argument("--shuffle-start", type=int, default=0,
                    help="first shuffle seed; seeds = [start, start+shuffles) (default: 0)")
    ap.add_argument("--semantic-topk", type=int, default=8,
                    help="# examples shown in the semantic condition (default: 8). "
                         "NOTE: top-k=2 only has 2 possible orderings, too few to measure "
                         "order sensitivity -- use >=4 for a meaningful test.")
    ap.add_argument("--runs", type=int, default=1,
                    help="LLM sampling repeats WITHIN each ordering (default: 1). "
                         "Keep 1 with greedy; raise only if --temperature > 0 to average decoding noise.")
    ap.add_argument("--seed", type=int, default=42,
                    help="LLM sampling seed, held FIXED across orderings (default: 42)")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="sampling temperature (default: 0.0 greedy -- recommended to isolate order)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--no-baseline", action="store_true",
                    help="skip the natural/default-order run (kept by default for comparison)")
    args = ap.parse_args()

    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    for c in conds:
        if c not in ("all", "semantic"):
            ap.error(f"unsupported condition '{c}' (choose from: all, semantic)")
    include_baseline = not args.no_baseline
    shuffle_seeds = list(range(args.shuffle_start, args.shuffle_start + args.shuffles))

    if "semantic" in conds and args.semantic_topk < 4:
        print(f"WARNING: --semantic-topk={args.semantic_topk}: only {math.factorial(args.semantic_topk)} "
              f"possible orderings -- too few to measure order sensitivity. Use >=4 (8 recommended).")
    if args.temperature > 0 and args.runs == 1:
        print(f"WARNING: temperature={args.temperature} with --runs 1: across-ordering SD will mix "
              f"order effect with decoding noise. Use --temperature 0 (greedy) or --runs >=3.")

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")

    vep_options, training_examples = va.load_knowledge_base()
    option_aliases = va.build_option_aliases(vep_options)
    test_queries = ev.TEST_QUERIES   # honours VEP_TESTSET_FILE

    print(f"Model={args.model}  examples={len(training_examples)}  options={len(vep_options)}  "
          f"queries={len(test_queries)}")
    print(f"Conditions={conds}  shuffles={args.shuffles} (seeds {shuffle_seeds[0]}..{shuffle_seeds[-1]})  "
          f"baseline={'yes' if include_baseline else 'no'}  semantic_topk={args.semantic_topk}")
    print(f"temperature={args.temperature}  runs/ordering={args.runs}  llm_seed={args.seed} (fixed)")

    prompts, gts, ordering_labels = _build_prompts(
        vep_options, training_examples, test_queries, conds,
        shuffle_seeds, args.semantic_topk, include_baseline)
    print(f"Prompts built ({len(prompts)}). Firing LLM calls...")

    # tasks: one per (cond, ordering, query, sampling-run)
    tasks = [(c, label, t, r)
             for c in conds
             for label in ordering_labels[c]
             for t in test_queries
             for r in range(args.runs)]

    results = {}     # (cond, label, qid) -> [score dicts]
    raw_log = []
    t0 = time.time()
    done = [0]

    def work(task):
        c, label, t, r = task
        cat, en, dis = gts[t["id"]]
        score = ev._run_condition(
            client, args.model, prompts[(c, label, t["id"])], t["query"],
            option_aliases, en, dis, cat, vep_options,
            args.temperature, args.seed + r, c)
        raw_log.append({
            "model": args.model, "condition": c, "ordering": label, "run": r,
            "query_id": t["id"], "query": t["query"], "use_case": cat,
            "enabled": sorted(score.get("enabled_found", [])),
            "disabled": sorted(score.get("disabled_found", [])),
            "gt_enabled": sorted(en), "gt_disabled": sorted(dis),
            "response": score.get("_response", ""),
        })
        return (c, label, t["id"]), score

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for fut in as_completed([ex.submit(work, tk) for tk in tasks]):
            key, score = fut.result()
            results.setdefault(key, []).append(score)
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(tasks):
                el = time.time() - t0
                eta = (len(tasks) - done[0]) / max(done[0] / max(el, 1e-9), 1e-9)
                print(f"  {done[0]}/{len(tasks)} calls  {el:.0f}s  "
                      f"({done[0]/max(el,1e-9):.3f} calls/s)  ETA ~{eta/60:.0f}m", flush=True)

    # --- aggregate: per ordering -> dataset-level metric; per cond -> across orderings ---
    # per_ordering[cond][label][metric] = dataset mean over the 20 queries
    per_ordering = {c: {} for c in conds}
    for c in conds:
        for label in ordering_labels[c]:
            agg_q = {}
            for t in test_queries:
                agg_q[t["id"]] = ev.aggregate_scores(results[(c, label, t["id"])])
            per_ordering[c][label] = {
                m: ev._safe_mean([agg_q[t["id"]].get(m) for t in test_queries])
                for m in SUMMARY_METRICS
            }

    report = _make_report(args, conds, ordering_labels, per_ordering, shuffle_seeds,
                          len(test_queries), len(training_examples), len(vep_options))

    rdir = Path(os.environ.get("VEP_RESULTS_DIR", DEMO / "results"))
    rdir.mkdir(parents=True, exist_ok=True)
    safe = args.model.replace("/", "_").replace(":", "_")
    out_md = rdir / f"order_sensitivity_{safe}.md"
    out_md.write_text(report)

    rawdir = rdir / "raw"
    rawdir.mkdir(parents=True, exist_ok=True)
    with open(rawdir / f"order_sensitivity_{safe}.jsonl", "w") as rf:
        for rec in raw_log:
            rf.write(json.dumps(rec) + "\n")

    print("\n" + report)
    print(f"Report -> {out_md}")
    print(f"Raw     -> {rawdir}/order_sensitivity_{safe}.jsonl ({len(raw_log)} calls)")


def _fmt_pct(x):
    return "n/a" if x is None else f"{x*100:.1f}%"


def _across(per_ordering_cond, shuffle_seeds, metric):
    """mean, SD, min, max of `metric` ACROSS shuffle orderings (excludes 'default')."""
    vals = [per_ordering_cond[f"s{s}"][metric] for s in shuffle_seeds
            if per_ordering_cond[f"s{s}"][metric] is not None]
    if not vals:
        return None, None, None, None
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return mean, sd, min(vals), max(vals)


def _make_report(args, conds, ordering_labels, per_ordering, shuffle_seeds,
                 n_queries, n_examples, n_options):
    L = []
    L.append("# Example-Order Sensitivity Experiment")
    L.append("")
    L.append(f"- **Model:** `{args.model}`")
    L.append(f"- **KB:** {n_examples} examples / {n_options} options "
             f"(leave-one-out; scored example never in prompt)")
    L.append(f"- **Test queries:** {n_queries}")
    L.append(f"- **Orderings:** {args.shuffles} random shuffles "
             f"(seeds {shuffle_seeds[0]}..{shuffle_seeds[-1]})"
             + (" + 1 natural/default order" if not args.no_baseline else ""))
    L.append(f"- **Conditions:** {', '.join(conds)}"
             + (f" (semantic top-k={args.semantic_topk})" if "semantic" in conds else ""))
    L.append(f"- **Decoding:** temperature={args.temperature}, "
             f"runs/ordering={args.runs}, LLM seed={args.seed} (held FIXED across orderings)")
    L.append(f"- **Headline metric:** priority-weighted Enable F1 (`enable_f1_weighted`), "
             f"leave-one-out, averaged over the {n_queries} queries.")
    L.append("")
    L.append("> One ordering = one data point. The spread (SD / min-max) ACROSS orderings is the "
             "order-sensitivity result. The set of examples is held fixed; only their order varies. "
             "The 20-example gold set is SIMULATED -> directional, not a benchmark.")
    L.append("")

    # Summary table: across-ordering mean +- SD per condition.
    L.append("## Summary: variability across orderings")
    L.append("")
    L.append("| Condition | Metric | mean | SD | min | max | range | default |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in conds:
        for m in SUMMARY_METRICS:
            mean, sd, lo, hi = _across(per_ordering[c], shuffle_seeds, m)
            rng = None if (lo is None or hi is None) else hi - lo
            default = per_ordering[c].get("default", {}).get(m) if not args.no_baseline else None
            L.append(f"| {c} | {m} | {_fmt_pct(mean)} | {_fmt_pct(sd)} | {_fmt_pct(lo)} | "
                     f"{_fmt_pct(hi)} | {_fmt_pct(rng)} | {_fmt_pct(default)} |")
    L.append("")

    # Per-ordering detail.
    for c in conds:
        L.append(f"## Per-ordering detail: `{c}`")
        L.append("")
        header = "| ordering | " + " | ".join(SUMMARY_METRICS) + " |"
        L.append(header)
        L.append("|" + "---|" * (len(SUMMARY_METRICS) + 1))
        for label in ordering_labels[c]:
            row = per_ordering[c][label]
            L.append(f"| {label} | " + " | ".join(_fmt_pct(row[m]) for m in SUMMARY_METRICS) + " |")
        L.append("")

    L.append("## How to read this")
    L.append("")
    L.append("- **Small SD / range (e.g. within +-1-2% Enable F1):** order is not a major lever for "
             "this pipeline; the fixed file order is fine and the standard `--runs` decoding-noise SD "
             "already bounds it.")
    L.append("- **Large SD / range:** order matters (the paper's §4.7 finding reproduces here). Pin a "
             "canonical order in the protocol and treat order as a logged variable; consider reporting "
             "results as mean +- SD over orderings, not a single run.")
    L.append("- **Comparing `all` vs `semantic`:** they show different NUMBERS of examples "
             f"({n_examples-1} LOO vs top-{args.semantic_topk}), so a difference in SD reflects BOTH "
             "count and retrieval, not order alone -- interpret as 'order sensitivity of each condition "
             "as configured', not a controlled count comparison.")
    return "\n".join(L)


if __name__ == "__main__":
    main()
