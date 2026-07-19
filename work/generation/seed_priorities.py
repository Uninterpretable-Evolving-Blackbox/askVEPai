#!/usr/bin/env python3
"""Stage 0 — author a PROVISIONAL priority_by_factor.json, FACTOR-NATIVELY, from the taxonomy
proposal's §3 "drives" clusters (research/taxonomy_proposal.md).

WHY (not the old use-case launder): the 7 use-cases are an abandoned *taxonomy*; re-keying their
priorities inherited their warts (e.g. clinvar critical for a "quick lookup") and left the default sides
(coding/regulatory) unsignalled, which over-recommended. Instead we author priorities directly from the
web-form-grounded clusters the proposal lists per factor value, plus two DETERMINISTIC gates computed
from the catalogue. Still PROVISIONAL — this is my reading of the proposal, not mentor-validated; the
resolver only reads the output file, so the mentor's real table is a one-file swap.

Structure of the output priority_by_factor.json (taxonomy_proposal §5 shape):
  option_id -> factor -> factor_value -> priority(label)

Run:
  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/generation/seed_priorities.py
"""
import json
import re
from collections import defaultdict

import genlib

RANK = {"critical": 3, "recommended": 2, "optional": 1, "not_applicable": 0}

# --- Predictor tiering ------------------------------------------------------------------------------
# READ THIS BEFORE CHANGING: **VEP itself ranks nothing.** `vep_plugins_web_config.txt` is a flat
# `available => 1` map with no rank/priority field, and the Ensembl web form lists
# "Missense pathogenicity" and "Splicing" as FLAT families; `plugins_dossier.md:112` puts CADD/REVEL/
# AlphaMissense/dbNSFP/ClinPred/EVE/SpliceAI/MaxEntScan/dbscSNV in one undifferentiated tier. So the
# core-vs-add-on split below is OUR EDITORIAL JUDGEMENT, grounded in ACMG PP3/BP4 as refined by ClinGen SVI
# (Pejaver et al. 2022) — a clinical-genetics standard EXTERNAL to VEP, which treats correlated in-silico
# predictors as ONE line of evidence. Cite it as ours; do not imply VEP prescribes it. This is exactly the
# "essential vs optional weighting" the priorities need sign-off on.
#
# The axis is METHOD INDEPENDENCE, read from each plugin's own catalogue `description`:
#   distinct   — derives a call from its own model/data
#   derivative — consumes other predictors' scores, so it double-counts the distinct ones
PREDICTOR_DISTINCT = ["sift", "polyphen", "cadd", "alphamissense", "eve"]
PREDICTOR_DERIVATIVE = ["revel", "clinpred", "dbnsfp"]
#   revel      = "ensemble method combining 13 individual pathogenicity predictors"
#   clinpred   = "incorporates existing pathogenicity scores"
#   dbnsfp     = "meta-resource aggregating many in-silico predictors (e.g. SIFT, PolyPhen-2)"
#   eve        = "unsupervised deep generative model trained on evolutionary sequence data" -> consumes NO
#                existing scores, so it is the most independent option in the set, NOT an add-on.
# `mutfunc`/`paralogues` carry category=pathogenicity_prediction but the web form files them under
# "Functional effect" on the Ensembl web form, so they are not part of this tiering.

# Splice tiering — NOTE the axis here is DIFFERENT from the pathogenicity split above. maxentscan (a
# maximum-entropy model) and dbscsnv (an AdaBoost/RF classifier) are NOT "derivative" of SpliceAI — they
# are self-contained models that consume no other tool's scores, so the method-independence axis does not
# separate them. The split is by ADOPTION/RECENCY: SpliceAI is the current community-default deep-learning
# splice predictor, MaxEntScan/dbscSNV are the older established tools kept as add-ons. Still editorial,
# still not VEP-ranked — just on a different (and honestly labelled) basis than the missense tier.
SPLICE_CORE = ["spliceai"]                 # human only (GRCh37+GRCh38) — see the species conditional below
SPLICE_ADDON = ["maxentscan", "dbscsnv"]   # maxentscan is the ONLY all-species splice option

# Missense predictors are INAPPLICABLE to non-coding variants — not merely less important. Catalogue:
# regulatory_noncoding = not_applicable for 9/10 (and for mane/protein/nmd); constraints_dossier.md:123
# "SIFT/PolyPhen 'for missense variants' ... Model as a soft dependency (recommender gate, not a CLI
# requirement): apply only to missense/coding variants". CADD is the documented exception — "a single
# deleteriousness score for coding AND non-coding variants" (catalogue: regulatory_noncoding=recommended).
MISSENSE_ONLY = [p for p in PREDICTOR_DISTINCT + PREDICTOR_DERIVATIVE if p != "cadd"]
REGION_GATE_NONCODING = MISSENSE_ONLY + ["mutfunc", "paralogues", "mane", "protein", "nmd"]

