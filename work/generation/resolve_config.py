#!/usr/bin/env python3
"""Stage 2 — deterministic config resolver (the reverse/asymmetric step).

Turns a factor tuple into `recommended_options` WITHOUT a teacher LLM, then hands the raw set to the
demo's constraint checker (reused, not reimplemented) to repair species/conflict/dependency. The emitted
set is the checker's OUTPUT, so re-running the checker on it is a no-op — the self-consistency invariant
Stage 4 asserts (validate_examples-style: zero further mutations).

Algorithm (taxonomy_proposal.md §5):
  1. hard gates: drop an option if a HARD factor (species, variant_size_class) marks it not_applicable,
     or the origin=somatic -> frequency (the 'filter_common' rule; catalogue id is 'frequency') fires;
  2. soft ranking: among survivors, take the strongest priority across all active factor values
     (critical>recommended>optional); enable critical+recommended;
  3. apply depends_on / conflicts_with / species via the reused checker, to a fixed point.

CLI: read factor tuples (from sample_factors.py) and write resolved candidate rows.
  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/generation/resolve_config.py --tuples candidates/tuples.json --out candidates/resolved.json
"""
import argparse
import json

import genlib

# Options whose value is not a bare boolean (everything else -> True when enabled).
VALUE_DEFAULTS = {"sift": "b", "polyphen": "b", "check_existing": "yes"}
# A small set of "commonly tempting but usually off" output-restriction options: emit as explicit
# disables (with notes) when not enabled, for closed-world Disable-F1 signal (matches the simulated
# gold convention). Kept deliberately small — full closed-world disables are a mentor decision (§15).
MEANINGFUL_DISABLES = {
    "most_severe": "keep full per-transcript detail, not a single top-line consequence",
    "summary": "need detailed annotations, not a summary line",
}


def _value_for(oid, species):
    if oid == "core_type":
        return "Ensembl/GENCODE" if species == "human" else "Ensembl"
    return VALUE_DEFAULTS.get(oid, True)


def intent_priorities(factor_tuple, catalogue, pbf, factors_cfg, enable=("critical", "recommended")):
    """Pre-checker intent: {oid: (enabled_bool, priority_or_None, gated_bool)} from factor priorities.

    `enable` is the set of priority labels that switch an option ON — default critical+recommended
    (taxonomy_proposal §5). Pass ('critical',) for a tighter, higher-precision config."""
    av = genlib.active_values(factor_tuple)
    priorities = pbf["priorities"]
    cond_rules = factors_cfg.get("conditional_rules", [])
    somatic_na = set()
    for f, spec in factors_cfg["factors"].items():
        for rule in spec.get("hard_rules", []):
            if factor_tuple.get(f) == rule["when_value"]:
                somatic_na.update(rule["not_applicable"])

    out = {}
    for opt in catalogue:
        oid = opt["id"]
        pf = priorities.get(oid, {})
        gated = False
        # (1) hard gates — a factor gates an option only if EVERY one of its ACTIVE values marks the
        # option not_applicable. For the single-select factors (species, variant_size_class) that is
        # identical to the previous "any active value" rule, since there is exactly one active value.
        # It matters for the multi-select `region_focus`: a coding+regulatory variant set HAS a coding
        # component, so a missense predictor still applies and must not be gated away just because a
        # regulatory component is also present. "any" would have dropped it; "all" keeps it.
        for hf in genlib.HARD_GATE_FACTORS:
            vals = av.get(hf, [])
            if vals and all(pf.get(hf, {}).get(v) == "not_applicable" for v in vals):
                gated = True
        if oid in somatic_na:
            gated = True
        if gated:
            out[oid] = (False, None, True)
            continue
        # (2) soft ranking over ALL active factor values
        labels = []
        for f, vals in av.items():
            for v in vals:
                labels.append(pf.get(f, {}).get(v))
        # (3) conditional rules — JOINT conditions the per-value table cannot express. The priority table
        # is keyed one factor value at a time and composes by max, so every value votes alone; there is no
        # slot for "non-human AND clinical together imply MaxEntScan". A rule fires only when EVERY 'when'
        # pair is active, and contributes its label to the same max — so it can only RAISE an option, never
        # lower one. It also cannot resurrect a hard-gated option: gating `continue`s above this.
        for rule in cond_rules:
            if all(wv in av.get(wf, []) for wf, wv in rule["when"].items()):
                lab = rule["then"].get(oid)
                if lab:
                    labels.append(lab)
        pr = genlib.strongest(labels)
        out[oid] = (pr in enable, pr, False)
    return out


