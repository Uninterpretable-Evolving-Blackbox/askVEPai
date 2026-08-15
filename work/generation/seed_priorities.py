#!/usr/bin/env python3
"""Stage 0 — dump the importance table to disk, for reading, diffing, or handing to a reviewer.

THIS IS NO LONGER A REQUIRED BUILD STEP. The table is a pure function of the DRIVES spec and the option
catalogue and is now derived at load time by `vep_assistant.build_priority_table` (~0.3 ms for 58
options), so updating an option is a single edit to `vep_options_expanded.json` and nothing else.

It used to be generated into a file that four separate copies of the system then read, kept in step by
hand. Nothing noticed when they drifted: edit the catalogue, forget to regenerate, and the shipped tool
silently ran an older table than every measurement had been taken on. Deriving removes that class of bug
instead of guarding against it.

What this script is still FOR:
  * reading the table — it is 65 options x 5 factors, easier to inspect as JSON than as a spec;
  * diffing it across a catalogue or spec change;
  * producing the artifact a reviewer edits. `load_priority_by_factor` treats a file on disk as an
    OVERRIDE that beats the derivation, so a signed-off table is adopted by dropping it in.

Note the consequence of that override: while a file exists at the default path, it wins. Delete it to go
back to the derived table.

  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/generation/seed_priorities.py [--stdout]
"""
import json
import sys

import genlib

# Re-exported so anything that imported these from here still works; the definitions live in the engine.
DRIVES = genlib.DRIVES
BASELINE_CRITICAL = genlib.BASELINE_CRITICAL
BASELINE_RECOMMENDED = genlib.BASELINE_RECOMMENDED
PREDICTOR_DISTINCT = genlib.PREDICTOR_DISTINCT
PREDICTOR_DERIVATIVE = genlib.PREDICTOR_DERIVATIVE
MISSENSE_ONLY = genlib.MISSENSE_ONLY
SPLICE_CORE = genlib.SPLICE_CORE
SPLICE_ADDON = genlib.SPLICE_ADDON
REGION_GATE_NONCODING = genlib.REGION_GATE_NONCODING
SIZE_GATE_SOURCE = genlib.SIZE_GATE_SOURCE
RANK = genlib.RANK


def main():
    catalogue = genlib.load_catalogue()
    table = genlib.build_priority_table(catalogue)
    text = json.dumps(table, indent=2)

    if "--stdout" in sys.argv:
        print(text)
        return

    # Every location that reads a table, so a dump cannot leave one copy behind the others. The engine
    # would derive an identical table for any of these; writing them keeps the on-disk artifacts honest.
    # The engine reads the canonical work/ copies whenever they are present, so these writes are not
    # what makes the tool correct — they refresh the demo-local FALLBACKS, which are only read when
    # vep_ai_demo/ is published standalone without work/ beside it. Nothing else syncs them, so without
    # this a standalone publish ships a stale catalogue.
    targets = [(genlib.CONFIG_DIR / "priority_by_factor.json", text),
               (genlib.DEMO / "priority_by_factor.json", text),
               (genlib.DEMO / "vep_options.json", genlib.Path(genlib.os.environ["VEP_OPTIONS_FILE"]).read_text()),
               (genlib.DEMO / "factors.json", (genlib.CONFIG_DIR / "factors.json").read_text())]
    written = [p for p, body in targets if not p.exists() or p.read_text() != body]
    for p, body in targets:
        if p in written:
            p.write_text(body)
    targets = [p for p, _ in targets]

    priced = sum(1 for e in table["priorities"].values() if e)
    unpriced = sorted(oid for oid, e in table["priorities"].items() if not e)
    for p in written:
        print(f"Wrote {p.relative_to(genlib.ROOT)}")
    if not written:
        print(f"Up to date: {targets[0].relative_to(genlib.ROOT)} (+1 copy, no change)")
    print(f"  {len(table['priorities'])} options; {priced} carry >=1 factor priority.")
    print(f"  {len(unpriced)} intentionally unpriced (can be listed, never auto-recommended): "
          f"{', '.join(unpriced)}")
    print("  NOTE: while these files exist they OVERRIDE the derived table. Delete them to derive.")


if __name__ == "__main__":
    main()
