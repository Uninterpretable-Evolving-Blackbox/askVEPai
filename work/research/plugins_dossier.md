I now have all 26 plugins grounded against the release/115 source and live docs, plus the InputForm.pm injection logic and custom datasets. Here is the complete catalogue.

---

# VEP Web-Exposed Plugins Catalogue (release/115)

## How plugins inject into the form (from InputForm.pm)
Plugins are NOT a standalone "Plugins" section. `_add_plugin_sections` / `_add_plugins` inject each plugin into one of the 6 canonical `CONFIG_SECTIONS` based on the plugin config's `section` field:
- `_build_predictions` calls `_add_plugin_sections($form, \@fieldsets)` AFTER the native SIFT/PolyPhen block (no filter) → plugins land under **predictions**.
- `_build_additional_annotations` calls `_add_plugin_sections` with filters `'Gene tolerance to change'` (before Transcript annotation), `"Functional effect"` (after Protein annotation), and creates a `'Regulatory impact'` fieldset → plugins land under **additional_annotations** sub-fieldsets.
- `_build_variants_frequency_data` adds a `'Variant data'` plugin sub-section → **variants_frequency_data**.
- CLI form for every plugin: `--plugin <Name>[,args]` (InputForm builds `plugin_<key>` form fields; the script command is `--plugin Name`).
- Each plugin renders either a checkbox (enable) or a radiolist (Disabled/Enabled) plus argument sub-fields when `$plugin->{form}` is defined.

**Species gating:** `_add_plugins` sets `field_class = _stt_<Species>` from the plugin's `species` array and skips the plugin unless that species is in the form's species list (`next unless duplicates ...`). A plugin with no `species` / `'*'` is all-species.

---

## The 26 plugins

Sections below use the canonical id, then the InputForm sub-fieldset legend in parentheses.

### Pathogenicity / missense predictors → `predictions` (HUMAN-ONLY)

1. **CADD** — `--plugin CADD` — "Combined Annotation Dependent Depletion... retrieves CADD scores for variants from one or more tabix-indexed CADD data files." Predicts combined deleteriousness (RawScore + PHRED) for SNVs, indels, and SVs. Source: CADD database (cadd.gs.washington.edu), tabix files. Species: human, GRCh37+GRCh38. Section: predictions. Use: rare disease, cancer, general variant prioritisation.

2. **REVEL** — `--plugin REVEL` — "Rare Exome Variant Ensemble Learner." Ensemble pathogenicity score (0–1) for missense variants. Source: REVEL downloads (sites.google.com/site/revelgenomics). Species: human, GRCh37+GRCh38. Section: predictions. Use: rare disease, ACMG missense classification.

3. **AlphaMissense** — `--plugin AlphaMissense` — "annotates missense variants with the pre-computed AlphaMissense pathogenicity scores." Score + class (likely_benign/ambiguous/likely_pathogenic). Source: AlphaMissense (Google DeepMind) tabix files. Species: human, GRCh37+GRCh38. Section: predictions. Use: rare disease, missense triage.

4. **dbNSFP** — `--plugin dbNSFP` — "retrieves data for missense variants from a tabix-indexed dbNSFP file." Aggregates many in-silico predictors (SIFT, PolyPhen2, MutationTaster, FATHMM, GERP, conservation, etc.) for missense variants. Source: dbNSFP database. Species: human, GRCh37+GRCh38. Section: predictions. Use: rare disease, cancer; one-stop meta-annotation.

5. **EVE** — `--plugin EVE` — "adds information from EVE (evolutionary model of variant effect)." Unsupervised deep-learning evolutionary pathogenicity score/class for missense. Source: EVE model (evemodel.org). Species: human, GRCh38 only. Section: predictions. Use: rare disease missense.

6. **ClinPred** — `--plugin ClinPred` — "adds pre-calculated scores from ClinPred." Predicts disease-relevant (pathogenic vs benign) nonsynonymous/missense variants. Source: ClinPred precomputed scores. Species: human, GRCh37+GRCh38. Section: predictions. Use: rare disease missense classification.

