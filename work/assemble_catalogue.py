#!/usr/bin/env python3
"""Assemble + validate the expanded VEP option catalogue from the workflow output.

Reads the catalogue-build workflow result (builtOptions + verifyVerdicts), enforces
schema compatibility with the demo's vep_options.json, surfaces adversarial-verifier
flags, and writes vep_options_expanded.json + a validation summary.

Usage: python assemble_catalogue.py <workflow_output.json>
"""
import json
import sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent                              # GSoC_WORK/work/
DEMO = HERE.parent / "vep_ai_demo" / "vep_options.json"   # the demo's 26-option KB
OUT = HERE / "vep_options_expanded.json"                  # the expanded catalogue (this dir)

# Canonical demo schema fields (the contract the existing code reads)
DEMO_FIELDS = [
    "id", "name", "cli_flag", "web_form_section", "category", "description",
    "when_to_use", "when_not_to_use", "use_case_tags", "priority_by_use_case",
    "species_restriction", "depends_on", "conflicts_with", "side_effects",
]
# Extra provenance/metadata fields we add (harmless to existing code)
META_FIELDS = ["source_type", "is_new", "web_form_subsection", "web_default", "provenance"]
USE_CASES = ["rare_disease_germline", "somatic_cancer", "regulatory_noncoding",
             "population_genetics", "structural_variants", "non_human", "quick_lookup"]
SECTIONS = ["identifiers", "variants_frequency_data", "additional_annotations",
            "predictions", "filters", "advanced"]


def load_result(path):
    """Load the workflow output, unwrapping the optional {"result": ...} envelope.

    The result may itself be a JSON string (double-encoded), so decode again if so.
    """
    top = json.load(open(path))
    r = top.get("result", top)
    if isinstance(r, str):
        r = json.loads(r)
    return r


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: assemble_catalogue.py <workflow_output.json>")
    r = load_result(sys.argv[1])
    built = r.get("builtOptions", [])
    verdicts = {v["id"]: v for v in r.get("verifyVerdicts", []) if isinstance(v, dict) and v.get("id")}
    print(f"Loaded {len(built)} built options, {len(verdicts)} verdicts.")

    # --- Validation ---
    ids = [o["id"] for o in built]
    dup = [k for k, c in Counter(ids).items() if c > 1]
    if dup:
        print(f"  !! DUPLICATE IDS: {dup}")
    idset = set(ids)

    problems = []
    for o in built:
        for f in DEMO_FIELDS:
            if f not in o:
                problems.append(f"{o['id']}: missing field '{f}'")
        pbu = o.get("priority_by_use_case", {})
        miss = [u for u in USE_CASES if u not in pbu]
        if miss:
            problems.append(f"{o['id']}: priority_by_use_case missing {miss}")
        if o.get("web_form_section") not in SECTIONS:
            problems.append(f"{o['id']}: web_form_section '{o.get('web_form_section')}' not in 6 canonical ids")
        for ref in o.get("conflicts_with", []) + o.get("depends_on", []):
            if ref not in idset:
                problems.append(f"{o['id']}: references unknown id '{ref}'")

    # --- Adversarial verifier flags ---
    flagged = {oid: v for oid, v in verdicts.items() if v.get("factual_ok") is False}
    major = {oid: v for oid, v in flagged.items() if v.get("severity") == "major"}

    # --- Emit clean catalogue (demo fields first, then metadata) ---
    clean = []
    for o in built:
        entry = {f: o.get(f) for f in DEMO_FIELDS}
        for f in META_FIELDS:
            if f in o:
                entry[f] = o[f]
        clean.append(entry)
    json.dump(clean, open(OUT, "w"), indent=2)

    # --- Report ---
    print(f"\nBy section: {dict(Counter(o['web_form_section'] for o in built))}")
    print(f"By source_type: {dict(Counter(o.get('source_type') for o in built))}")
    print(f"New (is_new): {sum(1 for o in built if o.get('is_new'))}")
    print(f"\nSCHEMA PROBLEMS ({len(problems)}):")
    for p in problems:
        print("  -", p)
    print(f"\nADVERSARIAL FLAGS: {len(flagged)} flagged, {len(major)} major")
    for oid, v in flagged.items():
        print(f"  [{v.get('severity')}] {oid}: {'; '.join(v.get('issues', []))[:240]}")
        if v.get("corrected_fields"):
            print(f"       corrected: {json.dumps(v['corrected_fields'])[:240]}")
    print(f"\nWrote {len(clean)} options -> {OUT}")


if __name__ == "__main__":
    main()
