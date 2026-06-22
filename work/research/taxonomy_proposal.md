# VEP use-case taxonomy — proposal for mentor review

**Status: DRAFT for mentor critique.** The 7 use-case categories the project currently uses were derived
*pragmatically by us, with no domain authority behind them.* This document presents them as an
**assumption to validate, not settled ground truth**, and asks the mentor to confirm or redesign the
taxonomy **before** any gold examples are labelled — so expert effort isn't spent labelling against a
carving we later decide was wrong.

> The honest framing for the mentor: *"I derived these 7 use cases pragmatically with no domain authority.
> Before we build a gold set on top of them, I need you to tell me whether this is the right way to carve
> up VEP usage, or point me to the canonical framing (Ensembl docs / training / a standard) I should adopt
> instead — and whether it should be single-label or multi-label / factor-based."*

---

## 1. The current 7 categories — and why they're shaky

`rare_disease_germline · somatic_cancer · regulatory_noncoding · population_genetics ·
structural_variants · non_human · quick_lookup`

These are **not a clean taxonomy** — they mix at least four different axes:
- **clinical context** — rare disease, cancer
- **variant type** — structural, regulatory/noncoding
- **scale** — population genetics, quick lookup
- **species** — non_human

So they are **not mutually exclusive**, and single-label assignment is lossy at the boundaries:
- *A somatic structural variant in a mouse tumour model* is `somatic_cancer` ∩ `structural_variants` ∩
  `non_human` simultaneously.
- *A regulatory variant in a rare-disease patient* spans `regulatory_noncoding` ∩ `rare_disease_germline`.
- `non_human` and `quick_lookup` are essentially **orthogonal** to all the others.

Forcing each query into exactly one bucket is arbitrary at those boundaries — which is precisely why
single-label use-case detection is unreliable (and why our own `extract_use_case` parser is fuzzy).

---

## 2. What the evidence says

### 2a. Ensembl / VEP's own framing  *(sourced — Ensembl docs, VEP paper, EBI training; URLs in appendix)*
**Ensembl has no official use-case taxonomy.** Where Ensembl segments anything it segments by (i)
interface / data-scale / bioinformatics experience (web for small/first-time · command-line for large/
flexible · REST for programmatic) and (ii) feature/option category — never by analysis scenario:
- **The web form's only canonical grouping is the 6 *function* sections** (`VEPConstants.pm`
  `CONFIG_SECTIONS`, release/115): *identifiers · variants & frequency data · additional annotations ·
  predictions · filtering · advanced*. These describe **what an option does**, not who the user is.
- **The official "Examples and use cases" page is organised by data-source/feature** (gnomAD, conservation,
  dbNSFP, structural variants, pangenome, citations) — **no scenario presets / recommended option-sets**
  for "rare disease", "somatic cancer", etc.
- **The VEP paper (McLaren 2016)** defines no use-case/user taxonomy; it segments users by expertise/data-
  scale and names application domains (clinic, GWAS, farm animals) only in passing, with no scenario
  option-sets. **EBI training** teaches the 6 section names verbatim and one generic workflow.
- **VEP is configured by orthogonal, composable flags** (`--species`, `--af_gnomade`/`--af_1kg`,
  `--plugin`/`--custom`, cache vs db) — there is no "pick your scenario" menu.

So our 7 categories **cannot be cited to Ensembl** — they are a project-internal construct, and the
use-case labels are provisional judgment on our part rather than authoritative. Two of them merely *echo*
Ensembl axes (structural variants is a *feature* heading; non-human is the species axis) but neither is a
sanctioned use-case scheme.

**On priorities (relevant to the second mentor ask):** there is **no Ensembl per-workflow option-
criticality/priority scheme anywhere** — so `priority_by_use_case` is genuinely project judgment that needs
the mentor. The *only* source-grounded priority signals are isolated heuristics: filter by population
allele frequency in rare-disease (the official VEP tutorial cites the **ACMG 5% AF** benchmark) and **MANE
Select** "recommended as the default transcript for reporting". Those few can be cited; the rest cannot.

### 2b. Field standards + peer tools  *(sourced; full citations in the appendix)*
**There is no single canonical, named taxonomy of variant-annotation workflows** — but standards,
databases, tools and ontologies *converge* on a small set of **orthogonal, composable axes**:
- **germline vs somatic is an axis-defining hard split:** two structurally different clinical standards —
  ACMG/AMP 2015 (5-tier pathogenicity) vs AMP/ASCO/CAP 2017 (4-tier clinical actionability). Not one
  framework with sub-cases; two distinct systems.
- **variant class is a real, tooling-level axis:** structural/CNV variants get their **own** ClinGen
  technical standard and their own tools/references (AnnotSV, gnomAD-SV) — separate from SNV/indel
  annotation.
- **species is a first-class flag** (VEP `--species`, AnnotSV human/mouse).
- **peer tools expose orthogonal flags/modules, not single-label presets:** Funcotator ships separate
  **germline vs somatic** data-source bundles; OpenCRAVAT spans "germline, somatic, common, rare, coding
  and non-coding" via composable annotator modules; Nirvana brands "clinical-grade" (a clinical-vs-research
  axis); none expose a flat scenario menu.
