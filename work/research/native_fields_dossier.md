All CLI flags confirmed against the live doc. I now have everything needed to produce the dossier, fully grounded in the source files and the CLI reference.

# Ensembl VEP Web Form — Native Field Catalogue (release/115)

Scope: every NATIVE web-form field (non-plugin, non-custom) emitted by `InputForm.pm` `_build_*` subs, with labels/helptips/value-lists from `Object_VEP.pm::get_form_details`, organised by the six canonical `CONFIG_SECTIONS` ids from `VEPConstants.pm`. CLI flags and canonical phrasing verified against `https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html`.

Species rule applied: a field is **human-only** when its `field_class` is `_stt_Homo_sapiens` with no other species token; otherwise **all species** (or the stated subset). `_stt_core/_stt_gencode_basic/_stt_gencode_primary/_stt_merged` tokens are transcript-database gating, not species gating.

NEW = not present in the demo's 26-option `vep_options.json`. CORRECTED = present in the demo but mismodelled.

---

## PRE-SECTION — Transcript database (rendered before the 6 togglable sections; not inside any CONFIG_SECTION)

### core_type — "Transcript database to use"
- **web-name:** `core_type`
- **CLI flag:** no flag for `core` (Ensembl default); `gencode_basic` → `--gencode_basic`; `gencode_primary` → `--gencode_primary`; `refseq` → `--refseq`; `merged` → `--merged`
- **section:** pre-section (InputForm.pm L206-217; only rendered if any species has refseq data). Closest catalogue home: `advanced` is wrong — keep as its own pre-section / transcript-selection concept.
- **subsection:** Transcript database
- **type:** radiolist · **default:** `core`
- **values:** `core`="Ensembl transcripts"; `gencode_basic`="Ensembl/GENCODE basic transcripts"; `gencode_primary`="Ensembl/GENCODE primary transcripts"; `refseq`="RefSeq transcripts"; `merged`="Ensembl and RefSeq transcripts"
- **species_restriction:** all species, but the *field itself only appears* for species that have RefSeq data (`field_class _stt_rfq`). For species without RefSeq, Ensembl is implicit.
- **description (helptip):** "Gencode basic: a subset of the Ensembl transcript set; partial and other low quality transcripts are removed. RefSeq: aligned transcripts from NCBI RefSeq."
- **when_to_use:** Choose Ensembl/GENCODE for most analyses; RefSeq when downstream/clinical tools need NCBI transcript IDs; merged for both.
- **when_not_to_use:** Avoid merged unless you genuinely need both sets (it inflates output); RefSeq coverage is patchy for non-human species.
- **side_effects/caveats:** The selected value sets many of the `_stt_core/_stt_gencode_*/_stt_merged` field-class gates that show/hide `tsl`, `appris`, `mane`, `canonical`, `domains`. CORRECTED: demo's `transcript_set` → `core_type`; value set must include `gencode_primary`.

---

## Section `identifiers` — "Identifiers"
(InputForm.pm `_build_identifiers`, L368-436)

### symbol — "Gene symbol"
- CLI: `--symbol` · section `identifiers` · type checkbox · **default ON (checked=1)** · all species
- helptip: "Report the gene symbol (e.g. HGNC)." Doc: "Adds the gene symbol (e.g. HGNC) (where available) to the output."
- when_to_use: Almost always; most human-readable gene identifier. when_not_to_use: Rarely off; only for ultra-minimal output. side_effects: Adds SYMBOL column; suppressed by `summary`/`most_severe`.

### transcript_version — "Transcript version"
- CLI: `--transcript_version` · section `identifiers` · type checkbox · **default ON** · all species
- helptip: "Report the transcript version (e.g. ENST00000380152.7)." Doc: "Add version numbers to Ensembl transcript identifiers."
- when_to_use: When you need exact versioned transcript IDs for reproducibility/clinical records. when_not_to_use: When matching against version-agnostic IDs. side_effects: Appends `.N` to transcript IDs.

