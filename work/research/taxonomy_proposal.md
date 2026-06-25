# VEP use-case taxonomy: proposal for review

Status: updated draft. This replaces the earlier 7-category version. After looking at how Ensembl and peer
tools actually organise things, and at where my own 7 categories broke down, I've moved the proposal to a
factor-based, multi-label scheme. I'd like your sign-off on the factors and, more importantly, on the
per-option priorities, before I build the gold set.

## 1. Why I moved away from the 7 single categories

I originally used 7 categories: rare_disease_germline, somatic_cancer, regulatory_noncoding,
population_genetics, structural_variants, non_human, quick_lookup. The problem is they mix four different
axes (clinical context, variant type, scale, species), so they aren't mutually exclusive and a single label
loses information at the boundaries:

- A somatic structural variant in a mouse tumour is somatic, structural AND non-human at once.
- A regulatory variant in a rare-disease patient is both regulatory and germline.

Forcing one label there is misleading for three things at once: it mislabels the example, it picks the
wrong option priorities, and "did the model detect the use case?" only ever scores one aspect of a
multi-aspect query.

## 2. What the canonical sources actually do

I couldn't find an official Ensembl use-case taxonomy. Ensembl groups by interface/data-scale and by what
an option does (the 6 web-form function sections in VEPConstants.pm, release/115), never by analysis
scenario. VEP is configured through independent, composable flags (`--species`, `--af_gnomade`,
`--plugin`), not a "pick your scenario" menu. The wider field is the same: germline vs somatic is a hard
split with separate standards (ACMG/AMP 2015 vs AMP/ASCO/CAP 2017); SV/CNV has its own ClinGen standard and
tools (AnnotSV, gnomAD-SV); species is a first-class flag; peer tools (Funcotator, OpenCRAVAT, Nirvana)
expose composable modules, not a flat scenario menu. Everything converges on orthogonal, composable axes.

## 3. Proposed scheme: factors, multi-label throughout

A "use case" becomes a set of factor tags, not one category. Each example carries one value per factor.

| factor | values | hard/soft | drives | evidence |
|---|---|---|---|---|
| species | human / non-human | hard | the whole human-only set (CADD/gnomAD/ClinVar) | strong (sourced) |
| origin | germline / somatic | hard | ClinVar-somatic, COSMIC, pathogenicity vs actionability | strong (sourced) |
| variant_size_class | small (SNV/indel) / structural-CNV | hard | SV plugins/overlap, gnomAD-SV vs gnomAD | strong (sourced) |
| annotation_focus | coding / regulatory-noncoding / clinical-frequency | soft | regulatory features, frequency DBs, predictors | medium |
| scale | single-variant lookup / cohort | weak | mostly upstream; minor for annotation config | weak (may drop) |

"Hard" factors can remove an option outright (e.g. CADD is not applicable for non-human); "soft" factors
only shift how strongly an optional extra is recommended.

## 4. How factors drive the four jobs categories used to do

1. **Labelling:** each example is tagged with all applicable factor values (multi-label), so the mouse
   somatic SV case is recorded truthfully instead of forced into one bucket.
2. **Option priority:** priorities are keyed to factor values, not one category (see section 5).
3. **Eval coverage and splits:** I balance and stratify on factor values (marginally — each value
   represented), using multi-label stratification, not on a single category.
4. **Model detection:** scored per factor (species/origin/size/focus), so it reflects the whole query
   rather than one aspect. This stays a diagnostic; the headline metric is still per-option Enable F1.

## 5. Option priority, keyed to factors

Today the catalogue stores `priority_by_use_case` keyed to the 7 categories. I'd re-key it to factor
values, e.g.:

```json
"priority_by_factor": {
  "origin":             { "germline": "critical", "somatic": "recommended" },
  "variant_size_class": { "structural": "critical", "small": "not_applicable" },
  "species":            { "non_human": "not_applicable" }
}
```

When several factors apply to a query, I resolve in two tiers:

- **hard factors first:** if any hard factor marks an option `not_applicable`, it's removed (the checker
  already does this for species);
- **then soft ranking:** among what remains, take the strongest priority across the active factor values
  (critical > recommended > optional).

This is the part I most need your domain input on — the per-option, per-factor priorities, and any
hard-removal rules I've got wrong.

## 6. Example counts and stratification

The dataset is sized by per-factor-value coverage, not by category. The rarest values (non-human, somatic,
structural, regulatory) set the floor, since each multi-label example covers one value of every factor at
once.

| tier | per factor value | total (approx) | what it supports |
|---|---|---|---|
| minimum viable | >=3 | ~24-30 | leave-one-out on the training set; any holdout directional only |
| stable | >=5-6 | ~50 | an 80/20 multi-label-stratified holdout becomes usable |
| benchmark | >=10 | ~100+ | per-factor F1 with meaningful confidence |

I'd build the gold set **balanced** across factor values (so non-human isn't drowned out by rare disease),
and keep a separate, **naturally-distributed** set of real questions as an out-of-distribution check. Below
~50 examples the 20% holdout is too small to score reliably, so I'd lean on leave-one-out until the set
grows.

## 7. What I'd like from you, in order

1. The factors: do these axes and values look right, should `scale` be dropped, and is an explicit
   clinical-vs-research axis worth adding?
2. The per-option, per-factor priorities and hard-removal rules (section 5) — these need your domain
   knowledge and aren't something I can derive.
3. The example counts (section 6) and how many you can help validate, so I build the gold set at a
   defensible size.

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
- VEPConstants.pm (CONFIG_SECTIONS, release/115)

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
the convergence I describe is something I pieced together across these standards and tools. The factor names
and the regulatory/scale caveats are my own reading, and I've flagged them as such.