7. **Blosum62** — `--plugin Blosum62` — "looks up the BLOSUM 62 substitution matrix score for the reference and alternative amino acids predicted for a missense mutation." Conservation/substitution score. Source: BLOSUM62 matrix (no external download). Species: documented as human in live page but algorithm is amino-acid based; effectively all-species where protein consequences exist (no species array in plugin config → all species). Section: predictions. Use: conservation/substitution context for missense.

### Splicing predictors → `predictions` (HUMAN-ONLY)

8. **SpliceAI** — `--plugin SpliceAI` — "retrieves pre-calculated annotations from SpliceAI." Delta scores/positions for acceptor/donor gain/loss (0–1). Source: Illumina SpliceAI precomputed files (Ensembl also provides files). Species: human, GRCh37+GRCh38. Section: predictions. Use: splicing, rare disease.

9. **dbscSNV** — `--plugin dbscSNV` — "retrieves data for splicing variants from a tabix-indexed dbscSNV file." ada_score / rf_score splice-site predictions for variants in splicing consensus regions. Source: dbscSNV database. Species: human, GRCh37+GRCh38. Section: predictions. Use: splicing.

10. **MaxEntScan** — `--plugin MaxEntScan` — "runs MaxEntScan to get splice site predictions." Maximum-entropy donor/acceptor splice-site scores. Source: MaxEntScan algorithm + Burge lab model data. Species: human (algorithmic; live docs list human). Section: predictions. Use: splicing.

### Gene tolerance / dosage → `additional_annotations` ("Gene tolerance to change")

11. **LOEUF** — `--plugin LOEUF` — "adds the LOEUF scores to VEP output." Loss-of-function observed/expected upper-bound fraction (gene constraint). Source: gnomAD constraint metrics. Species: human, GRCh37+GRCh38. Section: additional_annotations / Gene tolerance to change. Use: rare disease, LoF prioritisation.

12. **DosageSensitivity** — `--plugin DosageSensitivity` — "retrieves haploinsufficiency and triplosensitivity probability scores for affected genes from a dosage sensitivity catalogue." pHaplo / pTriplo. Source: Collins et al. rCNV dosage sensitivity scores. Species: human. Section: additional_annotations / Gene tolerance to change. Use: structural/CNV, rare disease, dosage.

### Functional / protein / experimental effect → `additional_annotations` ("Functional effect")

13. **mutfunc** — `--plugin mutfunc` — "retrieves data from mutfunc db predicting destabilization of protein structure, interaction interface, and motif." Source: mutfunc SQLite db. Species: human. Section: additional_annotations / Functional effect. Use: protein structure/interaction impact.

14. **MaveDB** — `--plugin MaveDB` — "retrieves data from MaveDB... multiplex assays of variant effect, including deep mutational scans and massively parallel reporter assays." Experimental functional scores. Source: MaveDB. Species: human, GRCh38 only. Section: additional_annotations / Functional effect. Use: functional evidence, rare disease.

15. **IntAct** — `--plugin IntAct` — "retrieves molecular interaction data for variants as reported by IntAct database." Source: IntAct (EBI). Species: human. Section: additional_annotations / Functional effect. Use: protein-protein interaction, mechanism.

16. **NMD** — `--plugin NMD` — "Nonsense-mediated mRNA decay escaping variants prediction." Rule-based flag whether a PTC escapes NMD (last exon, 50 bp of penultimate exon, first 100 coding bp, intronless). Source: transcript-structure analysis (no external data file). Species: all species (organism-agnostic; no species array → all). Section: additional_annotations / Functional effect. Use: LoF interpretation, rare disease.

17. **UTRAnnotator** — `--plugin UTRAnnotator` — "annotates the effect of 5' UTR variant especially for variant creating/disrupting upstream ORFs." uORF gain/loss, uAUG, Kozak, stop changes. Source: uORF_5UTR_GRCh37/38_PUBLIC.txt (Ensembl/UTRannotator repo). Species: human, GRCh37+GRCh38. Section: additional_annotations / Functional effect. Use: non-coding/UTR regulatory, rare disease.

18. **Paralogues** — `--plugin Paralogues` — annotates "variants overlapping the genomic coordinates of amino acids aligned between paralogue proteins" to predict pathogenicity by paralogue transfer. Source: custom VCF / VEP cache / Ensembl API; uses Ensembl paralogue annotations. Species: any species with Ensembl paralogues (human needs `--assembly`). Section: additional_annotations / Functional effect. Use: rare disease, paralogue-based missense interpretation.

