#!/usr/bin/env python3
"""Price EVERY candidate default for every factor, in BOTH directions. No model, no network.

WHY THIS EXISTS. `run_vep_ab.py` diffs the configuration a STATED factor produces against the one our
CHOSEN default produces. That prices the default we already picked and nothing else, so it can say
"guessing region_focus=both costs X" but it cannot say "both is safer than coding", which is the
claim the re-prompting proposal actually makes. To compare defaults you have to run the other
direction too: what does guessing coding cost when the truth is regulatory, and what does guessing
regulatory cost when the truth is coding.

WHAT IT MEASURES. For a factor F, for every ordered pair (guess G, truth T) with G != T, over the
FULL space of the other four factors:

    lost    = options the TRUTH tuple enables and the GUESS tuple does not   (user misses annotation)
    gained  = options the GUESS tuple enables and the TRUTH tuple does not   (user gets extra)

Both are then graded on the OUTPUT axis, because an option is not a cost until it changes the file:

    ROW-DELETING  in ROW_PARAM and honoured -> removes variants or transcript rows. The only class
                  that can destroy a finding. Gaining one of these is the danger the origin default
                  was chosen on.
    REAL COLUMN   COLUMN_VERDICT HONOURED and not web_default_on -> an annotation the user would
                  otherwise not have.
    NO-OP         web_default_on (the form ships it ticked) or RETURNED_BY_DEFAULT (REST returns it
                  unasked). Recommending it changes no file; failing to recommend it removes nothing.
    UNMEASURABLE  COLUMN_VERDICT IGNORED / no verdict -> REST cannot show it. Counted separately and
                  never scored as "harmless", per run_vep_ab.py's standing caveat.

WHAT IT CANNOT DO. This is the OPTION-SET layer graded by a previously established output verdict.
It does not run VEP. Its purpose is to find the pairs whose configurations actually differ so the
REST/local A/B is run only on those, instead of on one hand-picked direction.

  python3 work/harness/exp/default_direction_sweep.py
  python3 work/harness/exp/default_direction_sweep.py --factor origin --verbose
"""
import argparse
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))

import vep_assistant as va                                              # noqa: E402
from run_vep_rest import COLUMN_VERDICT                                 # noqa: E402
from run_vep_ab import ROW_PARAM                                        # noqa: E402

# The defaults the tool ships, so the sweep can mark which direction is the live one.
SHIPPED = {"species": ("human",), "origin": ("somatic",),
           "variant_size_class": ("small", "structural-CNV"),
           "region_focus": ("coding", "regulatory-noncoding")}
ASKED = {"analysis_goal"}


def value_sets(factor):
    """Every value a factor can take. Multi factors take any non-empty subset."""
    vals = va.FACTOR_VALUES[factor]
    if factor in va.MULTI_FACTORS:
        out = []
        for r in range(1, len(vals) + 1):
            out += [tuple(c) for c in itertools.combinations(vals, r)]
        return out
    return [(v,) for v in vals]


def as_factor_value(factor, tup):
    return list(tup) if factor in va.MULTI_FACTORS else tup[0]


