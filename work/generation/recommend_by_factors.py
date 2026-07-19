#!/usr/bin/env python3
"""Recommend a VEP web-form configuration from FACTOR VALUES, deterministically.

This is the factor-native entry point. You describe the analysis as a set of factor values rather than
as prose, and the recommender resolves it with no LLM in the loop at all: factor values -> per-option
priorities (priority_by_factor.json) -> hard gates -> the deterministic constraint checker. Same code
path the generation pipeline's Stage 2 uses, so what you see here is exactly what a generated example
would contain.

WHY NO LLM: the config half of this system was never the language model's job. The model's only task is
turning prose into factor values; once you supply the factors directly there is nothing left to infer, so
the answer is deterministic, instant, needs no GPU, and is identical on every run. That also makes this
the right tool for VALIDATING the priorities: what you see is the priority table, not a sample from a
model.

  # a human germline rare-disease exome question
  python recommend_by_factors.py --species human --origin germline --size small \
      --region coding --goal clinical-interpretation

  # multi-select factors repeat the flag (region_focus and analysis_goal are multi-select)
  python recommend_by_factors.py --species human --origin somatic --size structural-CNV \
      --region coding --region regulatory-noncoding --goal clinical-interpretation --goal population-frequency

  --json    emit the resolved row as JSON instead of the readable table
  --explain show WHICH factor value drove each option to its priority

Run `--list-factors` to see every legal value.

PROVISIONAL: the priorities this reads are authored, not mentor-validated. See priority_by_factor.json's
`_status`. The tiering of the pathogenicity predictors in particular is OUR editorial judgement (ACMG
PP3/BP4 as refined by ClinGen SVI, Pejaver et al. 2022) — VEP itself ranks none of them.
"""
import argparse
import json
import sys

import genlib
import resolve_config as rc

TIER_ORDER = ["critical", "recommended", "optional"]


