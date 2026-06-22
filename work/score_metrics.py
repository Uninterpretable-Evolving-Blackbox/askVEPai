#!/usr/bin/env python3
"""Offline, clinically-meaningful re-scoring from raw eval logs (work/results/raw/*.jsonl).

Exact-match Enable F1 over-penalises a recommender on an ambiguous task: it counts every
defensible *extra* option as an error, and treats interchangeable picks (CADD vs REVEL) as
misses. These metrics target what actually matters and are deterministic functions of the
saved raw outputs (no LLM re-run needed):

  exact_f1        — reproduces the report's Enable F1 (CONSISTENCY CHECK vs prior runs)
  critical_recall — of the gold's *critical* options for the use case, fraction recommended
  important_recall— same for critical+recommended ("must/should haves")
  category_cover  — of the annotation *categories* the gold needs, fraction with >=1 option rec'd
  over_rec_ratio  — |enabled| / |gold_enabled|  (>1 = over-recommends)
  species_harm    — raw human-only-options-for-non-human count (post-checker this is 0)

Usage: VEP_OPTIONS_FILE=work/vep_options_expanded.json python score_metrics.py [results_dir]
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "vep_ai_demo"))
import vep_assistant as va  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
CAT = json.load(open(os.environ.get("VEP_OPTIONS_FILE", HERE / "vep_options_expanded.json")))
PRIO = {o["id"]: o.get("priority_by_use_case", {}) for o in CAT}
CATEGORY = {o["id"]: o.get("category", "?") for o in CAT}
SPECIES = {o["id"]: o.get("species_restriction", "all species") for o in CAT}
ORDER = ["bare", "keyword", "all", "semantic"]


def prio(oid, uc):
    """Priority label ('critical'/'recommended'/...) of option oid for use case uc, or None."""
    return PRIO.get(oid, {}).get(uc)


def score_record(rec):
    """Compute the clinically-meaningful metrics for one raw eval record.

    rec is a saved per-call log line (enabled/gt_enabled/use_case/query). Returns a
    dict of: exact f1 (consistency check vs the report), critical/important recall
    (did we surface the must/should-have options), category coverage, over-rec ratio,
    and raw species harm. recall/cover are None when undefined (no critical golds, etc.)
    so mean() can skip them rather than count a spurious 0.
    """
    en, gt = set(rec["enabled"]), set(rec["gt_enabled"])
    uc, query = rec["use_case"], rec.get("query", "")
    overlap = en & gt
    prec = len(overlap) / len(en) if en else 0.0
    recl = len(overlap) / len(gt) if gt else 0.0
    f1 = 2 * prec * recl / (prec + recl) if (prec + recl) else 0.0

    crit = {o for o in gt if prio(o, uc) == "critical"}
    imp = {o for o in gt if prio(o, uc) in ("critical", "recommended")}
    crit_r = len(crit & en) / len(crit) if crit else None
    imp_r = len(imp & en) / len(imp) if imp else None

    gold_cats = {CATEGORY.get(o, "?") for o in gt}
    en_cats = {CATEGORY.get(o, "?") for o in en}
    cover = len(gold_cats & en_cats) / len(gold_cats) if gold_cats else None

    over = len(en) / len(gt) if gt else None
    species = va.infer_species(query)
    # Mirror the deployed checker's fail-closed posture: 'unknown' is treated like 'human' (human-only
    # options are kept + flagged, NOT counted as harm) — else the 8/20 human-but-unspecified queries
    # (GWAS / population / regulatory / SV) would report spurious harm. Only a CONFIRMED non-human counts.
    harm = sum(1 for o in en if species not in ("human", "unknown") and va._is_human_only(SPECIES.get(o, "all species")))
    return dict(f1=f1, crit_r=crit_r, imp_r=imp_r, cover=cover, over=over, harm=harm)


def mean(xs):
    """Mean over the non-None values (None = metric undefined for that record); NaN if empty."""
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def main():
    files = sorted((RES / "raw").glob("*.jsonl")) if (RES / "raw").exists() else []
    if not files:
        sys.exit(f"no raw logs in {RES}/raw/ — re-run run_parallel_eval.py (now logs raw outputs)")
    print(f"Clinically-meaningful re-scoring (from raw logs in {RES}/raw/)\n")
    print(f"{'model':14s} {'cond':9s} {'exactF1':>8s} {'critRecall':>11s} {'impRecall':>10s} "
          f"{'catCover':>9s} {'overRec':>8s} {'harm':>5s}")
    print("-" * 80)
    for f in files:
        recs = [json.loads(l) for l in open(f)]
        by_cond = defaultdict(list)
        for r in recs:
            by_cond[r["condition"]].append(score_record(r))
        model = f.stem
        for c in ORDER:
            if c not in by_cond:
                continue
            s = by_cond[c]
            print(f"{model:14s} {c:9s} {mean([x['f1'] for x in s]):>7.0%} "
                  f"{mean([x['crit_r'] for x in s]):>10.0%} {mean([x['imp_r'] for x in s]):>9.0%} "
                  f"{mean([x['cover'] for x in s]):>8.0%} {mean([x['over'] for x in s]):>7.2f} "
                  f"{sum(x['harm'] for x in s):>5d}")
        print()


if __name__ == "__main__":
    main()
