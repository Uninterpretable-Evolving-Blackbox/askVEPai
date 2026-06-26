# VEP use-case taxonomy: proposal for review

Status: updated draft. This replaces the earlier 7-category version. After looking at how Ensembl and peer
tools actually organise things, at where my own 7 categories broke down, and at the web form option-by-option,
I've moved the proposal to a factor-based, multi-label scheme. I'd like your sign-off on the factors and,
more importantly, on the per-option priorities, before I build the gold set.

## 1. Why I moved away from the 7 single categories

I originally used 7 categories: rare_disease_germline, somatic_cancer, regulatory_noncoding,
population_genetics, structural_variants, non_human, quick_lookup. The problem is they mix several different
axes (species, variant type, where the variant acts, why you're annotating), so they aren't mutually
exclusive and a single label loses information at the boundaries:

- A somatic structural variant in a mouse tumour is somatic, structural AND non-human at once.
- A regulatory variant in a rare-disease patient is both regulatory and germline.

Forcing one label there is misleading for three things at once: it mislabels the example, it picks the
wrong option priorities, and "did the model detect the use case?" only ever scores one aspect of a
multi-aspect query.

## 2. What the canonical sources actually do

I couldn't find an official Ensembl use-case taxonomy. Ensembl groups by interface/data-scale and by what
an option does (the web-form function sections in VEPConstants.pm, release/115), never by analysis
scenario. The web form itself says "the listed options change depending on the selected species" — species
is the one axis the form is explicitly built around. VEP is configured through independent, composable flags
(`--species`, `--af_gnomade`, `--plugin`), not a "pick your scenario" menu. The wider field is the same:
germline vs somatic is a hard split with separate standards (ACMG/AMP 2015 vs AMP/ASCO/CAP 2017); SV/CNV has
its own ClinGen standard and tools (AnnotSV, gnomAD-SV); species is a first-class flag; peer tools
(Funcotator, OpenCRAVAT, Nirvana) expose composable modules, not a flat scenario menu. Everything converges
on orthogonal, composable axes.

## 3. Proposed scheme: factors, multi-label throughout

A "use case" becomes a set of factor values, not one category. Two of the factors are **facts about the
data** (you don't choose them — the variant set does); two are **intent** (what the user actually wants out
of the annotation). I grounded each factor by checking it against the web form: a factor only earns its
place if its values actually gate or shift a concrete cluster of options.

| factor | values | kind | role | drives (grounded in the web form) |
|---|---|---|---|---|
| species | human / non-human | data fact | **hard gate** + importance | the entire human-only block: SIFT/PolyPhen, CADD/REVEL/AlphaMissense/EVE/ClinPred, dbNSFP, SpliceAI/dbscSNV, 1000G + gnomAD frequencies, ClinVar, MANE/APPRIS/TSL. The form says these "only apply when you have selected human". |
| origin | germline / somatic | data fact | importance (**one** hard rule) | frequency-filter interpretation, and COSMIC vs dbSNP/ClinVar emphasis on `check_existing`. Hard rule: `somatic ⇒ filter_common = not_applicable` (you must not drop common variants in a somatic workflow). |
| variant_size_class | small (SNV/indel) / structural-CNV | data fact | **hard gate** + importance | structural-CNV removes the missense/splice predictor cluster (those need an SNV) and swaps gnomAD for gnomAD-SV; SV-specific overlap output (OverlapBP/PC) appears instead. |
| region_focus | coding / regulatory-noncoding (**multi-select**) | intent (where) | importance | coding → protein/coding cluster (predictors, HGVSp, protein domains, exon/intron numbers); regulatory-noncoding → regulatory build, motif features, Enformer, UTRAnnotator, RiboseqORFs. |
| analysis_goal | basic-consequence / clinical-interpretation / population-frequency (**multi-select**) | intent (why) | importance | basic → identifiers + consequence only (the old quick-lookup); clinical → ClinVar, pathogenicity predictors, Phenotypes, Mastermind, Geno2MP; population → 1000G + gnomAD frequencies, filter_common. |

Every factor drives option importance (section 5). Two of them (`species`, `variant_size_class`)
*additionally* act as hard applicability gates that can remove an option outright; `origin` has exactly one
hard rule; `region_focus` and `analysis_goal` are purely soft (they only shift how strongly an option is
recommended).

### What changed from the previous draft, and why

- **Dropped `scale` (single-variant vs cohort).** Checking the form, scale changes no core annotation —
  a one-variant human somatic SNV needs the same predictors/frequencies/identifiers as a cohort of them. The
  only options it seemed to touch are the output-restriction controls (`most_severe`/`summary`/`pick`/
  `coding_only`) and the compute knobs (`buffer_size`/`fork`). The restriction controls are better explained
  by `analysis_goal` (basic-consequence wants a top-line call; clinical wants full per-transcript detail)
  than by how many variants you have, and the compute knobs are infrastructure the web tool manages, not
  recommendations the user needs. So scale was double-counting one real signal and otherwise out of scope.
- **Split the old `annotation_focus` into `region_focus` + `analysis_goal`.** The single three-value version
  (`coding / regulatory-noncoding / clinical-frequency`) repeated the exact flaw I'm trying to escape: it
  mixed *where* the variant acts (a region axis) with *why* you're annotating (a purpose axis) in one label.
  Splitting them — and making both multi-select — lets a rare-disease coding query be tagged truthfully as
  coding + clinical-interpretation + population-frequency, with each driver kept explicit.
- **Demoted `origin` from hard to soft (with one hard rule).** On clinical *standards* germline vs somatic is
  a hard split, but on the *web form* no option becomes invalid for one or the other — origin shifts
  priorities (filter interpretation, COSMIC vs ClinVar) rather than removing options. The single genuine
  hard consequence is `somatic ⇒ filter_common off`.

## 4. How factors drive the four jobs categories used to do

1. **Labelling:** each example is tagged with all applicable factor values (multi-label), so the mouse
   somatic SV case is recorded truthfully instead of forced into one bucket.
2. **Option priority:** priorities are keyed to factor values, not one category (see section 5).
3. **Eval coverage and splits:** I balance and stratify on factor values (each value represented), using
   multi-label stratification, not on a single category.
4. **Model detection:** scored per factor (species/origin/size/region/goal), so it reflects the whole query
   rather than one aspect. This stays a diagnostic; the headline metric is still per-option Enable F1.

## 5. Option priority, keyed to factors

Today the catalogue stores `priority_by_use_case` keyed to the 7 categories. I'd re-key it to factor values.
Every factor contributes a priority; the hard factors can also mark `not_applicable`. For example, ClinVar:

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

When several factors apply to a query, I resolve in two tiers:

- **hard factors first:** if any hard factor (or the somatic/filter_common rule) marks an option
  `not_applicable`, it's removed — the checker already does this for species;
- **then soft ranking:** among what remains, take the strongest priority across all active factor values
  (critical > recommended > optional).

This is the part I most need your domain input on — the per-option, per-factor priorities, and any
hard-removal rules I've got wrong.

## 6. Example counts and stratification

The dataset is sized by per-factor-value coverage, not by category. The rarest values (non-human, somatic,
structural, regulatory) set the floor. Because the scheme is multi-label, one example covers one value of
every factor at once, so coverage accumulates quickly.

| tier | per factor value | total (approx) | what it supports |
|---|---|---|---|
| minimum viable | >=3 | ~24-30 | leave-one-out on the training set; any holdout directional only |
| stable | >=5-6 | ~50 | an 80/20 multi-label-stratified holdout becomes usable |
| benchmark | >=10 | ~100+ | per-factor F1 with meaningful confidence |

I'd build the gold set **balanced** across factor values (so non-human isn't drowned out by rare disease),
and keep a separate, **naturally-distributed** set of real questions as an out-of-distribution check. Below
~50 examples the 20% holdout is too small to score reliably, so I'd lean on leave-one-out until the set
grows.

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
