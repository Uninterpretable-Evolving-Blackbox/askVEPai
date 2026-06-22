#!/usr/bin/env python3
"""Validate the bootstrap examples against the expanded catalogue + constraint checker.

A "confident" example must: reference only real catalogue ids, and pass the
deterministic checker with ZERO species/conflict violations and dependencies
already satisfied (no auto-changes). Run: python validate_examples.py
"""
import json
import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE.parent
# Load the demo's checker by path (not on sys.path) so we reuse the exact same
# check_and_fix_violations / infer_species the inference pipeline runs.
spec = importlib.util.spec_from_file_location(
    "vep_assistant", WORK.parent / "vep_ai_demo" / "vep_assistant.py")
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)

# Honour the same env vars as the rest of the harness; default to the bootstrap set.
options_path = Path(os.environ.get("VEP_OPTIONS_FILE", WORK / "vep_options_expanded.json"))
examples_path = Path(os.environ.get("VEP_EXAMPLES_FILE", HERE / "bootstrap_examples.json"))
catalogue = json.load(open(options_path))
examples = json.load(open(examples_path))
cat_ids = {o["id"] for o in catalogue}
print(f"Validating {examples_path.name} against {options_path.name}\n")

all_ok = True
for ex in examples:
    opts = ex["recommended_options"]
    enabled = {k for k, v in opts.items() if v.get("enabled")}
    disabled = {k for k, v in opts.items() if not v.get("enabled")}
    unknown = [k for k in opts if k not in cat_ids]
    # Run the example's own recommendation through the checker. A gold example must be
    # internally clean: copies of the sets are passed since the checker mutates in place.
    viol = va.check_and_fix_violations(set(enabled), set(disabled), catalogue,
                                       examples, ex["user_query"])
    by = lambda t: [v for v in viol if v["type"] == t]
    # A species entry with no option actually changed is an INFORMATIONAL flag, not a strip:
    # for an unspecified species the checker (fail-closed, since Exp 7) emits "assuming human,
    # keeping human-only options" WITHOUT removing anything. That is correct behaviour for a
    # human analysis that doesn't name its species, so it must NOT count as a validation failure.
    species_strips = [v for v in by("species") if v.get("option_disabled") or v.get("option_enabled")]
    # "confident" = no unknown ids AND the checker made no actual correction
    ok = not unknown and not species_strips and not by("conflict") and not by("dependency")
    all_ok &= ok
    print(f"[{'PASS' if ok else 'FAIL'}] {ex['id']:30s} "
          f"species={va.infer_species(ex['user_query'])} "
          f"en={len(enabled)} dis={len(disabled)}")
    if unknown:
        print(f"        unknown ids: {unknown}")
    if species_strips:
        print(f"        species: {[v.get('option_disabled') or v.get('option_enabled') for v in species_strips]}")
    for t in ("conflict", "dependency"):
        if by(t):
            print(f"        {t}: {[v.get('option_disabled') or v.get('option_enabled') for v in by(t)]}")

print("\n" + ("ALL PASS ✓" if all_ok else "FAILURES — fix before experimenting"))
