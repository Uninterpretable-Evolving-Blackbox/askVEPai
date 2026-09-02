#!/usr/bin/env python3
"""Factor-keyed leave-one-out evaluation of a generated example set.

Runs the RAG recommender (prose query -> retrieval over the other examples -> LLM -> parser) on each
generated query and scores its predicted config against that row's DETERMINISTIC gold config. Unlike the
main harness, recall is computed from each row's OWN factor priorities (the enabled set in
recommended_options), because the factor rows carry no `use_case_category` and
the catalogue's `priority_by_use_case` does not apply to them.

What it measures: whether the LLM recommender reproduces the deterministic priority table when it only
sees the query. High agreement = the RAG path is faithful to the table. This is self-consistency of the
two paths, not correctness against real gold — read it as directional (the table itself is provisional).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/harness/eval_factor_set.py --set work/generation/candidates/iced.json \
      --model gemma4:26b --runs 3
"""
import argparse
import json
import os
import statistics
import time
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va          # noqa: E402
import evaluate as ev              # noqa: E402
from openai import OpenAI           # noqa: E402


def f1(pred, gold):
    if not gold:
        return None
    ov = len(pred & gold)
    p = ov / len(pred) if pred else 0.0
    r = ov / len(gold)
    return (2 * p * r / (p + r)) if (p + r) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, help="the generated set (iced.json / review json)")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--merged-tiers", action="store_true",
                    help="render in-context examples with the TWO-tier scheme the user now sees "
                         "(one RECOMMENDED bucket). Retained for command compatibility; since the tier "
                         "--show-tiers. The A/B against the three-tier arm is what says whether the "
                         "merge costs the recommender anything.")
    ap.add_argument("--show-tiers", action="store_true",
                    help="render each in-context example WITH its tier (recommended / optional "
                         "add-ons) instead of the demo's tier-blind ON/OFF. The factor gold carries tiers; "
                         "hiding them makes the recommended-vs-optional line unlearnable from examples.")
    ap.add_argument("--factors", choices=["none", "oracle", "inferred"], default="none",
                    help="how the prompt's OPTION block is priced. 'none' = the legacy flat "
                         "priority_by_use_case dump (the pre-migration baseline). 'oracle' = resolve the "
                         "row's TRUE factor labels through intent_priorities, isolating the value of "
                         "showing scenario-resolved tiers from any classifier error. 'inferred' = classify "
                         "the query with infer_factors first, i.e. the full shipped path including "
                         "classifier mistakes. oracle - none = the prompt change; inferred - oracle = the "
                         "cost of imperfect factor inference.")
    ap.add_argument("--factor-model", default=None,
                    help="model for --factors inferred (default: VEP_FACTOR_MODEL, else gemma4:12b)")
    ap.add_argument("--think", choices=["default", "off", "low"], default="default",
                    help="reasoning phase on the recommender model. 'default' keeps the shipped "
                         "behaviour (compat endpoint, reasoning on). 'off'/'low' route through "
                         "Ollama's native endpoint, which is the only one that honours the parameter. "
                         "Reasoning is ~55%% of wall-clock, so this is the speed/accuracy knob.")
    ap.add_argument("--full-desc", action="store_true",
                    help="send each option's COMPLETE description instead of the first 120 chars. "
                         "All 65 exceed 120, so the default truncates every one of them mid-sentence "
                         "(check_existing is cut one character before the word ClinVar). Costs ~+2.9k "
                         "prompt tokens; prefill is not the bottleneck.")
    ap.add_argument("--gold", choices=["live", "stored"], default="live",
                    help="where the gold config comes from. 'live' (default) RESOLVES each row's "
                         "factor_labels through the current priority table, which is what this "
                         "harness claims to measure. 'stored' reads the frozen recommended_options "
                         "in the set file — the round-1 snapshot, kept for export_round2's "
                         "what-changed-since-your-review diff. They drifted apart on 2026-08-19 when "
                         "the mentor corrections landed in DRIVES but not in the frozen file, so "
                         "'stored' now scores every applied correction as an error.")
    ap.add_argument("--json", default=None, help="write the aggregate result to this path")
    args = ap.parse_args()
    THINK = {"default": None, "off": False, "low": "low"}[args.think]
    if args.factor_model:
        os.environ["VEP_FACTOR_MODEL"] = args.factor_model

    if args.show_tiers:
        def format_example_tiered(ex):
            opts = ex.get("recommended_options", {})
            lines = [f"Query: {ex['user_query']}", "Options (by importance):"]
            if args.merged_tiers:
                # The two-tier output the user sees.
                for o in sorted(k for k, c in opts.items()
                                if c.get("enabled") and c.get("priority") == "recommended"):
                    lines.append(f"  {o}: ON [recommended]")
            else:
                # There is one enabled tier since 2026-08-19, so --merged-tiers and the plain arm now
                # render identically. The flag survives so old commands keep working.
                for o in sorted(k for k, c in opts.items()
                                if c.get("enabled") and c.get("priority") == "recommended"):
                    lines.append(f"  {o}: ON [recommended]")
            for o in sorted(ex.get("add_on_options", {})):
                lines.append(f"  {o}: add-on [optional, off by default]")
            return "\n".join(lines)
        va.format_example = format_example_tiered   # the prompt builder calls va.format_example

    rows = json.load(open(args.set))
    # The generated rows carry justification=None (Stage 3b never drafted one); the demo's format_example
    # indexes ex["justification"], so give each row a short factor-derived rationale for its in-context use.
    for r in rows:
        if not r.get("justification"):
            fl = r["factor_labels"]
            r["justification"] = (f"Configuration for a {fl['species']} {fl['origin']} "
                                  f"{fl['variant_size_class']} scenario "
                                  f"({'+'.join(fl['region_focus'])}; {'+'.join(fl['analysis_goal'])}).")
        if r.get("use_case_category") is None:
            r["use_case_category"] = "factor-scheme"
    catalogue = va.load_catalogue() if hasattr(va, "load_catalogue") else \
        json.load(open(os.environ["VEP_OPTIONS_FILE"]))
    aliases = va.build_option_aliases(catalogue)
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")
    seeds = [int(s) for s in args.seeds.split(",")][:args.runs]

    # gold per row: the enabled set, from the row's own factor priorities.
    CORE = "core_type"
    gold = {}
    for r in rows:
        opts = r["recommended_options"]
        en = {o for o, c in opts.items() if c.get("enabled")}
        # MUST-HAVE RECALL IS WITHDRAWN (2026-08-19). It scored against `priority == "critical"`, a
        # tier that no longer exists — and which, while it did, was the one boundary the reviewer
        # corrected twelve times without those corrections ever being applied. With a single enabled
        # set there is one recall to report and `enable_f1` already covers it. Do not quote the old
        # 95.1%: it measured agreement with an unvalidated judgement, scored against itself.
        if args.gold == "live":
            res = va.resolve_for_query(r["factor_labels"], catalogue)
            en = {o for o, (e, _p, _g) in (res or {}).items() if e}
        gold[r["id"]] = {"query": r.get("user_query"), "enabled": en}

    # DRIFT ALARM. The frozen set and the live table disagreeing is not a nuisance to route around:
    # it means a published figure is scoring the model against a table that no longer exists. It went
    # unnoticed once already, so it is reported on every run rather than left to be rediscovered.
    drift = 0
    for r in rows:
        res = va.resolve_for_query(r["factor_labels"], catalogue) or {}
        if {o for o, c in r["recommended_options"].items() if c.get("enabled")} != \
           {o for o, (e, _p, _g) in res.items() if e}:
            drift += 1
    if drift:
        print(f"  !! {drift}/{len(rows)} rows: the set file's frozen config differs from what the "
              f"priority table resolves today.\n     Scoring against --gold {args.gold}. "
              f"'stored' would count every applied mentor correction as a model error.")

    by_id = {r["id"]: r for r in rows}

    def one(rid, seed):
        g = gold[rid]
        loo = [x for x in rows if x["id"] != rid]                      # leave-one-out corpus
        ft = None
        if args.factors == "oracle":
            ft = by_id[rid]["factor_labels"]
        elif args.factors == "inferred":
            # The shipped path: classify the query, then price the options from that. Note this runs
            # under --concurrency, where temp=0 is NOT reproducible on a Metal/MoE stack, so the
            # inferred arm carries a little extra run-to-run noise the other two arms do not.
            ft = va.infer_factors(client, args.model, g["query"])
        prompt = va.build_system_prompt(catalogue, loo, g["query"], retrieval_mode="all",
                                        factor_tuple=ft,
                                        desc_chars=None if args.full_desc else va._SENTINEL)
        # Per-query wall clock. Latency is a first-class result once `think` is a knob: the reasoning
        # phase is roughly half of it, so a model comparison that reports only accuracy hides the
        # thing a user actually experiences. Timed around the LLM call alone; prompt assembly and
        # parsing are sub-millisecond (measured) and would only add noise.
        _t0 = time.perf_counter()
        text = ev.call_llm(client, args.model, prompt, g["query"], temperature=args.temperature,
                           seed=seed, think=THINK)
        elapsed = time.perf_counter() - _t0
        enabled, _ = va.extract_recommendations(text, aliases)
        pred = set(enabled)
        return {
            "seconds": elapsed,
            "n_pred": len(pred),
            "enable_f1": f1(pred, g["enabled"]),
            "enable_recall": (len(pred & g["enabled"]) / len(g["enabled"])) if g["enabled"] else None,
        }

    per_run = []
    # Progress. Without this the run prints NOTHING until every row of a seed is done — ~7 minutes of
    # silence at concurrency 1, which is indistinguishable from a hang. Same failure the reasoning
    # phase had: work happening with no evidence of it.
    done = {"n": 0}
    def one_progress(rid, seed):
        r = one(rid, seed)
        done["n"] += 1
        print(f"    [{done['n']:2d}/{len(rows)}] {r['seconds']:5.1f}s  "
              f"F1 {(r['enable_f1'] or 0)*100:3.0f}%  {rid[:44]}", flush=True)
        return r

    for seed in seeds:
        done["n"] = 0
        print(f"  seed {seed}: running {len(rows)} rows at concurrency {args.concurrency}…", flush=True)
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            res = list(ex.map(lambda rid: one_progress(rid, seed), [r["id"] for r in rows]))
        ef = [x["enable_f1"] for x in res if x["enable_f1"] is not None]
        er = [x["enable_recall"] for x in res if x["enable_recall"] is not None]
        run = {"enable_f1": statistics.mean(ef), "enable_recall": statistics.mean(er),
               "n_rows": len(ef),
               "seconds": statistics.mean(x["seconds"] for x in res),
               "n_pred": statistics.mean(x["n_pred"] for x in res)}
        per_run.append(run)
        print(f"  seed {seed}: enable-F1 {run['enable_f1']*100:.0f}%  "
              f"enable-recall {run['enable_recall']*100:.0f}%  "
              f"{run['seconds']:.1f}s/query")

    def agg(k):
        xs = [r[k] for r in per_run]
        return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)
    print(f"\n{len(rows)} rows, {args.runs} runs (seeds {seeds}), model {args.model}, all-examples LOO, "
          f"factors={args.factors}, gold={args.gold}, "
          f"tiers={'shown' if args.show_tiers else 'hidden'}")
    for label, key in [("enable-F1", "enable_f1"), ("enable-recall", "enable_recall")]:
        m, sd = agg(key)
        print(f"  {label:22s} {m*100:.0f}% ± {sd*100:.0f}%")
    sec_m, sec_sd = agg("seconds")
    pred_m, _ = agg("n_pred")
    conc_note = ("single-threaded, so this IS what one user waits"
                 if args.concurrency == 1 else
                 f"concurrency {args.concurrency}: requests CONTEND for one GPU, so this is "
                 f"INFLATED vs one user's wait — measured ~3x at concurrency 4. Use "
                 f"--concurrency 1 for a user-facing latency figure")
    print(f"  {'seconds/query':22s} {sec_m:.1f}s ± {sec_sd:.1f}")
    print(f"  {'':22s} ({conc_note})")
    print(f"  {'options proposed':22s} {pred_m:.1f}")
    if args.json:
        Path(args.json).write_text(json.dumps({
            "model": args.model, "think": args.think, "runs": args.runs, "seeds": seeds,
            "rows": len(rows), "show_tiers": args.show_tiers, "factors": args.factors,
            "gold": args.gold, "gold_drift_rows": drift,
            "concurrency": args.concurrency, "temperature": args.temperature,
            "full_desc": args.full_desc,
            "enable_f1": agg("enable_f1"), "enable_recall": agg("enable_recall"),
            "seconds": agg("seconds"), "n_pred": agg("n_pred"),
            "per_run": per_run,
        }, indent=2))
        print(f"  -> {args.json}")
    print("  (must-have recall is withdrawn as of 2026-08-19: it scored against the `critical` tier,")
    print("   which no longer exists. There is one enabled set now, so there is one recall.)")


def catalogue_ids(catalogue):
    return {o["id"] for o in catalogue}


if __name__ == "__main__":
    main()