def flag_arbitrary_conflicts(checker_changes, intent):
    """Conflicts the checker resolved WITHOUT a factor-priority difference — i.e. the two options were
    equally important under the factor scheme, so the checker's choice of which to drop fell through to
    its arbitrary tiebreak (restrictiveness, then alphabetical). We do NOT trust a coin-flip in a gold
    row: surface it for human review instead of silently committing it. (The principled fix is to resolve
    the output-mode conflict by `analysis_goal` — see README open items — but until then, flag.)"""
    def rank(oid):
        return genlib.PRIORITY_ORDER.get((intent.get(oid) or (None, None, None))[1], 0)

    out = []
    for v in checker_changes:
        if v.get("type") != "conflict":
            continue
        a, b = v.get("option_disabled"), v.get("option_kept")
        if a is None or b is None:
            continue
        if rank(a) == rank(b):
            out.append({
                "disabled": a, "kept": b,
                "reason": (f"'{a}' and '{b}' have equal factor-priority — dropping '{a}' used the checker's "
                           f"arbitrary tiebreak (restrictiveness/alphabetical); needs human review"),
            })
    return out


# A factor value's INTENT, defined by the catalogue CATEGORIES that would satisfy it — NOT by which
# factor happens to price a given option. This is the fix for a false-positive class: `population-frequency`
# means "frequency data of some kind", and gnomAD-SV is frequency data (category frequency_data) even
# though it is priced under `variant_size_class`, not under `analysis_goal`. Asking "did any option in the
# satisfying CATEGORY survive?" is the right question; asking "did the options THIS factor value names
# survive?" wrongly flags a somatic structural-CNV population query as unsatisfiable when gnomAD-SV is right
# there answering it. Only values whose entire satisfying set is a coherent category go here; a value with
# no single such category (e.g. clinical-interpretation spans several) is not checkable this way and is
# omitted rather than guessed.
_INTENT_CATEGORIES = {
    ("analysis_goal", "population-frequency"): {"frequency_data"},
}


def unsatisfiable_factors(factor_tuple, pbf, intent, catalogue=None):
    """Active factor values whose SATISFYING CATEGORY was entirely gated away — the scenario asks for a
    kind of annotation this catalogue cannot deliver for this species/size.

    The sampler treats factors as independent (PROGRESS §10), so it draws combinations the catalogue
    cannot serve: `non-human + population-frequency` (gnomAD/1000G are human-only, so NO frequency source
    survives). Stage 3, told only the factor prose, writes a query asking for frequencies anyway, and
    nothing else catches it — the config is checker-clean and the query expresses its factors. This
    surfaces it for the reviewer; the fix (catalogue addition, or sampler exclusion) is their call.

    Category-based so it is not fooled by cross-factor supply: a frequency source priced under a DIFFERENT
    factor (gnomAD-SV, under size) still counts as satisfying `population-frequency`."""
    if catalogue is None:
        return []
    av = genlib.active_values(factor_tuple)
    cat_of = {o["id"]: o.get("category") for o in catalogue}
    out = []
    for (f, v), sat_cats in _INTENT_CATEGORIES.items():
        if v not in av.get(f, []):
            continue
        # every catalogue option in a satisfying category
        candidates = [oid for oid, c in cat_of.items() if c in sat_cats]
        # ...that survived the gates for THIS scenario (not hard-gated away)
        alive = [oid for oid in candidates if not intent.get(oid, (False, None, True))[2]]
        if candidates and not alive:
            out.append({"factor": f, "value": v, "cluster": sorted(candidates),
                        "reason": (f"'{f}={v}' needs {'/'.join(sorted(sat_cats))} annotation, but every "
                                   f"such option is unavailable for this scenario — the query will ask "
                                   f"for something the config cannot deliver")})
    return out


