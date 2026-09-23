#!/usr/bin/env python3
"""Mirror the engine's data files into work/, for the scripts that still read the work/ paths.

The engine (vep_ai_demo/) holds the source copies and reads only those. The work/ copies exist for
older harness scripts that point VEP_OPTIONS_FILE at work/vep_options_expanded.json. Run after any edit
to an engine data file:

  python3 work/generation/seed_priorities.py
"""
import genlib


def main():
    pairs = [(genlib.DEMO / "priority_by_factor.json", genlib.CONFIG_DIR / "priority_by_factor.json"),
             (genlib.DEMO / "vep_options.json", genlib.WORK / "vep_options_expanded.json"),
             (genlib.DEMO / "factors.json", genlib.CONFIG_DIR / "factors.json"),
             (genlib.DEMO / "species_index.json", genlib.CONFIG_DIR / "species_index.json")]
    written = 0
    for src, dst in pairs:
        body = src.read_text()
        if not dst.exists() or dst.read_text() != body:
            dst.write_text(body); written += 1
            print(f"Wrote {dst.relative_to(genlib.ROOT)}  <-  {src.relative_to(genlib.ROOT)}")
    if not written:
        print("Up to date: the work/ copies match the engine's.")


if __name__ == "__main__":
    main()
