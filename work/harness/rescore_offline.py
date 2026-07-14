#!/usr/bin/env python3
"""Offline re-score of the logged gemma4:26b eval responses with the CURRENT (fixed) code.

WHY OFFLINE (not a live re-run): every fix since the 87% run — phantom-id filter, 0-not-None, errored-
exclude, species fail-closed — is a PARSING / SCORING / METRIC change; build_system_prompt and the model
are unchanged. So re-parsing the 240 logged responses (results_fixedparser/raw/gemma4_26b.jsonl) with the
new code yields the corrected metrics for the EXACT same model outputs: it isolates the code change as the
only variable, has zero sampling/batch noise, and needs no GPU. It also doubles as an integration test of
the fixed parse -> score -> aggregate -> report path on 240 real responses.
(Valid ONLY because the prompt is unchanged; any build_system_prompt change would force a live re-run.)

Run:  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/harness/rescore_offline.py
"""
import json, os, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va          # noqa: E402
import evaluate as ev               # noqa: E402
import score_metrics as sm          # noqa: E402  (clinical metrics; uses the fixed species_harm)

CAT = json.load(open(os.environ["VEP_OPTIONS_FILE"]))
REAL_IDS = {o["id"] for o in CAT}
ALIASES = va.build_option_aliases(CAT)
VALID = set(ALIASES.values())
LOG = ROOT / "work" / "results_fixedparser" / "raw" / "gemma4_26b.jsonl"
COND_KEY = {"bare": "without_kb", "keyword": "with_kb", "all": "with_kb_all", "semantic": "with_kb_semantic"}
ORDER = ["bare", "keyword", "all", "semantic"]

def pf(x):
    return "n/a" if (x is None or x != x) else f"{x:.0%}"   # x!=x catches NaN

def classify_phase(resp):
    """Which extract_recommendations phase fires: P0 (structured ✓/✗ + [source:]), P1 (table), P2 (prose)."""
    for line in resp.splitlines():
        m = re.search(r"\[source:\s*([A-Za-z0-9_]+)", line)
        if not m:
            continue
        oid = m.group(1)
        resolvable = oid in VALID or va._match_option(oid, ALIASES)
        head = line[:m.start()]
        if resolvable and any(g in head for g in ("✓", "✅", "✗", "✘", "❌")):
            return "P0"
    if re.search(r"\|\s*\*{0,2}[^|]+?\*{0,2}\s*\|\s*\*{0,2}(enable|disable|on|off|yes|no|true|false)",
                 resp.lower()):
        return "P1"
    return "P2"

recs = [json.loads(l) for l in open(LOG)]
runs = defaultdict(list)            # (query_id, cond) -> [full score dict per run]
cond_scores = defaultdict(list)     # cond -> [score dict]  (query x run)
clin = defaultdict(list)            # cond -> [clinical metric dict]
phase_ct = defaultdict(Counter)     # cond -> Counter(phase)
phantom = Counter()                 # phantom id (old parser) -> count
species_ct = Counter()
errored = 0
new_phantom_leak = 0                # sanity: new parser must emit ZERO phantom ids
gt_by_q = {}

for rec in recs:
    resp = rec.get("response", "") or ""
    cond, qid, query, uc = rec["condition"], rec["query_id"], rec["query"], rec["use_case"]
    gt_en, gt_dis = set(rec["gt_enabled"]), set(rec["gt_disabled"])
    gt_by_q[qid] = (uc, gt_en, gt_dis, query)
    if not resp.strip():
        errored += 1

    new_en, new_dis = va.extract_recommendations(resp, ALIASES)            # RE-PARSE with the fixed parser
    new_phantom_leak += len(new_en - REAL_IDS)                             # must be 0
    for pid in set(rec.get("enabled", [])) - REAL_IDS:                     # phantoms the OLD parser emitted
        phantom[pid] += 1

    score = ev.score_response(new_en, new_dis, gt_en, gt_dis, CAT, query, gt_category=uc)  # RE-SCORE (None-aware)
    score["use_case_detected"] = ev.extract_use_case(resp)
    score["use_case_correct"] = (score["use_case_detected"] == uc)
    cr, cf, ct = ev.measure_citation_rate(resp)
    score["citation_rate"], score["citations_found"], score["total_recommendations"] = cr, cf, ct
    if not resp.strip():
        score["_errored"] = True
    runs[(qid, cond)].append(score)
    cond_scores[cond].append(score)

    rec2 = dict(rec); rec2["enabled"] = sorted(new_en)                     # clinical metrics on re-parsed set
    clin[cond].append(sm.score_record(rec2))
    phase_ct[cond][classify_phase(resp)] += 1

for uc, gt_en, gt_dis, query in {q: gt_by_q[q] for q in gt_by_q}.values():
    species_ct[va.infer_species(query)] += 1

conds = [c for c in ORDER if c in cond_scores]

# Rebuild all_results and run the FIXED generate_report on real data (integration test + comparable .md)
all_results = {"model": "gemma4:26b", "num_runs": 3, "base_seed": 42, "temperature": 0.0, "queries": []}
for qid, (uc, gt_en, gt_dis, query) in gt_by_q.items():
    entry = {"id": qid, "query": query, "source": "simulated", "gt_category": uc}
    for c in conds:
        if (qid, c) in runs:
            entry[COND_KEY[c]] = ev.aggregate_scores(runs[(qid, c)])
    all_results["queries"].append(entry)
report = ev.generate_report(all_results)
out = ROOT / "work" / "results_fixedparser" / "evaluation_results_gemma4_26b_RESCORED.md"
out.write_text(report)

# ---- corrected metric table (mean over query x run; matches the clinical headline) ----
print("=== CORRECTED metrics — offline re-score of 240 logged 26b responses with the fixed code ===")
print(f"{'cond':9s} {'enF1':>6s} {'enF1_wt':>8s} {'disF1':>6s} {'critRec':>8s} {'catCov':>7s} {'overRec':>8s} {'harm':>5s}")
for c in conds:
    s, sc = clin[c], cond_scores[c]
    print(f"{c:9s} {pf(sm.mean([x['f1'] for x in s])):>6s} "
          f"{pf(sm.mean([x.get('enable_f1_weighted') for x in sc])):>8s} "
          f"{pf(sm.mean([x.get('disable_f1') for x in sc])):>6s} "
          f"{pf(sm.mean([x['crit_r'] for x in s])):>8s} "
          f"{pf(sm.mean([x['cover'] for x in s])):>7s} "
          f"{sm.mean([x['over'] for x in s]):>8.2f} {sum(x['harm'] for x in s):>5d}")
print("\nrecorded 2026-06-08 (all-examples): enF1 87% · critRec 95% · catCov 96% · disF1 81% · harm 0")

print("\n=== FALLBACK-TRIGGER audit (which paths actually fire vs are defensive) ===")
for c in conds:
    print(f"  parser phase [{c:9s}]: {dict(phase_ct[c])}")
print(f"  species class (20 unique queries): {dict(species_ct)}")
print(f"  phantom ids the OLD parser emitted (now filtered): {dict(phantom) or 'none'}")
print(f"  new parser phantom leak (must be 0): {new_phantom_leak}")
print(f"  errored/empty responses in the log: {errored}")
print(f"\ncorrected report written -> {out}")
