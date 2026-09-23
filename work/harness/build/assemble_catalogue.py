#!/usr/bin/env python3
"""Assemble + validate the expanded VEP option catalogue from the workflow output.

Reads the catalogue-build workflow result (builtOptions + verifyVerdicts), enforces
schema compatibility with the demo's vep_options.json, surfaces adversarial-verifier
flags, and writes the engine's vep_options.json + a validation summary.

Usage: python assemble_catalogue.py <workflow_output.json>
"""
import json
import sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent                    # GSoC_WORK/work/harness/build/
DEMO = HERE.parents[2] / "vep_ai_demo" / "vep_options.json"   # the engine's catalogue
OUT = DEMO                                                 # the engine's catalogue, the source copy

# Canonical demo schema fields (the contract the existing code reads)
DEMO_FIELDS = [
    "id", "name", "cli_flag", "web_form_section", "category", "description",
    "species", "assemblies", "depends_on", "conflicts_with",
]
# Extra provenance/metadata fields we add (harmless to existing code)
META_FIELDS = ["web_form_subsection", "provenance"]
# Fields added to the catalogue after this script was written. Listing them here is not enough on its
# own -- KEEP_UNKNOWN below carries anything else across too -- but naming them documents what the
# engine now reads: the form's defaults and the CADD annotation-file values.
LATER_FIELDS = ["web_default_on", "web_default_value", "web_form_values", "deprecated"]
# Removed from the catalogue 2026-09-22: no reader in any of the three trees. `side_effects` is
# superseded by Ensembl's own Output fields / Incompatible with columns (research/output_effects_dossier.md);
# `use_case_tags` belonged to the use-case labels retired 2026-09-13. `web_default` and its `_basis` were
# the prose `web_default_on` was first read from; all 68 on/off defaults now check against InputForm.pm
# and the release-116 plugin_config.txt (research/form_defaults_check_2026-09-22.md). The priority
# blocks moved to priority_by_factor.json. `when_to_use` / `when_not_to_use` were our advice prose with no
# Ensembl equivalent; `name` and `description` are now Ensembl's own words (source in `provenance`).
# `source_type` repeated `cli_flag`; `vep_assistant.option_source()` reads it off the flag.
# `species_restriction` (prose) and `requires_species_data` (a pointer to a second copy of the species
# list) repeated `species`, which now holds Ensembl's list for every option.
# Dropped here so a rebuild from an older workflow output does not carry them back in.
RETIRED_FIELDS = ["use_case_tags", "side_effects", "is_new", "size_dependent_value",
                  "_category_before_2026-09-15", "web_default", "_web_default_basis",
                  "_web_form_values_basis", "priority_by_factor", "when_to_use", "when_not_to_use", "source_type",
                  "species_restriction", "requires_species_data"]
USE_CASES = ["rare_disease_germline", "somatic_cancer", "regulatory_noncoding",
             "population_genetics", "structural_variants", "non_human", "quick_lookup"]
# "input" is the block at the top of the form, above every CONFIG_SECTIONS panel. One control lives
# there -- `core_type`, "Transcript database to use" -- read off the live release-116 page on
# 2026-09-15 (research/ensembl_docs_116/form_layout_live.json).
SECTIONS = ["input", "identifiers", "variants_frequency_data", "additional_annotations",
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
        # priority_by_use_case retired 2026-09-13 (frozen copy in harness/legacy/); no longer required.
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
        # Anything the existing catalogue carries and this script does not know about is kept as it
        # is. Before this, a rebuild wrote only the fields listed above and dropped the rest.
        for f in (LATER_FIELDS + [k for k in o
                                  if k not in DEMO_FIELDS + META_FIELDS + LATER_FIELDS + RETIRED_FIELDS]):
            if f in o:
                entry[f] = o[f]
        for f in META_FIELDS:
            if f in o:
                entry[f] = o[f]
        clean.append(entry)
    json.dump(clean, open(OUT, "w"), indent=2)

    # --- Report ---
    print(f"\nBy section: {dict(Counter(o['web_form_section'] for o in built))}")
    print(f"By flag kind: {dict(Counter(('plugin' if (o.get('cli_flag') or '').startswith('--plugin') else 'custom' if (o.get('cli_flag') or '').startswith('--custom') else 'native') for o in built))}")
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
