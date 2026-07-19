#!/usr/bin/env python3
"""Stage 1 — stratified factor-tuple sampler.

Chooses which gold rows to build next, balancing PER-FACTOR-VALUE coverage (not single categories) —
the multi-label sizing of taxonomy_proposal.md §6. Uses greedy inverse-frequency selection (pick the
rarest uncovered value each draw), which is deterministic and guarantees the minority values
(non-human, somatic, structural-CNV, regulatory-noncoding) appear early — the exact coverage gaps a
naive per-value draw misses. Multi-select factors get one value on odd draws and two on
even draws, so the set includes genuine multi-label rows.

  python work/generation/sample_factors.py --n 6 --out candidates/tuples.json
"""
import argparse
import itertools
import json
import random
from collections import defaultdict

import genlib


def violates_exclusion(t, exclusions):
    """True if the tuple contains a factor-value PAIR the catalogue cannot satisfy (factors.json
    `exclusions`) — e.g. non-human + population-frequency, where every frequency source is human-only, so
    the query asks for data the config provably cannot contain."""
    for ex in exclusions:
        pair = ex["pair"]
        if all(v in (t[f] if isinstance(t[f], list) else [t[f]]) for f, v in pair.items()):
            return ex
    return None


def _repair(t, factors_cfg, exclusions, rng):
    """Re-draw the multi-select side of an excluded pair. Prefers dropping the INTENT value (what the user
    wants) over the DATA FACT (what the variant set is): species/size are properties of the sample and the
    reason the row exists, while a goal is only one of several the row could have carried."""
    ex = violates_exclusion(t, exclusions)
    if not ex:
        return t
    for f, v in ex["pair"].items():
        spec = factors_cfg["factors"][f]
        if spec["select"] != "multi":
            continue
        alts = [x for x in t[f] if x != v]
        if alts:                                     # multi-select: just drop the impossible value
            t[f] = sorted(alts)
            return _repair(t, factors_cfg, exclusions, rng)
        others = [x for x in spec["values"] if x != v]
        t[f] = [rng.choice(others)]
        return _repair(t, factors_cfg, exclusions, rng)
    # both sides single-select (e.g. non-human + structural-CNV): flip the SIZE, not the species —
    # dropping non-human would defeat the reason the sampler over-weights it (the species safety net).
    for f, v in ex["pair"].items():
        if f == "variant_size_class":
            t[f] = next(x for x in factors_cfg["factors"][f]["values"] if x != v)
            return _repair(t, factors_cfg, exclusions, rng)
    return t


