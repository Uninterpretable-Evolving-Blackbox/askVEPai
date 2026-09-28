#!/usr/bin/env python3
"""Author the SILVER reference set (~30) for mentor validation.

Configs come from a hand-built, DOC-GROUNDED priority rule set (`doc_priority`, written directly from the
catalogue's `when_to_use`/`when_not_to_use` fields, which are distilled + adversarially-verified from Ensembl
release/115). This is deliberately an INDEPENDENT rule set from the pipeline's `priority_by_factor.json` — so
comparing the two validates the pipeline's priority table. Hard gates (species via the checker's own
_is_human_only; size for SNV-only predictors/splice/SNV-frequency) are applied so every config is
checker-clean by construction. Queries are hand-written (varied phrasing/persona/terminology), each faithful
to its factor tuple. Output labelled SILVER (Opus-authored) — NOT validated gold.

  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json python evidence/legacy_superseded/use_cases/author_reference_set.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parents[2] / "generation"
sys.path.insert(0, str(GEN))
import genlib  # noqa: E402

RANK = {"critical": 3, "recommended": 2, "optional": 1, "off": 0}

# 30 hand-written queries, index-aligned to the sampled tuples (seed 42). Each expresses its five factors in
# varied phrasing/terminology/persona; faithfulness is verified by the Stage-4 factor round-trip afterwards.
QUERIES = [
    # 1 human germline SV coding+reg basic+clinical
    "I have germline whole-genome data from a rare-disease family and I'm looking at large copy-number changes — big deletions and duplications. I need both a quick read on what genes and regulatory regions they hit and whether any look clinically relevant.",
    # 2 non-human somatic small coding population
    "We sequenced tumours from a zebrafish cancer model and called point mutations and small indels in coding genes. I mainly want to know how common these variants are in the reference zebrafish population.",
    # 3 human germline small coding+reg basic+population
    "Annotating germline SNVs and small indels from a human cohort, across both coding and non-coding regions — I just want the basic consequence and how frequent each one is in the population.",
    # 4 non-human somatic SV regulatory clinical
    "I'm studying somatic structural variants — large deletions and rearrangements — in mouse tumours, focused on non-coding regulatory regions, and I want to interpret which ones are likely functionally important.",
    # 5 non-human germline small coding+reg basic+population
    "I have inherited small variants (SNVs/indels) from a population survey of wild deer mice, spanning coding and regulatory regions. I want basic consequences and population allele frequencies.",
    # 6 human somatic SV regulatory clinical
    "Somatic copy-number and structural variants from a human tumour cohort, focused on non-coding regulatory elements — I want to interpret their likely clinical/functional significance.",
    # 7 non-human germline SV coding+reg clinical+population
    "Germline structural variants (large CNVs) in a chicken breeding population, across coding and regulatory regions — I'd like functional interpretation and how common each CNV is in the population.",
    # 8 human somatic small coding basic
    "I've called somatic point mutations in the coding regions of a human tumour sample and I just need a quick consequence call on each — nothing fancy.",
    # 9 human germline small coding+reg clinical+population
    "Germline SNVs and small indels from a rare-disease patient's genome, spanning coding and regulatory regions. I want full clinical interpretation and population frequencies for ACMG filtering.",
    # 10 non-human somatic SV coding basic
    "Large somatic deletions and duplications from a rat tumour WGS run — I only need to know which protein-coding genes they disrupt, a quick overview.",
    # 11 human germline small coding+reg clinical+population
    "I'm doing diagnostic interpretation of a patient's germline exome and genome — coding and regulatory single-nucleotide and small indel variants — and I need pathogenicity evidence plus gnomAD frequencies.",
    # 12 non-human somatic SV regulatory basic
    "Somatic structural variants in the non-coding genome of pig tumour samples — I just want a quick read on which regulatory features are affected.",
    # 13 non-human somatic SV coding+reg clinical+population
    "Somatic CNVs from Drosophila tumour models, coding and regulatory, and I'd like functional interpretation plus how common the events are in the population.",
    # 14 human germline small regulatory basic
    "I have a handful of inherited non-coding single-nucleotide variants in a person, sitting in enhancer/promoter regions, and I just want the basic regulatory consequence.",
    # 15 non-human germline small coding+reg clinical+population
    "Inherited SNVs and small indels from a cohort of laboratory mice, across coding and regulatory regions — I want functional interpretation and population frequencies.",
    # 16 human somatic SV coding basic
    "Somatic large deletions/duplications in a human tumour, protein-coding focus — just a quick list of which genes are hit.",
    # 17 human germline small coding+reg basic+population
    "Germline point variants and small indels from a healthy human population study, coding and non-coding — basic consequence plus allele frequencies to flag common ones.",
    # 18 non-human somatic SV regulatory clinical
    "I'm interpreting somatic structural variants in the regulatory, non-coding genome of a mouse cancer model and want to judge their likely functional impact.",
    # 19 human somatic SV coding+reg basic+clinical
    "Somatic copy-number variants in a human tumour, coding and regulatory — I want both a quick overview of what's disrupted and a clinical interpretation of the important ones.",
    # 20 non-human germline small coding population
    "Inherited coding SNVs from a large population panel of Atlantic salmon — my only interest is the population allele frequency of each.",
    # 21 non-human germline small coding+reg basic+population
    "Germline small variants from a population study in domestic dogs, coding and regulatory — I want basic consequences and how common each variant is.",
    # 22 human somatic SV coding clinical
    "Somatic structural variants disrupting protein-coding genes in a human cancer sample — I want to interpret which are likely clinically actionable.",
    # 23 non-human germline small coding+reg basic+population
    "A population catalogue of inherited SNVs and indels in honeybees, spanning coding and regulatory sequence — basic consequence plus allele frequency, please.",
    # 24 human somatic SV regulatory clinical
    "Somatic non-coding structural variants from a human tumour, in regulatory regions — I want to interpret their functional/clinical relevance.",
    # 25 non-human somatic small coding+reg clinical+population
    "Somatic point mutations in a mouse tumour, coding and regulatory, and I'd like functional interpretation together with population frequency context.",
    # 26 human germline SV coding basic
    "I have inherited copy-number variants affecting protein-coding genes in a person's genome and just need a quick overview of what they disrupt.",
    # 27 human somatic small coding+reg basic+clinical
    "Somatic SNVs and small indels in a human tumour, coding and regulatory regions — I want a quick consequence overview and clinical interpretation of the drivers.",
    # 28 non-human germline SV regulatory population
    "Germline structural variants in the non-coding regulatory genome of a cattle breeding population — my focus is how common each variant is across the population.",
    # 29 human germline SV coding+reg basic+population
    "Inherited copy-number variants in a human population cohort, coding and regulatory — I want basic consequences and population frequencies.",
    # 30 non-human somatic small regulatory clinical
    "Somatic point mutations in the regulatory, non-coding genome of a zebrafish tumour — I want to interpret their likely functional significance.",
]

# SNV-level categories the structural-CNV gate removes (need a point variant / protein consequence).
SIZE_GATE_CATEGORIES = {"pathogenicity_prediction", "splice_prediction"}
SIZE_GATE_IDS = {"af_gnomade", "af_gnomadg", "af", "af_1kg"}   # SNV frequency panels -> swap for gnomAD-SV


def doc_priority(oid, cat, tags):
    """DOC-GROUNDED priority for one option given the active factor tags. Returns critical/recommended/
    optional/off. Written from the catalogue when_to_use/when_not_to_use guidance (release/115)."""
    (human, nonhuman, germline, somatic, small, sv, coding, regulatory,
     basic, clinical, population) = (tags[k] for k in
        ("human", "nonhuman", "germline", "somatic", "small", "sv", "coding",
         "regulatory", "basic", "clinical", "population"))
    category = cat.get(oid, "?")

    # --- baseline identifiers (all species, "almost always useful") ---
    if oid == "symbol": return "critical"
    if oid in ("core_type", "biotype"): return "recommended"
    if oid == "canonical": return "recommended"                       # primary transcript (esp. non-human)
    if oid == "transcript_version": return "optional"

    # --- human clinical reporting identifiers ---
    if oid == "mane": return "recommended" if (human and (clinical or coding)) else "off"
    if oid == "hgvs": return "recommended" if clinical else "optional"
    if oid == "protein": return "recommended" if (coding and clinical) else "optional" if coding else "off"
    if oid == "numbers": return "recommended" if coding else "optional"
    if oid in ("uniprot", "ccds"): return "optional" if coding else "off"
    if oid in ("tsl", "appris"): return "optional" if (human and coding) else "off"

    # --- known-variant lookup (dependency for clinvar/freq) ---
    if oid == "check_existing": return "recommended"
    if oid in ("var_synonyms", "failed"): return "optional" if clinical else "off"

    # --- clinical evidence (human) ---
    if oid == "clinvar": return "critical" if clinical else "optional" if population else "off"
    if oid == "pubmed": return "optional" if clinical else "off"
    if oid == "mastermind": return "optional" if clinical else "off"
    if oid == "geno2mp": return "optional" if (clinical and germline) else "off"
    if oid == "phenotypes": return "recommended" if (clinical or (germline and regulatory)) else "optional"

    # --- frequency panels (human; SNV) ---
    if oid == "af_gnomade":
        return "critical" if population else "recommended" if clinical else "off"
    if oid == "af_gnomadg":
        return "recommended" if (population or clinical or regulatory) else "off"
    if oid in ("af", "af_1kg"): return "recommended" if population else "off"
    if oid == "frequency":                                             # filter; NOT somatic (doc)
        return "recommended" if (population and germline) else "off"

    # --- missense pathogenicity (coding, small) ---
    if category == "pathogenicity_prediction":
        if not coding:                                                 # cadd also scores non-coding
            return "recommended" if (oid == "cadd" and regulatory and clinical) else "off"
        if oid in ("sift", "polyphen"): return "recommended" if clinical else "optional"
        if oid in ("cadd", "alphamissense"): return "recommended" if clinical else "optional"
        return "optional"                                              # revel/eve/clinpred/dbnsfp/mutfunc/paralogues (redundant)

    # --- splice (coding or regulatory, small) ---
    if category == "splice_prediction":
        if oid == "spliceai": return "recommended" if clinical else "optional"
        return "optional"                                              # maxentscan/dbscsnv

    # --- gene constraint / dosage ---
    if oid == "loeuf": return "optional" if (germline and clinical) else "off"
    if oid == "dosage_sensitivity": return "recommended" if sv else "off"   # doc: rare-disease + CNV

    # --- regulatory (region regulatory) ---
    if oid == "regulatory": return "critical" if regulatory else "off"
    if oid == "cell_type": return "recommended" if regulatory else "off"
    if oid in ("utrannotator", "enformer"): return "recommended" if (regulatory and clinical) else "optional" if regulatory else "off"
    if oid == "mirna": return "optional" if regulatory else "off"

    # --- functional effect ---
    if oid == "nmd": return "recommended" if coding else "optional"

    # --- structural-variant frequency ---
    if oid == "gnomad_sv": return "critical" if (sv and (population or clinical)) else "off"

    # --- output control ---
    if oid in ("most_severe", "summary"): return "off"                 # emitted as explicit disables
    if oid in ("pick", "pick_allele", "per_gene"): return "off"
    if oid in ("coding_only",): return "optional" if (coding and not regulatory) else "off"
    return "off"


def main():
    va = genlib.load_va()
    cat = genlib.load_catalogue()
    corpus = genlib.load_corpus()
    catmap = {o["id"]: o.get("category", "?") for o in cat}
    restr = {o["id"]: o.get("species_restriction", "all species") for o in cat}
    tuples = json.load(open("/tmp/ref30_tuples.json"))
    assert len(tuples) == len(QUERIES), f"{len(tuples)} tuples vs {len(QUERIES)} queries"

    VALUE = {"sift": "b", "polyphen": "b", "check_existing": "yes", "frequency": "common"}
    DISABLE_NOTE = {
        "most_severe": "need full per-transcript detail, not a single top-line consequence",
        "summary": "need detailed annotations, not a summary line",
    }

    out = []
    for i, (t, q) in enumerate(zip(tuples, QUERIES), 1):
        rf, ag = t["region_focus"], t["analysis_goal"]
        tags = {
            "human": t["species"] == "human", "nonhuman": t["species"] == "non-human",
            "germline": t["origin"] == "germline", "somatic": t["origin"] == "somatic",
            "small": t["variant_size_class"] == "small", "sv": t["variant_size_class"] == "structural-CNV",
            "coding": "coding" in rf, "regulatory": "regulatory-noncoding" in rf,
            "basic": "basic-consequence" in ag, "clinical": "clinical-interpretation" in ag,
            "population": "population-frequency" in ag,
        }
        crit, enabled = {}, {}
        for oid in catmap:
            pr = doc_priority(oid, catmap, tags)
            # hard gates -> checker-clean by construction
            if tags["nonhuman"] and va._is_human_only(restr.get(oid, "all species")):
                continue
            if tags["sv"] and (catmap[oid] in SIZE_GATE_CATEGORIES or oid in SIZE_GATE_IDS):
                continue
            if not tags["sv"] and oid == "gnomad_sv":
                continue
            if pr in ("critical", "recommended"):
                enabled[oid] = pr
                crit[oid] = pr

        # assemble recommended_options (+ explicit meaningful disables)
        species = t["species"]
        ro = {}
        for oid in sorted(enabled):
            v = VALUE.get(oid, True)
            if oid == "core_type":
                v = "Ensembl/GENCODE" if species == "human" else "Ensembl"
            ro[oid] = {"value": v, "enabled": True}
        for oid, note in DISABLE_NOTE.items():
            ro[oid] = {"value": False, "enabled": False, "note": note}

        # checker to a fixed point -> record any change (should be none; deps auto-added stay)
        en = {k for k, v in ro.items() if v.get("enabled")}
        dis = {k for k, v in ro.items() if not v.get("enabled")}
        viol = va.check_and_fix_violations(set(en), set(dis), cat, q)
        changes = [(v["type"], v.get("option_disabled") or v.get("option_enabled")) for v in viol
                   if v.get("option_disabled") or v.get("option_enabled")]

        # doc-grounded justification (names the active option clusters)
        clusters = []
        if any(o in ro for o in ("symbol", "mane", "hgvs", "canonical", "biotype", "numbers", "protein")):
            clusters.append("gene/transcript identifiers")
        if "clinvar" in ro:
            clusters.append("ClinVar clinical significance")
        if any(o in ro for o in ("af_gnomade", "af_gnomadg", "af", "af_1kg")):
            clusters.append("gnomAD/1000G frequencies")
        if "frequency" in en:
            clusters.append("common-variant frequency filter")
        if any(catmap.get(o) == "pathogenicity_prediction" for o in en):
            clusters.append("missense pathogenicity predictors")
        if any(catmap.get(o) == "splice_prediction" for o in en):
            clusters.append("splice predictors")
        if "regulatory" in ro:
            clusters.append("regulatory build / non-coding annotation")
        if "gnomad_sv" in ro:
            clusters.append("gnomAD-SV frequency")
        if "dosage_sensitivity" in ro:
            clusters.append("gene dosage sensitivity")
        just = (f"{t['species']} {t['origin']} {t['variant_size_class']} variants, "
                f"{'+'.join(t['region_focus'])} focus, goal {'+'.join(t['analysis_goal'])}: "
                + ("; ".join(clusters) if clusters else "consequence-only")
                + ". Config from a doc-grounded rule set; hard gates (species/size) applied so it is checker-clean.")

        # doc-grounded uncertainty flags (the honest caveats the mentor should adjudicate)
        unc = []
        if tags["sv"]:
            unc.append("CATALOGUE GAP: the essential SV overlap output (VEP --overlaps / OverlapBP/OverlapPC) is "
                       "not in the 58-option KB, so SV rows cannot express it — flag for the catalogue.")
        if tags["nonhuman"] and tags["population"]:
            unc.append("Non-human + population-frequency is largely UNSATISFIABLE with VEP built-ins: gnomAD/1000G are "
                       "human-only, so no frequency option is available — this factor combo may be out of scope for this species.")
        if tags["nonhuman"] and "regulatory" in ro:
            unc.append("Regulatory build availability is SPECIES-SPECIFIC (human + a few model organisms); 'regulatory' is "
                       "enabled but must be confirmed for this species (the checker cannot verify per-species data).")
        if any(catmap.get(o) == "pathogenicity_prediction" for o in en) and tags["clinical"]:
            unc.append("Predictor redundancy: SIFT/PolyPhen/CADD/AlphaMissense are correlated missense predictors and "
                       "ACMG PP3/BP4 warns against double-counting — mentor may prune to one meta-predictor + CADD.")
        if "frequency" in en:
            unc.append("Frequency filter: ACMG BA1 stand-alone-benign threshold = AF > 5% (ClinGen SVI 2018, >=2000 "
                       "alleles); confirm filter-out vs annotate-only.")
        if tags["nonhuman"] and "sift" in en:
            unc.append("SIFT is species-limited (not universal); confirm SIFT data exists for this species.")

        out.append({
            "id": f"silver_{i:02d}_{genlib.factor_slug(t)[:40]}",
            "user_query": q,
            "use_case_category": None,
            "factor_labels": t,
            "confidence": "SILVER (Opus-authored, doc-grounded rules) — pending mentor validation, not gold",
            "recommended_options": ro,
            "justification": just,
            "_review": {
                "author": "opus — silver standard, NOT validated gold; config from doc-grounded rule set",
                "criticality": crit,
                "uncertain": unc,
                "n_enabled": len(en), "checker_changes": changes,
            },
        })

    with open(HERE / "silver_reference_set.json", "w") as f:
        json.dump(out, f, indent=2)
    ncc = sum(1 for r in out if r["_review"]["checker_changes"])
    print(f"Wrote {len(out)} silver examples -> silver_reference_set.json")
    print(f"  enabled/row: min {min(r['_review']['n_enabled'] for r in out)}, "
          f"max {max(r['_review']['n_enabled'] for r in out)}, "
          f"mean {sum(r['_review']['n_enabled'] for r in out)/len(out):.1f}")
    print(f"  rows with checker changes (should be 0): {ncc}")
    for r in out:
        fl = r["factor_labels"]
        print(f"  {r['id'][:44]:44s} en={r['_review']['n_enabled']:2d} "
              f"chg={len(r['_review']['checker_changes'])}")


if __name__ == "__main__":
    main()
