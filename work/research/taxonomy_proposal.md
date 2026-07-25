# VEP use-case taxonomy: proposal for review

**Status: updated draft** — replaces the earlier 7-category version. After checking how Ensembl and peer
tools organise things, where my own 7 categories broke down, and the web form option-by-option, I've moved
to a **factor-based, multi-label** scheme. I'd like your sign-off on the factors and — more importantly — on
the **per-option priorities**, before I build the gold set.

## 1. Why I moved away from the 7 single categories

The 7 categories (rare_disease_germline, somatic_cancer, regulatory_noncoding, population_genetics,
structural_variants, non_human, quick_lookup) **mix several axes** — species, variant type, where the variant
acts, why you're annotating — so they aren't mutually exclusive and a single label loses information at the
boundaries:

- a somatic structural variant in a mouse tumour is somatic, structural **and** non-human at once;
- a regulatory variant in a rare-disease patient is both regulatory **and** germline.

Forcing one label mislabels the example, picks the wrong option priorities, and lets "did the model detect
the use case?" score only one aspect of a multi-aspect query.

## 2. What the canonical sources actually do

There is no official Ensembl use-case taxonomy. The evidence points to **orthogonal, composable axes**, not a
scenario menu:

- **Ensembl** groups by interface/data-scale and by what an option *does* (the web-form function sections in
  `VEPConstants.pm`, release/115), never by scenario.
- **The web form** is built around species — "the listed options change depending on the selected species" —
  and is configured through independent flags (`--species`, `--af_gnomade`, `--plugin`).
- **The wider field** splits the same way: germline vs somatic have separate standards (ACMG/AMP 2015 vs
  AMP/ASCO/CAP 2017); SV/CNV has its own (ClinGen, AnnotSV, gnomAD-SV); species is a first-class flag; peer
  tools (Funcotator, OpenCRAVAT, Nirvana) expose composable modules, not a flat menu.

## 3. Proposed scheme: factors, multi-label throughout

A "use case" becomes a **set of factor values**, not one category. **Three factors are facts about the data**
(the variant set decides them, not the user) — species, origin, variant_size_class; **two are intent** (what
the user wants out of the annotation) — region_focus, analysis_goal. Each earns its place only if its values
gate or shift a concrete cluster of options in the web form.

| factor | values | kind | role | drives (grounded in the web form) |
|---|---|---|---|---|
| species | human / non-human | data fact | **hard gate** + importance | the human-only block: PolyPhen, CADD/REVEL/AlphaMissense/EVE/ClinPred, dbNSFP, SpliceAI/dbscSNV, 1000G + gnomAD frequencies, ClinVar, MANE/APPRIS/TSL. The form says these "only apply when you have selected human". (SIFT is species-conditional, not human-only, so it is *not* gated.) |
| origin | germline / somatic | data fact | importance (**one** hard rule) | frequency-filter interpretation, and COSMIC vs dbSNP/ClinVar emphasis on `check_existing`. Hard rule: `somatic ⇒ filter_common = not_applicable` (you must not drop common variants in a somatic workflow). |
| variant_size_class | small (SNV/indel) / structural-CNV | data fact | **hard gate** + importance | structural-CNV removes the missense/splice predictor cluster (those need an SNV) and swaps gnomAD for gnomAD-SV; SV-specific overlap output (OverlapBP/PC) appears instead. |
| region_focus | coding / regulatory-noncoding (**multi-select**) | intent (where) | importance | coding → protein/coding cluster (predictors, HGVSp, protein domains, exon/intron numbers); regulatory-noncoding → regulatory build, motif features, Enformer, UTRAnnotator, RiboseqORFs. |
| analysis_goal | basic-consequence / clinical-interpretation / population-frequency (**multi-select**) | intent (why) | importance | basic → identifiers + consequence only (the old quick-lookup); clinical → ClinVar, pathogenicity predictors, Phenotypes, Mastermind, Geno2MP; population → 1000G + gnomAD frequencies, filter_common. |

Every factor drives option importance (§5). Beyond that:

- **hard gates** — `species` and `variant_size_class` can remove an option outright;
- **one hard rule** — `origin`: `somatic ⇒ filter_common = not_applicable`;
- **soft** — `region_focus` and `analysis_goal` only shift how strongly an option is recommended.
  *(Amendment under review: I have implemented `region_focus` as a **hard gate** — a purely regulatory query
  drops the missense predictors, which produce empty columns for it; CADD is exempt as it scores non-coding.
  This departs from "purely soft" above and needs your decision — gate, or rank?)*

### What changed from the previous draft, and why

- **Dropped `scale` (single-variant vs cohort).** It changes no core annotation — a one-variant human somatic
  SNV needs the same predictors/frequencies/identifiers as a cohort. It only touched the output-restriction
  controls (better explained by `analysis_goal`) and the compute knobs (infrastructure the web tool manages),
  so it double-counted one real signal and was otherwise out of scope.