def sample(n, factors_cfg, seed=42):
    factors = factors_cfg["factors"]
    exclusions = factors_cfg.get("exclusions", [])
    counts = defaultdict(int)  # (factor, value) -> count
    rng = random.Random(seed)  # seeded tie-break decorrelates the binary factors (reproducible per seed)

    def rarest(f, vals, k=1):
        """The k rarest values for factor f; ties broken by the seeded RNG so tuples don't collapse."""
        ordered = sorted(vals, key=lambda v: counts[(f, v)])
        chosen = []
        while ordered and len(chosen) < k:
            m = counts[(f, ordered[0])]
            tie = [v for v in ordered if counts[(f, v)] == m]
            pick = rng.choice(tie)
            chosen.append(pick)
            ordered.remove(pick)
        return chosen

    def cellkey(t):
        return (t["species"], t["origin"], t["variant_size_class"],
                tuple(sorted(t["region_focus"])), tuple(sorted(t["analysis_goal"])))

    def draw(i):
        t = {}
        for f, spec in factors.items():
            if spec["select"] == "single":
                chosen = rarest(f, spec["values"], 1)
            else:
                # one value on odd draws, two on even draws (multi-label coverage)
                k = 2 if (i % 2 == 0 and len(spec["values"]) >= 2) else 1
                chosen = rarest(f, spec["values"], k)
            t[f] = chosen[0] if spec["select"] == "single" else sorted(chosen)
        # Repair BEFORE counting, so the excluded draw doesn't pollute the inverse-frequency balance.
        return _repair(t, factors_cfg, exclusions, rng)

    # `n` means n DISTINCT cells, not n draws. The inverse-frequency draw breaks ties with the seeded RNG
    # on a balanced count where many values tie, so successive draws collapse to the same cell — the
    # previous version emitted 41 tuples that were only 30 distinct configs, making the mentor re-review
    # identical configs. `rarest()` is deterministic given the counts, so a bare retry re-returns the same
    # cell; instead, on a collision we force a genuinely different cell by re-drawing the multi-select
    # factors to their 2nd-choice combination (draw_variant). Counting happens only for ACCEPTED distinct
    # cells, so the inverse-frequency balance still tracks what actually shipped.
    # On a collision, keep the rarest SINGLE-select values (species/origin/size — the data-fact floors the
    # mentor cares about for the safety net) and vary only the MULTI-select intent factors, cycling their
    # distinct subsets. This preserves inverse-frequency floor-building on the binary factors while making
    # the cell distinct through region/goal — of which there are many combinations.
    multi_combos = {f: _subsets(spec["values"])
                    for f, spec in factors.items() if spec["select"] == "multi"}

    def draw_variant(i, attempt):
        t = {}
        for f, spec in factors.items():
            if spec["select"] == "single":
                t[f] = rarest(f, spec["values"], 1)[0]        # keep the rarest — build the floor
        # vary the multi-select factors through their subsets, offset by `attempt`, rarest-subset-first
        for f in multi_combos:
            combos = sorted(multi_combos[f],
                            key=lambda c: sum(counts[(f, v)] for v in c) / len(c))
            t[f] = sorted(combos[attempt % len(combos)])
        return _repair(t, factors_cfg, exclusions, rng)

    tuples, seen = [], set()
    i, guard = 0, 0
    while len(tuples) < n and guard < n * 200:
        guard += 1
        t = draw(i)
        attempt = 1
        while cellkey(t) in seen and attempt < 80:
            t = draw_variant(i, attempt)
            attempt += 1
        if cellkey(t) in seen:
            break                                    # space genuinely exhausted
        seen.add(cellkey(t))
        for f, spec in factors.items():
            for v in (t[f] if isinstance(t[f], list) else [t[f]]):
                counts[(f, v)] += 1
        tuples.append(t)
        i += 1
    return tuples, counts


def coverage_topup(tuples, factors_cfg, catalogue, pbf, k=8, max_add=12):
    """Add DISTINCT, realistic tuples until every priced option is exercised in >= k rows.

    WHY: the sampler balances the 11 factor VALUES, but what review has to validate is the 58x5 priority
    TABLE — and balanced values do not give balanced option coverage. Predictors need the conjunction
    human AND coding AND clinical, which independent balanced sampling hits ~1/8 of the time: measured at
    3-5 rows each out of 30, while `core_type` (which nobody disputes) got 30. The most editorial call in
    the table was the least exercised.

    This is safe to bolt on because both objectives are FLOORS, and floors compose: adding rows can only
    RAISE a count, so a factor floor once met can never be broken. Measured: +6 rows takes every priced
    option from a floor of 3 to a floor of 8 while every factor value stays >= 15. What does shift is the
    RATIO (human 50%->58%), which is fine — this set was never a traffic sample; it deliberately
    over-weights rare values to exercise the species gate.

    Two constraints keep the greedy honest:
      * DISTINCT cells — without this it re-picks the same maximal-gain tuple k times, exercising an
        option k times in one context. That is redundancy, not coverage.
      * NO kitchen sinks — a tuple asking for all three goals across both regions covers the most options
        and is the least realistic thing in the space; no user asks it.
    """
    import resolve_config as rc

    exclusions = factors_cfg.get("exclusions", [])
    # Coverage targets options that can appear as core or add-on. Exclude the always-disabled set
    # (MEANINGFUL_DISABLES = most_severe/summary): they are priced but structurally emitted as explicit
    # DISABLES on every row, so they can never reach a core/add-on count — chasing them would make the
    # floor read 0 forever and pad the set with rows trying to cover an uncoverable target.
    priced = {o for o, f in pbf["priorities"].items() if f} - set(rc.MEANINGFUL_DISABLES)

    def cells(t):
        intent = rc.intent_priorities(t, catalogue, pbf, factors_cfg)
        return {o for o, (_e, p, g) in intent.items() if not g and p in ("critical", "recommended", "optional")}

    def key(t):
        return (t["species"], t["origin"], t["variant_size_class"],
                tuple(sorted(t["region_focus"])), tuple(sorted(t["analysis_goal"])))

    space = []
    F = factors_cfg["factors"]
    for sp in F["species"]["values"]:
        for og in F["origin"]["values"]:
            for sz in F["variant_size_class"]["values"]:
                for rg in _subsets(F["region_focus"]["values"]):
                    for gl in _subsets(F["analysis_goal"]["values"]):
                        t = {"species": sp, "origin": og, "variant_size_class": sz,
                             "region_focus": sorted(rg), "analysis_goal": sorted(gl)}
                        if violates_exclusion(t, exclusions):
                            continue
                        if len(gl) == len(F["analysis_goal"]["values"]) and len(rg) > 1:
                            continue                       # kitchen sink
                        space.append(t)

    have = defaultdict(int)
    for t in tuples:
        for o in cells(t) & priced:
            have[o] += 1
    used = {key(t) for t in tuples}
    added = []
    while any(have[o] < k for o in priced) and len(added) < max_add:
        cands = [t for t in space if key(t) not in used]
        if not cands:
            break
        best = max(cands, key=lambda t: sum(1 for o in cells(t) & priced if have[o] < k))
        if sum(1 for o in cells(best) & priced if have[o] < k) == 0:
            break
        for o in cells(best) & priced:
            have[o] += 1
        used.add(key(best))
        added.append(best)
    return added, have, priced