### ccds — "CCDS"
- CLI: `--ccds` · section `identifiers` · type checkbox · **default off (unchecked)** · **human + mouse** (field_class `_stt_Homo_sapiens _stt_Mus_musculus` plus transcript-db tokens; field only added when Homo_sapiens present in species list)
- helptip: "Report the Consensus CDS identifier where applicable." Doc: "Adds the CCDS transcript identifer (where available) to the output."
- when_to_use: When linking to NCBI/CCDS-based clinical resources. when_not_to_use: Non-CCDS species or non-coding work. side_effects: Adds CCDS column.

### protein — "Protein"
- CLI: `--protein` · section `identifiers` · type checkbox · **default off** (no `'checked'` key in InputForm.pm L409-415, so unchecked — note this contradicts the "on" claim in the brief; source is authoritative: NOT checked) · all species
- helptip: "Report the Ensembl protein identifier." Doc: "Add the Ensembl protein identifier to the output where appropriate."
- when_to_use: Protein-level/structural downstream analysis. when_not_to_use: Non-coding analysis. side_effects: Adds ENSP column; suppressed by `summary`/`most_severe`.

### uniprot — "UniProt"
- CLI: `--uniprot` · section `identifiers` · type checkbox · **default off** · all species
- helptip: "Report identifiers from SWISSPROT, TrEMBL and UniParc." Doc: "Adds best match accessions for translated protein products from three UniProt-related databases."
- when_to_use: Mapping to UniProt/SwissProt resources. when_not_to_use: Non-coding work. side_effects: Adds SWISSPROT/TREMBL/UNIPARC columns.

