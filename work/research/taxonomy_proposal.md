# VEP use-case taxonomy: proposal for review

Status: draft for your feedback.

The tool currently organises VEP usage into 7 use-case categories. I came up with these myself, fairly
pragmatically, and I don't have a domain source to back them up. Before we build a gold-standard example
set on top of them, I'd like your view on whether this is a sensible way to carve up VEP usage, or whether
there's a standard framing I should adopt instead. I'd rather settle this now than have you label examples
against a categorisation we later decide to change.

The main question for you: are these 7 the right categories, is there a canonical Ensembl/EBI or community
framing I should use instead, and should a query carry a single label or several at once?

## 1. The current 7 categories, and why I'm unsure about them

rare_disease_germline, somatic_cancer, regulatory_noncoding, population_genetics, structural_variants,
non_human, quick_lookup

My worry is that these aren't a clean taxonomy. They mix at least four different things:

- clinical context: rare disease, cancer
- variant type: structural, regulatory/noncoding
- scale: population genetics, quick lookup
- species: non-human

Because of that they aren't mutually exclusive, and forcing one label per query loses information at the
boundaries:

- A somatic structural variant in a mouse tumour model is somatic_cancer, structural_variants and
  non_human all at once.
- A regulatory variant in a rare-disease patient is both regulatory_noncoding and rare_disease_germline.
- non_human and quick_lookup are basically independent of the rest.

This is also why the single-label use-case detection in the tool is unreliable at those boundaries.

## 2. What I found when I looked for a canonical source

### Ensembl / VEP's own framing

I couldn't find an official Ensembl use-case taxonomy. Where Ensembl groups anything, it groups by
interface and data scale (web for small/first-time, command line for large/flexible, REST for
programmatic), or by what an option does, not by analysis scenario:

- The web form's only canonical grouping is the 6 function sections in VEPConstants.pm (release/115):
  identifiers, variants & frequency data, additional annotations, predictions, filtering, advanced. These
  describe what an option does, not who the user is.
- The official "Examples and use cases" page is organised by data source and feature (gnomAD,
  conservation, dbNSFP, structural variants, pangenome, citations), not by scenario presets for "rare
  disease", "somatic cancer", and so on.
- The VEP paper (McLaren et al. 2016) doesn't define a use-case taxonomy; it groups users by expertise and
  data scale, and only mentions application domains (clinic, GWAS, farm animals) in passing. EBI training
  teaches the 6 section names and one generic workflow.
- VEP is configured through independent, composable flags (--species, --af_gnomade / --af_1kg,
  --plugin / --custom, cache vs db), not a "pick your scenario" menu.

So I don't think the 7 categories can be attributed to Ensembl; they're my own construct. Two of them
loosely echo Ensembl axes (structural variants is a feature heading, non-human is the species flag), but
neither is an official use-case scheme.

On the option priorities: I couldn't find any Ensembl per-workflow option-priority scheme either, so the
priority_by_use_case weightings are also my own judgement and need your input. The only priority signals I
could actually source are isolated heuristics: filtering by population allele frequency in rare disease
(the VEP tutorial cites the ACMG 5% allele-frequency benchmark), and MANE Select being recommended as the
default transcript for reporting.

### Field standards and peer tools

There isn't a single named taxonomy of variant-annotation workflows in the wider field either, but the
standards, databases and tools I looked at tend to converge on a few independent, composable axes:

- Germline vs somatic is a hard split: two separate clinical standards (ACMG/AMP 2015 pathogenicity tiers
  vs AMP/ASCO/CAP 2017 actionability tiers), not one framework with sub-cases.
- Variant class is a real axis: structural and CNV variants have their own ClinGen standard and their own
  tools (AnnotSV, gnomAD-SV), separate from SNV/indel annotation.
- Species is a first-class flag (VEP --species, AnnotSV human/mouse).
- Peer tools expose composable flags or modules rather than single-label presets: Funcotator ships
  separate germline and somatic data-source bundles; OpenCRAVAT covers "germline, somatic, common, rare,
  coding and non-coding" through composable modules; Nirvana markets itself as "clinical-grade" (a
  clinical-vs-research distinction). None offer a flat scenario menu.
- Ontologies model variants along several dimensions at once (Sequence Ontology: alteration type, affected
  feature, effect).

Both angles point the same way: a factor-based, multi-label scheme fits better than 7 mutually exclusive
buckets. I didn't find any authority for a flat 7-way single-label scheme.

## 3. A possible alternative: factor-based and multi-label

Instead of 7 fixed categories, we could use a few independent factors, where a "use case" is a combination
and option priority is keyed to the factors that actually drive the config:

| factor | values | drives | evidence |
|---|---|---|---|
| species | human / non-human | the whole human-only annotation set (CADD/gnomAD/ClinVar) | strong (sourced) |
| origin | germline / somatic | ClinVar-somatic, COSMIC, pathogenicity vs actionability | strong (sourced) |
| variant size class | small (SNV/indel) / structural-CNV | SV plugins/overlap, gnomAD-SV vs gnomAD | strong (sourced) |
| annotation focus | coding / regulatory-noncoding / clinical-frequency | regulatory features, frequency DBs, predictors | medium |
| scale (optional, low weight) | single-variant lookup / cohort | mostly upstream (calling/QC); minor for annotation config | weak |

A few things I'd flag on this:

- The real "origin" axis is germline vs somatic; germline still includes het/hom/compound-het.
- Regulatory/noncoding is more of a region or annotation-focus attribute than a sibling of "structural" —
  a noncoding variant is usually still an SNV/indel, so it shouldn't sit on the size-class axis.
- Scale is the weakest axis for an annotation-config tool, since it mostly matters upstream at calling and
  joint-genotyping. I'd keep it low-weight or drop it.
- It might be worth an explicit clinical-vs-research axis (which drives the choice of frequency DBs and
  pathogenicity plugins); peer tools expose this and the current 7 don't really capture it.

## 4. Why I'd want to settle this before building the gold set

Changing the taxonomy isn't a small tweak: it re-keys the priority tables, changes the label on every
example, and breaks comparability with my earlier runs. So I'd rather agree it with you up front. If you
label a batch of examples against the 7 categories and we then change the carving, that effort is wasted.
That's the reason for the order below.

## 5. What I'd like from you, in order

1. The taxonomy itself: is there a canonical Ensembl/EBI framing or a standard I should adopt, and should
   it be multi-label / factor-based rather than single-category? (The mouse + somatic + SV example is the
   clearest case where single-label breaks down.)
2. Then the priority weightings and per-option explanations, since those need your domain knowledge and
   aren't something I can derive.
3. Then the example count and schema, so the gold set is built on a taxonomy we've already agreed.

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

A note on the above: there's no formally named "variant-annotation workflow taxonomy" in the literature, so
the convergence I describe is something I pieced together across these standards and tools. The axis names
and the regulatory/scale caveats are my own reading, and I've flagged them as such.