19. **RiboseqORFs** — `--plugin RiboseqORFs` — "uses a standardized catalog of human Ribo-seq ORFs to re-calculate consequences for variants located in these translated regions." Source: GENCODE Ribo-seq ORFs (ftp.ebi.ac.uk/pub/databases/gencode/riboseq_orfs). Species: human only. Section: additional_annotations / Functional effect. Use: non-canonical ORFs, translation.

### Variant evidence / phenotype → `variants_frequency_data` ("Variant data") or phenotype sub-section

20. **Mastermind** — `--plugin Mastermind` — "uses the Mastermind Genomic Search Engine to report variants that have clinical evidence cited in the medical literature." Citation counts (MMCNT). Source: Mastermind (Genomenon). Species: human, GRCh37+GRCh38. Section: variants_frequency_data (Variant data). Use: clinical literature evidence, rare disease/cancer.

21. **Geno2MP** — `--plugin Geno2MP` — "adds information from Geno2MP, a web-accessible database of rare variant genotypes linked to phenotypic information." Source: Geno2MP. Species: human, GRCh37 coordinates. Section: variants_frequency_data (Variant data) / phenotype. Use: rare disease, phenotype lookup.

22. **Phenotypes** — `--plugin Phenotypes` — "retrieves overlapping phenotype information." Phenotype associations mapped to genes/variants/QTLs/regulatory features (drives the "Phenotype data and citations" section; relates to `--gene_phenotype`). Source: Ensembl phenotype annotation DB (GFF). Species: all species with variation/phenotype data. Section: additional_annotations / Phenotype data and citations. Use: rare disease, gene-phenotype.

### Regulatory / expression → `additional_annotations` ("Regulatory impact")

23. **Enformer** — `--plugin Enformer` — "adds pre-calculated Enformer predictions of variant impact on chromatin and gene expression." Source: Enformer model predictions (DeepMind). Species: human, GRCh37+GRCh38. Section: additional_annotations / Regulatory impact. Use: regulatory/non-coding, expression impact.

### Other annotations → `additional_annotations` / `identifiers`-adjacent

24. **AncestralAllele** — `--plugin AncestralAllele` — "retrieves ancestral allele sequences from a FASTA file." Source: Ensembl ancestral-sequence FASTA. Species: multiple key species (all-species capable). Section: additional_annotations (Transcript annotation grouping; no `section` → defaults to Transcript annotation per `_get_plugins_by_section`). Use: population/evolutionary, polarising alleles.

25. **GO** — `--plugin GO` — "retrieves Gene Ontology (GO) terms associated with transcripts or their translations using custom GFF annotation containing GO terms." Source: Ensembl core DB / custom GFF. Species: multiple (species-dependent). Section: additional_annotations (Transcript/Functional). Use: functional enrichment, gene annotation.

26. **OpenTargets** — `--plugin OpenTargets` — "integrates data from Open Targets Genetics... variant-centric statistical evidence... prioritisation of candidate causal variants... and identification of potential drug targets." Adds L2G (locus-to-gene) scores. Source: Open Targets Genetics (EMBL-EBI). Species: not restricted in code (effectively human GWAS data). Section: additional_annotations (Functional effect / Variant data). Use: GWAS, drug-target, complex disease.

---

## Species-restriction summary (per the catalogue rule)
- **HUMAN-ONLY** (12 strongly human, most pathogenicity/missense + human-data): CADD, REVEL, AlphaMissense, dbNSFP, EVE (GRCh38), ClinPred, SpliceAI, dbscSNV, MaxEntScan, LOEUF, DosageSensitivity, mutfunc, MaveDB (GRCh38), IntAct, UTRAnnotator, Mastermind, Geno2MP (GRCh37), RiboseqORFs, Enformer. (REVEL/CADD/AlphaMissense/dbNSFP/ClinPred/SpliceAI/dbscSNV/UTRAnnotator/Mastermind/Enformer = GRCh37+GRCh38; EVE/MaveDB = GRCh38; Geno2MP = GRCh37; RiboseqORFs = human.)
- **ALL / MULTI-SPECIES**: NMD (organism-agnostic), Blosum62 (amino-acid matrix, no species array), AncestralAllele (key species), GO (species-dependent), Phenotypes (all variation species), Paralogues (any species with paralogues), OpenTargets (not code-restricted).
- Note: SIFT is multi-species (native field, not a plugin); PolyPhen native field is human-only. Do not confuse these natives with the dbNSFP plugin that bundles them.

