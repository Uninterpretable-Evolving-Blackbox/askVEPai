# Rationale for `priority_by_factor.json` — moved verbatim from `vep_assistant.py` on 2026-09-22

Until 2026-09-22 the table was DERIVED at load from a `DRIVES` spec in the engine plus per-option blocks in
the catalogue. The file is now the single authored source and the spec is gone. Every comment that sat in
the spec is below, unaltered, so the reasoning (and the mentor quotes in it) survive the move. The code
lines are kept too, so a note like "see canonical note above" still resolves.

The one thing NOT in the table file is the species gate: it is a fact about each option (its
`species_restriction`), not an opinion, and is stamped on at load by `load_priority_by_factor`.

```python
# --- The importance spec, and the table DERIVED from it ---------------------------------------------
#
# This lives in the engine rather than in the generation pipeline for the same reason `intent_priorities`
# and the classifier prompt do: the shipped recommender and the pipeline must not be able to disagree
# about what a scenario's priorities are. `work/generation/seed_priorities.py` imports it back out.
#
# WHY IT IS DERIVED AND NOT A MAINTAINED FILE. The table is a pure function of this spec and the option
# catalogue, and computing all 65 options takes ~0.02 ms — there is no reason to precompute it. Keeping
# it as a generated artifact meant four copies of it existed across two trees, kept in step by hand, with
# nothing to notice when they drifted: edit the catalogue and forget to regenerate, and the shipped tool
# silently ran an older table than every measurement was taken on. Deriving it removes that class of bug
# rather than guarding against it, and reduces "how do I update an option?" to editing one file.
#
# A FILE STILL WINS IF PRESENT. That is the point of the override in load_priority_by_factor below: once
# the mentor signs off a validated table, dropping it in takes precedence over this spec, and its mere
# presence then means "a human authored this" instead of "a build step ran".
# TWO TIERS since 2026-08-19. `critical` is gone from the scheme, not merely hidden. The
# critical/recommended boundary was the one part of this table an expert reviewed, and twelve of her
# twenty edits moved options across it. Merging the DISPLAY made those corrections invisible, so they
# were never applied — while --minimal, restore_missing_* and the must-have metric went on reading the
# uncorrected boundary. Removing the tier removes the unvalidated judgement instead of hiding it.
RANK = {"recommended": 2, "optional": 1, "not_applicable": 0}

# Predictor tiering. READ THIS BEFORE CHANGING: **VEP itself ranks nothing.** vep_plugins_web_config.txt
# is a flat `available => 1` map with no rank field, and the web form lists "Missense pathogenicity" as one
# undifferentiated family. The core-vs-add-on split is OUR EDITORIAL JUDGEMENT, grounded in ACMG PP3/BP4 as
# refined by ClinGen SVI (Pejaver et al. 2022) — a clinical-genetics standard EXTERNAL to VEP. Cite it as
# ours; do not imply VEP prescribes it. The axis is METHOD INDEPENDENCE, read from each plugin's own
# catalogue description: a distinct predictor forms its own call, a derivative one consumes other
# predictors' scores and so double-counts them.
PREDICTOR_DISTINCT = ["sift", "polyphen", "cadd", "alphamissense", "eve"]
PREDICTOR_DERIVATIVE = ["revel", "clinpred", "dbnsfp"]
# Splice tiering uses a DIFFERENT axis, honestly labelled: maxentscan and dbscsnv are self-contained models,
# NOT derivative of SpliceAI, so method-independence does not separate them. The split is ADOPTION/RECENCY.
SPLICE_CORE = ["spliceai"]                 # human only; species-gated below
SPLICE_ADDON = ["maxentscan", "dbscsnv"]   # maxentscan is the ONLY all-species splice option
# Missense predictors are INAPPLICABLE to non-coding variants, not merely less important: the catalogue
# rates 9/10 regulatory_noncoding=not_applicable. CADD is the documented exception (it scores coding AND
# non-coding) and is deliberately absent from this list.
MISSENSE_ONLY = [p for p in PREDICTOR_DISTINCT + PREDICTOR_DERIVATIVE if p != "cadd"]
# `symbol` is in BASELINE_RECOMMENDED, so it went out on every purely regulatory query. Regulatory
# features carry Ensembl regulatory IDs, not gene symbols (Likhitha, 2026-08-15), so the column is
# empty for the thing such a query is annotating. Gated rather than demoted: the gate fires only when
# EVERY active region value rules it out, so a coding+regulatory query keeps it.
REGION_GATE_NONCODING = MISSENSE_ONLY + ["mutfunc", "paralogues", "mane", "protein", "nmd", "symbol"]

# WHERE-vs-WHY discipline: taxonomy_proposal §3 split region_focus from analysis_goal precisely because a
# single axis mixed *where* the variant acts with *why* you are annotating. So region_focus drives the
# STRUCTURAL annotation of a locus and analysis_goal the INTERPRETIVE. Hanging the predictor cluster off
# both re-mixed them and — since composition takes the max — made a coding+basic-consequence quick lookup
# pull in the full predictor stack.
DRIVES = {
    "region_focus": {
        "coding": {
            # tsl/appris are web_default=on, so ranking them optional would recommend LESS than the form
            # already gives. protein/nmd sit at optional in the catalogue's own columns.
            # protein promoted per her rows 2/8/9: "protein should be recommended because this is a
            # protein coding question".
            # `domains` by name, NOT `cat:protein_annotation`. The category token swept in every member,
            # and ProtVar (added 2026-09-13, category protein_annotation to match the form's section)
            # landed in RECOMMENDED on 56 tuples on nothing but its category -- past its own block, which
            # says clinical-interpretation:optional, and past its peer mutfunc, which is an add-on. Her
            # item-11 instruction is to recommend the type of tool and not endorse a product.
            "recommended": ["hgvs", "numbers", "domains", "tsl", "appris", "protein"],
            "optional": ["uniprot", "ccds", "nmd", "coding_only"],
        },
        "regulatory-noncoding": {
            # The regulatory build IS the annotation a regulatory query asks for; without it the question
            # is unanswerable, not merely under-served.
            # cell_type, mirna and enformer demoted per her rows 1/3/4/5/6/7/9: cell_type restricts
            # regulatory annotation to particular cell types, mirna is miRNA secondary structure.
            # Specialised rather than standard, so offered rather than switched on.
            "recommended": ["regulatory", "utrannotator", "canonical"],   # see canonical note above
            # cell_type stays an add-on and is NOT unpriced (David, 2026-09-14): there is no point
            # switching it on unless the user names the cell types, and when they do it is exactly what
            # they want. It is the only option in the catalogue that both adds a field (CELL_TYPE) and
            # removes rows ("Report ONLY regulatory regions that are found in the given cell type(s)"),
            # and on the form it is `cell_type_<species>`, hidden until the regulatory dropdown is moved
            # off its default to "Yes and limit by cell type". So it is offered, never switched on.
            "optional": ["cell_type", "enformer", "mirna"],
            "not_applicable": REGION_GATE_NONCODING,
        },
    },
    "analysis_goal": {
        # canonical: recommended wherever MANE is NOT. Her rows 1/7/10 verbatim, all human, are
        # "Recommended should have canonical for fallback tx when MANE isn't available", "The query
        # mentions reliable transcripts, so add mane and canonical to recommended" and "Add canonical,
        # mane, overlaps, protein to recommended" -- each CONDITIONAL on the scenario. Extending that
        # to every tuple is OUR inference, not hers, and David approved the narrower human-clinical
        # case on 2026-09-14; flag it when the sheet goes out. MANE is raised only
        # under clinical-interpretation and is gated off regulatory rows, so a basic, population-frequency
        # or regulatory query on human had no main-transcript flag at all. canonical exists for every
        # species and every gene. The clinical-interpretation block below also lists it, quoting her
        # rows directly, so the net effect is one navigation column on EVERY tuple -- simpler than
        # "wherever MANE isn't", and harmless where both are present.
        "basic-consequence": {"recommended": ["canonical"], "optional": ["most_severe", "hgvs"]},
        "clinical-interpretation": {
            # clinvar, hgvs and mane were `critical`. She corrected hgvs and mane off that tier on
            # rows 3, 5, 6 and 8 ("useful but aren't essential"); the correction was never applied
            # because it was invisible. One bucket now, so that disagreement cannot recur.
            # mavedb: measured functional evidence rather than prediction. It had NO positive priority
            # anywhere, so it could not appear in any configuration (0 of 31 rows). Likhitha and Jamie
            # asked for it independently. Its size gate lives in the catalogue, which had no
            # structural_variants key at all.
            # mastermind: promoted from optional per her row-5 note, "adds useful literature evidence".
            # canonical rides beside mane. MANE flags only genes that HAVE a MANE transcript, and it is
            # "Only available for human on the GRCh38 assembly" (vep_options.html), so on a human variant
            # in a gene MANE does not cover the user gets no navigation flag at all. Her rows 1 and 7:
            # "Recommended should have canonical for fallback tx when MANE isn't available" and "The
            # query mentions reliable transcripts, so add mane and canonical to recommended". Costs one
            # column, removes nothing. The form renders it for every species -- unlike tsl/appris/mane it
            # carries no `_stt_Homo_sapiens` class -- so the species entry below stays as it is.
            "recommended": ["clinvar", "hgvs", "mane", "canonical"] + PREDICTOR_DISTINCT + SPLICE_CORE
                           + ["phenotypes", "mavedb", "mastermind"],
            # `failed` dropped entirely per her rows 1/3/5: it includes variants flagged as failing QC,
            # so offering it as an add-on invites someone to switch on known-bad calls.
            # intact and opentargets were priced for NOTHING, so they could not appear in any
            # scenario -- while the round-2 sheet's preamble told the mentors they were reachable
            # (check_round2_ready.py, 2026-09-20). Both are interpretation aids on the form: IntAct
            # links a change to the protein interactions it disrupts, Open Targets' L2G links a
            # non-coding variant to the gene it most plausibly acts through. Offered, not recommended:
            # the pricing is ours, and neither is something we would switch on unasked.
            "optional": PREDICTOR_DERIVATIVE + SPLICE_ADDON + ["geno2mp", "loeuf",
                                                              "dosage_sensitivity", "pubmed",
                                                              "var_synonyms", "intact", "opentargets",
                                                              "mutfunc", "paralogues"],
        },
        "population-frequency": {
            # `frequency` is an ADD-ON, not a recommendation (David, 2026-09-14). The goal is to REPORT
            # frequencies; the four af_* options do that by adding columns. `--check_frequency` answers
            # the same question by DELETING variants -- measured at 4 of 12 on our cohort with freq_pop=AF
            # -- so recommending both partly answers "show me the frequencies" by removing the variants
            # whose frequencies were asked for. The form agrees: its radio ships on "No filtering", and
            # the page says "if you aren't sure, don't use any of these options!".
            # OPEN: Likhitha is checking whether most human queries are rare-variant work, which would
            # be the case for raising it again. Not yet answered -- see MENTOR_MESSAGES.md.
            "recommended": ["af_gnomade", "af_gnomadg", "af", "af_1kg", "canonical"],
            "optional": ["clinvar", "frequency"],
        },
    },
    "origin": {
        # Origin modulates which co-located source matters; it does not independently add ClinVar.
        # Composition is max-only, so listing clinvar here forced it into EVERY germline query.
        # check_existing demoted to an add-on per her rows 2/4/5/7/9/10: "finding known matches isn't
        # necessary for such a simple analysis/question". It still returns automatically wherever
        # ClinVar is switched on, because ClinVar depends on it and the dependency pass restores it.
        "germline": {"optional": ["check_existing"]},
        "somatic": {"optional": ["check_existing"], "not_applicable": ["frequency"]},
    },
    "variant_size_class": {
        # loeuf added per Likhitha 2026-08-15. Gene-level constraint is the evidence for a deletion
        # spanning a gene, where there is no per-variant score to have. It had no size rule at all,
        # so clinical-interpretation:optional was the only thing raising it and it never reached
        # RECOMMENDED on an SV row.
        "structural-CNV": {"recommended": ["gnomad_sv", "dosage_sensitivity", "loeuf"]},
    },
    "species": {
        # canonical is web_default=off and its own when_not_to_use prefers MANE for human clinical work.
        # Its documented job is the primary-transcript fallback where MANE is unavailable.
        "non-human": {"recommended": ["canonical"]},
    },
}

# Unconditional floor, under EVERY analysis_goal value. Deliberately small. NOTE anything here can never be
# `optional` anywhere, because put() is strongest-wins — which is why hgvs/mane/canonical live in DRIVES.
# One list since the tier merge (2026-08-19); `core_type` was the sole "critical" baseline.
BASELINE_RECOMMENDED = ["core_type", "symbol", "biotype"]

SIZE_GATE_SOURCE = "catalogue priority_by_factor['variant_size_class']['structural-CNV'] == 'not_applicable'"
```
