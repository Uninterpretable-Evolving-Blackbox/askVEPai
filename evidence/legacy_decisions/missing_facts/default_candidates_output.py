#!/usr/bin/env python3
"""Which default is SAFER, priced on real VEP output — every candidate value, not just the fallback.

WHY THIS SHAPE. `defaults_evidence.py` already argues each guessed value by comparing it against the
alternatives on OPTION counts ("guessing somatic harms 0 of 16 germline rows; silence harms 6 of 15
somatic rows"). That is the right argument and the wrong axis: an option count cannot tell a lost
column from a deleted variant, and the whole reason `origin` was settled by a danger audit is that
the two are not comparable.

This runs the same comparison through real VEP. For a factor, for every candidate value we might
guess, against every value the user might actually have had:

    guess = what the tool assumes when the query does not say
    truth = what the user's data actually is
    cost  = what the user's OUTPUT loses, by identity: named columns, and rows keyed by transcript id

A default is safer than another when its worst cell is less bad -- and "less bad" is ordered:
deleted rows > lost columns > gained columns. That ordering is the point: a gained column is
ignorable, a deleted row is a finding the user never sees.

Diagonal cells (guess == truth) are run as controls and must come back empty.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/legacy_decisions/missing_facts/default_candidates_output.py --factor region_focus
"""
import argparse, itertools, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "output_effects"))   # run_vep_rest, run_vep_ab
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
from run_vep_rest import REST_PARAM, COLUMN_VERDICT, PANEL, SPECIES_PANEL   # noqa: E402
import run_vep_ab as ab                                                 # noqa: E402

# Candidate values per factor. `variant_size_class` is deliberately absent: a both-size scenario
# emits TWO VEP runs, not one merged configuration, so a configuration diff cannot express its cost.
CANDIDATES = {
    "region_focus":  [["coding"], ["regulatory-noncoding"], ["coding", "regulatory-noncoding"]],
    "analysis_goal": [["basic-consequence"], ["clinical-interpretation"], ["population-frequency"]],
    "species":       ["human", "non-human"],
    "origin":        ["germline", "somatic"],
}
BASE = {"species": "human", "origin": "germline", "variant_size_class": ["small"],
        "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}


def label(v):
    return "+".join(v) if isinstance(v, list) else str(v)


def cost(species, panel, params_t, params_g):
    """Per variant class: columns lost/gained by identity, and rows lost/gained by transcript id."""
    out = {}
    for cls, entry in panel.items():
        endpoint, ident, _what = entry
        pa, ea = ab.fetch(species, endpoint, ident, params_t)
        time.sleep(0.35)
        pb, eb = ab.fetch(species, endpoint, ident, params_g)
        time.sleep(0.35)
        if ea or eb:
            out[cls] = {"error": ea or eb}
            continue
        ka, kb = ab.populated_keys(pa), ab.populated_keys(pb)
        ia, ib = ab.row_ids(pa), ab.row_ids(pb)
        rows_lost = sorted(set(ia["transcript_consequences"]) - set(ib["transcript_consequences"]))
        rows_gain = sorted(set(ib["transcript_consequences"]) - set(ia["transcript_consequences"]))
        out[cls] = {"columns_lost": sorted(set(ka) - set(kb)),
                    "columns_gained": sorted(set(kb) - set(ka)),
                    "rows_lost": rows_lost, "rows_gained": rows_gain}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", required=True, choices=sorted(CANDIDATES))
    ap.add_argument("--species", default="human")
    ap.add_argument("--json")
    args = ap.parse_args()
    catalogue, _ = va.load_knowledge_base()
    panel = SPECIES_PANEL.get(args.species, PANEL)
    vals = CANDIDATES[args.factor]
    grid = {}

    for truth, guess in itertools.product(vals, vals):
        ft_t = {**BASE, args.factor: truth}
        ft_g = {**BASE, args.factor: guess}
        if args.factor == "species":
            ft_t, ft_g = {**ft_t, "species": truth}, {**ft_g, "species": guess}
        rec_t = [o for o, (e, _p, _g) in (va.resolve_for_query(ft_t, catalogue) or {}).items() if e]
        rec_g = [o for o, (e, _p, _g) in (va.resolve_for_query(ft_g, catalogue) or {}).items() if e]
        pt, *_ = ab.params_for(rec_t)
        pg, *_ = ab.params_for(rec_g)
        c = cost(args.species, panel, pt, pg)
        cl = sum(len(v.get("columns_lost", [])) for v in c.values())
        cg = sum(len(v.get("columns_gained", [])) for v in c.values())
        rl = sum(len(v.get("rows_lost", [])) for v in c.values())
        rg = sum(len(v.get("rows_gained", [])) for v in c.values())
        grid[f"{label(truth)}|{label(guess)}"] = {
            "truth": truth, "guess": guess, "n_opts_truth": len(rec_t), "n_opts_guess": len(rec_g),
            "columns_lost": cl, "columns_gained": cg, "rows_lost": rl, "rows_gained": rg,
            "per_class": c}
        tag = "  <- control, must be empty" if label(truth) == label(guess) else ""
        print(f"  truth={label(truth):28s} guess={label(guess):28s} "
              f"cols -{cl:<3d} +{cg:<3d}  rows -{rl:<3d} +{rg:<3d}{tag}", flush=True)

    print(f"\n=== {args.factor}: which value is safest to guess ===\n")
    print(f"  {'guess':30s} {'worst cols lost':>16s} {'worst rows lost':>16s}")
    for g in vals:
        cells = [v for k, v in grid.items() if label(v["guess"]) == label(g)
                 and label(v["truth"]) != label(g)]
        print(f"  {label(g):30s} {max(c['columns_lost'] for c in cells):16d} "
              f"{max(c['rows_lost'] for c in cells):16d}")
    print("\n  Ordering: deleted rows > lost columns > gained columns. A gained column is ignorable;")
    print("  a deleted row is a finding the user never sees.")
    if args.json:
        Path(args.json).write_text(json.dumps(grid, indent=1))
        print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
