#!/usr/bin/env python3
"""Species-specific options: does a non-human user get the option list for THEIR species?

WHY. Past the binary species factor, what a non-human user is offered depends on WHICH organism it is:
SIFT exists for eleven non-human species, CADD for pig, chicken and turkey, CCDS for mouse, frequency
files for four species, and each plugin has Ensembl's own species list (now the `species` field of each
option in `vep_ai_demo/vep_options.json`; CCDS has since left the catalogue). The
checker picks the organism for those lookups with `resolve_species_name(user_query)`, a scan that takes
the first name in the text it finds in Ensembl's species index. The classifier also names the organism
(`organism` field, 2026-09-20), but that answer reaches only the display line, not the checker
(noted 2026-09-22). This measures what that costs, and what passing the model's answer
would give.

2026-09-23: done. Since engine commit 51912b2 (2026-09-22) the checker takes the classifier's organism
and falls back to the scan only when there is none. The `model` arm below is what ships; the `scan`
arm is the behaviour before it.

NO MODEL CALL. It replays the 242 queries of the 121-organism sample (`organism_754_names.py --sample-121`,
called organism_121_names.py until 2026-09-26; 121 organisms × plain / decoy). The
model arm reads the organism the classifier already returned in
`results/organism_121_names_reasoning_on.json` beside this script
(reasoning on, the shipped setting).

For each query, one fixed non-human scenario (germline, small variants, coding, clinical interpretation:
the tuple with the most species-dependent options) is resolved, and every option offered (RECOMMENDED and
ADD-ONS) goes through `check_and_fix_violations` three times, with the organism for the data lookups set to:

    truth   the organism the query is about (the index's species for the name written)
    scan    what the checker used before 51912b2: resolve_species_name(query)
    model   the classifier's resolved `organism` answer for that query

SCORED  the offered set equals the truth arm's set (the user sees the right list for their species),
        and the organism is right (species level: strain names collapse to the species).

  python3 evidence/legacy_decisions/species_data/species_options_scan_vs_model.py   # prints the table, writes results/

Called evidence/current_evidence/species_option_accuracy.py until 2026-09-23. It moved here once the
engine used the model's organism: it is the evidence for that decision, and it tests no model.
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "evidence" / "current_evidence"))           # organism_754_names
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
import organism_754_names as on                                         # noqa: E402  (on.build() = the 121 sample)

TUPLE = {"species": "non-human", "origin": "germline", "variant_size_class": ["small"],
         "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
MODEL_RESULTS = Path(__file__).resolve().parent / "results" / "organism_121_names_reasoning_on.json"


def offered_for(organism, query, catalogue, resolved):
    """The options offered for TUPLE when the checker's organism lookup returns `organism`."""
    enabled = {o for o, (_e, pri, gated) in resolved.items() if not gated and pri in ("recommended", "optional")}
    disabled = set()
    real = va.resolve_species_name
    va.resolve_species_name = lambda _q: organism
    try:
        va.check_and_fix_violations(enabled, disabled, catalogue, query,
                                    species_override="non-human", resolved=resolved)
    finally:
        va.resolve_species_name = real
    return frozenset(enabled)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(Path(__file__).resolve().parent / "results" / f"species_options_scan_vs_model_{date.today().isoformat()}.json"))
    a = ap.parse_args()

    catalogue, _ = va.load_knowledge_base()
    resolved = va.resolve_for_query(TUPLE, catalogue)
    cases = on.build()
    saved = {r["id"]: r for r in json.load(open(MODEL_RESULTS))["rows"]}
    assert [c["id"] for c in cases] == list(saved), "case list differs from the saved organism_121_names run"

    rows, cache = [], {}
    for c in cases:
        for v in ("plain", "decoy"):
            q = c[f"{v}_query"]
            truth = c["expected_species"]
            orgs = {"truth": truth, "scan": va.resolve_species_name(q),
                    "model": saved[c["id"]]["result"][v]["resolved"]}
            sets = {}
            for arm, org in orgs.items():
                key = va.species_key(org) if org else None
                if key not in cache:
                    cache[key] = offered_for(org, q, catalogue, resolved)
                sets[arm] = cache[key]
            rows.append({
                "id": c["id"], "kind": c["kind"], "version": v, "query": q,
                "organism": {arm: (va.species_key(o) if o else None) for arm, o in orgs.items()},
                "organism_ok": {arm: bool(orgs[arm]) and va.species_key(orgs[arm]) == truth for arm in ("scan", "model")},
                "options_ok": {arm: sets[arm] == sets["truth"] for arm in ("scan", "model")},
                "options_wrong": {arm: sorted(sets[arm] ^ sets["truth"]) for arm in ("scan", "model")},
            })

    n = len(rows)
    print(f"species-specific options: {n} queries ({n // 2} organisms x plain/decoy), tuple {TUPLE}\n")
    print(f"  {'':34}{'scan (old)':>14}{'model (shipped)':>16}")
    for label, key in (("organism right", "organism_ok"), ("offered options right", "options_ok")):
        print(f"  {label:34}" + "".join(f"{sum(r[key][arm] for r in rows):>10}/{n}" for arm in ("scan", "model")))
    for v in ("plain", "decoy"):
        sel = [r for r in rows if r["version"] == v]
        print(f"  {'  offered options right, ' + v:34}"
              + "".join(f"{sum(r['options_ok'][arm] for r in sel):>10}/{len(sel)}" for arm in ("scan", "model")))
    print("\n  offered options right, by kind of name")
    for k in on.KINDS + ("trap",):
        sel = [r for r in rows if r["kind"] == k]
        print(f"    {k:30}" + "".join(f"{sum(r['options_ok'][arm] for r in sel):>10}/{len(sel)}" for arm in ("scan", "model")))
    wrong = Counter(o for r in rows for o in r["options_wrong"]["scan"])
    print("\n  options wrong under the scan (offered or withheld against the truth), by option: "
          + ", ".join(f"{o} {c}" for o, c in wrong.most_common()))
    print("\n  scan misses:")
    for r in rows:
        if not r["options_ok"]["scan"]:
            print(f"    {r['id']:10} {r['version']:5} truth {r['organism']['truth']:28} scan {r['organism']['scan']!s:28} "
                  f"model {r['organism']['model']!s:24} wrong: {', '.join(r['options_wrong']['scan'])}")
    summary = {arm: {"organism_ok": sum(r["organism_ok"][arm] for r in rows),
                     "options_ok": sum(r["options_ok"][arm] for r in rows)} for arm in ("scan", "model")}
    Path(a.json).write_text(json.dumps({"tuple": TUPLE, "n": n, "model_results": MODEL_RESULTS.name,
                                        "summary": summary, "rows": rows}, indent=1))
    print(f"\n  wrote {a.json}")


if __name__ == "__main__":
    main()
