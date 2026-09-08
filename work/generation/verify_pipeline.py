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
    check(f"all {len(ids)} catalogue options present in priority table",
          set(pbf["priorities"]) == ids, f"{len(pbf['priorities'])} vs {len(ids)}")
    check("priority table self-labels PROVISIONAL", "PROVISIONAL" in pbf.get("_status", ""))
    # The catalogue's own priority_by_factor blocks are the one part of the config a maintainer edits by
    # hand to make a new option recommendable. Every typo in them used to be silently ignored, so this
    # asserts they are well-formed rather than merely present.
    _pb = va.validate_priority_blocks(cat, factors)
    check("catalogue priority_by_factor blocks are all well-formed",
          not _pb, "; ".join(_pb) if _pb else "0 problems")


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
    # Reads the rule where it NOW lives. It moved out of the legacy use-case table on 2026-08-19; if
    # this kept reading the old column it would pass while a new-location edit went unenforced.
    sv_na = {o["id"] for o in cat
             if (o.get("priority_by_factor") or {}).get("variant_size_class", {}).get(
                 "structural-CNV") == "not_applicable"}
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

    print("\n== 6. Under-recommendation is repaired (the prose path) ==")
    # The checker only ever REMOVED (species/assembly/conflict) or added a dependency; nothing checked
    # that the options the scenario REQUIRES are present. A short or truncated model draft therefore
    # shipped as "authoritative" with its must-haves missing, and --full made it worse by adding only the
    # optional tier: observed on the README quickstart query, a two-option draft produced a config with
    # every derivative predictor (REVEL/ClinPred/dbNSFP) and none of the distinct ones they consume.
    ft = {"species": "human", "origin": "germline", "variant_size_class": "small",
          "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
    q = "germline exome variants, rare disease, human GRCh38"
    resolved = va.intent_priorities(ft, cat, pbf, factors)
    # The must-have set IS the RECOMMENDED bucket since the tier removal on 2026-08-19. Left as
    # `crit` because the assertions below read it by that name.
    crit = {o for o, (_e, p, g) in resolved.items() if p == "recommended" and not g}

    def run_draft(draft, level):
        en, dis = set(draft), set()
        va.check_and_fix_violations(en, dis, cat, corpus, q)
        va.restore_missing_recommended(en, dis, resolved, cat, corpus, q)
        if level != "standard":
            va.apply_config_level(en, dis, resolved, level, cat, corpus, q)
        return en

    for lvl in ("standard", "minimal", "full"):
        en = run_draft({"core_type", "hgvs"}, lvl)      # the observed two-option draft
        check(f"a 2-option draft still yields every recommended option (--{lvl})",
              not (crit - en), f"missing {sorted(crit - en)}")
    # --full must mean every tier the scenario justifies, not just the add-ons.
    #
    # The FACTOR table is not the only gate: the query names GRCh38, and the checker drops sources whose
    # data exists only on the other build (Geno2MP is GRCh37-only). Those are correctly absent from the
    # final set even though the factor table prices them, so they are subtracted here rather than
    # asserted away — otherwise this check would fight the assembly gate it wants to keep.
    full = run_draft({"core_type", "hgvs"}, "full")
    asm = va.infer_assembly(q)
    build_blocked = {o["id"] for o in cat
                     if (r := va._assembly_restriction(o.get("species_restriction", ""))) and asm not in r}
    want = {o for o, (_e, p, g) in resolved.items()
            if p in ("recommended", "optional") and not g} - build_blocked
    check("--full enables recommended + optional, not optional alone",
          not (want - full), f"missing {sorted(want - full)[:5]}")
    check(f"...and the {asm} assembly gate still removes the other build's sources",
          bool(build_blocked) and not (build_blocked & full), f"blocked={sorted(build_blocked)}")
    # The ACMG-grounded tiering must never invert: derivative predictors consume the distinct ones'
    # scores, so shipping them without any distinct predictor is worse than shipping neither.
    deriv, dist = {"revel", "clinpred", "dbnsfp"}, {"sift", "polyphen", "cadd", "alphamissense", "eve"}
    check("derivative predictors never ship without the distinct ones they consume",
          not (deriv & full) or bool(dist & full),
          f"derivative={sorted(deriv & full)} distinct={sorted(dist & full)}")
    # An empty draft is the worst case and must still produce a usable core.
    check("even an EMPTY draft is repaired to the full recommended set",
          not (crit - run_draft(set(), "standard")))

    print("\n== 7. The two-tier display is a regrouping, not a filter ==")
    # The whole case for merging critical into recommended was that it costs nothing: the tiers were
    # already enabled together, so the merge only relabels. That claim is only true while
    # tier_by_importance stays a pure partition of the SAME enabled set — the failure mode is a future
    # edit that drops an option on the way into a bucket, which would silently shrink what the user is
    # shown while every option-set metric stays green, because the metrics never read the display.
    #
    # Checked across every factor tuple the sampler can produce, not one scenario, because a bucket is
    # only ever wrong for particular priorities and a single tuple exercises few of them.
    tuples = [{"species": sp, "origin": og, "variant_size_class": sz,
               "region_focus": rg, "analysis_goal": gl}
              for sp in ("human", "non-human") for og in ("germline", "somatic")
              for sz in ("small", "structural-CNV")
              for rg in (["coding"], ["regulatory-noncoding"], ["coding", "regulatory-noncoding"])
              for gl in (["basic-consequence"], ["clinical-interpretation"], ["population-frequency"])]
    lost, promoted, offered_on = [], [], []
    for t in tuples:
        r = va.intent_priorities(t, cat, pbf, factors)
        en = {o for o, (e, _, _) in r.items() if e}
        b = va.tier_by_importance(en, r)
        if set(b["recommended"]) | set(b["addons_on"]) | set(b["unpriced"]) != en:
            lost.append(va.factor_slug(t))
        # An option rated `optional` must not be swept into RECOMMENDED by the merge — that would turn
        # the relabel into an actual change to what the sheet says is switched on.
        if any(r[o][1] == "optional" for o in b["recommended"]):
            promoted.append(va.factor_slug(t))
        # "Offered" means NOT enabled. An option in both lists would read as on and off at once.
        if set(b["addons_offered"]) & en:
            offered_on.append(va.factor_slug(t))
    check(f"every enabled option lands in exactly one bucket ({len(tuples)} tuples)",
          not lost, f"lost on {lost[:3]}")
    check("the display bucket takes `recommended` only — no `optional` is promoted",
          not promoted, f"promoted on {promoted[:3]}")
    check("options offered as add-ons are never also enabled",
          not offered_on, f"both on {offered_on[:3]}")
    # The third tier is GONE as of 2026-08-19, not merely hidden — see the RANK comment in
    # vep_assistant.py. This asserts the removal rather than the old invariant: if `critical` ever
    # reappears in a resolved row, something has reintroduced a boundary nobody has validated.
    r = va.intent_priorities(ft, cat, pbf, factors)
    check("no `critical` survives anywhere in a resolved row",
          not any(p == "critical" for _e, p, _g in r.values()),
          sorted({p for _e, p, _g in r.values() if p})),

    # The displayed set and the generated command must be the SAME set. Before 2026-08-19 the output
    # carried four buckets, two of which were switched on, and the command silently spanned all of
    # them — so "ALSO AVAILABLE, not switched on" could appear in the command the user was told to
    # run. One list now, and this asserts it stays one.
    ft2 = {"species": "human", "origin": "germline", "variant_size_class": ["small"],
           "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
    res2 = va.intent_priorities(ft2, cat, pbf, factors)
    on2 = {o for o, (e, _p, _g) in res2.items() if e}
    t2 = va.tier_by_importance(on2, res2)
    shown = set(t2["recommended"]) | set(t2["unpriced"]) | set(t2["addons_on"])
    check("what is displayed as switched on IS the enabled set", shown == on2,
          f"displayed {len(shown)} vs enabled {len(on2)}; diff {sorted(shown ^ on2)[:4]}")
    check("nothing appears in both 'switch on' and 'also available'",
          not (shown & set(t2["addons_offered"])), sorted(shown & set(t2["addons_offered"]))[:4])

    print("\n== 8. The shipped CLI path — wiring, not just functions ==")
    # These three exist because the suites passed while the CLI was broken. test_user_context.py
    # calls the checker and the restore pass with `assembly_override=` itself, so it proved the
    # FUNCTIONS honour a stated build while run_recommend was not handing them one: `--assembly
    # GRCh37` was acknowledged on screen, used to suppress the assembly question, then dropped, and
    # the run shipped MANE, EVE and MaveDB. A test of a function is not a test of its caller.
    import inspect
    body = inspect.getsource(va.run_recommend)
    # The taxonomy's one HARD rule — somatic must not get the common-variant pre-filter — is the
    # only gate whose violation destroys data rather than adding a column. The resolver never enables
    # a gated option; until 2026-08-24 nothing stopped the MODEL from proposing one, and the stored
    # eval logs show it overriding a gate 33 times, 10 of them exactly this one.
    ft_som = {"species": "human", "origin": "somatic", "variant_size_class": ["small"],
              "region_focus": ["coding"], "analysis_goal": ["population-frequency"]}
    res_som = va.resolve_for_query(ft_som, cat)
    check("the somatic hard rule gates `frequency` in the table", res_som["frequency"][2])
    en, dis = {"frequency", "sift"}, set()
    v = va.check_and_fix_violations(en, dis, cat, corpus, "somatic tumour", resolved=res_som)
    check("a model-proposed gate violation is removed, not shipped",
          "frequency" not in en and any(x["type"] == "scenario" for x in v), sorted(en))
    en, dis = {"frequency", "sift"}, set()
    va.check_and_fix_violations(en, dis, cat, corpus, "somatic tumour")
    check("...and without `resolved` the checker is unchanged (callers opt in)",
          "frequency" in en, sorted(en))

    # The safety property that makes the gate rule non-destructive: run the RESOLVER'S OWN enabled
    # set back through the checker for every tuple and it must touch nothing. The rule can then only
    # ever fire on an option the MODEL added, never on the configuration the table itself specifies.
    scen_hits = []
    for sp in ("human", "non-human"):
        for org in ("germline", "somatic"):
            for sz in ("small", "structural-CNV"):
                for rf in ("coding", "regulatory-noncoding"):
                    for ag in ("basic-consequence", "clinical-interpretation", "population-frequency"):
                        t = {"species": sp, "origin": org, "variant_size_class": [sz],
                             "region_focus": [rf], "analysis_goal": [ag]}
                        rr = va.resolve_for_query(t, cat)
                        e2 = {o for o, (en_, _p, _g) in rr.items() if en_}
                        vv = va.check_and_fix_violations(e2, set(), cat, corpus, "x", resolved=rr)
                        scen_hits += [x for x in vv if x["type"] == "scenario"]
    check("the gate rule never strips the resolver's own configuration (48 tuples)",
          not scen_hits, f"{len(scen_hits)} unexpected")

    for fn in ("check_and_fix_violations", "restore_missing_recommended", "apply_config_level"):
        i = body.find(fn + "(")
        call = body[i:body.find(")", i) + 1] if i >= 0 else ""
        ok = (i >= 0 and "assembly_override" in call and "species_override" in call
              and ("resolved" in call or fn != "check_and_fix_violations"))
        check(f"run_recommend hands the stated assembly AND species to {fn}",
              ok, "found" if ok else "MISSING — a stated fact will not reach the gate")

    # The gate itself, at the two ends: told the build, it removes the other build's sources; told
    # nothing, it stays out of the way (fail-open is deliberate — see test_user_context.py).
    en, dis = {"mane", "eve", "mavedb", "sift"}, set()
    va.check_and_fix_violations(en, dis, cat, corpus, "human exome", assembly_override="GRCh37")
    check("a stated GRCh37 removes every GRCh38-only source", en == {"sift"}, sorted(en))

    # The species mirror of the same wiring bug: `--species human` on a query whose TEXT says mouse
    # must stop the gate re-reading "mouse" out of the prose — the human-only options the table
    # recommends were being stripped inside restore's re-check, whose violations are never printed.
    en, dis = {"clinvar", "cadd", "sift", "check_existing"}, set()
    va.check_and_fix_violations(en, dis, cat, corpus, "somatic SNVs from a mouse tumour",
                                species_override="human")
    check("a stated human survives mouse wording in the text",
          {"clinvar", "cadd"} <= en, sorted(en))
    en, dis = {"clinvar", "cadd", "sift", "check_existing"}, set()
    va.check_and_fix_violations(en, dis, cat, corpus, "somatic SNVs from a mouse tumour")
    check("...and without the override the text still gates (unchanged behaviour)",
          "clinvar" not in en and "cadd" not in en, sorted(en))

    # A tick the model's own line contradicts. Observed live: the model wrote `✓ regiulatory
    # [source: regulatory, priority=NOT APPLICABLE]` with `Reason: Not applicable ...`, and a
    # coding-only exome run shipped --regulatory carrying "Not applicable" as its justification.
    aliases = va.build_option_aliases(cat)
    draft = ("\u2713 sift [source: sift, priority=recommended] confidence: high\n"
             "  Reason: Standard missense predictor.\n"
             "\u2713 regiulatory [source: regulatory, priority=NOT APPLICABLE] confidence: high\n"
             "  Reason: Not applicable as the focus is explicitly on coding regions.\n"
             "\u2713 most_severe [source: most_severe] confidence: high\n"
             "  Reason: Disabled because clinical interpretation needs every consequence.\n")
    p_en, p_dis = va.extract_recommendations(draft, aliases)
    check("a tick its own priority field contradicts is read as OFF",
          "regulatory" in p_dis and "regulatory" not in p_en, f"enabled={sorted(p_en)}")
    check("a tick its own Reason contradicts is read as OFF",
          "most_severe" in p_dis and "most_severe" not in p_en, f"disabled={sorted(p_dis)}")
    check("an uncontradicted tick is still an enable", p_en == {"sift"}, sorted(p_en))
    check("every overruled tick is reported, never silent",
          "regulatory" in va.format_marker_overrides(
              va.extract_recommendations_detailed(draft, aliases), cat))

    # The web app calls this without reason_by_id; the parameter defaults to None and the body used
    # to call .get on it.
    res3 = va.intent_priorities(ft2, cat, pbf, factors)
    on3 = {o for o, (e, _p, _g) in res3.items() if e}
    # Header renamed 2026-09-08 ("SWITCH THESE ON" -> "RECOMMENDED"): the tool does not run VEP, so
    # it cannot switch anything on. The check is that the call SURVIVES a None reason_by_id, not the
    # wording, so it asserts on the tier name the output schema already uses.
    check("format_corrected_config survives a caller that passes no per-option prose",
          "RECOMMENDED" in va.format_corrected_config(on3, set(), cat, [], resolved=res3))

    print("\n== 8b. One VEP run per variant size ==")
    # The web form cannot express a configuration covering both sizes at once (CADD's annotation-file
    # drop-down forces the choice), so a both-size scenario resolves to two passes. These checks are the
    # ones that would fail if the split ever started LOSING or INVENTING options, which is the only way
    # it could be worse than the union configuration it replaced.
    both = {"species": "human", "origin": "germline",
            "variant_size_class": ["small", "structural-CNV"],
            "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
    passes = va.size_passes(both)
    check("a both-size scenario resolves to two passes", len(passes) == 2,
          " -> ".join(lbl for _v, lbl, _t in passes))
    check("short variants come first", passes[0][0] == "small")
    check("each pass pins the size to exactly one value",
          all(len(va.active_values(pt)["variant_size_class"]) == 1 for _v, _l, pt in passes))
    check("a pass changes nothing but the size",
          all({k: v for k, v in pt.items() if k != "variant_size_class"}
              == {k: v for k, v in both.items() if k != "variant_size_class"}
              for _v, _l, pt in passes))
    check("a single-size scenario still resolves to one pass",
          len(va.size_passes({**both, "variant_size_class": ["small"]})) == 1)

    def _on(ft):
        return {o for o, (e, _p, _g) in va.intent_priorities(ft, cat, pbf, factors).items() if e}

    # THE INVARIANT THAT MATTERS. Splitting must be a re-assignment, not a re-decision: every option the
    # single configuration switched on is switched on by exactly one of the two passes, and no pass
    # invents anything the union did not already have. Checked over every both-size factor tuple, not
    # one example.
    diffs, tuples = [], 0
    for spc in factors["factors"]["species"]["values"]:
        for org in factors["factors"]["origin"]["values"]:
            for reg in (["coding"], ["regulatory-noncoding"], ["coding", "regulatory-noncoding"]):
                for goal in ([g] for g in factors["factors"]["analysis_goal"]["values"]):
                    ft = {"species": spc, "origin": org,
                          "variant_size_class": ["small", "structural-CNV"],
                          "region_focus": reg, "analysis_goal": goal}
                    tuples += 1
                    union = _on(ft)
                    split = set().union(*(_on(pt) for _v, _l, pt in va.size_passes(ft)))
                    if union != split:
                        diffs.append(ft)
    check("the two passes together enable exactly what one config did, on every both-size tuple",
          not diffs, f"{tuples} tuples, {len(diffs)} differ")

    a = _on(passes[0][2])
    b = _on(passes[1][2])
    check("the passes are not the same configuration twice", a != b,
          f"{len(a - b)} only in short, {len(b - a)} only in structural")

    # CADD is the one control whose VALUE depends on the size, and it is the reason the split exists.
    small_lab, _ = va.size_dependent_choice("cadd", "small", cat)
    sv_lab, _ = va.size_dependent_choice("cadd", "structural-CNV", cat)
    check("CADD takes a different annotation file in each pass",
          bool(small_lab) and bool(sv_lab) and small_lab != sv_lab, f"{small_lab} vs {sv_lab}")
    _lab, why37 = va.size_dependent_choice("cadd", "structural-CNV", cat, "GRCh37")
    _lab, why38 = va.size_dependent_choice("cadd", "structural-CNV", cat, "GRCh38")
    _lab, whyopen = va.size_dependent_choice("cadd", "structural-CNV", cat, None)
    check("the SV annotation file is refused on a stated GRCh37", bool(why37), why37)
    check("...allowed on GRCh38, and left open when no build is stated",
          not why38 and not whyopen)
    dropme = {"cadd", "sift"}
    gone = va.drop_unavailable_size_values(dropme, cat, "structural-CNV", "GRCh37")
    check("an option with no usable file for this pass is dropped, not left on empty",
          [o for o, _w in gone] == ["cadd"] and dropme == {"sift"})

    print("\n== 9. Helpers ==")
    check("rouge_l(identical) == 1", abs(genlib.rouge_l("a b c", "a b c") - 1.0) < 1e-9)
    check("rouge_l(disjoint) == 0", genlib.rouge_l("a b c", "x y z") == 0.0)
    check("strongest ranks recommended > optional",
          genlib.strongest(["optional", "recommended"]) == "recommended")
    # `critical` is no longer a known label, so it must not outrank anything — a stale table or a
    # hand-edited priority file carrying it should be ignored, not silently treated as the top tier.
    check("a stray `critical` label is ignored rather than ranked",
          genlib.strongest(["optional", "critical"]) == "optional")

    print("\n" + "=" * 62)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:", FAIL)
        sys.exit(1)
    print("ALL PASS ✓  — deterministic pipeline invariants hold (no GPU needed)")


if __name__ == "__main__":
    main()