# --- Hand-authored DRIVES spec (factor value -> {priority: [tokens]}), from taxonomy_proposal §3. ---
# A token is a catalogue `category` name prefixed "cat:", or a bare option id.
#
# WHERE-vs-WHY discipline: taxonomy §3 split `region_focus` from `analysis_goal` precisely because the old
# single axis "mixed *where* the variant acts with *why* you're annotating". So region_focus drives the
# STRUCTURAL annotations of a locus (HGVS, protein, exon numbers, domains, the regulatory build) and
# analysis_goal drives the INTERPRETIVE ones (predictors, ClinVar, phenotypes, frequencies). The previous
# spec hung the predictor cluster off BOTH, which re-mixed the two axes and — because composition takes the
# max — meant a coding+basic-consequence "quick lookup" still pulled in the full predictor stack.
DRIVES = {
    "region_focus": {          # WHERE — structural annotation of the locus
        "coding": {
            # tsl/appris are web_default=on, so ranking them 'optional' would recommend LESS than the form
            # already gives. protein/nmd sit at 'optional' in the catalogue's own columns (nmd is
            # LoF-specific: "not to use ... missense, synonymous, regulatory or non-truncating variants").
            "recommended": ["hgvs", "numbers", "cat:protein_annotation", "tsl", "appris"],
            "optional": ["protein", "uniprot", "ccds", "nmd", "coding_only"],
        },
        "regulatory-noncoding": {
            # The regulatory build IS the annotation a regulatory query is asking for; without it the
            # question is unanswerable, not merely under-served (catalogue: regulatory_noncoding=critical).
            "critical": ["regulatory"],
            # catalogue rates all three regulatory_noncoding=recommended — do not demote them.
            "recommended": ["cell_type", "utrannotator", "enformer", "mirna"],
            "not_applicable": REGION_GATE_NONCODING,   # the documented recommender gate — see above
        },
    },
    "analysis_goal": {         # WHY — interpretive annotation
        "basic-consequence": {
            # "identifiers + consequence only" (taxonomy §3, the old quick-lookup).
            "optional": ["most_severe", "hgvs"],
        },
        "clinical-interpretation": {
            # hgvs and mane are rated `critical` for rare_disease_germline in the catalogue; mane is
            # additionally "the community standard" for human clinical reporting (canonical's own
            # when_not_to_use says to prefer it) — one of the two REAL priority signals we could source.
            "critical": ["clinvar", "hgvs", "mane"],
            "recommended": PREDICTOR_DISTINCT + SPLICE_CORE + ["phenotypes"],
            "optional": PREDICTOR_DERIVATIVE + SPLICE_ADDON + ["mastermind", "geno2mp", "loeuf",
                                                               "dosage_sensitivity", "pubmed",
                                                               "var_synonyms", "failed",
                                                               "mutfunc", "paralogues"],
        },
        "population-frequency": {
            "critical": ["af_gnomade", "af_gnomadg", "af", "af_1kg"],
            "recommended": ["frequency"],
            # co-located ClinVar is informative in a population scan but is not what it is FOR; a
            # clinical+population query still lifts this to critical via the clinical value (max wins).
            "optional": ["clinvar"],
        },
    },
    "origin": {
        # Taxonomy §3: origin drives "frequency-filter interpretation, and COSMIC vs dbSNP/ClinVar
        # *emphasis* on check_existing" — i.e. it modulates which co-located source matters, it does not
        # independently add ClinVar. Composition is max-only (it can add, never subtract), so listing
        # clinvar here forced it into EVERY germline query regardless of goal — reproducing the very wart
        # this file was written to escape ("clinvar critical for a quick lookup"). ClinVar is driven by
        # analysis_goal alone: critical for clinical, optional for population, absent for basic.
        "germline": {"recommended": ["check_existing"]},
        "somatic": {"recommended": ["check_existing"], "not_applicable": ["frequency"]},
    },
    "variant_size_class": {
        "structural-CNV": {"critical": ["gnomad_sv"], "recommended": ["dosage_sensitivity"]},
    },
    "species": {
        # canonical is web_default=off and its own when_not_to_use says "For human clinical analysis prefer
        # MANE (mane) as the community standard" — so it is NOT an unconditional baseline. Its documented
        # job is the primary-transcript fallback "especially for non-human species where MANE is not
        # available" (mane is human-only, so it is species-gated out there anyway). This one IS genuinely
        # species-conditional: any non-human query wants a primary transcript, whatever its goal.
        #
        # maxentscan is NOT listed here, though it is the only all-species splice option (spliceai/dbscsnv
        # are human-only and get gated, so a non-human clinical query has no *recommended* splice tool, only
        # maxentscan as an add-on). Promoting it under `species` would recommend a SPLICE predictor to every
        # non-human query — including population-frequency scans that have no splice interest at all.
        # Composition is max-only across independent factor values, so "recommended IFF non-human AND
        # clinical" is not expressible: a cross-factor conjunction has no home in this scheme. Rather than
        # hack it, maxentscan stays a clinical splice add-on and the limitation is recorded here.
        "non-human": {"recommended": ["canonical"]},
    },
}

