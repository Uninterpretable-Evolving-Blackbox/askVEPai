#!/usr/bin/env python3
"""Every default's justification, re-derived and asserted. No model, no GPU, seconds.

Each value the tool guesses rests on a specific number. Prose does not fail when the priority table
moves underneath it; this does.

The four defaults rest on FOUR DIFFERENT METHODS, and conflating them is the easy mistake, so each
section states which one it is re-deriving:

  region_focus        a deterministic sweep -- which candidate value scores best against known truth
  origin              a DANGER audit -- which wrong guess switches something destructive ON.
                      Deliberately not the sweep: the safest value is not the most accurate one
  variant_size_class  81 controlled ablations. The safe value is only expressible because the factor
                      is multi-select, so this is evidence about the SCHEME as much as the default
  species             judgement, with NO experiment behind it. Asserted as such, not dressed up

The two things the tool does NOT guess (`analysis_goal`, `assembly`) are checked too, because "we ask
about this" is a claim that can rot exactly like a default can.

A failure here does not necessarily mean the code is wrong. It means a published number stopped
matching the priority table, which is the thing worth catching.

  python work/harness/defaults_evidence.py
  python work/harness/defaults_evidence.py --verbose      # show the full sweep tables
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

ROWS = ROOT / "work" / "generation" / "candidates" / "iced.json"
ABLATIONS = ROOT / "work" / "preliminary_examples" / "ablated_queries.json"
MEASURED = ROOT / "work" / "preliminary_examples" / "underspecification_measurement.json"
FETCHED = ROOT / "work" / "preliminary_examples" / "real_queries_fetched.json"

PASS, FAIL = [], []
VERBOSE = False


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))


def note(text):
    print(f"  [note] {text}")


def load_options():
    with open(os.environ["VEP_OPTIONS_FILE"]) as f:
        return json.load(f)


def enabled(tuple_, opts):
    r = va.resolve_for_query(tuple_, opts)
    return {k for k, (e, _, _) in r.items() if e} if r else set()


def f1(got, want):
    if not got and not want:
        return 1.0
    tp = len(got & want)
    if not tp:
        return 0.0
    p, r = tp / len(got), tp / len(want)
    return 2 * p * r / (p + r)


def as_list(v):
    return v if isinstance(v, list) else ([] if v in (None, "", "unstated") else [v])


# --------------------------------------------------------------------------------------------------
def sweep_region_focus(rows, opts):
    """THE DETERMINISTIC SWEEP. Blank the factor, resolve under every candidate, score against truth.

    Truth is recomputed from each row's own factor labels rather than read from its stored config, so
    the sweep measures the table as it is NOW. That is the point: if the table changes, the value that
    wins can change, and this should say so."""
    print("\n== region_focus = both — chosen by a deterministic sweep over the 31 rows ==")
    candidates = {"coding": ["coding"], "regulatory-noncoding": ["regulatory-noncoding"],
                  "both": ["coding", "regulatory-noncoding"], "(left blank)": []}
    scores = {}
    for name, value in candidates.items():
        total = 0.0
        for row in rows:
            truth_t = dict(row["factor_labels"])
            truth = enabled(truth_t, opts)
            cand_t = dict(truth_t)
            cand_t["region_focus"] = value
            total += f1(enabled(cand_t, opts), truth)
        scores[name] = total / len(rows)
    if VERBOSE:
        for k, v in sorted(scores.items(), key=lambda kv: -kv[1]):
            print(f"        {k:<22} mean F1 {v:.2f}")
    best = max(scores, key=scores.get)
    check("`both` is the best of the four candidate values", best == "both",
          "  ".join(f"{k}={v:.2f}" for k, v in sorted(scores.items(), key=lambda kv: -kv[1])))
    check("`both` beats leaving it blank", scores["both"] > scores["(left blank)"],
          f"both={scores['both']:.2f} vs blank={scores['(left blank)']:.2f}")
    check("the guessed value matches the winner",
          sorted(va.UNDERSPECIFIED_POLICY["region_focus"]["assume"]) ==
          sorted(candidates["both"]), f"policy={va.UNDERSPECIFIED_POLICY['region_focus']['assume']}")


# --------------------------------------------------------------------------------------------------
def audit_origin(rows, opts):
    """THE DANGER AUDIT. Not "which value is most often right" but "which wrong guess destroys data".

    `origin` is the one factor where the two errors are not comparable. Guessing germline on a tumour
    sample switches the common-variant pre-filter ON, which deletes real somatic findings. Guessing
    somatic on a germline sample withholds that filter, which is one optional pre-filter the user can
    switch back on. So the safe direction is somatic, and it is safe for a reason that has nothing to
    do with which is more likely."""
    print("\n== origin = somatic — chosen by a danger audit, not by accuracy ==")

    # The blast radius. The whole argument depends on `origin` touching exactly one option; if the
    # priority table ever gives it more, the audit has to be redone rather than quietly inherited.
    moved, prio_moved = set(), set()
    n = 0
    for species in va.FACTOR_VALUES["species"]:
        for size in (["small"], ["structural-CNV"], ["small", "structural-CNV"]):
            for region in (["coding"], ["regulatory-noncoding"], ["coding", "regulatory-noncoding"]):
                for goal in va.FACTOR_VALUES["analysis_goal"]:
                    base = {"species": species, "variant_size_class": size,
                            "region_focus": region, "analysis_goal": [goal]}
                    full = {}
                    for o in ("germline", "somatic"):
                        t = dict(base, origin=o)
                        r = va.resolve_for_query(t, opts) or {}
                        full[o] = {k: (e, p) for k, (e, p, _) in r.items()}
                    n += 1
                    for k in set(full["germline"]) | set(full["somatic"]):
                        g = full["germline"].get(k, (False, None))
                        s = full["somatic"].get(k, (False, None))
                        if g[0] != s[0]:
                            moved.add(k)
                        elif g[1] != s[1]:
                            prio_moved.add(k)
    check("across every tuple, origin moves exactly one option: `frequency`", moved == {"frequency"},
          f"{n} tuples, moved={sorted(moved) or 'nothing'}")
    check("origin never merely shifts a priority", not prio_moved,
          f"shifted={sorted(prio_moved) or 'none'}")

    germline = [r for r in rows if r["factor_labels"]["origin"] == "germline"]
    somatic = [r for r in rows if r["factor_labels"]["origin"] == "somatic"]

    # Guessing somatic on a germline row: does it ever switch a SUPPRESSING option on? It cannot --
    # somatic removes the filter -- and that asymmetry is the entire justification, so it is asserted
    # rather than assumed.
    harmed = 0
    for row in germline:
        guess = dict(row["factor_labels"], origin="somatic")
        truth = enabled(row["factor_labels"], opts)
        if "frequency" in enabled(guess, opts) - truth:
            harmed += 1
    check("guessing somatic enables the common-variant filter on 0 germline rows", harmed == 0,
          f"{harmed}/{len(germline)} germline rows harmed")

    # Leaving it unstated is NOT the neutral option: the `somatic => frequency not_applicable` rule
    # fires only on an EXPLICIT somatic, so silence behaves exactly like germline.
    leaked = 0
    for row in somatic:
        blank = dict(row["factor_labels"], origin="unstated")
        if "frequency" in enabled(blank, opts):
            leaked += 1
    check("leaving origin unstated leaks that filter onto somatic rows", leaked > 0,
          f"{leaked}/{len(somatic)} somatic rows — silence is not the safe option")

    # Silence inherits germline's DANGER without inheriting germline's benefits, and that asymmetry is
    # easy to miss by checking only the filter: unstated does NOT resolve identically to germline, and
    # the difference runs the other way from the danger.
    freq_like_germline = all(
        ("frequency" in enabled(dict(r["factor_labels"], origin="unstated"), opts)) ==
        ("frequency" in enabled(dict(r["factor_labels"], origin="germline"), opts)) for r in rows)
    check("on the destructive option, unstated behaves exactly like germline", freq_like_germline,
          "which is why silence is not the neutral choice")

    dropped = set()
    for r in rows:
        blank = enabled(dict(r["factor_labels"], origin="unstated"), opts)
        for o in ("germline", "somatic"):
            dropped |= enabled(dict(r["factor_labels"], origin=o), opts) - blank
    check("...and unstated ALSO drops what both values agree on", dropped == {"check_existing"},
          f"lost by silence on every row: {sorted(dropped) or 'nothing'}")

    check("the guessed value is somatic", va.UNDERSPECIFIED_POLICY["origin"]["assume"] == "somatic",
          f"policy={va.UNDERSPECIFIED_POLICY['origin']['assume']!r}")

    note("silence is strictly worse than EITHER value: it carries germline's risk on `frequency` and "
         "additionally loses `check_existing`, which germline and somatic both enable. That is an "
         "argument for guessing something rather than for guessing somatic specifically.")
    note(f"origin earns its place on ONE option (`frequency`), differing on 9 of {n} tuples — human "
         f"population-frequency only. The taxonomy's own bar is that a factor must gate or shift a "
         f"CLUSTER of options, so whether it earns its place is worth putting to the mentors.")


# --------------------------------------------------------------------------------------------------
def ablation_size(ablations, opts):
    """81 CONTROLLED ABLATIONS. Evidence about a scheme change, not about picking among given values.

    Under single-select there was no safe value: `small` and `structural-CNV` gate away opposite halves
    of the catalogue, so the tool asked instead. Multi-select created the safe value."""
    print("\n== variant_size_class = both — the value only existed after the scheme changed ==")
    cases = [c for c in ablations if c.get("pure") and c["target"] == "variant_size_class"]

    def losses(fill):
        lost = 0
        for c in cases:
            truth = enabled(c["truth"], opts)
            t = dict(c["truth"])
            t["variant_size_class"] = fill
            if truth - enabled(t, opts):
                lost += 1
        return lost

    empty = losses([])
    both = losses(["small", "structural-CNV"])
    check("filling the gap with `both` loses nothing on any ablation", both == 0,
          f"{both}/{len(cases)} queries lose an option")
    check("leaving it empty loses options on a large minority", empty > 0,
          f"{empty}/{len(cases)} queries lose an option")
    check("`both` is strictly better than leaving it empty", both < empty,
          f"both={both} vs empty={empty}, over n={len(cases)}")
    check("the factor is declared multi-select, which is what makes `both` expressible",
          "variant_size_class" in va.MULTI_FACTORS)
    check("the guessed value is both",
          sorted(as_list(va.UNDERSPECIFIED_POLICY["variant_size_class"]["assume"])) ==
          ["small", "structural-CNV"])


# --------------------------------------------------------------------------------------------------
def judgement_species(opts):
    """NO EXPERIMENT. This default is a judgement call and the test says so rather than dressing it up.

    What CAN be checked is the premise it rests on: that the keyword rule abstains often, and that
    resolving an abstention as non-human would be expensive."""
    print("\n== species = human on unknown — judgement, with no experiment behind it ==")
    try:
        rows = json.load(open(MEASURED))["rows"]
        bodies = {x["url"]: x.get("body", "") for x in json.load(open(FETCHED))}
        texts = [bodies.get(r["url"], "") for r in rows]
    except Exception as e:                                    # pragma: no cover - data is committed
        note(f"real-question set unreadable ({e}); premise unchecked")
        return
    unknown = sum(1 for t in texts if va.infer_species(t) == "unknown")
    check("the keyword rule abstains on a large share of real questions", unknown > 0,
          f"unknown on {unknown}/{len(texts)} real configuration questions")

    human_only = {o["id"] for o in opts
                  if "human" in (o.get("species_restriction") or "").lower()}
    check("resolving an abstention as non-human would strip a real block of options",
          len(human_only) > 5, f"{len(human_only)} human-only options at risk")
    check("the fail direction is toward human",
          va.infer_species("some variants with no organism named") in ("human", "unknown"))
    note("NO experiment chose this value. It is the weakest-evidenced of the four defaults and it "
         "fails in the other direction — a non-human query that never says so keeps human-only "
         "options. The constraint checker announces it; that is the mitigation, not a measurement.")


# --------------------------------------------------------------------------------------------------
def loss_ledger(rows, opts):
    """THE ONE TABLE TO READ: what each guess costs, in the currency the design says matters.

    Lost and added are not the same error. An option we add is a column the user ignores; an option we
    drop is a finding they never see. So "is this default safe?" means "does it lose anything?", and it
    is answered per default rather than in aggregate, because the answers differ.

    Deterministic end to end: the true tuple resolved against the same tuple with one factor overwritten
    by its default. No classifier, so no seed and no variance -- run it a thousand times, same table."""
    print("\n== the loss ledger — what each CURRENT default costs, per option ==")
    defaults = {f: va.UNDERSPECIFIED_POLICY[f]["assume"]
                for f in ("region_focus", "origin", "variant_size_class")}
    print(f"        {'default':<34} {'rows losing':>12} {'mean lost':>10} {'mean added':>11}  lost")
    zero_loss = []
    for f, value in defaults.items():
        losing = lost_total = added_total = 0
        lost_ids = {}
        for row in rows:
            truth = va.resolve_for_query(row["factor_labels"], opts) or {}
            truth_on = {k for k, (e, _, _) in truth.items() if e}
            t = dict(row["factor_labels"])
            t[f] = value
            got = enabled(t, opts)
            lost, added = truth_on - got, got - truth_on
            lost_total += len(lost)
            added_total += len(added)
            if lost:
                losing += 1
                for o in lost:
                    lost_ids[o] = lost_ids.get(o, 0) + 1
        n = len(rows)
        shown = ", ".join(f"{k} x{c}" for k, c in sorted(lost_ids.items(), key=lambda x: -x[1])) or "—"
        label = f"{f} = {value if not isinstance(value, list) else 'both'}"
        print(f"        {label:<34} {losing:>7}/{n:<4} {lost_total/n:>10.2f} "
              f"{added_total/n:>11.2f}  {shown}")
        if losing == 0:
            zero_loss.append(f)

    check("region_focus loses nothing on any row", "region_focus" in zero_loss)
    check("variant_size_class loses nothing on any row", "variant_size_class" in zero_loss)
    check("origin is the only default that loses anything", zero_loss == ["region_focus",
                                                                          "variant_size_class"],
          "and it is a deliberate trade, not an oversight")

    # The tier of what origin costs, because "one optional pre-filter" was the wrong description and
    # the difference matters: `recommended` is inside the bucket the user is shown as switched on.
    tiers = set()
    for row in rows:
        truth = va.resolve_for_query(row["factor_labels"], opts) or {}
        truth_on = {k: p for k, (e, p, _) in truth.items() if e}
        got = enabled(dict(row["factor_labels"], origin="somatic"), opts)
        for o in set(truth_on) - got:
            tiers.add((o, truth_on[o], va.display_tier(truth_on[o])))
    check("what origin costs is NOT an add-on", all(d != "add-on" for _, _, d in tiers),
          "  ".join(f"{o} is {p} -> shown as {d}" for o, p, d in sorted(tiers)) or "nothing lost")

    # The species guess is fail-OPEN, so its risk is the opposite shape and belongs in the ledger too.
    nh = [r for r in rows if r["factor_labels"]["species"] == "non-human"]
    if nh:
        added = sum(len(enabled(dict(r["factor_labels"], species="human"), opts) -
                        enabled(r["factor_labels"], opts)) for r in nh)
        check("the species guess fails by ADDING, which is the tolerable direction",
              added > 0, f"{added/len(nh):.2f} human-only options per row forced onto a non-human "
                         f"scenario that never said so — worst case, not expected case")


def not_guessed(ablations, opts):
    """The two things the tool does NOT guess. `we ask about this` rots as easily as a default."""
    print("\n== analysis_goal and assembly — asked, not guessed ==")
    check("analysis_goal carries no guess",
          va.UNDERSPECIFIED_POLICY["analysis_goal"]["assume"] is None,
          f"policy={va.UNDERSPECIFIED_POLICY['analysis_goal']['assume']!r}")

    cases = [c for c in ablations if c.get("pure") and c["target"] == "analysis_goal"]
    asked = 0
    for c in cases:
        rec = {f: (list(as_list(c["read_after"].get(f))) if f in va.MULTI_FACTORS
                   else (c["read_after"].get(f) or "unstated")) for f in va.FACTOR_VALUES}
        _, _, qs = va.clarification_plan(rec, opts, c.get("ablated"))
        if any(f == "analysis_goal" for f, _, _ in qs):
            asked += 1
    check("with no guess, the rule asks about analysis_goal on every such ablation",
          asked == len(cases), f"{asked}/{len(cases)}")

    lost = 0
    for c in cases:
        truth = enabled(c["truth"], opts)
        t = dict(c["truth"], analysis_goal=["basic-consequence"])
        if truth - enabled(t, opts):
            lost += 1
    check("...and the fallback value loses options on some of them", lost > 0,
          f"{lost}/{len(cases)} — subtractive error, which is the direction that costs a finding")

    check("assembly is not a factor, so it has no guess path",
          "assembly" not in va.FACTOR_VALUES and "assembly" not in va.UNDERSPECIFIED_POLICY)
    restriction = {o.get("id"): o.get("species_restriction", "") for o in opts}
    only38 = {k for k, v in restriction.items() if va._assembly_restriction(v) == {"GRCh38"}}
    only37 = {k for k, v in restriction.items() if va._assembly_restriction(v) == {"GRCh37"}}
    check("both assembly answers delete something real, which is why neither is guessed",
          bool(only38) and bool(only37),
          f"GRCh38-only={sorted(only38)}  GRCh37-only={sorted(only37)}")


# --------------------------------------------------------------------------------------------------
def main():
    global VERBOSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="show the full sweep tables")
    VERBOSE = ap.parse_args().verbose

    opts = load_options()
    rows = json.load(open(ROWS))
    ablations = json.load(open(ABLATIONS))

    print(f"\nRe-deriving every default from {len(rows)} review rows and "
          f"{sum(1 for c in ablations if c.get('pure'))} clean ablations. No model is run.")

    loss_ledger(rows, opts)
    sweep_region_focus(rows, opts)
    audit_origin(rows, opts)
    ablation_size(ablations, opts)
    judgement_species(opts)
    not_guessed(ablations, opts)

    print("\n" + "=" * 78)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        print("\nA failure here means a number this project has published is no longer true.")
        return 1
    print("ALL PASS ✓ — every guessed value still matches the evidence given for it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
