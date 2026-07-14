#!/usr/bin/env python3
"""Aggregate evaluation_results_*.md summary tables into one cross-model view.

Pulls the overall-Summary 'Enable F1' and 'Enable F1 (priority-weighted)' rows
from each report and prints the all-examples-vs-keyword delta per model — the
quantity that tests whether selective retrieval catches up as the model grows.

Usage: python aggregate_results.py [results_dir]
"""
import re
import sys
from pathlib import Path

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "results"
# rough size ordering for display
ORDER = ["qwen2.5_3b", "gemma4_e4b", "qwen2.5_7b", "gemma4_12b", "gemma4_26b", "qwen2.5_14b"]


def pct(s):
    """Pull the first (possibly negative) integer percentage out of a cell string."""
    m = re.search(r"(-?\d+)%", s)
    return int(m.group(1)) if m else None


def summary_row(text, label):
    """Return the cells of the `| label | ... |` row from the report's Summary table.

    Scoped to the text after '## Summary' so a same-named row in the per-query
    section can't be picked up by mistake. Returns None if the row is absent.
    """
    # take rows from the overall "## Summary" section only
    summ = text.split("## Summary", 1)[-1]
    for line in summ.splitlines():
        if line.strip().startswith(f"| {label} "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            return cells  # [label, bare, keyword, all, semantic, deltas...]
    return None


def main():
    # One row per model report; sort by rough size order so the table reads
    # small -> large and the all-kw delta trend is visible down the column.
    reports = sorted(RES.glob("evaluation_results_*.md"))
    rows = []
    for r in reports:
        name = r.stem.replace("evaluation_results_", "")
        text = r.read_text()
        f1 = summary_row(text, "Enable F1")
        wf1 = summary_row(text, "Enable F1 (priority-weighted)")
        if not f1:
            continue
        bare, kw, allx, sem = [pct(f1[i]) for i in range(1, 5)]
        rows.append({"model": name, "bare": bare, "keyword": kw, "all": allx, "semantic": sem,
                     "all_minus_kw": (allx - kw) if (allx is not None and kw is not None) else None,
                     "wf1_all": pct(wf1[3]) if wf1 else None})
    rows.sort(key=lambda x: ORDER.index(x["model"]) if x["model"] in ORDER else 99)

    print(f"Cross-model Enable F1 (real system: 58 options, 20 examples, LOO, N=3)\n")
    print(f"{'model':14s} {'bare':>5s} {'keyword':>8s} {'all-ex':>7s} {'semantic':>9s} {'all−kw':>7s}")
    print("-" * 56)
    for r in rows:
        print(f"{r['model']:14s} {r['bare']:>4}% {r['keyword']:>7}% {r['all']:>6}% "
              f"{r['semantic']:>8}% {r['all_minus_kw']:>+6}%")
    print("\nall−kw shrinking (or going negative) as models grow = selective retrieval")
    print("catches up with all-examples → the 'all-examples only wins at small scale' thesis.")


if __name__ == "__main__":
    main()