# Unconditional floor — under EVERY analysis_goal value (every query carries >=1). Kept deliberately small.
# `core_type` is critical in all seven catalogue columns ("Always choose a transcript database") and is a
# radiolist that always carries a value. `symbol`/`biotype` are web_default=on and rated `recommended`
# everywhere — the catalogue never rates symbol critical, and it documents an omission case ("Only omit for
# minimal machine-parsed output"), so do NOT escalate it.
# NOTE: anything listed here can never be `optional` anywhere, because put() is strongest-wins — which is
# why `hgvs`/`mane`/`canonical` live in DRIVES, where they can vary by factor value.
BASELINE_CRITICAL = ["core_type"]
BASELINE_RECOMMENDED = ["symbol", "biotype"]

# Deterministic size gate: options not_applicable to structural variants.
#
# This reads the catalogue's OWN `structural_variants` column rather than a hand-authored category list.
# A category list (pathogenicity_prediction + splice_prediction, minus a manual `cadd` exemption) misses
# options the catalogue itself marks not_applicable for SVs — enformer, utrannotator, mutfunc, paralogues,
# domains, protein, uniprot, ccds, coding_only, geno2mp, var_synonyms — which would then be offered on
# structural-CNV rows. The catalogue column is the source-grounded truth (it is how the web form behaves),
# it is a strict superset of the category gate, and it makes the `cadd` exemption automatic (cadd is
# `recommended`, not `not_applicable`, for SVs — so it is never gated).
# Kept as a marker constant for the verify suite / audit; the actual set is derived in main() from the KB.
SIZE_GATE_SOURCE = "catalogue priority_by_use_case['structural_variants'] == 'not_applicable'"


def expand(tokens, by_cat):
    ids = []
    for t in tokens:
        ids.extend(by_cat[t[4:]] if t.startswith("cat:") else [t])
    return ids