### hgvs — "HGVS"
- CLI: `--hgvs` · section `identifiers` · type checkbox · **default off** (no `'checked'` key, L425-431 — source authoritative; brief's "ON" is not borne out by InputForm.pm) · all species
- helptip: "Report HGVSc (coding sequence) and HGVSp (protein) notations for your variants." Doc: "Add HGVS nomenclature based on Ensembl stable identifiers to the output."
- when_to_use: Clinical reporting, ACMG-compliant notation, database submission. when_not_to_use: Quick exploratory runs. side_effects: Adds HGVSc/HGVSp; suppressed by `summary`/`most_severe`; needs FASTA in offline mode. CORRECTED in demo: was in section "Identifiers and transcript information" → must be `identifiers`.

---

## Section `variants_frequency_data` — "Variants and frequency data"
(InputForm.pm `_build_variants_frequency_data`, L438-637; whole section only shown for species with variation data / relevant plugins / customs)

### check_existing — "Find co-located short variants"
- CLI: `--check_existing` · section `variants_frequency_data` · type dropdown · **default `yes`** · species with variation (`field_class _stt_var`)
- values: `no`="No"; `yes`="Yes"; `no_allele`="Yes but don't compare alleles" (→ CLI `--check_existing` with allele-comparison disabled, i.e. `--no_check_alleles` behaviour)
- helptip: "Report known variants from the Ensembl Variation database that are co-located with input. Use 'compare alleles' to only report co-located variants where none of the input variant's alleles are novel." Doc: "Checks for the existence of known variants that are co-located with your input."
- when_to_use: Almost always — yields rsIDs, ClinVar CLIN_SIG, SOMATIC, PHENO. when_not_to_use: Speed-critical large population runs needing consequence only. side_effects: Gates the human frequency/citation block (`_stt_yes`/`_stt_allele` children). NOTE on clinvar: ClinVar significance reaches the web output via this field (co-located variants), NOT a standalone native checkbox — model clinvar source_type as derived-from-check_existing, not a native field. CORRECTED in demo.

### var_synonyms — "Variant synonyms"
- CLI: `--var_synonyms` · section `variants_frequency_data` · type checkbox · **default off (checked=0)** · **human + pig** (field_class `_stt_Homo_sapiens _stt_Sus_scrofa`; child classes `_stt_yes _stt_allele`)
- helptip: "Report known synonyms for co-located variants." Doc: same.
- when_to_use: When you need alternative IDs/synonyms for known variants. when_not_to_use: Other species; minimal output. side_effects: Only meaningful when check_existing is on (gated by `_stt_yes`/`_stt_allele`). NEW vs demo.

### af — "1000 Genomes global minor allele frequency"
- CLI: `--af` · section `variants_frequency_data` · type checkbox (in human checklist) · **default ON (checked=1)** · **human-only** (parent div `_stt_Homo_sapiens`)
- helptip: "Report the minor allele frequency for the combined 1000 Genomes Project phase 3 population." Doc: "Add the global allele frequency (AF) from 1000 Genomes Phase 3 data for known co-located variants."
- when_to_use: Baseline population frequency for filtering common variants. when_not_to_use: Non-human; somatic driver hunts. side_effects: Adds global AF column; gated by check_existing. CORRECTED: `af` (global) is DISTINCT from `af_1kg` (continental).

### af_1kg — "1000 Genomes continental allele frequencies"
- CLI: `--af_1kg` · section `variants_frequency_data` · type checkbox · **default off (checked=0)** · **human-only**
- helptip: "Report allele frequencies for the combined 1000 Genomes Project phase 3 continental populations - AFR, AMR, EAS, EUR and SAS." Doc: "Add allele frequency from continental populations of 1000 Genomes Phase 3."
- when_to_use: Population-genetics comparisons across super-populations. when_not_to_use: When gnomAD frequencies suffice; non-human. side_effects: Adds AFR/AMR/EAS/EUR/SAS_AF columns. NEW vs demo (demo only had the global concept).

### af_gnomade — "gnomAD (exomes) allele frequencies"
- CLI: `--af_gnomade` · section `variants_frequency_data` · type checkbox · **default off** · **human-only**
- helptip: "Report allele frequencies from the genome Aggregation Database (exomes)." Doc: "Include allele frequency from gnomAD exome populations."
- when_to_use: Exome/panel data common-variant filtering. when_not_to_use: Non-human; somatic. side_effects: Adds gnomADe population columns. CORRECTED: demo's single `gnomad_af` must split into `af_gnomade` + `af_gnomadg`.

### af_gnomadg — "gnomAD (genomes) allele frequencies"
- CLI: `--af_gnomadg` · section `variants_frequency_data` · type checkbox · **default off** · **human-only**
- helptip: "Report allele frequencies from the genome Aggregation Database (genomes)." Doc: "Include allele frequency from gnomAD genome populations."
- when_to_use: WGS data common-variant filtering; whole-genome coverage. when_not_to_use: Non-human; somatic. side_effects: Adds gnomADg population columns. CORRECTED (split from `gnomad_af`).

### pubmed — "PubMed IDs for citations of co-located variants"
- CLI: `--pubmed` · section `variants_frequency_data` · type checkbox · **default ON (checked=1)** · **human-only** (inside `_stt_Homo_sapiens` block; child classes `_stt_yes _stt_allele`)
- helptip: "Report the PubMed IDs of any publications that cite this variant." Doc: "Report Pubmed IDs for publications that cite existing variant."
- when_to_use: Literature triage; checking prior reports of a variant. when_not_to_use: Non-human; bulk runs. side_effects: Adds PUBMED column; gated by check_existing. NEW vs demo.

### failed — "Include flagged variants"
- CLI: `--failed 1` (default `--failed 0`) · section `variants_frequency_data` · type checkbox · **default off (checked=0, value=1)** · species with variation (child classes `_stt_yes _stt_allele`)
- helptip: "The Ensembl QC pipeline flags some variants as failed; by default these are not included when searching for known variants." Doc: "--failed [0|1] Default: 0 (exclude)."
- when_to_use: When you want QC-failed known variants included in co-located lookups. when_not_to_use: Default clinical work (keep failed excluded). side_effects: Can surface lower-quality known variants. NEW vs demo.

---

## Section `additional_annotations` — "Additional annotations"
(InputForm.pm `_build_additional_annotations`, L639-885; multiple subsections)

### Subsection: Transcript annotation

#### biotype — "Transcript biotype"
- CLI: `--biotype` · type checkbox · **default ON (checked=1)** · all species
- helptip: "Report the biotype of overlapped transcripts, e.g. protein_coding, miRNA, psuedogene." Doc: "Adds the biotype of the transcript or regulatory feature."
- when_to_use: Almost always; distinguishes coding vs ncRNA vs pseudogene. when_not_to_use: Minimal output only. side_effects: Adds BIOTYPE column. NEW vs demo.

#### numbers — "Exon and intron numbers"
- CLI: `--numbers` · type checkbox · **default off (checked=0)** · all species
- helptip: "For variants that fall in the exon or intron, report the exon or intron number as NUMBER / TOTAL." Doc: "Adds affected exon and intron numbering... Number/Total."
- when_to_use: Reporting which exon/intron is hit (clinical reports, primer design). when_not_to_use: Non-coding/bulk. side_effects: Adds EXON/INTRON columns. NEW vs demo.

#### tsl — "Transcript support level"
- CLI: `--tsl` · type checkbox · **default ON (checked=1)** · **human-only** (field_class transcript-db tokens + `_stt_Homo_sapiens`; field only added if Homo_sapiens present)
- helptip: glossary lookup for "TSL" (Transcript Support Level). Doc: "Adds the transcript support level for this transcript to the output."
- when_to_use: Human transcript prioritisation / pick ranking. when_not_to_use: Non-human. side_effects: Adds TSL column; feeds `--pick` ranking. NEW vs demo.

#### appris — "APPRIS"
- CLI: `--appris` · type checkbox · **default ON (checked=1)** · **human-only**
- helptip: glossary lookup for "APPRIS". Doc: "Adds the APPRIS isoform annotation for this transcript to the output."
- when_to_use: Principal-isoform identification (human). when_not_to_use: Non-human. side_effects: Adds APPRIS column; feeds `--pick` ranking. NEW vs demo.

#### mane — "MANE"
- CLI: `--mane` · type checkbox · **default ON (checked=1)** · **human-only**
- helptip: glossary lookup for "MANE". Doc: "Adds a flag indicating if transcript is MANE Select or MANE Plus Clinical."
- when_to_use: Clinical reporting — flags the community-agreed representative transcript (MANE Select + MANE Plus Clinical). when_not_to_use: Non-human; GRCh37. side_effects: Flag only (does not filter); top of `--pick` ranking. CORRECTED: demo's `mane_select` → `mane`; the native flag is `--mane` (Select + Plus Clinical), not `--mane_select`.

#### canonical — "Identify canonical transcripts"
- CLI: `--canonical` · type checkbox · **default off (checked=0)** · all species (field_class transcript-db tokens only, no species token)
- helptip: glossary lookup for "Canonical transcript". Doc: "Adds a flag indicating if the transcript is the canonical transcript for the gene."
- when_to_use: Identify primary transcript per gene, especially non-human (where MANE absent). when_not_to_use: For human clinical prefer MANE. side_effects: Flag only; feeds `--pick`. (In demo already; keep section `additional_annotations`.)

#### distance — "Upstream/Downstream distance (bp)"
- CLI: `--distance [bp]` · type string (free text) · **default `5000`** (`MAX_DISTANCE_FROM_TRANSCRIPT`) · all species
- helptip: "Change the distance to transcript for which VEP assigns upstream and downstream consequences." Doc: "Default: 5000. Modify distance between variant and transcript for upstream/downstream consequences."
- when_to_use: Widen/narrow the up/downstream calling window. when_not_to_use: Default suits most. side_effects: Larger values increase upstream/downstream_gene_variant calls. NEW vs demo.

#### mirna — "miRNA structure"
- CLI: `--mirna` · type checkbox · **default off (checked=0)** · all species
- helptip: "Determines where in the secondary structure of a miRNA a variant falls." Doc: "Reports where the variant lies in the miRNA secondary structure."
- when_to_use: Variants in miRNA genes; secondary-structure context. when_not_to_use: Non-miRNA analyses. side_effects: Adds miRNA structure annotation; requires miRNA secondary-structure data. NEW vs demo. (Exact label is "miRNA structure"; the brief's "...miRNA secondary structure..." paraphrases the helptip.)

### Subsection: Protein annotation

#### domains — "Protein matches"
- CLI: `--domains` · type checkbox · **default off (checked=0)** · all species (field_class transcript-db tokens only)
- helptip: "Report overlapping protein domains from Pfam, Prosite and InterPro. Link to a protein 3D viewer when the variants overlap an Alphafold model or a PDB protein model." Doc: "Adds names of overlapping protein domains to output."
- when_to_use: Missense interpretation — is the residue in a functional domain. when_not_to_use: Non-coding. side_effects: Adds DOMAINS column; suppressed by `summary`/`most_severe`. NOTE exact web label is "Protein matches" (not "Protein domains"). CORRECTED in demo (label + section `additional_annotations`).

### Subsection: Regulatory data
(rendered per regulatory-capable species; the whole subsection's visibility is class-gated to those species)

#### regulatory — "Get regulatory region consequences"
- web-name: per-species `regulatory_<Species>` (e.g. `regulatory_Homo_sapiens`); canonical CLI `--regulatory`
- CLI: `--regulatory` (and `cell` value additionally enables cell-type limiting) · type dropdown · **default `reg` (=Yes)** in the per-species widget (note: overall section hidden unless species has a regulatory build) · species with a regulatory build (human, mouse, and others with `DATABASE_FUNCGEN` Regulatory_Build)
- values: `no`="No"; `reg`="Yes"; `cell`="Yes and limit by cell type"
- helptip: "Get consequences for variants that overlap regulatory features and transcription factor binding motifs." Doc: "Look for overlaps with regulatory regions."
- when_to_use: Non-coding/GWAS/regulatory variant interpretation. when_not_to_use: Pure exome work; speed-critical runs. side_effects: Reduces max buffer size from 5000 to 500 on the web interface (see advanced `buffer_size` note); adds regulatory_region_variant / TF binding consequences. (In demo; keep section `additional_annotations`. Default in demo said "no" — source default for the per-species dropdown is `reg`.)

#### cell_type — "Limit to cell type(s)"
- web-name: per-species `cell_type_<Species>`; CLI `--cell_type [list]` · type dropdown multiple-select · **default n/a** (shown only when regulatory dropdown = `cell`) · depends on regulatory build (values are that species' epigenome short names)
- helptip: "Select one or more cell types to limit regulatory feature results to. Hold Ctrl (Windows) or Cmd (Mac) to select multiple entries." Doc: "Report only regulatory regions found in the given cell type(s)."
- when_to_use: Restrict regulatory consequences to tissue/cell types of interest. when_not_to_use: When you want all cell types. side_effects: Filters regulatory output to chosen epigenomes; depends on `regulatory=cell`. NEW vs demo.

### Subsection: Phenotype data and citations
- This subsection's fieldset is created only for species with phenotype data; it carries no hard-coded native checkbox in `_build_*` — its content is injected by the **Phenotypes plugin** (`_end_section`/`_add_plugins`). The associated native CLI behaviour is **`--gene_phenotype`** ("Indicates if the overlapped gene is associated with a phenotype, disease or trait"; adds GENE_PHENO flag). Model `gene_phenotype` as section `additional_annotations`, subsection "Phenotype data and citations", source_type=native-CLI-but-plugin-driven-on-web. all species (most data human). (Demo had `gene_phenotype` under "Phenotype data and citations" → map to `additional_annotations`.)

### Subsection: Regulatory impact
- Plugin-only subsection (Enformer/UTRAnnotator-class plugins). No native field. Not a native catalogue entry.

---

## Section `predictions` — "Predictions"
(InputForm.pm `_build_predictions`, L888-942; "Pathogenicity predictions" subsection. Section shown only if a species has SIFT or PolyPhen data.)

### sift — "SIFT"
- CLI: `--sift [p|s|b]` · type dropdown · **default `b`** · **species with SIFT data** (`field_class _stt_sift`; NOT human-only — many species have SIFT)
- values: `no`="No"; `b`="Prediction and score"; `p`="Prediction only"; `s`="Score only"
- helptip: "Report SIFT scores and/or predictions for missense variants. SIFT is an algorithm to predict whether an amino acid substitution is likely to affect protein function." Doc: "Output SIFT prediction term, score, or both."
- when_to_use: Missense functional-impact assessment; use `b` for both. when_not_to_use: Non-coding/structural; suppressed by `summary`/`most_severe`. side_effects: Output only for missense variants. (In demo; species_restriction must be "many species with SIFT data", NOT human-only.)

### polyphen — "PolyPhen"
- CLI: `--polyphen [p|s|b]` · type dropdown · **default `b`** · **human-only** (`field_class _stt_pphn`; PolyPhen precomputed data is human-only)
- values: `no`="No"; `b`="Prediction and score"; `p`="Prediction only"; `s`="Score only"
- helptip: "Report PolyPhen scores and/or predictions for missense variants. PolyPhen is an algorithm to predict whether an amino acid substitution is likely to affect protein function." Doc: "Output PolyPhen prediction term, score, or both."
- when_to_use: Missense impact (human); complementary to SIFT. when_not_to_use: Non-human; non-coding; suppressed by `summary`/`most_severe`. side_effects: Output only for missense variants. (In demo; keep human-only.)

(Note: CADD/REVEL/AlphaMissense/SpliceAI/MaxEntScan/dbNSFP etc. appear in this section ONLY as PLUGINS via `_add_plugin_sections`; source_type=plugin, NOT native checkboxes — exclude from native catalogue. CORRECTED vs demo, which wrongly listed cadd/revel/alphamissense/spliceai/maxentscan as native.)

---

## Section `filters` — "Filtering options"
(InputForm.pm `_build_filters`, L290-366)

### frequency — "Filter by frequency"
- CLI: `--check_frequency` (plus `--freq_pop`, `--freq_freq`, `--freq_gt_lt`, `--freq_filter`) · type radiolist · **default `no`** · **human-only** (`field_class _stt_Homo_sapiens`; whole field only added if Homo_sapiens present)
- values: `no`="No filtering"; `common`="Exclude common variants"; `advanced`="Advanced filtering"
- helptip: "Exclude common variants to remove input variants that overlap with known variants that have a minor allele frequency greater than 1% in the 1000 Genomes Phase 1 combined population. Use advanced filtering to change the population, frequency threshold and other parameters." Doc (`--check_frequency`): "Turns on frequency filtering based on co-located existing variant frequencies."
- Sub-controls (shown when `advanced`, `_stt_advanced`):
  - `freq_filter` (dropdown, default `exclude`): `exclude`="Exclude" / `include`="Include only" → `--freq_filter [exclude|include]`
  - `freq_gt_lt` (dropdown, default `gt`): `gt`="variants with MAF greater than" / `lt`="variants with MAF less than" → `--freq_gt_lt [gt|lt]`
  - `freq_freq` (string, default `0.01`, max 1) → `--freq_freq [0-1]`
  - `freq_pop` (dropdown, default `1kg_all`): `1kg_all`,`1kg_afr`,`1kg_amr`,`1kg_eas`,`1kg_eur`,`1kg_sas`,`aa` (ESP African-American), `ea` (ESP European-American) → `--freq_pop [pop]`
- when_to_use: Pre-filter input to drop common (or keep only common) variants by population MAF. when_not_to_use: Non-human; when you want all variants retained. side_effects: This is an input/pre-filter that can remove variants from results entirely (not just annotation). NEW vs demo (incl. all four sub-controls).

### coding_only — "Return results for variants in coding regions only"
- CLI: `--coding_only` · type checkbox · **default off (checked=0, value=yes)** · all species
- helptip: "Exclude results in intronic and intergenic regions." Doc: "Only return consequences that fall in the coding regions of transcripts."
- when_to_use: Exome/coding-only triage. when_not_to_use: Non-coding/regulatory/splicing work (drops those results). side_effects: Removes intronic/intergenic consequences from output. NEW vs demo.

### "Restrict results" dropdown — single control `summary`, mutually-exclusive values
- web-name: `summary` · web label: **"Restrict results"** · type dropdown · **default `no`** · all species · section `filters`
- helptip: "Restrict results by severity of consequence; note that consequence ranks are determined subjectively by Ensembl." Form note: "NB: Restricting results may exclude biologically important data!"
- CORRECTED: these are VALUES of ONE dropdown, NOT separate native checkboxes. Model as mutually-exclusive entries in `filters`. Listed individually per the brief:

  - **`no`** — "Show all results" — no CLI flag (default). Use: keep everything. side_effects: largest output.
  - **`pick`** — "Show one selected consequence per variant" — CLI `--pick`. Doc: "Pick one line of consequence data per variant according to specified criteria." Use: one representative consequence/variant; reduces volume. Not when: you need all transcripts (e.g. cancer). side_effects: may drop clinically relevant non-picked transcripts; ranking uses MANE>canonical>APPRIS>TSL>biotype>CCDS>rank>length.
  - **`pick_allele`** — "Show one selected consequence per variant allele" — CLI `--pick_allele`. Doc: "Like --pick, but chooses one line per variant allele." Use: multi-allelic sites where you want one consequence per allele. NEW vs demo.
  - **`per_gene`** — "Show one selected consequence per gene" — CLI `--per_gene`. Doc: "Output only the most severe consequence per gene." Use: multi-gene overlaps, worst consequence per gene. side_effects: preserves multi-gene overlaps, reduces transcript detail.
  - **`summary`** — "Show only list of consequences per variant" — CLI `--summary`. Doc: "Output only a comma-separated list of all observed consequences per variant." Use: quick triage. Not when: you need per-transcript detail (suppresses SIFT/PolyPhen/HGVS/symbol/protein/domains). NEW vs demo as a dropdown value.
  - **`most_severe`** — "Show most severe consequence per variant" — CLI `--most_severe`. Doc: "Output only the most severe consequence per variant." Use: single worst term per variant. Not when: any transcript-level annotation needed (incompatible with sift, polyphen, hgvs, symbol, protein, domains, canonical, mane). side_effects: loses all transcript-level annotation.
- Caveat: `pick`/`pick_allele`/`per_gene`/`summary`/`most_severe` are mutually exclusive (one dropdown). `summary`/`most_severe` additionally suppress the identifier/prediction columns above.

---

## Section `advanced` — "Advanced options"
(InputForm.pm `_build_advanced`, L946-987)

### buffer_size — "Buffer size"
- CLI: `--buffer_size [number]` · type dropdown · **default `5000`** · all species
- values: `5000`, `2500`, `1000`, `500`, `250`, `100`
- helptip: "Number of variants that are read in to memory simultaneously (default value: 5000)." Doc: "Default: 5000. Sets internal buffer size."
- Form note (regulatory species only): "When the Regulatory data option is selected then due to the large amount of regulatory data available, the maximum buffer size is automatically reduced from the default value of 5000 to 500... you can select a value lower than 500."
- when_to_use: Lower it to reduce memory if jobs fail; raise for speed if memory allows. when_not_to_use: Default fine for most. side_effects: Interacts with `regulatory` (auto-capped at 500). Exact label is "Buffer size" (brief left it blank). NEW vs demo.

### shift_3prime — "Right align variants prior to consequence calculation"
- CLI: `--shift_3prime [0|1]` (default 0); the `shift_genomic` value maps to additional genomic-update behaviour · type dropdown · **default `no`** · all species
- values: `no`="No"; `shift_3prime`="Right align relative to transcript"; `shift_genomic`="Right align relative to transcript and update genomic location"
- helptip: "Insertions and deletions within repeated regions will be shifted in the 3' direction relative to their associated transcripts prior to consequence calculation." Doc: "Default: 0. Right aligns all variants relative to associated transcripts."
- when_to_use: Indels in repeat regions where 3'-shifting normalises consequence calls. when_not_to_use: When you require left-aligned/VCF-normalised positions unchanged. side_effects: Can change reported variant position/consequence; `shift_genomic` also updates genomic coordinates. NEW vs demo.

---

## Summary of corrections to the demo's 26 options
- `transcript_set` → **`core_type`**; add value `gencode_primary`; CLI for default `core` is no flag.
- `mane_select`/`--mane_select` → **`mane`/`--mane`** (MANE Select + MANE Plus Clinical), section `additional_annotations`.
- `gnomad_af` → split into **`af_gnomade`** (`--af_gnomade`) and **`af_gnomadg`** (`--af_gnomadg`).
- **`af`** (global 1000G, `--af`, default ON) is distinct from **`af_1kg`** (continental, `--af_1kg`, default off).
- `pick`/`pick_allele`/`per_gene`/`summary`/`most_severe` are **values of one `summary` dropdown labelled "Restrict results"** in `filters`, not separate native checkboxes.
- CADD/REVEL/AlphaMissense/SpliceAI/MaxEntScan/dbNSFP are **plugins** (source_type=plugin), not native fields.
- **clinvar** is not a native checkbox: ClinVar CLIN_SIG arrives via `check_existing` co-located variants (+ plugins). Mark source_type=derived.
- `web_form_section` for every field re-mapped to one of the 6 canonical ids: `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters`, `advanced` (the demo's "Identifiers and transcript information", "Transcript set", "N/A (CLI custom annotation)" are not valid section ids).

## NEW native fields absent from the demo's 26
`transcript_version`, `ccds`, `protein`, `uniprot`, `var_synonyms`, `af` (as distinct global), `af_1kg`, `af_gnomade`, `af_gnomadg`, `pubmed`, `failed`, `biotype`, `numbers`, `tsl`, `appris`, `distance`, `mirna`, `cell_type`, `frequency` (+`freq_pop`/`freq_freq`/`freq_gt_lt`/`freq_filter`), `coding_only`, `pick_allele`, `buffer_size`, `shift_3prime`.

## Discrepancies between the brief's defaults and the authoritative source (`InputForm.pm`)
- `protein`: brief says default "on" — InputForm.pm L409-415 has **no `checked` key → default OFF**.
- `hgvs`: brief says default "ON" — InputForm.pm L425-431 has **no `checked` key → default OFF**.
- `regulatory`: brief says default "no" — the per-species dropdown default in InputForm.pm L779 is **`reg` (=Yes)** (though the whole section only renders for regulatory-capable species).
All other defaults in the brief match the source.

Source files: `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/VEP/InputForm.pm`, `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/Object_VEP.pm`, `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/VEPConstants.pm`, `/Users/davidgao/Desktop/GSoC_WORK/vep_ai_demo/vep_options.json`; CLI flags verified at `https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html`.