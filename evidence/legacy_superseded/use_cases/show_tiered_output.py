#!/usr/bin/env python3
"""Prototype: render the 12-query check results with the Core/Add-ons output split.

Display-only demo of vep_assistant.tier_options / format_tiered_config — reuses the pipeline
functions (single source of truth), no model re-run. Reads the saved enabled sets from
evidence/local_runs/results/user_query_check.json.

  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json python evidence/legacy_superseded/use_cases/show_tiered_output.py
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va  # noqa: E402

cat = json.load(open(os.environ.get("VEP_OPTIONS_FILE", ROOT / "vep_ai_demo" / "vep_options.json")))
rep = json.load(open(ROOT / "evidence" / "local_runs" / "results" / "user_query_check.json"))

tot_core = tot_add = 0
for row in rep["rows"]:
    tiers = va.tier_options(row["enabled"], cat)
    tot_core += len(tiers["core"]); tot_add += len(tiers["addons"])
    print("\n" + "=" * 78)
    print(f"Q{row['i']}: {row['query'][:72]}")
    print("-" * 78)
    print(va.format_tiered_config(row["enabled"], cat))

n = len(rep["rows"])
print("\n" + "=" * 78)
print(f"SUMMARY over {n} queries: mean core={tot_core/n:.1f}  mean add-ons={tot_add/n:.1f}  "
      f"({tot_add/(tot_core+tot_add)*100:.0f}% of enabled options are add-ons)")