def main():
    catalogue = genlib.load_catalogue()
    va = genlib.load_va()
    ids = {o["id"] for o in catalogue}
    by_cat = defaultdict(list)
    for o in catalogue:
        by_cat[o.get("category", "?")].append(o["id"])
    species_restr = {o["id"]: o.get("species_restriction", "all species") for o in catalogue}

    priorities = {oid: defaultdict(dict) for oid in ids}

    def put(oid, factor, value, label):
        if oid not in priorities:
            return
        cur = priorities[oid][factor].get(value)
        if cur is None or RANK[label] > RANK[cur]:   # strongest wins; not_applicable only if nothing else
            priorities[oid][factor][value] = label

    # (1) hand-authored DRIVES
    for factor, valmap in DRIVES.items():
        for value, prio_tokens in valmap.items():
            for label, tokens in prio_tokens.items():
                for oid in expand(tokens, by_cat):
                    put(oid, factor, value, label)
    # (2) baseline floor under every analysis_goal value
    for value in ("basic-consequence", "clinical-interpretation", "population-frequency"):
        for oid in BASELINE_CRITICAL:
            put(oid, "analysis_goal", value, "critical")
        for oid in BASELINE_RECOMMENDED:
            put(oid, "analysis_goal", value, "recommended")
    # (3) deterministic species gate. Two cases:
    #   (a) human-only options — the checker's own predicate (gnomAD, ClinVar, PolyPhen, MANE...).
    #   (b) NARROW non-human options: species_restriction "human + <one species> only" (var_synonyms =
    #       human+pig, ccds = human+mouse). These are NOT human-only, so (a) keeps them — and they would
    #       then be offered on the WRONG non-human species (var_synonyms, a human+pig option, on a mouse
    #       query). The species factor is binary (human / non-human) and cannot say "pig but not mouse", so
    #       for a generic non-human query we cannot guarantee the species matches; gate them. Cost is tiny
    #       (both are optional-tier, and pig is never sampled). This is the binary-species-granularity
    #       limitation — flagged for review.
    narrow_nonhuman = re.compile(r"human\s*\+\s*\w+.*only", re.IGNORECASE)
    for oid, restr in species_restr.items():
        if va._is_human_only(restr) or narrow_nonhuman.search(restr or ""):
            put(oid, "species", "non-human", "not_applicable")
    # (4) deterministic size gate — driven by the catalogue's own structural_variants column (see
    #     SIZE_GATE_SOURCE). Strict superset of the old hand-authored gate; cadd auto-exempt (it is
    #     `recommended` for SVs in the catalogue, not `not_applicable`).
    for oid, opt in ((o["id"], o) for o in catalogue):
        if opt.get("priority_by_use_case", {}).get("structural_variants") == "not_applicable":
            put(oid, "variant_size_class", "structural-CNV", "not_applicable")

    out = {
        "_status": ("PROVISIONAL — authored factor-natively from taxonomy_proposal.md §3 'drives' clusters "
                    "by seed_priorities.py. NOT mentor-validated. Replace this file wholesale on sign-off; "
                    "the resolver reads it, so no code changes are needed."),
        "_authoring": {
            "drives": DRIVES,
            "baseline_critical": BASELINE_CRITICAL,
            "baseline_recommended": BASELINE_RECOMMENDED,
            "predictor_tiers": {
                "_basis_missense": ("METHOD INDEPENDENCE (distinct vs derivative): a distinct predictor "
                                    "forms its own call; a derivative one (REVEL/ClinPred/dbNSFP) consumes "
                                    "other predictors' scores, so it double-counts them. Per ACMG PP3/BP4 / "
                                    "ClinGen SVI (Pejaver et al. 2022)."),
                "_basis_splice": ("ADOPTION/RECENCY, not independence: MaxEntScan and dbscSNV are "
                                  "independent models, NOT derivative of SpliceAI. SpliceAI is the current "
                                  "community default; the older tools are kept as add-ons."),
                "_caveat": ("VEP itself ranks NONE of these — both splits are our editorial judgement on "
                            "standards external to VEP. This is the 'essential vs optional' call the mentor "
                            "was asked to adjudicate."),
                "distinct": PREDICTOR_DISTINCT, "derivative": PREDICTOR_DERIVATIVE,
                "splice_core": SPLICE_CORE, "splice_addon": SPLICE_ADDON,
            },
            "species_gate": ("not_applicable for non-human where _is_human_only(species_restriction), OR "
                             "where the restriction is a narrow 'human + <one species> only' set that the "
                             "binary species factor cannot guarantee matches the query's species "
                             "(var_synonyms=human+pig, ccds=human+mouse)"),
            "size_gate": SIZE_GATE_SOURCE,
            "region_gate": {"value": "regulatory-noncoding", "not_applicable": REGION_GATE_NONCODING,
                            "_amends": ("taxonomy_proposal §3 calls region_focus 'purely soft'; the "
                                        "catalogue rates 9/10 missense predictors regulatory_noncoding="
                                        "not_applicable and constraints_dossier.md:123 prescribes a "
                                        "recommender gate. Proposed amendment — needs mentor sign-off.")},
        },
        "_generated_from": genlib.Path(genlib.os.environ["VEP_OPTIONS_FILE"]).name,
        "priorities": {oid: dict(fac) for oid, fac in priorities.items()},
    }
    out_path = genlib.CONFIG_DIR / "priority_by_factor.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    n_priced = sum(1 for e in priorities.values() if e)
    n_sp_gate = sum(1 for e in priorities.values() if e.get("species", {}).get("non-human") == "not_applicable")
    n_sz_gate = sum(1 for e in priorities.values()
                    if e.get("variant_size_class", {}).get("structural-CNV") == "not_applicable")
    print(f"Wrote {out_path.relative_to(genlib.ROOT)}")
    print(f"  {len(ids)} options; {n_priced} carry >=1 factor priority; "
          f"{n_sp_gate} species-gated (human-only), {n_sz_gate} size-gated (SNV-only) for structural-CNV.")
    unpriced = sorted(oid for oid, e in priorities.items() if not e)
    if unpriced:
        print(f"  {len(unpriced)} options intentionally unpriced (never auto-enabled): "
              f"{', '.join(unpriced[:12])}{'...' if len(unpriced) > 12 else ''}")


if __name__ == "__main__":
    main()