- **ontologies model variants multi-dimensionally** (Sequence Ontology: alteration-type × affected-feature
  × effect, composable).
- ⇒ **Multi-label / factor-based is the field-consistent choice; single-label is a UI simplification, not a
  field norm.**

### 2c. Both research passes converge
The Ensembl-official pass (no use-case taxonomy; only interface/data-scale + the 6 option-categories) and
the independent field-standard pass (orthogonal composable axes; no peer tool exposes a single-label
scenario menu) reach the **same conclusion from different directions**: **factor-based / multi-label, not
7 mutually-exclusive buckets.** Neither found any canonical authority for a flat 7-way single-category
scheme.

---

## 3. Proposed alternative — factor-based, multi-label

Replace the 7 monolithic categories with a few **orthogonal factors**; a "use case" is a *combination*,
and option priority is keyed to the factors that actually drive the config:

| factor | values | drives | strength of evidence |
|---|---|---|---|
| **species** | human / non-human | whole human-only annotation set (CADD/gnomAD/ClinVar…) | strong (sourced) |
| **origin** | germline / somatic | ClinVar-somatic, COSMIC, pathogenicity vs actionability | strong (sourced) |
| **variant size class** | small (SNV/indel) / structural-CNV | SV plugins/overlap, gnomAD-SV vs gnomAD | strong (sourced) |
| **annotation focus** | coding / regulatory-noncoding / clinical-frequency | regulatory features, frequency DBs, predictors | medium |
| *(optional, low weight)* **scale** | single-variant lookup / cohort | mostly upstream (calling/QC); minor for annotation config | weak (sourced but upstream) |

**Refinements the research flagged (worth raising with the mentor):**
- "zygosity-context" is **mislabelled** → the real axis is **origin (germline/somatic)**; germline still
  includes het/hom/compound-het.
- **regulatory/noncoding is a *region/annotation-focus* attribute, not a sibling of "structural"** — a
  noncoding variant is usually still an SNV/indel. Don't put it on the size-class axis.
- **scale** is the **weakest** axis for an *annotation-config* tool (it bites upstream at calling/joint-
  genotyping). Keep it low-weight or drop it.
- Consider an explicit **clinical-vs-research / annotation-source-intent** axis (drives which frequency DBs
  + pathogenicity plugins) — peer tools expose this and the current 7 under-represent it.

---

## 4. Why this is a deliberate redesign, not a tweak (and must come first)

Changing the taxonomy **invalidates**: the `priority_by_use_case` tables (re-keyed to factors), the
use-case label on every example, and comparability with all prior runs. Per our own experiment discipline
(*don't change >1 variable quietly*), this is a deliberate redesign to do **with the mentor up front** —
not casually. If she labels 50 examples against the 7 categories and we then change the taxonomy, that's
wasted expert effort. Hence the ordered asks below.

---

## 5. Ordered asks to the mentor

1. **Validate the taxonomy itself** (this document). Is there a canonical Ensembl/EBI framing or a standard
   we should adopt? Should it be **multi-label / factor-based** rather than single-category? (Present the
   mouse-somatic-SV overlap as the concrete failure of single-label.)
2. **Then** the `priority_by_use_case` scores + the per-option explanations (these still need her domain
   authority — they're judgment, not derivable).
3. **Then** the example count + schema (so the gold set is built on a validated taxonomy).

---

## Appendix — sourced citations

**Ensembl-official pass:**
- VEP docs index — https://www.ensembl.org/info/docs/tools/vep/index.html
- VEP "Examples and use cases" page — https://www.ensembl.org/info/docs/tools/vep/script/vep_example.html
- VEP web/online docs — https://www.ensembl.org/info/docs/tools/vep/online/index.html ; options reference —
  https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html ; FAQ — .../vep_faq.html
- McLaren et al. 2016, *Genome Biology* 17:122 — https://doi.org/10.1186/s13059-016-0974-4 (PMC4893825)
- Official VEP tutorial, Hunt et al. (PMC7613081) — ACMG 5% AF + MANE-Select-default heuristics
- Ensembl/EBI training — training.ensembl.org ; ebi.ac.uk/training (VEP materials)
- Local provenance: `work/ensembl_source/VEPConstants.pm` (`CONFIG_SECTIONS`, release/115)

**Field-standard pass:**
- ACMG/AMP 2015 germline guidelines (Richards et al.); AMP/ASCO/CAP 2017 somatic (Li et al.) — JMD,
  CIViC course materials.
- ClinGen CNV technical standard (Riggs et al.) — clinicalgenome.org; GIM.
- gnomAD-SV (Broad, 2019); AnnotSV (Bioinformatics 2018, lbgi.fr/AnnotSV).
- GATK Funcotator (germline/somatic data-source bundles); GATK joint-calling logic; GLnexus.
- VEP options / examples / cache docs (ensembl.org); OpenCRAVAT (bioRxiv 2019); Nirvana (clinical-grade).
- Sequence Ontology (Genome Biology 2005; J Biomed Semantics 2015); GENO ontology.

*Honesty: no formally-named "variant-annotation workflow taxonomy" exists in the literature; the
convergence above is de-facto, assembled across standards/tools. Axis-renaming and the regulatory/scale
caveats are reasoned inferences, flagged as such. Full URLs are in the research-agent transcript.*