def _drivers(oid, factor_tuple, pbf):
    """Which (factor, value) pairs claimed this option, and at what label — the provenance of a priority."""
    av = genlib.active_values(factor_tuple)
    pf = pbf["priorities"].get(oid, {})
    out = []
    for f, vals in av.items():
        for v in vals:
            lab = pf.get(f, {}).get(v)
            if lab:
                out.append((f, v, lab))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Resolve a VEP config from factor values (deterministic, no LLM).")
    ap.add_argument("--species", choices=["human", "non-human"])
    ap.add_argument("--origin", choices=["germline", "somatic"])
    ap.add_argument("--size", choices=["small", "structural-CNV"], dest="variant_size_class")
    ap.add_argument("--region", action="append", choices=["coding", "regulatory-noncoding"],
                    dest="region_focus", help="multi-select: repeat the flag")
    ap.add_argument("--goal", action="append",
                    choices=["basic-consequence", "clinical-interpretation", "population-frequency"],
                    dest="analysis_goal", help="multi-select: repeat the flag")
    ap.add_argument("--json", action="store_true", help="emit the resolved row as JSON")
    ap.add_argument("--explain", action="store_true", help="show which factor value drove each option")
    ap.add_argument("--list-factors", action="store_true", help="print the factor scheme and exit")
    args = ap.parse_args()

    if args.list_factors:
        factors = genlib.load_factors()["factors"]
        for f, spec in factors.items():
            sel = "multi-select" if spec.get("select") == "multi" else "single-select"
            gate = " [HARD GATE]" if f in genlib.HARD_GATE_FACTORS else ""
            print(f"{f:20s} {sel:14s}{gate}\n  {' | '.join(spec['values'])}")
        return 0

    missing = [n for n in ("species", "origin", "variant_size_class") if not getattr(args, n)]
    if missing:
        ap.error(f"missing required single-select factor(s): {', '.join(missing)} "
                 f"(see --list-factors)")
    # analysis_goal defaults to basic-consequence: the mentor-agreed default when nothing else is implied
    # (the agreed default when nothing else is implied).
    factor_tuple = {
        "species": args.species,
        "origin": args.origin,
        "variant_size_class": args.variant_size_class,
        "region_focus": args.region_focus or ["coding"],
        "analysis_goal": args.analysis_goal or ["basic-consequence"],
    }

    va = genlib.load_va()
    catalogue = genlib.load_catalogue()
    pbf = genlib.load_priority_by_factor()
    factors_cfg = genlib.load_factors()
    corpus = genlib.load_corpus()

    row = rc.resolve_row(factor_tuple, catalogue, pbf, factors_cfg, va, corpus)
    if args.json:
        print(json.dumps(row, indent=2))
        return 0

    by_id = {o["id"]: o for o in catalogue}
    rec, add_ons = row["recommended_options"], row["add_on_options"]

    print("\nSCENARIO")
    for f, v in factor_tuple.items():
        print(f"  {f:20s} {', '.join(v) if isinstance(v, list) else v}")

    # --- CORE: what to switch on, by importance -----------------------------------------------------
    tiers = {t: [] for t in TIER_ORDER}
    for oid, cfg in rec.items():
        if cfg.get("enabled"):
            tiers.setdefault(cfg.get("priority", "recommended"), []).append(oid)
    n_core = sum(len(tiers[t]) for t in TIER_ORDER)
    print(f"\nCORE — switch these on ({n_core})")
    for t in TIER_ORDER:
        for oid in sorted(tiers[t]):
            o = by_id.get(oid, {})
            line = f"  [{t:11s}] {oid:22s} {str(o.get('cli_flag',''))[:30]:32s}"
            if args.explain:
                drv = ", ".join(f"{f}={v}->{lab}" for f, v, lab in _drivers(oid, factor_tuple, pbf))
                line += f"\n      driven by: {drv or '(checker-added dependency)'}"
            print(line)

    # --- ADD-ONS: offered, not on by default --------------------------------------------------------
    print(f"\nADD-ONS — defensible extras, not on by default ({len(add_ons)})")
    for oid in sorted(add_ons):
        o = by_id.get(oid, {})
        print(f"  [optional   ] {oid:22s} {str(o.get('cli_flag',''))[:30]:32s}")
    if not add_ons:
        print("  (none)")

    # --- OFF: explicit disables ---------------------------------------------------------------------
    off = {oid: c for oid, c in rec.items() if not c.get("enabled")}
    if off:
        print(f"\nEXPLICITLY OFF ({len(off)})")
        for oid, cfg in sorted(off.items()):
            print(f"  {oid:22s} {str(cfg.get('note',''))[:80]}")

    # --- what the factors REMOVED, and why ----------------------------------------------------------
    intent = rc.intent_priorities(factor_tuple, catalogue, pbf, factors_cfg)
    gated = sorted(oid for oid, (_e, _p, g) in intent.items() if g)
    print(f"\nGATED OUT by the factors ({len(gated)}) — not applicable to this scenario")
    print(f"  {', '.join(gated) if gated else '(none)'}")

    res = row["_resolver"]
    # The most important thing we can tell someone: you asked for something VEP cannot give you here.
    # Deterministic, not a guess — every option that factor value asks for was gated out.
    for uf in res.get("unsatisfiable_factors", []):
        print(f"\n⚠️  VEP CANNOT SATISFY '{uf['factor']} = {uf['value']}' FOR THIS SCENARIO")
        print(f"   Every option it needs is unavailable here: {', '.join(uf['cluster'])}")
        if uf["factor"] == "analysis_goal" and uf["value"] == "population-frequency":
            print("   gnomAD and 1000 Genomes are human-only, so there is no population-frequency source")
            print("   for a non-human species. Co-located variants (check_existing) may still report")
            print("   frequencies where your species has variation data.")
        elif uf["value"] == "structural-CNV":
            print("   gnomAD-SV is human-only, so there is no structural-variant frequency source for a")
            print("   non-human species.")
        print("   The configuration below is correct for what IS available — it simply cannot answer")
        print("   that part of the question.")

    if res["checker_changes"]:
        print(f"\nCHECKER REPAIRS ({len(res['checker_changes'])})")
        for v in res["checker_changes"]:
            print(f"  {v['type']:12s} {v.get('reason','')[:90]}")
    if res["arbitrary_conflicts"]:
        print(f"\nNEEDS A HUMAN — arbitrary tiebreaks ({len(res['arbitrary_conflicts'])})")
        for a in res["arbitrary_conflicts"]:
            print(f"  {a['reason']}")
    if res.get("add_ons_withheld"):
        print(f"\nADD-ONS WITHHELD (would contradict a core option)")
        for oid, why in res["add_ons_withheld"].items():
            print(f"  {oid:22s} {why}")

    print(f"\n  Priorities: {pbf['_status'].split('.')[0]}.")
    print("  The predictor core-vs-add-on split is our editorial judgement (ACMG PP3/BP4, ClinGen SVI);")
    print("  VEP itself does not rank these options.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
