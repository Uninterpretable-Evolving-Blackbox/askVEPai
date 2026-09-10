#!/usr/bin/env python3
"""Exp 16 — What a lost option costs in the OUTPUT, not the option list (REST proxy).

THE QUESTION. Re-prompting is scored today by counting options lost when a default fills a gap. But a
lost option only harms the user if its FIELD would have been populated for their variants. Losing SIFT
on a synonymous variant loses nothing; losing it on a missense variant loses the evidence the clinical
question asked for. This experiment measures that difference on Ensembl's own VEP, and proposes the
labelling the ask/assume evaluation should use.

DESIGN. Two goal-fallback pairs — the only defaults that lose RECOMMENDED options at all:

    clinical-interpretation  -> basic-consequence   (the analysis_goal fallback, 1.00 REC lost/query)
    population-frequency     -> basic-consequence   (same fallback on a frequency question)

For each pair: resolve both configurations, take the RECOMMENDED options the fallback loses, and run
the TRUTH configuration through VEP REST on a four-class variant panel:

    known missense      rich annotation: predictions + colocated record
    novel missense      predictions exist, no colocated data (no ClinVar, no frequencies)
    known synonymous    colocated data exists, missense predictors have nothing to score
    known noncoding     an rsID with no protein consequence at all

A lost option is then labelled twice:

  CLASS  — what raised it, read from the engine's own decision trace (intent_priorities):
             ANSWER   raised by the query's analysis_goal: it IS the evidence the user asked for
             SCOPE    raised by size/region/species/origin or a conditional rule
             CONTEXT  the unconditional baseline (symbol, biotype, core_type)
  REALIZED — its field was actually populated for this variant in the truth run (REST).

THE PROPOSED METRIC. Score a gap-filling policy by REALIZED ANSWER LOSSES — lost options that are both
the goal's own evidence and populated for the variant class at hand — instead of raw option counts.
The raw count treats every row of the loss table identically; the panel shows they are not.

CAVEATS, STATED. REST is a proxy: same VEP, not the web form, and it exposes the native options but
almost none of the 26 plugins, so plugin losses (CADD, SpliceAI, MaveDB...) stay unmeasured here.
One Ensembl release answers each run (recorded in the output). The panel is constructed, small, and
human-only; it demonstrates the variant-class dependence, it does not estimate population rates.
`origin`'s cost (`--check_frequency`, a pre-filter) is invisible to REST and is not measured.

  python work/harness/exp_output_loss.py            # runs the panel (network; ~6 REST calls)
  python work/harness/exp_output_loss.py --markdown # table for the docs
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "harness"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402
from run_vep_rest import REST, REST_PARAM, fetch_release, present       # noqa: E402

OUT = ROOT / "work" / "results" / "rest_output_loss.json"

PANEL = [
    ("known missense",   "hgvs", "ENST00000366667.4:c.803C>T"),
    ("novel missense",   "hgvs", "ENST00000366667.4:c.802G>C"),
    ("known synonymous", "hgvs", "ENST00000366667.4:c.798C>T"),
    ("known noncoding",  "id",   "rs12979860"),
]

BASE = {"species": "human", "origin": "germline", "variant_size_class": ["small"],
        "region_focus": ["coding"]}
PAIRS = [("clinical-interpretation", "basic-consequence"),
         ("population-frequency", "basic-consequence")]


def rest_call(endpoint, ident, params):
    q = urllib.parse.urlencode({**params, "content-type": "application/json"})
    url = f"{REST}/vep/human/{endpoint}/{urllib.parse.quote(ident)}?{q}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def resolve(goal):
    ft = dict(BASE, analysis_goal=[goal])
    catalogue, _ = va.load_knowledge_base()
    pbf = va.load_priority_by_factor(catalogue)
    cfg = va.load_factors()
    trace = {}
    res = va.intent_priorities(ft, catalogue, pbf, cfg, trace=trace)
    on = {o for o, (e, _p, _g) in res.items() if e}
    return on, trace


def classify(oid, trace):
    """CLASS from the engine's own decision trace — no new judgement is introduced here."""
    if oid in set(va.BASELINE_CRITICAL) | set(va.BASELINE_RECOMMENDED):
        return "CONTEXT"
    winner = (trace.get(oid) or {}).get("winner")
    if winner and winner[0] == "analysis_goal":
        return "ANSWER"
    return "SCOPE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--cached", action="store_true", help="re-print from the saved JSON, no network")
    args = ap.parse_args()

    if args.cached and OUT.exists():
        results = json.loads(OUT.read_text())
    else:
        release, _ = fetch_release()
        results = {"ensembl_release": release, "panel": {}, "pairs": {}}
        # One truth-config call per (pair, variant): the union of the checkable params.
        for truth_goal, fb_goal in PAIRS:
            t_on, t_trace = resolve(truth_goal)
            f_on, _ = resolve(fb_goal)
            lost = sorted(t_on - f_on)
            checkable = [o for o in lost if o in REST_PARAM]
            params = {REST_PARAM[o][0]: 1 for o in t_on if o in REST_PARAM}
            pair_key = f"{truth_goal}->{fb_goal}"
            results["pairs"][pair_key] = {
                "lost": lost,
                "lost_checkable": checkable,
                "lost_unmeasured": sorted(set(lost) - set(checkable)),
                "class": {o: classify(o, t_trace) for o in lost},
                "realized": {},
            }
            for name, endpoint, ident in PANEL:
                time.sleep(0.5)
                payload = rest_call(endpoint, ident, params)
                if isinstance(payload, dict):                    # REST error object
                    results["pairs"][pair_key]["realized"][name] = {"error": str(payload)[:200]}
                    continue
                results["panel"].setdefault(name, {
                    "ident": ident,
                    "consequence": payload[0].get("most_severe_consequence"),
                    "known": bool(payload[0].get("colocated_variants")),
                })
                results["pairs"][pair_key]["realized"][name] = {
                    o: present(payload, REST_PARAM[o][1]) for o in checkable}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=1))

    rel = results["ensembl_release"]
    print(f"\nExp 16 — realized output loss, Ensembl release {rel} (REST proxy; native options only)\n")
    for pair_key, pr in results["pairs"].items():
        print(f"== {pair_key} ==")
        print(f"   options lost by the fallback: {', '.join(pr['lost'])}")
        if pr["lost_unmeasured"]:
            print(f"   unmeasured here (plugins/filters): {', '.join(pr['lost_unmeasured'])}")
        hdr = f"   {'lost option':<16} {'class':<8}" + "".join(
            f" {name.split()[1][:9] if len(name.split()) > 1 else name:>10}" for name, _e, _i in PANEL)
        # column titles: use full panel names
        hdr = f"   {'lost option':<16} {'class':<8}" + "".join(f" {n:>17}" for n, _e, _i in PANEL)
        print(hdr)
        for o in pr["lost_checkable"]:
            row = f"   {o:<16} {pr['class'][o]:<8}"
            for name, _e, _i in PANEL:
                r = pr["realized"].get(name, {})
                v = r.get(o)
                cell = "LOST(real)" if v else ("no-op" if v is False else "?")
                row += f" {cell:>17}"
            print(row)
        print()
    print("   LOST(real) = the field was populated in the truth run: dropping the option deletes")
    print("                evidence the user would have received for this variant.")
    print("   no-op      = the field was empty anyway; the loss costs nothing HERE.\n")

    if args.markdown:
        print("| pair | lost option | class |" + "|".join(f" {n} " for n, _e, _i in PANEL) + "|")
        print("|---|---|---|" + "---|" * len(PANEL))
        for pair_key, pr in results["pairs"].items():
            for o in pr["lost_checkable"]:
                cells = "|".join(
                    f" {'**lost**' if pr['realized'].get(n, {}).get(o) else 'no-op'} "
                    for n, _e, _i in PANEL)
                print(f"| {pair_key} | `{o}` | {pr['class'][o]} |{cells}|")


if __name__ == "__main__":
    main()
