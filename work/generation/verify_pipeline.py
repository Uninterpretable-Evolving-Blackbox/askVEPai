#!/usr/bin/env python3
"""Deterministic verification suite for the generation pipeline — NO GPU / LLM needed.

Proves the safety properties a reviewer (or the mentor) actually cares about, reproducibly:
config integrity, the resolver's zero-mutation invariant, the species/size/somatic gates, the
arbitrary-conflict flag, review-schema shape, and the helpers. This is the "prove the machine is
correct" companion to the full generation run (which proves it produces good candidates).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json PYTHONHASHSEED=0 \
  python work/generation/verify_pipeline.py
"""
import json
import sys

import genlib
import resolve_config as rc
import sample_factors as sf
import seed_priorities as sp_

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def enabled(r):
    return {k for k, v in r["recommended_options"].items() if v.get("enabled")}


def main():
    va = genlib.load_va()
    cat = genlib.load_catalogue()
    corpus = genlib.load_corpus()
    factors = genlib.load_factors()
    pbf = genlib.load_priority_by_factor()
    ids = {o["id"] for o in cat}
    restr = {o["id"]: o.get("species_restriction", "all species") for o in cat}
    by_cat = {}
    for o in cat:
        by_cat.setdefault(o.get("category"), []).append(o["id"])

    print("\n== 1. Config integrity ==")
    # Actually load every config file this claims to cover. It used to hardcode True with the comment
    # "loaded above without exception" — but main() never loaded query_axes.json, so a malformed
    # query_axes (which Stage 3 needs) sailed through the whole suite green.
    cfg_err = None
    try:
        axes = genlib.load_query_axes()
        assert axes.get("axes"), "query_axes.json has no 'axes' block"
    except Exception as e:                    # noqa: BLE001 - report any config breakage as a failure
        cfg_err = f"{type(e).__name__}: {e}"
    check("factors / query_axes / priority JSON all parse", cfg_err is None, cfg_err or "")
    check("all 58 catalogue options present in priority table",
          set(pbf["priorities"]) == ids, f"{len(pbf['priorities'])} vs {len(ids)}")
    check("priority table self-labels PROVISIONAL", "PROVISIONAL" in pbf.get("_status", ""))

    print("\n== 2. Resolver: zero-mutation invariant (8 sampled tuples) ==")
    tuples, _ = sf.sample(8, factors, seed=42)
    rows = [rc.resolve_row(t, cat, pbf, factors, va, corpus) for t in tuples]
    allclean = True
    for r in rows:
        opts = r["recommended_options"]
        en = {k for k, v in opts.items() if v.get("enabled")}
        dis = {k for k, v in opts.items() if not v.get("enabled")}
        cue = genlib.species_cue_query(r["factor_labels"]["species"])
        changed = [v for v in va.check_and_fix_violations(set(en), set(dis), cat, corpus, cue)
                   if v.get("option_disabled") or v.get("option_enabled")]
        allclean &= not changed
    check("every resolved config is checker-clean (0 further mutations)", allclean, f"{len(rows)} rows")

    print("\n== 3. Gate properties across the resolved rows ==")
    sp = [(r["id"], o) for r in rows if r["factor_labels"]["species"] == "non-human"
          for o in enabled(r) if va._is_human_only(restr.get(o, "all species"))]
    check("non-human rows never enable a human-only option", not sp, str(sp[:3]))
    # The size gate is driven by the catalogue's own structural_variants column: every option the
    # catalogue marks not_applicable for SVs must be absent from every structural-CNV row's enabled set.
    # This is the strong version of the earlier "SNV predictors" check — it also covers enformer,
    # utrannotator, mutfunc, paralogues, etc. that a hand-authored category gate missed.
    sv_na = {o["id"] for o in cat
             if o.get("priority_by_use_case", {}).get("structural_variants") == "not_applicable"}
    sz = [(r["id"], o) for r in rows if r["factor_labels"]["variant_size_class"] == "structural-CNV"
          for o in enabled(r) if o in sv_na]
    check("structural-CNV rows never enable a catalogue-SV-not_applicable option", not sz, str(sz[:5]))
    # CADD must survive on SVs (catalogue rates it recommended, not n/a) — the exemption is now automatic.
    check("CADD is NOT size-gated (catalogue: structural_variants=recommended)", "cadd" not in sv_na)
    # Region gate (proposed §3 amendment): a purely regulatory query must not get missense predictors.
    reg_only = [(r["id"], o) for r in rows
                if r["factor_labels"]["region_focus"] == ["regulatory-noncoding"]
                for o in enabled(r) if o in set(sp_.MISSENSE_ONLY)]
    check("regulatory-only rows never enable a missense predictor", not reg_only, str(reg_only[:3]))
    # ...but a coding+regulatory query MUST keep them — the gate is 'all active values', not 'any'.
    # Constructed explicitly rather than filtered out of `rows`: the sampled tuples need not contain this
    # combination, and a filter that finds nothing would make this assertion pass vacuously.
    mixed_row = rc.resolve_row({"species": "human", "origin": "germline", "variant_size_class": "small",
                                "region_focus": ["coding", "regulatory-noncoding"],
                                "analysis_goal": ["clinical-interpretation"]},
                               cat, pbf, factors, va, corpus)
    kept = sorted(set(sp_.MISSENSE_ONLY) & enabled(mixed_row))
    check("coding+regulatory rows still keep missense predictors (gate is ALL, not ANY)",
          bool(kept), f"kept={kept}")
    sm = [r["id"] for r in rows if r["factor_labels"]["variant_size_class"] == "small"
          and "gnomad_sv" in enabled(r)]
    check("small-variant rows never enable gnomad_sv", not sm)
    som = [r["id"] for r in rows if r["factor_labels"]["origin"] == "somatic" and "frequency" in enabled(r)]
    check("somatic rows never enable the frequency filter", not som)
    # Conditional rules fire ONLY on the full joint condition. The failure this guards against is real: an
    # earlier attempt promoted maxentscan under `species=non-human` alone, which recommended a SPLICE
    # predictor to a non-human population-frequency scan.
    def _splice(species, goal):
        i = rc.intent_priorities({"species": species, "origin": "germline", "variant_size_class": "small",
                                  "region_focus": ["coding"], "analysis_goal": [goal]},
                                 cat, pbf, factors)
        return i["maxentscan"][1]
    check("conditional rule fires on non-human AND clinical",
          _splice("non-human", "clinical-interpretation") == "recommended")
    check("conditional rule stays silent on non-human alone (no splice tool for a frequency scan)",
          _splice("non-human", "population-frequency") != "recommended",
          f"got {_splice('non-human', 'population-frequency')}")
    # Unsatisfiable detection is CATEGORY-based, so cross-factor supply doesn't fool it: a human somatic
    # structural-CNV population query IS satisfiable (gnomAD-SV, priced under size, answers it), while a
    # non-human population query is NOT (every frequency_data option is human-only). An earlier per-factor
    # version false-flagged the former on 7/41 rows.
    def _unsat(sp, og, sz):
        t = {"species": sp, "origin": og, "variant_size_class": sz,
             "region_focus": ["coding"], "analysis_goal": ["population-frequency"]}
        return bool(rc.unsatisfiable_factors(t, pbf, rc.intent_priorities(t, cat, pbf, factors), cat))
    check("human somatic SV + population is SATISFIABLE (gnomAD-SV, cross-factor)",
          not _unsat("human", "somatic", "structural-CNV"))
    check("non-human + population is UNSATISFIABLE (no frequency source exists)",
          _unsat("non-human", "germline", "small"))

    print("\n== 4. Arbitrary-conflict flag (coin-flip tiebreaks are surfaced, not buried) ==")
    eq = rc.flag_arbitrary_conflicts(
        [{"type": "conflict", "option_disabled": "pick", "option_kept": "per_gene"}],
        {"pick": (True, None, False), "per_gene": (True, None, False)})
    ne = rc.flag_arbitrary_conflicts(
        [{"type": "conflict", "option_disabled": "most_severe", "option_kept": "sift"}],
        {"most_severe": (True, "optional", False), "sift": (True, "recommended", False)})
    check("flags an equal-priority (arbitrary) conflict", len(eq) == 1)
    check("stays silent on an unequal-priority conflict", len(ne) == 0)
    conf = [v for v in va.check_and_fix_violations({"pick", "per_gene"}, set(), cat, corpus,
                                                   "human variant analysis") if v.get("type") == "conflict"]
    e2e = rc.flag_arbitrary_conflicts(conf, {"pick": (True, None, False), "per_gene": (True, None, False)})
    check("real pick/per_gene tie flagged end-to-end through the checker", len(e2e) == 1)

    print("\n== 5. Review-schema shape (rows are gold-shaped for the mentor queue) ==")
    gold = json.load(open(genlib.WORK / "preliminary_examples" / "simulated_gold_examples.json"))[0]
    need = set(gold.keys())
    r0 = rows[0]
    check("resolved row carries every gold review key", need <= set(r0.keys()),
          str(sorted(need - set(r0.keys()))))
    ro = next(iter(r0["recommended_options"].values()))
    check("recommended_options values have {enabled, value}", {"enabled", "value"} <= set(ro.keys()))
    # honesty: use_case_category is intentionally null under the factor scheme
    check("use_case_category is null (factor scheme) — eval-harness needs the migration",
          r0.get("use_case_category") is None)

    print("\n== 6. Helpers ==")
    check("rouge_l(identical) == 1", abs(genlib.rouge_l("a b c", "a b c") - 1.0) < 1e-9)
    check("rouge_l(disjoint) == 0", genlib.rouge_l("a b c", "x y z") == 0.0)
    check("strongest ranks critical > recommended > optional",
          genlib.strongest(["recommended", "critical", "optional"]) == "critical")

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:", FAIL)
        sys.exit(1)
    print("ALL PASS ✓  — deterministic pipeline invariants hold (no GPU needed)")


if __name__ == "__main__":
    main()
