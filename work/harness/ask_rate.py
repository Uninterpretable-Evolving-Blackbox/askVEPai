#!/usr/bin/env python3
"""How often the tool interrupts, measured — the ask rule's firing rate under each candidate policy.

Every ask-rate figure in `reprompting_proposal.md` comes from here. The point is comparability: the
arms differ only in the flags below, so a difference in the table is a difference in the rule and
nothing else.

No model, no GPU, seconds. The classifier has ALREADY been run on every ablated query and its reading
recorded as `read_after`, so this replays only the decision half of the path, and replays it exactly
rather than approximating it by blanking the true tuple.

WHAT THIS MEASURES is the gate, given a gap the ablation put there on purpose. It is NOT a rate over
real traffic. Eight configuration questions is too few to carry one (`reprompting_proposal.md` §7),
and claiming otherwise would be the overclaim the withdrawn Biostars set is withdrawn for.

  python work/harness/ask_rate.py                       # every arm, one table
  python work/harness/ask_rate.py --arm shipped         # just the policy the engine runs
  python work/harness/ask_rate.py --by-row --arm shipped
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

ABLATIONS = ROOT / "work" / "preliminary_examples" / "ablated_queries.json"

BOTH_SIZES = ["small", "structural-CNV"]

_REAL_ASSEMBLY_QUESTION = va.assembly_question

# Copied rather than referenced, so an arm cannot mutate the real policy out from under the engine.
#
# Three guesses, with the factor that has no safe value asked about instead.
GUESS_GOAL_ASSUMPTIONS = {
    "region_focus": ["coding", "regulatory-noncoding"],
    "origin": "somatic",
    "analysis_goal": ["basic-consequence"],
    "variant_size_class": None,
}

# What the engine runs: `variant_size_class` is guessable because it is multi-select, and
# `analysis_goal` is asked because it meets neither condition for guessing.
SHIPPED_ASSUMPTIONS = {
    "region_focus": ["coding", "regulatory-noncoding"],
    "origin": "somatic",
    "analysis_goal": None,
    "variant_size_class": None,          # supplied by the `multi` flag; see apply_arm
}

# Guess only where the guess is free, ask about everything else. `region_focus` is the only factor that
# loses nothing on any ablation, so it is the only survivor.
MINIMAL_ASSUMPTIONS = {
    "region_focus": ["coding", "regulatory-noncoding"],
    "origin": None,
    "analysis_goal": None,
    "variant_size_class": None,
}

# The bar is the option set whose movement justifies an interruption. WIDE is the bucket the user is
# shown; NARROW is the internal must-have tier. The engine uses WIDE — see ASK_BAR_PRIORITIES.
NARROW = ("critical",)
WIDE = ("critical", "recommended")

ASSUME_SETS = {"guess-goal": GUESS_GOAL_ASSUMPTIONS, "shipped": SHIPPED_ASSUMPTIONS,
               "minimal": MINIMAL_ASSUMPTIONS}

ARMS = {
    "single-select": dict(assume="guess-goal", multi=False, bar=NARROW, assembly=False,
                          note="size single-select and asked, goal guessed, no assembly question"),
    "shipped": dict(assume="shipped", multi=True, bar=WIDE, assembly=True,
                    note="what the engine does"),
    "shipped, no assembly": dict(assume="shipped", multi=True, bar=WIDE, assembly=False,
                                 note="isolates how much of the shipped rate is the assembly question"),
    "shipped, narrow bar": dict(assume="shipped", multi=True, bar=NARROW, assembly=True,
                                note="bar on the internal must-have tier instead of the visible bucket"),
    "goal guessed": dict(assume="guess-goal", multi=True, bar=WIDE, assembly=True,
                         note="shipped, but guessing analysis_goal — prices the cost of asking it"),
    "ask-all": dict(assume="minimal", multi=True, bar=WIDE, assembly=True,
                    note="guess only where free, ask about the rest"),
    "ask-all, narrow bar": dict(assume="minimal", multi=True, bar=NARROW, assembly=True,
                                note="where the two bars diverge: the narrow one drops the origin questions"),
}


def load_options():
    with open(os.environ["VEP_OPTIONS_FILE"]) as f:
        return json.load(f)


def apply_arm(arm):
    """Set the module globals the rule reads. Same two edits the real change would make, plus the bar.

    Monkeypatched rather than written to disk, so measuring a policy cannot leave the repository in a
    half-changed state."""
    multi = tuple(f for f in va.MULTI_FACTORS if f != "variant_size_class")
    if arm["multi"]:
        multi = multi + ("variant_size_class",)
    va.MULTI_FACTORS = multi

    policy = {}
    for f, assume in ASSUME_SETS[arm["assume"]].items():
        if f == "variant_size_class" and arm["multi"]:
            # Multi-select is what MAKES a guess available here: "both" is only expressible once the
            # factor can hold two values, and it is the value with 0.00 options lost across the 29
            # ablations. Under single-select there is no safe value, which is why it is None above.
            assume = list(BOTH_SIZES)
        policy[f] = {"assume": assume, "why": ""}
    va.UNDERSPECIFIED_POLICY = policy
    va.ASK_BAR_PRIORITIES = tuple(arm["bar"])
    # Assembly is not a factor, so an arm has to be able to switch its question off independently —
    # that is what lets `single-select` reproduce the 16 it exists to anchor.
    va.assembly_question = (_REAL_ASSEMBLY_QUESTION if arm["assembly"]
                            else (lambda *a, **k: []))


def coerce(rec):
    """Re-shape a recorded classifier reading to the arm's schema.

    `read_after` holds `variant_size_class` as a string. Under a multi arm the same fact has to arrive
    as a list, or `clarification_plan` reads a populated field as blank and asks about something the
    user already answered. The arms must differ in the POLICY and nowhere else, so this conversion is
    load-bearing rather than cosmetic."""
    out = {}
    for f in va.FACTOR_VALUES:
        v = rec.get(f)
        if f in va.MULTI_FACTORS:
            if isinstance(v, list):
                out[f] = list(v)
            else:
                out[f] = [] if v in (None, "", "unstated") else [v]
        else:
            if isinstance(v, list):
                out[f] = v[0] if v else "unstated"
            else:
                out[f] = "unstated" if v in (None, "") else v
    return out


def run_arm(arm, cases, opts):
    saved = (va.MULTI_FACTORS, va.UNDERSPECIFIED_POLICY, va.ASK_BAR_PRIORITIES,
             va.assembly_question)
    try:
        apply_arm(arm)
        per_row, asked = [], Counter()
        interrupted = 0
        for c in cases:
            rec = coerce(c["read_after"])
            # The ablated TEXT is passed so `infer_assembly` gets its chance, exactly as it would in a
            # real run. It never fires here — none of the 31 generated queries names a build — but
            # hard-coding that assumption into the harness would hide it if the generator ever changed.
            _, _, questions = va.clarification_plan(rec, opts, c.get("ablated"))
            names = [f for f, _, _ in questions]
            for f in names:
                asked[f] += 1
            if names:
                interrupted += 1
            per_row.append((c["row"], c["target"], names))
        return {"questions": sum(asked.values()), "interrupted": interrupted,
                "by_factor": asked, "rows": per_row}
    finally:
        (va.MULTI_FACTORS, va.UNDERSPECIFIED_POLICY, va.ASK_BAR_PRIORITIES,
         va.assembly_question) = saved


def check_shipped_arm_matches_repo():
    """The `shipped` arm claims to be what the repository does. Verify it instead of trusting it.

    Every other number here is a comparison AGAINST that arm, so if it drifts from factors.json the
    whole table quietly becomes fiction. Cheap to check, and the failure it prevents is the expensive
    kind: a policy argued from a baseline nobody is running."""
    arm = ARMS["shipped"]
    want_multi = "variant_size_class" in va.MULTI_FACTORS
    if want_multi != arm["multi"]:
        return (f"factors.json has variant_size_class multi={want_multi}, "
                f"the `shipped` arm assumes multi={arm['multi']}")
    for f, assume in SHIPPED_ASSUMPTIONS.items():
        live = va.UNDERSPECIFIED_POLICY.get(f, {}).get("assume")
        want = list(BOTH_SIZES) if (f == "variant_size_class" and arm["multi"]) else assume
        if (sorted(live) if isinstance(live, list) else live) != (
                sorted(want) if isinstance(want, list) else want):
            return f"UNDERSPECIFIED_POLICY[{f}].assume is {live!r}, the arm assumes {want!r}"
    if tuple(va.ASK_BAR_PRIORITIES) != tuple(arm["bar"]):
        return (f"ASK_BAR_PRIORITIES is {va.ASK_BAR_PRIORITIES}, "
                f"the `shipped` arm assumes {arm['bar']}")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS), help="one arm instead of the whole table")
    ap.add_argument("--by-row", action="store_true", help="list every case that raises a question")
    ap.add_argument("--set", dest="set_path", default=str(ABLATIONS),
                    help="which ablation set to score. Defaults to the published one; point it at a "
                         "re-run to see what a fresh build of the ablations does to the rate.")
    a = ap.parse_args()

    drift = check_shipped_arm_matches_repo()
    if drift:
        sys.exit(f"ask_rate.py is out of date with the engine:\n  {drift}\n"
                 "Update ARMS['shipped'] (and the arm notes) before quoting any number here.")

    with open(a.set_path) as f:
        cases = [c for c in json.load(f) if c.get("pure")]
    opts = load_options()
    n = len(cases)

    names = [a.arm] if a.arm else list(ARMS)
    print(f"\nask rate over {n} clean ablations from {Path(a.set_path).name}"
          f"  (the gate only; no model is run)\n")
    print(f"  {'arm':<18} {'questions':>10} {'queries asked':>14}   factors")
    print(f"  {'-' * 18} {'-' * 10:>10} {'-' * 14:>14}   {'-' * 30}")
    results = {}
    for name in names:
        r = run_arm(ARMS[name], cases, opts)
        results[name] = r
        by = ", ".join(f"{f} {c}" for f, c in r["by_factor"].most_common()) or "—"
        print(f"  {name:<18} {r['questions']:>10} {r['interrupted']:>10}/{n}   {by}")
    print()
    for name in names:
        print(f"  {name:<18} {ARMS[name]['note']}")

    if a.by_row:
        for name in names:
            print(f"\n  {name} — cases raising a question:")
            hits = [(row, tgt, q) for row, tgt, q in results[name]["rows"] if q]
            for row, tgt, q in hits:
                print(f"    row {row:>2}  deleted={tgt:<20} asks {', '.join(q)}")
            if not hits:
                print("    none")
    print()


if __name__ == "__main__":
    main()
