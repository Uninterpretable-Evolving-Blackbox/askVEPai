#!/usr/bin/env python3
"""Re-resolve the stored review rows against TODAY's priority table. No model, seconds.

WHY. Stages 1-3 (sample a factor tuple, resolve it, have the teacher write a query) ran in August.
The queries and their factor labels are still valid -- they describe a scenario, not a configuration --
but the `recommended_options` stored beside them are whatever the table said in August. Measured on
2026-09-20: all 31 rows differ from the live table, 184 option-instances in total (canonical and
Mastermind arriving, check_existing and the frequency filter leaving, and so on). Anything that reads
those rows is therefore reporting August: `check_round2_ready.py` says "canonical missing on rows 1,
7, 10" when canonical is recommended on every tuple today.

This re-runs ONLY stage 2 (`resolve_config`) on the tuples the rows already carry, and writes the new
sets back. Deliberately NOT a regeneration: no new scenarios, no teacher call, the ids, the queries and
the screening records are untouched, so the evaluation set stays the same set.

`justification` is left as written and is now partly stale -- it names options the table has since
moved. Rewriting it needs the teacher, which is a separate decision.

  python3 data/build/refresh_resolved.py            # dry run: what would change
  python3 data/build/refresh_resolved.py --write    # rewrite iced.json (backup kept)
"""
import argparse
import json
import shutil
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))   # genlib and the pipeline stages
import genlib
import resolve_config

HERE = Path(__file__).resolve().parent
ICED = HERE.parent / "iced.json"


def resolve(row, ctx):
    """The row's own factor tuple through stage 2, returning (recommended, add-ons)."""
    out = resolve_config.resolve_row(dict(row["factor_labels"]), *ctx)
    return out["recommended_options"], out.get("add_on_options", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--iced", default=str(ICED))
    a = ap.parse_args()

    path = Path(a.iced)
    rows = json.loads(path.read_text())
    ctx = (genlib.load_catalogue(), genlib.load_priority_by_factor(), genlib.load_factors(),
           genlib.load_va(), genlib.load_corpus())

    changed, total_delta = 0, 0
    for row in rows:
        rec, add = resolve(row, ctx)
        before = {k for k, v in row["recommended_options"].items() if v.get("enabled")}
        after = {k for k, v in rec.items() if v.get("enabled")}
        if before != after:
            changed += 1
            total_delta += len(before ^ after)
            print(f"  {row['id'][:52]:54} +{sorted(after - before)} -{sorted(before - after)}")
        row["recommended_options"], row["add_on_options"] = rec, add
        row.setdefault("_refreshed", []).append(str(date.today()))

    print(f"\n{changed} of {len(rows)} rows change, {total_delta} option-instances")
    if not a.write:
        print("dry run; pass --write to update the file")
        return
    # Never overwrite an existing backup: running this twice in a day would otherwise replace the
    # pre-refresh copy with an already-refreshed one, and the original is the thing worth keeping.
    backup = path.with_name(f"{path.stem}_pre_refresh_{date.today()}{path.suffix}")
    n = 2
    while backup.exists():
        backup = path.with_name(f"{path.stem}_pre_refresh_{date.today()}_{n}{path.suffix}")
        n += 1
    shutil.copy2(path, backup)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {path.name}; previous version kept as {backup.name}")


if __name__ == "__main__":
    main()
