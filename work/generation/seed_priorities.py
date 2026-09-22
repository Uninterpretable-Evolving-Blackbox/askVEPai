#!/usr/bin/env python3
"""Sync the engine's fallback copies of the three data files from the canonical work/ copies.

THE TABLE IS AUTHORED, NOT BUILT (2026-09-22). `priority_by_factor.json` in generation_config/ is the
single source; nothing derives it, so there is nothing to seed. What this script still does is the one
job left from its old role: the engine reads the work/ copies whenever they are present, and keeps
byte-identical fallbacks under vep_ai_demo/ for a standalone publish. Nothing else syncs them, so
without this a standalone publish ships stale data.

  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/generation/seed_priorities.py
"""
import genlib


def main():
    pairs = [(genlib.CONFIG_DIR / "priority_by_factor.json", genlib.DEMO / "priority_by_factor.json"),
             (genlib.Path(genlib.os.environ["VEP_OPTIONS_FILE"]), genlib.DEMO / "vep_options.json"),
             (genlib.CONFIG_DIR / "factors.json", genlib.DEMO / "factors.json")]
    written = 0
    for src, dst in pairs:
        body = src.read_text()
        if not dst.exists() or dst.read_text() != body:
            dst.write_text(body); written += 1
            print(f"Wrote {dst.relative_to(genlib.ROOT)}  <-  {src.relative_to(genlib.ROOT)}")
    if not written:
        print("Up to date: the three vep_ai_demo/ fallback copies match work/.")


if __name__ == "__main__":
    main()
