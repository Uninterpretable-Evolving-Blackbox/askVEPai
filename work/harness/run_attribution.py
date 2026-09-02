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
  --mode combined     blank r's description AND its priority label AND drop it from the examples
  --mode text         blank only r's description        -> isolates the option-catalogue text
  --mode priority     drop only r's priority label for this scenario -> isolates the table's push
  --mode examples     drop r only from the few-shot demonstrations -> isolates in-context imitation
  --full-desc         send the WHOLE description instead of the first 120 characters

  REBUILT 2026-08-19. `--mode description` is gone. It blanked `when_to_use` and `when_not_to_use`
  as well, which `compress_options` never puts in the prompt — so two of its four ablations removed
  nothing the model could read. It also folded in the priority label, a genuinely separate channel,
  which now has its own mode. The runs it produced (examples 56 / description 26 / combined 79) are
  SUPERSEDED; see the correction at the head of EXPERIMENTS.md Exp 6.

  Current, seed 42, concurrency 1, ONE seed: combined 90 / examples 71 / full description 8 /
  compressed description 2 / priority label 0.

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

Usage (env vars select the KB / example set / test set / results dir):
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


def ablate_text(catalogue, r, do_text):
    """Blank option r's DESCRIPTION — the only free text about it that reaches the model.

    r's id / cli_flag / species_restriction / conflicts / depends stay intact, so the option is still
    listable. If we dropped r entirely, its disappearance from the output could mean "no longer
    offered" rather than "no longer justified", and we want the latter.

    REWRITTEN 2026-08-19. This used to also blank `when_to_use` and `when_not_to_use` and flatten
    `priority_by_use_case`. The first two never reach the prompt at all — `compress_options` excludes
    them, and they feed only the semantic-retrieval embeddings, which this experiment does not use
    (retrieval_mode="all"). So two of the four ablations were no-ops. The third, the priority label,
    is a genuinely separate channel and now has its own mode instead of being folded in here.
    """
    if not do_text:
        return catalogue
    cat = copy.deepcopy(catalogue)           # deepcopy: never mutate the shared KB across tasks
    for o in cat:
        if o["id"] == r:
            o["description"] = ""
    return cat


def ablate_priority(resolved, r, do_priority):
    """Remove option r's PRIORITY LABEL for this scenario — the table's push toward it.

    The prompt reads "Priorities: <label> for this scenario". Setting the label to None makes it read
    "no priority for this scenario", which is ABSENCE rather than a different instruction. Demoting to
    `optional` was the obvious alternative and is wrong: it actively tells the model to leave the
    option off, so a drop would measure obedience to a push-away rather than the loss of a push-toward.
    The absent state is also in-distribution — 27 of 65 options genuinely read that way in a real run.
    """
    if not do_priority or resolved is None:
        return resolved
    out = dict(resolved)
    if r in out:
        enabled, _label, gated = out[r]
        out[r] = (enabled, None, gated)
    return out


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


def run_one(client, model, opts, corpus, query, aliases, seed=42,
            resolved=None, desc_chars=va._SENTINEL, think=None):
    """One greedy pass of the real pipeline -> the set of option ids the model enables.

    prompt assembly (all-examples condition) -> LLM (temp=0, fixed seed) -> parse. We discard the
    'disabled' set; attribution is defined on what the model ENABLES. retrieval_mode='all' is held
    fixed across the whole experiment (no retrieval filtering is the studied condition).

    `resolved` is this query's factor priorities. Passing it is what puts the run on the SHIPPED
    prompt: without it `compress_options` falls back to dumping all seven legacy use-case labels,
    which is the pre-migration shape and the same path that produced the withdrawn 77/91 figure.

    `desc_chars=None` sends the WHOLE description instead of the first 120 characters. Every one of
    the 65 descriptions exceeds that cut — median 295 characters, 11,834 discarded in total — so the
    truncated arm cannot tell you whether description text helps; it can only tell you whether the
    first sentence does.
    """
    sp = va.build_system_prompt(opts, corpus, query, retrieval_mode="all",
                                desc_chars=desc_chars, resolved_override=resolved)
    resp = ev.call_llm(client, model, sp, query, temperature=0.0, seed=seed, think=think)
    enabled, _ = va.extract_recommendations(resp, aliases)
    return enabled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--queries", type=int, default=0, help="0=all; else a stratified subset of this size")
    ap.add_argument("--mode", default="combined",
                    choices=["combined", "text", "priority", "examples"],
                    help="which channel to ablate. `description` was split into `text` (the option's\n                          description, the only free text the model reads) and `priority` (the\n                          table's label for this scenario) on 2026-08-19 — the old mode conflated\n                          them and also blanked two fields the prompt never contains.")
    ap.add_argument("--concurrency", type=int, default=4, help="USE 1 for deterministic/reproducible runs")
    ap.add_argument("--seed", type=int, default=42, help="fixed seed; determinism requires --concurrency 1")
    ap.add_argument("--tag", default="", help="optional suffix for output filenames (e.g. 'real', 's123')")
    ap.add_argument("--full-desc", action="store_true",
                    help="send the WHOLE description instead of the first 120 characters. All 65 "
                         "exceed the cut (median 295 chars), so the truncated arm can only tell you "
                         "whether the first sentence carries the signal.")
    ap.add_argument("--think", choices=["off", "low", "default"], default="off",
                    help="reasoning on the recommender. Exp 14 found it costs ~2x wall clock for no "
                         "accuracy gain, but that measured ACCURACY; whether reasoning makes the model "
                         "read the description more carefully is this experiment's question.")
    args = ap.parse_args()
    # Which channel(s) each mode ablates (see module docstring).
    do_text = args.mode in ("combined", "text")
    do_priority = args.mode in ("combined", "priority")
    do_examples = args.mode in ("combined", "examples")
    desc_chars = None if args.full_desc else va._SENTINEL
    think = {"off": False, "low": "low", "default": None}[args.think]

    # Ollama's OpenAI-compatible endpoint. load_knowledge_base()/TEST_QUERIES honour the VEP_* env vars,
    # so the same code scores either the demo KB or the expanded catalogue.
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
    # The SHIPPED prompt prices each option for the query's own factor tuple, so we have to classify
    # first — the test queries carry no factor labels. One classifier call per query, cached and
    # reused for that query's baseline and all of its ablations, so the tuple is held fixed and the
    # only thing varying within a query is the channel being ablated.
    print("classifying factors (once per query, reused across its ablations)...")
    resolved_by_q = {}
    for t in tqs:
        ft = va.infer_factors(client, args.model, t["query"], apply_defaults=True,
                              seed=args.seed, temperature=0.0)
        resolved_by_q[t["id"]] = va.resolve_for_query(ft, catalogue) if ft else None
    n_res = sum(1 for v in resolved_by_q.values() if v)
    print(f"  resolved {n_res}/{len(tqs)} queries onto the factor scheme"
          + ("" if n_res == len(tqs) else "  (the rest fall back to the legacy prompt)"))

    baselines = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(run_one, client, args.model, catalogue, loo(t), t["query"], aliases,
                          args.seed, resolved_by_q[t["id"]], desc_chars, think): t for t in tqs}
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
                     ablate_text(catalogue, r, do_text),            # r's description, if the mode says so
                     ablate_examples(corpus, r, do_examples),       # ...and/or its worked examples
                     query, aliases, args.seed,
                     ablate_priority(resolved_by_q[qid], r, do_priority),   # ...and/or its priority label
                     desc_chars, think)
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
