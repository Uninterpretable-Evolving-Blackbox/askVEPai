#!/usr/bin/env python3
"""Compute run-level mean +/- SD for the logged gemma4:26b eval.

For each (condition, run) we take the dataset mean over the 20 LOO queries, giving 3 dataset-level
values per condition; we then report mean +/- SD ACROSS those 3 runs (seeds 42/43/44). This is the
"mean +/- SD" the project's discipline means (decoding-noise SD), now propagated to the dataset level
(the per-query SD in the .md report is a different, larger quantity).

Re-parses the logged responses with the CURRENT corrected parser (same approach as rescore_offline.py),
so the numbers match the corrected headline. No GPU, no new inference.

Run:  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/compute_run_sd.py
"""
import json, os, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va          # noqa: E402
import evaluate as ev               # noqa: E402
import score_metrics as sm          # noqa: E402

CAT = json.load(open(os.environ["VEP_OPTIONS_FILE"]))
ALIASES = va.build_option_aliases(CAT)
# Optional argv: [1] raw-log path, [2] model label. Defaults reproduce the original
# 3-seed gemma4:26b headline so existing invocations are unchanged.
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "work" / "results_fixedparser" / "raw" / "gemma4_26b.jsonl"
LABEL = sys.argv[2] if len(sys.argv) > 2 else "gemma4:26b"
ORDER = ["bare", "keyword", "all", "semantic"]

recs = [json.loads(l) for l in open(LOG)]

# (cond, run) -> list of per-query score dicts
per = defaultdict(list)
clin = defaultdict(list)
for r in recs:
    resp = r.get("response", "") or ""
    cond, run, uc = r["condition"], r["run"], r["use_case"]
    gt_en, gt_dis = set(r["gt_enabled"]), set(r["gt_disabled"])
    en, dis = va.extract_recommendations(resp, ALIASES)       # corrected parser
    s = ev.score_response(en, dis, gt_en, gt_dis, CAT, r["query"], gt_category=uc)
    per[(cond, run)].append(s)
    rec2 = dict(r); rec2["enabled"] = sorted(en)
    clin[(cond, run)].append(sm.score_record(rec2))

runs = sorted({k[1] for k in per})

def run_means(cond, key, clinical=False):
    """Per-run dataset mean of `key`, across runs -> list of 3 values."""
    out = []
    for rn in runs:
        if clinical:
            vals = [d[key] for d in clin[(cond, rn)]]
        else:
            vals = [d.get(key) for d in per[(cond, rn)]]
        m = ev._safe_mean(vals)
        if m is not None:
            out.append(m)
    return out

def fmt(cond, key, clinical=False, pct=True):
    v = run_means(cond, key, clinical)
    if not v:
        return "n/a"
    mean = statistics.mean(v)
    sd = statistics.stdev(v) if len(v) > 1 else 0.0
    if pct:
        return f"{mean*100:.0f}% +/- {sd*100:.0f}%"
    return f"{mean:.2f} +/- {sd:.2f}"

metrics = [
    ("Enable F1",            "enable_f1",          False, True),
    ("Enable F1 (weighted)", "enable_f1_weighted", False, True),
    ("Disable F1",           "disable_f1",         False, True),
    ("Critical-recall",      "crit_r",             True,  True),
    ("Category-cover",       "cover",              True,  True),
    ("Over-recommendation",  "over",               True,  False),
]

_seeds = sorted({r.get("seed") for r in recs if r.get("seed") is not None})
_seedstr = "/".join(str(s) for s in _seeds) if _seeds else "?"
print(f"{LABEL}  |  {len(runs)} runs (seeds {_seedstr})  |  mean +/- SD ACROSS runs (dataset-level)\n")
header = f"{'Metric':22s} " + " ".join(f"{c:>16s}" for c in ORDER)
print(header)
print("-" * len(header))
for label, key, clinical, pct in metrics:
    row = f"{label:22s} " + " ".join(f"{fmt(c, key, clinical, pct):>16s}" for c in ORDER)
    print(row)

# Markdown table for direct paste into the README
print("\n--- markdown ---\n")
print("| Condition | " + " | ".join(l for l, *_ in metrics) + " |")
print("|" + "---|" * (len(metrics) + 1))
for c in ORDER:
    cells = [fmt(c, key, clinical, pct).replace("+/-", "±") for _, key, clinical, pct in metrics]
    print(f"| {c} | " + " | ".join(cells) + " |")
