# Ensembl VEP web interface — input-form reference

**Purpose:** Ground truth for agents describing what the Ensembl VEP **web form** offers.
**Sources:** Ensembl public web documentation (input form, filtering, advanced options); cross-checked
against `work/ensembl_source/` (`VEPConstants.pm`, `InputForm.pm`, `vep_plugins_web_config.txt`) at
**release/115**.

**Ask VEPai catalogue rule:** Per-option `web_form_section` / `web_form_subsection` / `cli_flag` in
`work/vep_options_expanded.json` must match **release/115 source**, not model memory. If this doc and the
live Ensembl website disagree, trust `ensembl_source/` + the expanded catalogue. See also
`work/research/plugins_dossier.md`.

**Global behaviour:** Listed options **change depending on selected species**. Many predictors and
frequency fields are **human-only** (`_stt_Homo_sapiens` gating in `InputForm.pm`).

---

## Data input (not a `CONFIG_SECTION`; precedes option panels)

1. **Species** — determines which options appear.
2. **Job name** (optional).
3. **Input** — file upload, paste, or URL. Formats auto-detected (Ensembl default, VCF, rsIDs, HGVS, SPDI).
4. **Instant preview** — for pasted data, quick consequence preview on first variant.
5. **Transcript database** — Ensembl/GENCODE (default), GENCODE Basic, GENCODE Primary, RefSeq, or combined.

---

## Six canonical option sections (`CONFIG_SECTIONS`)

Ids from `VEPConstants.pm`: `identifiers` · `variants_frequency_data` · `additional_annotations` ·
`predictions` · `filters` · `advanced`

### 1. Identifiers (`identifiers`)

| Option | CLI equivalent (typical) |
|--------|--------------------------|
| Gene symbol | `--symbol` |
| Transcript version | `--transcript_version` |
| CCDS | `--ccds` |
| Protein (ENSP) | `--protein` |
| UniProt | `--uniprot` |
| HGVS (HGVSc / HGVSp) | `--hgvs` |

### 2. Variants and frequency data (`variants_frequency_data`)

| Option | Notes |
|--------|-------|
| Find co-located known variants | `--check_existing`; default compares alleles; "Yes but don't compare alleles" available |
| Variant synonyms | For co-located variants |
| 1000 Genomes global AF | `--af` |
| 1000 Genomes continental AFs | `--af_1kg` |
| gnomAD exomes AFs | `--af_gnomade` |
| gnomAD genomes AFs | `--af_gnomadg` |
| PubMed IDs for co-located variants | `--pubmed` |
| Include flagged variants | Failed QC variants |
| Paralogue variants | **Paralogues** plugin |
| Open Targets Platform | **OpenTargets** plugin |

**ClinVar:** There is **no standalone ClinVar checkbox**. `CLIN_SIG` is **derived** from co-located
variant lookup (`check_existing`). In Ask VEPai KB, `clinvar` is documented as derived from
`check_existing`.

### 3. Additional annotations (`additional_annotations`)

Sub-fieldsets (from `InputForm.pm` + live web docs):

#### Gene tolerance to change
- **DosageSensitivity** plugin — haploinsufficiency / triplosensitivity scores
- **LOEUF** plugin — gnomAD constraint

#### Transcript annotation (native + some plugins)
- Transcript biotype (`--biotype`)
- Exon and intron numbers (`--numbers`)
- Transcript support level (`--tsl`)
- APPRIS (`--appris`)
- MANE
- Identify canonical transcripts (`--canonical`)
- Upstream/downstream distance (`--distance`)
- miRNA structure (`--mirna`)
- **NMD** plugin
- **UTRAnnotator** plugin
- **RiboseqORFs** plugin

#### Protein annotation
- Protein matches / domains (`--domains`) — PDBe, AlphaFold, Pfam, Prosite, InterPro
- **mutfunc** plugin — protein structure / interaction destabilisation
- **ProtVar** plugin — missense contextualisation (structures, pockets, interfaces)

#### Functional effect (plugins)
- **IntAct** plugin — molecular interaction sites
- **MaveDB** plugin — experimental variant-effect assays

#### Regulatory data (native)
- Get regulatory region consequences (`--regulatory`) — regulatory build, TF binding motifs

#### Regulatory impact (plugins)
- **Enformer** plugin — chromatin / expression impact

#### Phenotype data and citations
- **Phenotypes** plugin — phenotype associations on genes/variants/QTLs/regulatory features
- **Gene Ontology** plugin
- **Geno2MP** plugin — rare-variant genotypes linked to HPO phenotypes
- **Mastermind** plugin — literature clinical evidence

> **Release/115 note:** In our catalogue (`vep_options_expanded.json`), **Mastermind** and **Geno2MP**
> are filed under `variants_frequency_data` / Variant data; **Phenotypes** under
> `additional_annotations`. Live web docs may group Mastermind/Geno2MP under “Phenotype data and citations”.
> For Ask VEPai, use catalogue + `ensembl_source/` fields.

### 4. Predictions (`predictions`)

#### Pathogenicity predictions (human-only natives + plugins)
- SIFT (`--sift`) — multi-species availability for native field; web pairs with PolyPhen gating
- PolyPhen (`--polyphen`) — human
- **dbNSFP**, **AlphaMissense**, **CADD**, **REVEL**, **ClinPred**, **EVE** plugins

#### Splicing predictions (plugins)
- **dbscSNV**, **MaxEntScan**, **SpliceAI**

#### Conservation (plugins)
- **BLOSUM62**, **AncestralAllele**

### 5. Filtering options (`filters`)

| Option | CLI / behaviour |
|--------|-----------------|
| Filter by frequency | `--filter_common` — exclude variants with co-located AF > 0.01 in 1000G global |
| Advanced filtering | Population + threshold + include/exclude |
| Return results for coding regions only | `--coding_only` |
| Restrict results | `--pick`, `--per_gene`, `--summary`, `--most_severe` (dropdown `summary` field) |

**Caution (from Ensembl):** Restricting results can exclude biologically important data.

### 6. Advanced options (`advanced`)

| Option | Notes |
|--------|-------|
| Buffer size | Default 5000; **max 500 when regulatory data enabled** (memory) |
| Right align variants | 3′ shift for indels in repeats |

---

## Evidence-type groupings (for priority audit, not user scenario labels)

Ensembl organises plugins into **evidence families** within the sections above:

| Family | Examples | Typical section |
|--------|----------|-----------------|
| Missense pathogenicity | SIFT, PolyPhen, CADD, REVEL, AlphaMissense, dbNSFP, ClinPred, EVE | predictions |
| Splicing | SpliceAI, dbscSNV, MaxEntScan | predictions |
| Gene constraint | LOEUF, DosageSensitivity | additional_annotations |
| Functional effect | mutfunc, MaveDB, NMD, UTRAnnotator, IntAct, RiboseqORFs | additional_annotations |
| Regulatory impact | `--regulatory`, Enformer | additional_annotations |
| Clinical / literature / phenotype | ClinVar (via check_existing), Phenotypes, Mastermind, Geno2MP | mixed |
| Population frequency | 1000G, gnomAD exomes/genomes, filter_common | variants_frequency_data |

Ask VEPai uses **scenario factors** (species, origin, size, region, goal) for labelling queries; use these
families when writing `priority_by_factor`, not as top-level user categories.

---

## Out of scope for the recommender (context only)

Jobs queue, results preview/filtering/download, input/output format specs, and FAQ are documented on the
Ensembl site but are **not** part of the web-form config the assistant recommends.

**Citation:** McLaren et al., Genome Biology 2016 (doi:10.1186/s13059-016-0974-4).