def _subsets(vals):
    out = []
    for r in range(1, len(vals) + 1):
        out += [list(c) for c in itertools.combinations(vals, r)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cover", type=int, default=0, metavar="K",
                    help="after the balanced draw, add distinct rows until every priced option is "
                         "exercised in >=K rows (0 = off). Factor floors are preserved: adding rows can "
                         "only raise counts.")
    args = ap.parse_args()

    factors_cfg = genlib.load_factors()
    tuples, counts = sample(args.n, factors_cfg, seed=args.seed)

    added = []
    if args.cover:
        catalogue = genlib.load_catalogue()
        pbf = genlib.load_priority_by_factor()
        added, have, priced = coverage_topup(tuples, factors_cfg, catalogue, pbf, k=args.cover)
        tuples = tuples + added
        counts = defaultdict(int)
        for t in tuples:
            for f in factors_cfg["factors"]:
                for v in (t[f] if isinstance(t[f], list) else [t[f]]):
                    counts[(f, v)] += 1

    with open(args.out, "w") as f:
        json.dump(tuples, f, indent=2)

    print(f"Sampled {len(tuples)} factor tuples -> {args.out}"
          f"{f'  ({args.n} balanced + {len(added)} coverage)' if added else ''}\n")
    for i, t in enumerate(tuples):
        tag = "  [coverage]" if i >= args.n else ""
        print(f"  {i+1}. species={t['species']:9s} origin={t['origin']:8s} "
              f"size={t['variant_size_class']:14s} region={t['region_focus']} "
              f"goal={t['analysis_goal']}{tag}")
    print("\nper-(factor,value) coverage  [floor must hold]:")
    for f, spec in factors_cfg["factors"].items():
        cov = "  ".join(f"{v}={counts[(f, v)]}" for v in spec["values"])
        print(f"  {f:20s} {cov}")
    if args.cover:
        floor = min(have[o] for o in priced)
        worst = sorted((have[o], o) for o in priced)[:4]
        print(f"\nper-OPTION coverage: floor={floor} (target {args.cover}); "
              f"least-exercised: {', '.join(f'{o}={n}' for n, o in worst)}")
    ex = factors_cfg.get("exclusions", [])
    if ex:
        print(f"\nexcluded (catalogue cannot satisfy): "
              f"{'; '.join(' + '.join(f'{k}={v}' for k, v in e['pair'].items()) for e in ex)}")


if __name__ == "__main__":
    main()