def resolve_row(factor_tuple, catalogue, pbf, factors_cfg, va, corpus, enable=("critical", "recommended")):
    """Resolve one factor tuple to a checker-clean candidate row (no user_query yet)."""
    intent = intent_priorities(factor_tuple, catalogue, pbf, factors_cfg, enable=enable)
    raw_enabled = {oid for oid, (en, _, _) in intent.items() if en}

    # (3) repair via the reused checker, to a fixed point, using a species-cue query.
    species = factor_tuple["species"]
    cue = genlib.species_cue_query(species)
    en, dis = set(raw_enabled), set()
    seen, checker_changes = set(), []
    for _ in range(6):
        viol = va.check_and_fix_violations(en, dis, catalogue, corpus, cue)
        changed = [v for v in viol if v.get("option_disabled") or v.get("option_enabled")]
        # Record DISTINCT fixes (type, option) — the fixed-point loop can re-report the same fix
        # across iterations, and set-iteration order otherwise makes the raw count non-reproducible.
        for v in changed:
            key = (v["type"], v.get("option_disabled") or v.get("option_enabled"))
            if key not in seen:
                seen.add(key)
                checker_changes.append(v)
        if not changed:
            break

    # (4) assemble recommended_options: ONLY the enabled options (with resolved priority + value).
    #
    # We deliberately do NOT emit explicit disables anymore. The deterministic checker already disables
    # conflicting/tempting-but-wrong options at runtime (verified: enabling most_severe alongside a detailed
    # config is auto-dropped by conflict resolution), so an explicit disable list in the gold row is pure
    # redundancy — the model only ever needs to say what to turn ON; the checker owns everything OFF
    # (conflicts, dependencies, species). This keeps the row to a single positive claim (the enabled set),
    # drops the weakly-defined disable-F1 signal, and removes a constant, non-informative field from the
    # mentor's review. `checker_changes` is still kept in `_resolver` below for provenance/diagnostics.
    rec = {}
    for oid in sorted(en):
        pr = intent.get(oid, (True, None, False))[1] or "recommended"  # checker-added deps default recommended
        rec[oid] = {"value": _value_for(oid, species), "enabled": True, "priority": pr}

    # (5) ADD-ONS — options the factor priorities rank `optional`. The mentor's own pipeline spec asks for
    # generated options "including mandatory and optional" (mentor_comms_log, step 2), and these were
    # previously computed by intent_priorities() and then dropped on the floor here, because this function
    # only ever iterated the ENABLED set. They live in a separate key rather than in `recommended_options`
    # with enabled=False, because the eval harness reads enabled=False as "should be OFF"
    # (evaluate.get_ground_truth) — an add-on is neither on-by-default nor wrong-to-enable.
    #
    # An add-on that conflicts with a core option is not a real suggestion (e.g. `most_severe` is optional
    # under basic-consequence but suppresses the per-transcript columns `symbol`/`hgvs` provide), so those
    # are withheld and the reason recorded rather than offered as a contradictory click.
    conflicts_of = {o["id"]: set(o.get("conflicts_with") or []) for o in catalogue}
    add_ons, add_ons_withheld = {}, {}
    for oid, (_en, pr, gated) in sorted(intent.items()):
        if pr != "optional" or gated or oid in rec:
            continue
        clash = sorted((conflicts_of.get(oid, set()) & en)
                       | {c for c in en if oid in conflicts_of.get(c, set())})
        if clash:
            add_ons_withheld[oid] = f"conflicts with enabled core option(s): {', '.join(clash)}"
            continue
        add_ons[oid] = {"value": _value_for(oid, species), "priority": "optional"}

    n_gated = sum(1 for _, _, g in intent.values() if g)
    arbitrary_conflicts = flag_arbitrary_conflicts(checker_changes, intent)
    unsatisfiable = unsatisfiable_factors(factor_tuple, pbf, intent, catalogue)
    return {
        "id": f"gen_{genlib.factor_slug(factor_tuple)}",
        "user_query": None,               # filled by Stage 3
        "factor_labels": factor_tuple,
        "use_case_category": None,        # deprecated under the factor scheme; kept nullable for the harness
        "confidence": "provisional",
        "recommended_options": rec,       # the CORE: critical + recommended (on) + meaningful disables (off)
        "add_on_options": add_ons,        # the ADD-ONS: optional (offered, not on by default)
        "justification": None,            # optionally drafted by Stage 3b
        "_resolver": {
            "n_enabled": len(en),
            "n_add_ons": len(add_ons),
            "n_hard_gated": n_gated,
            "checker_changes": checker_changes,
            "arbitrary_conflicts": arbitrary_conflicts,
            "unsatisfiable_factors": unsatisfiable,
            "add_ons_withheld": add_ons_withheld,
            "config_source": "PROVISIONAL priority_by_factor.json (drives-authored) — not mentor-validated",
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tuples", required=True, help="JSON list of factor tuples (from sample_factors.py)")
    ap.add_argument("--out", required=True, help="output JSON of resolved candidate rows")
    ap.add_argument("--enable", choices=["critical", "critical+recommended"], default="critical+recommended",
                    help="which priority labels switch an option ON (default critical+recommended, per §5)")
    args = ap.parse_args()

    enable = ("critical",) if args.enable == "critical" else ("critical", "recommended")
    va = genlib.load_va()
    catalogue = genlib.load_catalogue()
    pbf = genlib.load_priority_by_factor()
    factors_cfg = genlib.load_factors()
    corpus = genlib.load_corpus()
    tuples = json.load(open(args.tuples))

    rows = [resolve_row(t, catalogue, pbf, factors_cfg, va, corpus, enable=enable) for t in tuples]
    with open(args.out, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"Resolved {len(rows)} candidate configs -> {args.out}")
    for r in rows:
        en = [k for k, v in r["recommended_options"].items() if v.get("enabled")]
        fl = r["factor_labels"]
        print(f"  {r['id'][:52]:52s} species={fl['species']:9s} enabled={len(en):2d} "
              f"gated={r['_resolver']['n_hard_gated']:2d} checker_fixes={len(r['_resolver']['checker_changes'])}")


if __name__ == "__main__":
    main()