- **Split the old `annotation_focus` into `region_focus` + `analysis_goal`.** The single three-value version
  mixed *where* the variant acts with *why* you're annotating — the exact flaw I'm escaping. Splitting them
  (both multi-select) lets a rare-disease coding query be tagged truthfully as coding + clinical-interpretation
  + population-frequency, each driver kept explicit.
- **Demoted `origin` from hard to soft (one hard rule).** On clinical *standards* germline vs somatic is a
  hard split, but on the *web form* no option becomes invalid for one or the other — origin shifts priorities
  (filter interpretation, COSMIC vs ClinVar). The one genuine hard consequence is `somatic ⇒ filter_common off`.

## 4. How factors drive the four jobs categories used to do

- **Labelling** — each example is tagged with all applicable factor values (multi-label), so the mouse somatic
  SV is recorded truthfully instead of forced into one bucket.
- **Option priority** — keyed to factor values, not one category (§5).
- **Eval coverage & splits** — balanced and stratified on factor values (multi-label stratification), not one
  category.
- **Model detection** — scored per factor (species/origin/size/region/goal), reflecting the whole query. This
  stays a diagnostic; the headline metric is still per-option Enable F1.

## 5. Option priority, keyed to factors

The catalogue's `priority_by_use_case` (keyed to the 7 categories) gets **re-keyed to factor values**. Every
factor contributes a priority; hard factors can also mark `not_applicable`. For example, ClinVar:

```json
"clinvar": {
  "species":       { "non_human": "not_applicable" },
  "origin":        { "germline": "critical", "somatic": "recommended" },
  "analysis_goal": { "clinical_interpretation": "critical", "population_frequency": "optional" }
}
```

and the one origin hard rule:

```json
"filter_common": {
  "origin": { "somatic": "not_applicable" }
}
```

Resolution is two-tier:

- **hard factors first** — any hard factor (or the somatic/filter_common rule) marking `not_applicable`
  removes the option (the checker already does this for species);
- **then soft ranking** — among what remains, take the **strongest** priority across all active factor values
  (critical > recommended > optional).

**This is where I most need your domain input** — the per-option, per-factor priorities, and any hard-removal
rules I've got wrong.

## 6. Example counts and stratification

Sized by **per-factor-value coverage**, not by category — the rarest values (non-human, somatic, structural,
regulatory) set the floor. Because the scheme is multi-label, one example covers one value of every factor at
once, so coverage accumulates quickly.

| tier | per factor value | total (approx) | what it supports |
|---|---|---|---|
| minimum viable | >=3 | ~24-30 | leave-one-out on the training set; any holdout directional only |
| stable | >=5-6 | ~50 | an 80/20 multi-label-stratified holdout becomes usable |
| benchmark | >=10 | ~100+ | per-factor F1 with meaningful confidence |

I'd build the gold set **balanced** across factor values (so non-human isn't drowned out by rare disease),
plus a separate **naturally-distributed** real-question set as an out-of-distribution check. Below ~50
examples the 20% holdout is too small to score reliably, so I'd lean on leave-one-out until it grows.

## Appendix: sources

Ensembl / VEP:

- VEP docs index — https://www.ensembl.org/info/docs/tools/vep/index.html
- "Examples and use cases" — https://www.ensembl.org/info/docs/tools/vep/script/vep_example.html
- Web/online docs — https://www.ensembl.org/info/docs/tools/vep/online/index.html ; options reference —
  https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html ; FAQ —
  https://www.ensembl.org/info/docs/tools/vep/script/vep_faq.html
- McLaren et al. 2016, Genome Biology 17:122 — https://doi.org/10.1186/s13059-016-0974-4 (PMC4893825)
- VEP tutorial, Hunt et al. (PMC7613081) — ACMG 5% allele-frequency and MANE-Select-default heuristics
- Ensembl/EBI training — training.ensembl.org ; ebi.ac.uk/training
- VEPConstants.pm (CONFIG_SECTIONS, release/115); InputForm.pm (per-species field gating, release/115)

Field standards:

- ACMG/AMP 2015 germline guidelines (Richards et al.); AMP/ASCO/CAP 2017 somatic (Li et al.)
- ClinGen CNV technical standard (Riggs et al.)
- gnomAD-SV (2019); AnnotSV (Bioinformatics 2018)
- GATK Funcotator (germline/somatic bundles); GATK joint-calling; GLnexus
- OpenCRAVAT (2019); Nirvana (clinical-grade)
- Sequence Ontology; GENO ontology

On data and evaluation method:

- Multi-label stratification — Sechidis, Tsoumakas & Vlahavas 2011, "On the Stratification of Multi-Label
  Data" (the basis for iterative_train_test_split in scikit-multilearn)
- Golden-dataset sizing guidance — 50-200 rows for iteration, ~100+ for a stable benchmark

A note on the above: there's no formally named "variant-annotation workflow taxonomy" in the literature, so
the convergence I describe is something I pieced together across these standards and tools. The factor names,
the region/goal split, and the dropped-scale reasoning are my own reading, grounded in the web form, and I've
flagged them as such.