def grade(oid, catalogue_by_id):
    """The output class of one option. See the module docstring.

    ROW_PARAM membership decides row-affecting, NOT the REST verdict. `frequency`, `coding_only`,
    `most_severe` and `summary` are row-affecting by construction and REST merely refuses to apply
    them; grading them "unmeasurable" alongside a column option REST ignores would hide the single
    thing the origin default was chosen to avoid. They are reported as `row_blind` -- row-affecting,
    needs the local VEP install to size -- and counted as a danger, not as a null.
    """
    opt = catalogue_by_id.get(oid, {})
    row = ROW_PARAM.get(oid)
    if row:
        return "row" if row[2] == "HONOURED" else "row_blind"
    if opt.get("web_default_on") or COLUMN_VERDICT.get(oid) == "RETURNED_BY_DEFAULT":
        return "noop"
    if COLUMN_VERDICT.get(oid) == "HONOURED":
        return "column"
    return "unmeasurable"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", help="only this factor")
    ap.add_argument("--verbose", action="store_true", help="name the options behind each number")
    ap.add_argument("--json", default=str(ROOT / "work/results/default_direction_sweep.json"))
    args = ap.parse_args()

    catalogue, _ = va.load_knowledge_base()
    by_id = {o["id"]: o for o in catalogue}

    cache = {}

    def enabled_for(tuple_dict):
        key = json.dumps(tuple_dict, sort_keys=True)
        if key not in cache:
            res = va.resolve_for_query(tuple_dict, catalogue) or {}
            cache[key] = frozenset(o for o, (e, _p, _g) in res.items() if e)
        return cache[key]

    factors = [args.factor] if args.factor else list(va.FACTOR_VALUES)
    out = {"factors": {}}

    for f in factors:
        others = [g for g in va.FACTOR_VALUES if g != f]
        contexts = [dict(zip(others, combo))
                    for combo in itertools.product(*[[as_factor_value(g, v) for v in value_sets(g)]
                                                     for g in others])]
        vs = value_sets(f)
        rows = []
        for guess, truth in itertools.permutations(vs, 2):
            keys = ("row", "row_blind", "column", "noop", "unmeasurable")
            agg = {k: [] for k in keys}
            lost_agg = {k: [] for k in keys}
            n_ctx_with_row_gain = 0
            for ctx in contexts:
                tg = dict(ctx, **{f: as_factor_value(f, guess)})
                tt = dict(ctx, **{f: as_factor_value(f, truth)})
                eg, et = enabled_for(tg), enabled_for(tt)
                gained, lost = eg - et, et - eg
                got_row = False
                for oid in gained:
                    g = grade(oid, by_id)
                    agg[g].append(oid)
                    if g in ("row", "row_blind"):
                        got_row = True
                for oid in lost:
                    lost_agg[grade(oid, by_id)].append(oid)
                if got_row:
                    n_ctx_with_row_gain += 1
            rows.append({
                "guess": list(guess), "truth": list(truth), "n_contexts": len(contexts),
                "gained_row_instances": len(agg["row"]) + len(agg["row_blind"]),
                "contexts_gaining_a_row_deleter": n_ctx_with_row_gain,
                "gained_row_options": sorted(set(agg["row"])),
                "gained_row_blind_options": sorted(set(agg["row_blind"])),
                "gained_column_mean": round(len(agg["column"]) / len(contexts), 2),
                "gained_column_options": sorted(set(agg["column"])),
                "gained_noop_mean": round(len(agg["noop"]) / len(contexts), 2),
                "gained_unmeasurable_options": sorted(set(agg["unmeasurable"])),
                "lost_column_mean": round(len(lost_agg["column"]) / len(contexts), 2),
                "lost_column_options": sorted(set(lost_agg["column"])),
                "lost_row_options": sorted(set(lost_agg["row"])),
                "lost_row_blind_options": sorted(set(lost_agg["row_blind"])),
                "lost_noop_mean": round(len(lost_agg["noop"]) / len(contexts), 2),
                "lost_unmeasurable_options": sorted(set(lost_agg["unmeasurable"])),
            })
        out["factors"][f] = {"shipped_default": list(SHIPPED.get(f, ())) or None,
                             "asked_not_guessed": f in ASKED,
                             "n_contexts": len(contexts), "pairs": rows}

        mark = "ASKED, not guessed" if f in ASKED else f"shipped default: {'+'.join(SHIPPED.get(f, ())) or '-'}"
        print(f"\n=== {f}  ({len(contexts)} contexts per pair; {mark}) ===")
        print(f"{'guess':<34}{'truth':<34}{'ROWdel':>7}{'col+':>7}{'col-':>7}{'noop+':>7}{'unmeas':>7}")
        for r in sorted(rows, key=lambda r: (-r["contexts_gaining_a_row_deleter"],
                                             -r["lost_column_mean"])):
            live = " *" if list(SHIPPED.get(f, ())) == r["guess"] else "  "
            print(f"{'+'.join(r['guess']):<32}{live}{'+'.join(r['truth']):<34}"
                  f"{r['contexts_gaining_a_row_deleter']:>7}{r['gained_column_mean']:>7}"
                  f"{r['lost_column_mean']:>7}{r['gained_noop_mean']:>7}"
                  f"{len(r['gained_unmeasurable_options']):>7}")
            if args.verbose:
                for k, lbl in (("gained_row_options", "ROW-DELETING gained"),
                               ("gained_row_blind_options", "ROW-DELETING (REST-blind)"),
                               ("gained_column_options", "real columns gained"),
                               ("lost_column_options", "real columns lost"),
                               ("gained_unmeasurable_options", "unmeasurable gained")):
                    if r[k]:
                        print(f"      {lbl:<22} {', '.join(r[k])}")

    print("\n  ROWdel = contexts (of n) where GUESSING this switches on a row-deleting option.")
    print("  col+/col- = mean real columns gained / lost per context. noop+ = options the form")
    print("  already ships ticked or REST returns unasked, so they change no file either way.")
    print("  '*' marks the value the tool currently guesses.")

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1))
    print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