---

## Custom datasets (vep_custom_web_config.json) — NOT plugins (`source_type=custom`)
- **gnomAD_SV** — human GRCh38, section `variants_frequency_data` ("Variants and frequency data"). VCF, type=exact, overlap_cutoff [80/90/100/exact]. Reports SV allele frequencies (AF + 9 subpops: afr, ami, amr, asj, eas, fin, mid, nfe, rmi, sas). Use: structural/population.
- **AllOfUs** — human GRCh38, section `variants_frequency_data`. Per-chromosome VCF, type=exact. Fields gvs_all_af, gvs_max_af + subpops (afr, amr, eas, eur, mid, oth, sas). Use: population frequency.
- **GENCODE_promoter** — human GRCh38, section `additional_annotations` ("Regulatory data"). GFF, type=overlap, gff_type=gencode_promoter. Reports overlap with stable 1000 bp GENCODE promoter windows. Use: regulatory.
- (Also present in the JSON but NOT in your scope list: ClinVar_SV/nstd102 human SV clinical significance under "Phenotype data and citations"; and EVA/NextGen frequency customs for chicken, dog, goat, sheep — non-human, section variants_frequency_data.)

## ClinVar situation
There is **no standalone native ClinVar checkbox** in InputForm.pm. ClinVar clinical significance reaches the web output via (a) `check_existing` / co-located short variants in `variants_frequency_data` (Object_VEP supplies ClinVar significance through the variation DB), and (b) plugins/customs (e.g., the ClinVar_SV custom dataset for structural variants). Model ClinVar as `source_type=variation/co-located` (and a custom for SV), NOT as a native option and NOT as a plugin.

---

## Recommended ~17–20 plugins for a ~55-option catalogue
Include these (tier 1, must-have) — all `source_type=plugin`, sections as noted:

Predictions (pathogenicity/missense/splicing): **CADD, REVEL, AlphaMissense, dbNSFP, ClinPred, EVE, SpliceAI, MaxEntScan, dbscSNV, Blosum62** (10).
Gene tolerance / dosage (additional_annotations): **LOEUF, DosageSensitivity** (2).
Functional effect / non-coding (additional_annotations): **NMD, UTRAnnotator, Paralogues** (3).
Variant evidence / phenotype: **Mastermind, Phenotypes, Geno2MP** (3).

That is 18 high-priority plugins. If room for 19–20, add **mutfunc** (protein-structure functional effect) and **Enformer** (regulatory/expression) to cover the regulatory-impact and protein-destabilisation niches.

Lower priority / optional (defer if tight on space): GO, AncestralAllele, OpenTargets, IntAct, MaveDB, RiboseqORFs.

## Demo modeling corrections confirmed against source
- `transcript_set` → **core_type** (radiolist, CLI `--refseq`/`--merged`, default `core`; only shown when a species has refseq — InputForm lines 206-217).
- `mane_select` → **mane** (`--mane`, ON, human-only — line 694-702).
- `gnomad_af` → split into **af_gnomade** (`--af_gnomade`) + **af_gnomadg** (`--af_gnomadg`), both human, default off — lines 593-605.
- **af_1kg** (`--af_1kg`, continental, off) is distinct from **af** (`--af`, 1000G global MAF, ON) — lines 581-592.
- pick / pick_allele / per_gene / summary / most_severe / no / all are **mutually-exclusive VALUES of ONE dropdown** named `summary`, label "Restrict results", section `filters` (lines 348-363) — NOT separate checkboxes.
- CADD/REVEL/AlphaMissense/SpliceAI/MaxEntScan/dbNSFP are `source_type=plugin` under predictions, NOT native checkboxes.
- Every plugin's `web_form_section` must be one of: `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters`, `advanced`.

Relevant source files: `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/vep_plugins_web_config.txt`, `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/vep_custom_web_config.json`, `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/VEP/InputForm.pm`.