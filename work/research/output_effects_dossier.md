# What each VEP option does to the output, and how options interact — from Ensembl's documentation

Built 2026-09-13 from the official release-116 pages saved in `research/ensembl_docs_116/` by
`harness/build_output_effects_dossier.py`. **Nothing in §1–§4 comes from running VEP.** The pages are the
record; this file reconciles our catalogue against them. Re-run the script after any catalogue edit.

Sources (all now 308-redirect to `jun2026.archive.ensembl.org`, the same move the form made):

- `vep_options.html` — every CLI flag with **Description · Output fields · Incompatible with**
- `vep_online_input.html` — the **web form**: each control, its CLI equivalent, the form's own warnings
- `vep_plugins.html` — every plugin, its category and what it adds

## 0. The page's own warnings, verbatim

These three sentences are Ensembl's, on the form page, about the whole *Filtering options* section:

> Ensembl VEP allows you to pre-filter your results e.g. by MAF or consequence type. Note that it is also
> possible to perform equivalent operations on the results page for Ensembl VEP, so if you aren't sure,
> don't use any of these options!

> Note that enabling one of these options not only loses potentially relevant data, but in some cases may
> be scientifically misleading.

> NB: Restricting results may exclude biologically important data!

So the product's own documentation says: do not pre-filter unless you are sure. That is the premise for
everything in §6.

## 1. Five output behaviours, as the page describes them

| class | what the page says the option does | options |
|---|---|---|
| **removes rows or variants** | "Only return…", "Output only…", "Pick one line…", "exclude variants" | `coding_only`, `most_severe`, `summary`, `per_gene`, `pick`, `pick_allele`, `frequency` |
| **swaps the transcript set** | "in place of the default Ensembl transcripts", "Limit your analysis to transcripts belonging to…" | `core_type` (`--refseq`, `--merged`, `--gencode_basic`, `--gencode_primary`) |
| **changes which rows exist** | "Modify the distance … for which Ensembl VEP will assign the upstream_gene_variant or downstream_gene_variant consequences" | `distance` |
| **adds fields** | non-empty *Output fields* cell on the page | every other native option with an *Output fields* entry, and every plugin |
| **changes values only / no output effect** | positions, identifiers, matching, performance | `shift_3prime`, `transcript_version`, `failed`, `buffer_size` |

`cell_type` is in two classes: it adds `CELL_TYPE` and restricts regulatory rows to the named cell types.

## 2. Native options — page record vs our catalogue

Columns: what the page says it does · the *Output fields* the page names · the page's default · the page's
*Incompatible with* (as catalogue ids; page flags outside our catalogue are dropped) · our `conflicts_with` ·
how our priority table prices it · whether it is on by default on the form.

| option | form control | behaviour | output fields (page) | default (page) | incompatible with (page) | ours: conflicts_with | ours: priority | form default |
|---|---|---|---|---|---|---|---|---|
| `af` | 1000 Genomes global | adds fields | AF | off | — | — | analysis_goal.population-frequency=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | **on** |
| `af_1kg` | 1000 Genomes continental | adds fields | AFR_AF, AMR_AF, EAS_AF, EUR_AF, SAS_AF | off | — | — | analysis_goal.population-frequency=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | off |
| `af_gnomade` | gnomAD exomes | adds fields | gnomADe_AF, gnomADe_AFR_AF, gnomADe_AMR_AF, gnomADe_ASJ_AF, gnomADe_EAS_AF, gnomADe_FIN_AF, gnomADe_NFE_AF, gnomADe_OTH_AF, gnomADe_SAS_AF | off | — | — | analysis_goal.population-frequency=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | off |
| `af_gnomadg` | gnomAD genomes | adds fields | gnomADg_AF, gnomADg_AFR_AF, gnomADg_AMI_AF, gnomADg_AMR_AF, gnomADg_ASJ_AF, gnomADg_EAS_AF, gnomADg_FIN_AF, gnomADg_MID_AF, gnomADg_NFE_AF, gnomADg_OTH_AF, gnomADg_SAS_AF | off | — | — | analysis_goal.population-frequency=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | off |
| `appris` | APPRIS | adds fields | APPRIS | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=recommended; species.non-human=not_applicable | **on** |
| `biotype` | Transcript biotype | adds fields | BIOTYPE | off | `most_severe`, `summary` | `most_severe`, `summary` | analysis_goal.basic-consequence=recommended; analysis_goal.clinical-interpretation=recommended; analysis_goal.population-frequency=recommended | **on** |
| `buffer_size` | Buffer size | values only | — | — | — | — | unpriced `{}` | **on** |
| `canonical` | Identify canonical transcripts | adds fields | CANONICAL | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.regulatory-noncoding=recommended; analysis_goal.basic-consequence=recommended; analysis_goal.clinical-interpretation=recommended; analysis_goal.population-frequency=recommended; species.non-human=recommended | off |
| `ccds` | CCDS | adds fields | CCDS | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | off |
| `cell_type` | *(not on form page)* | adds field + restricts regulatory rows | CELL_TYPE | off | — | — | region_focus.regulatory-noncoding=optional | off |
| `check_existing` | Frequency data for co-located variants | adds fields | Existing_variation, CLIN_SIG, SOMATIC, PHENO | off | — | — | origin.germline=optional; origin.somatic=optional | **on** |
| `clinvar` | via *Frequency data for co-located variants* — no separate control | adds fields | Existing_variation, CLIN_SIG, SOMATIC, PHENO | off | — | — | analysis_goal.clinical-interpretation=recommended; analysis_goal.population-frequency=optional; species.non-human=not_applicable | **on** |
| `coding_only` | Return results for variants in coding regions only | **removes rows** | — | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=optional; variant_size_class.structural-CNV=not_applicable | off |
| `core_type` | Transcript database to use | **swaps transcript set** | REFSEQ_MATCH, BAM_EDIT | — | — | — | analysis_goal.basic-consequence=recommended; analysis_goal.clinical-interpretation=recommended; analysis_goal.population-frequency=recommended | **on** |
| `distance` | Upstream/Downstream distance (bp) | **changes row extent** | — | 5000 | — | — | unpriced `{}` | **on** |
| `domains` | Protein matches | adds fields | DOMAINS | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=recommended; variant_size_class.structural-CNV=not_applicable | off |
| `failed` | Include flagged variants | values only | — | 0 (exclude) | — | — | unpriced `{}` | off |
| `frequency` | By frequency; Exclude common variants; Advanced filtering | **removes rows** | FREQS | off | — | — | analysis_goal.population-frequency=optional; origin.somatic=not_applicable; species.non-human=not_applicable | off |
| `hgvs` | HGVS | adds fields | HGVSc, HGVSp, HGVS_OFFSET | off | — | `most_severe`, `summary` | region_focus.coding=recommended; analysis_goal.basic-consequence=optional; analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable | off |
| `mane` | MANE (checkbox, ticked) | adds fields | MANE, MANE_SELECT, MANE_PLUS_CLINICAL | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=recommended; species.non-human=not_applicable | **on** |
| `mirna` | miRNA structure | no output field | — | off | — | — | region_focus.regulatory-noncoding=optional | off |
| `most_severe` | Show most severe per variant | **removes rows** | — | off | `appris`, `biotype`, `canonical`, `ccds`, `coding_only`, `domains`, `mane`, `numbers`, `pick`, `pick_allele`, `polyphen`, `protein`, `sift`, `summary`, `symbol`, `tsl`, `uniprot` | `alphamissense`, `appris`, `biotype`, `cadd`, `canonical`, `ccds`, `clinpred`, `coding_only`, `dbnsfp`, `dbscsnv`, `domains`, `eve`, `hgvs`, `mane`, `maxentscan`, `numbers`, `paralogues`, `per_gene`, `pick`, `pick_allele`, `polyphen`, `protein`, `revel`, `sift`, `spliceai`, `summary`, `symbol`, `tsl`, `uniprot` | analysis_goal.basic-consequence=optional | off |
| `numbers` | Exon and intron numbers | adds fields | EXON, INTRON | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=recommended | off |
| `per_gene` | Show one selected consequence per gene | **removes rows** | — | off | — | `most_severe`, `pick`, `pick_allele`, `summary` | species.human=not_applicable; species.non-human=not_applicable | off |
| `pick` | Show one selected consequence | **removes rows** | — | off | `most_severe`, `summary` | `most_severe`, `per_gene`, `pick_allele`, `summary` | species.human=not_applicable; species.non-human=not_applicable | off |
| `pick_allele` | Restrict results value — in Object_VEP.pm, omitted from the form page | **removes rows** | — | off | `most_severe`, `summary` | `most_severe`, `per_gene`, `pick`, `summary` | species.human=not_applicable; species.non-human=not_applicable | off |
| `polyphen` | PolyPhen predictions | adds fields | PolyPhen | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | **on** |
| `protein` | Protein | adds fields | ENSP | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=recommended; region_focus.regulatory-noncoding=not_applicable; variant_size_class.structural-CNV=not_applicable | off |
| `pubmed` | PubMed IDs for citations of co-located variants | adds fields | PUBMED | off | — | — | analysis_goal.clinical-interpretation=optional; species.non-human=not_applicable | **on** |
| `regulatory` | Get regulatory region consequences | adds fields | MOTIF_NAME, MOTIF_POS, HIGH_INF_POS, MOTIF_SCORE_CHANGE | off | — | — | region_focus.regulatory-noncoding=recommended | **on** |
| `shift_3prime` | Right align variants prior to consequence calculation | values only | — | — | — | — | unpriced `{}` | off |
| `sift` | SIFT predictions | adds fields | SIFT | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable | **on** |
| `summary` | Show only list of consequences per variant | **removes rows** | — | off | `appris`, `biotype`, `canonical`, `ccds`, `coding_only`, `domains`, `mane`, `most_severe`, `numbers`, `pick`, `pick_allele`, `polyphen`, `protein`, `sift`, `symbol`, `tsl`, `uniprot` | `alphamissense`, `appris`, `biotype`, `cadd`, `canonical`, `ccds`, `clinpred`, `coding_only`, `dbnsfp`, `dbscsnv`, `domains`, `eve`, `hgvs`, `mane`, `maxentscan`, `most_severe`, `numbers`, `paralogues`, `per_gene`, `pick`, `pick_allele`, `polyphen`, `protein`, `revel`, `sift`, `spliceai`, `symbol`, `tsl`, `uniprot` | species.human=not_applicable; species.non-human=not_applicable | off |
| `symbol` | Gene symbol | adds fields | SYMBOL, SYMBOL_SOURCE, HGNC_ID | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.regulatory-noncoding=not_applicable; analysis_goal.basic-consequence=recommended; analysis_goal.clinical-interpretation=recommended; analysis_goal.population-frequency=recommended | **on** |
| `transcript_version` | Transcript version | values only | — | — | — | — | unpriced `{}` | **on** |
| `tsl` | Transcript support level | adds fields | TSL | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=recommended; species.non-human=not_applicable | **on** |
| `uniprot` | UniProt | adds fields | SWISSPROT, TREMBL, UNIPARC, UNIPROT_ISOFORM | off | `most_severe`, `summary` | `most_severe`, `summary` | region_focus.coding=optional; variant_size_class.structural-CNV=not_applicable | off |
| `var_synonyms` | Variant synonyms | adds fields | VAR_SYNONYMS | off | — | — | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable | off |

Verbatim page text for the row-affecting options, so the class is traceable:

- `coding_only` — "Only return consequences that fall in the coding regions of transcripts."
- `most_severe` — "Output only the most severe consequence per variant. Transcript-specific columns will be left blank."
- `summary` — "Output only a comma-separated list of all observed consequences per variant. Transcript-specific columns will be left blank."
- `per_gene` — "Output only the most severe consequence per gene."
- `pick` — "Pick one line or block of consequence data per variant, including transcript-specific columns."
- `pick_allele` — "Like --pick, but chooses one line or block of consequence data per variant allele."
- `frequency` — "Use this to include or exclude variants based on the frequency of co-located existing variants in the Ensembl Variation database."
- `core_type` — "Limit your analysis to transcripts belonging to the GENCODE basic set. / Consequence output will be given relative to these transcripts in place of the default Ensembl transcripts"
- `distance` — "Modify the distance up and/or downstream between a variant and a transcript for which Ensembl VEP will assign the upstream_gene_variant or downstream_gene_variant consequences."

Two page notes that change how a recommendation should read:

- `--most_severe`: "To include regulatory consequences, use the --regulatory option in combination with this flag."
- `--check_frequency`: "Frequencies used in filtering are added to the output under the FREQS key in the Extra field." — the filter also *adds* a field, so an option-count diff sees it as +1 while it deletes variants.

## 3. Plugins — page record vs our catalogue

Every plugin adds fields; none removes rows. The page gives a category and a blurb; the form page says
which are offered on the web form and in which section.

| option | form control (section) | page category | ours | page description (first sentence) | ours: priority |
|---|---|---|---|---|---|
| `alphamissense` | AlphaMissense (Predictions) | pathogenicity_predictions | pathogenicity_prediction |  | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `ancestral_allele` | Ancestral allele (Predictions) | conservation | conservation | An Ensembl VEP plugin that retrieves ancestral allele sequences from a FASTA file. | analysis_goal.population-frequency=optional; variant_size_class.structural-CNV=not_applicable |
| `avi` | AVI (Predictions) | pathogenicity_predictions | pathogenicity_prediction | An Ensembl VEP plugin that retrieves AlphaGenome Variant Impact (AVI) scores for single nucleotide variants from a tabix-indexed, bgzip-compressed TSV file. | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `blosum62` | BLOSUM62 (Predictions) | conservation | conservation | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that looks up the BLOSUM 62 substitution matrix score for the reference and alternative amino acids predicted for a missense mutation. | analysis_goal.clinical-interpretation=optional; region_focus.regulatory-noncoding=not_applicable; variant_size_class.structural-CNV=not_applicable |
| `cadd` | CADD (Predictions) | pathogenicity_predictions | pathogenicity_prediction | **Combined Annotation Dependent Depletion** — An Ensembl VEP plugin that retrieves CADD scores for variants from one or more tabix-indexed CADD data files. | analysis_goal.clinical-interpretation=recommended; species.non-human=not_applicable |
| `clinpred` | ClinPred (Predictions) | pathogenicity_predictions | pathogenicity_prediction | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that adds pre-calculated scores from ClinPred. | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `dbnsfp` | dbNSFP (Predictions) | pathogenicity_predictions | pathogenicity_prediction | An Ensembl VEP plugin that retrieves data for missense variants from a tabix-indexed dbNSFP file. | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `dbscsnv` | dbscSNV (Predictions) | splicing_predictions | splice_prediction | An Ensembl VEP plugin that retrieves data for splicing variants from a tabix-indexed dbscSNV file. | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `dosage_sensitivity` | DosageSensitivity (Additional annotations) | gene_tolerance_to_change | gene_constraint |  | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=recommended; species.non-human=not_applicable |
| `enformer` | Enformer (Additional annotations) | regulatory_impact | regulatory | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that adds pre-calculated Enformer predictions of variant impact on chromatin and gene expression. | region_focus.regulatory-noncoding=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `eve` | EVE (Predictions) | pathogenicity_predictions | pathogenicity_prediction | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that adds information from EVE (evolutionary model of variant effect). | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `geno2mp` | Geno2MP (Additional annotations) | phenotype_data_and_citations | phenotype_data_and_citations |  | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `gnomad_sv` | *(not on form page)* | — | frequency_data | *(not on plugins page)* | variant_size_class.structural-CNV=recommended; species.non-human=not_applicable |
| `go` | Gene Ontology (Additional annotations) | phenotype_data_and_citations | phenotype_data_and_citations | **Gene Ontology** — An Ensembl VEP plugin that retrieves Gene Ontology (GO) terms associated with transcripts (e.g. | analysis_goal.clinical-interpretation=optional |
| `intact` | IntAct (Additional annotations) | functional_effect | functional_effect |  | species.non-human=not_applicable |
| `loeuf` | LOEUF (Additional annotations) | gene_tolerance_to_change | gene_constraint | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that adds the LOEUF scores to VEP output. | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=recommended; species.non-human=not_applicable |
| `mastermind` | Mastermind (Additional annotations) | phenotype_data_and_citations | literature_citation | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that uses the Mastermind Genomic Search Engine ( https://www.genomenon.com/mastermind ) to report variants that have clinical evidence cited in the medical  | analysis_goal.clinical-interpretation=recommended; species.non-human=not_applicable |
| `mavedb` | MaveDB (Additional annotations) | functional_effect | functional_effect |  | analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `maxentscan` | MaxEntScan (Predictions) | splicing_predictions | splice_prediction | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that runs MaxEntScan ( http://hollywood.mit.edu/burgelab/maxent/Xmaxentscan_scoreseq.html ) to get splice site predictions. | analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable |
| `mutfunc` | mutfunc (Additional annotations) | protein_annotation | protein_annotation |  | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `nmd` | NMD (Additional annotations) | transcript_annotation | transcript_annotation | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that predicts if a variant allows the transcript escape nonsense-mediated mRNA decay based on certain rules. | region_focus.coding=optional; region_focus.regulatory-noncoding=not_applicable |
| `opentargets` | Open Targets Platform (Variants and frequency data) | variant_data | variant_data |  | species.non-human=not_applicable |
| `paralogues` | Paralogue variants (Variants and frequency data) | variant_data | variant_data |  | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable |
| `phenotypes` | Phenotypes (Additional annotations) | phenotype_data_and_citations | phenotype |  | analysis_goal.clinical-interpretation=recommended |
| `protvar` | ProtVar (Additional annotations) | protein_annotation | protein_annotation |  | analysis_goal.clinical-interpretation=optional; region_focus.regulatory-noncoding=not_applicable; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `revel` | REVEL (Predictions) | pathogenicity_predictions | pathogenicity_prediction | This is a plugin for the Ensembl Variant Effect Predictor (VEP) that adds the REVEL score for missense variants to the output. | region_focus.regulatory-noncoding=not_applicable; analysis_goal.clinical-interpretation=optional; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `riboseqorfs` | RiboseqORFs (Additional annotations) | transcript_annotation | transcript_annotation | An Ensembl VEP plugin that uses a standardized catalog of human Ribo-seq ORFs to re-calculate consequences for variants located in these translated regions. | region_focus.regulatory-noncoding=optional; species.non-human=not_applicable |
| `species_frequency` | *(not on form page)* | — | frequency_data | *(not on plugins page)* | analysis_goal.population-frequency=recommended; species.human=not_applicable; variant_size_class.structural-CNV=not_applicable |
| `spliceai` | SpliceAI (Predictions) | splicing_predictions | splice_prediction | An Ensembl VEP plugin that retrieves pre-calculated annotations from SpliceAI. | analysis_goal.clinical-interpretation=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |
| `utrannotator` | UTRAnnotator (Additional annotations) | transcript_annotation | transcript_annotation |  | region_focus.regulatory-noncoding=recommended; variant_size_class.structural-CNV=not_applicable; species.non-human=not_applicable |

## 4. Interactions — the page's incompatibility graph

The *Restrict results* family is one dropdown on the form (`summary`), so its five values are mutually
exclusive by construction. The page additionally lists these as incompatible with the transcript-level
annotations, because "Transcript-specific columns will be left blank":

- `--most_severe` × `--appris`, `--biotype`, `--canonical`, `--ccds`, `--coding_only`, `--domains`, `--flag_pick`, `--flag_pick_allele`, `--no_intergenic`, `--numbers`, `--pick`, `--pick_allele`, `--polyphen`, `--protein`, `--sift`, `--summary`, `--symbol`, `--tsl`, `--uniprot`, `--xref_refseq`, `--mane`, `--mane_select`, `--vcf`
- `--summary` × `--appris`, `--biotype`, `--canonical`, `--ccds`, `--coding_only`, `--domains`, `--flag_pick`, `--flag_pick_allele`, `--most_severe`, `--no_intergenic`, `--numbers`, `--pick`, `--pick_allele`, `--polyphen`, `--protein`, `--sift`, `--symbol`, `--tsl`, `--uniprot`, `--xref_refseq`, `--mane`, `--mane_select`, `--vcf`

Of those, the ones that are **on by default on the form** are `appris`, `biotype`, `mane`, `polyphen`, `sift`, `symbol`, `tsl`. So choosing
*Show most severe* or *Show only list of consequences* on the form conflicts with 7 controls the form has
already ticked. How the form resolves that is not stated on the page.

`coding_only` × `most_severe` and `coding_only` × `summary` are on the page and **absent from our catalogue** (§5).

`core_type` values: `--gencode_basic` × `--gencode_primary` × `--refseq`; `--merged` × `--refseq`. `--gencode_primary` is
"Only available for human on the GRCh38 assembly" — an assembly gate on one value of an option we recommend everywhere.

The frequency filter is four controls, not one: `--freq_filter` (exclude / include only), `--freq_gt_lt`, `--freq_freq`,
`--freq_pop`. `--filter_common` is the page's shortcut for the form's *Exclude common variants* radio: "this will exclude
variants that have a co-located existing variant with global AF > 0.01 (1%)".

## 5. Where our catalogue disagrees with the page

**On the web form, added to our catalogue on 2026-09-13 from this page**

- **AVI** (`avi`) — "AlphaGenome Variant Impact (AVI) scores for single nucleotide variants" (plugins page); Predictions.
- **ProtVar** (`protvar`) — "provides contextualised information for missense variation, including destabilisation of protein structures, overlapping protein pockets, and protein-protein interaction interfaces" (form page); Additional annotations.

**In our catalogue, absent from the documented form page — but every one is on the form**

- `cell_type` — ON THE FORM: InputForm.pm:763-795 renders one checkbox per available cell type (`cell_type_<name>`) at runtime, so the documentation page has no static control for it
- `gnomad_sv` — ON THE FORM as a `--custom` dataset rendered from vep_custom_web_config.json, not a documented control
- `species_frequency` — catalogue web_form_section = variants_frequency_data

**Form section differs from our `web_form_section`**

- `core_type` — form: Data input; ours: `advanced`

**Modelled as a switch on our side, a value or multi-control on theirs**

- `frequency` — the form's *Filter by frequency* is a three-way radio (No filtering / Exclude common variants / Advanced filtering). *Exclude common variants* is `--filter_common`, which our catalogue never names; *Advanced* exposes `freq_filter`, `freq_gt_lt`, `freq_freq`, `freq_pop`. We price one on/off.
- `core_type` — five values on the form; page lists `--gencode_basic`, `--gencode_primary`, `--refseq`, `--merged` each with their own incompatibilities. We recommend the option on every tuple and never name a value.
- `sift` / `polyphen` — page: `b` prediction+score, `p` prediction, `s` score. We price the switch.
- `distance` — free-text, page default 5000. Unpriced by us.
- The form page's *Show one selected consequence* links to `#opt_per_gene` but its text says "Equivalent to --pick". Page error; recorded so nobody "fixes" our mapping to match the anchor.

**The one thing the page cannot tell you** — documented behaviour that does not happen. `--check_frequency` with
the shipped default population `1KG_ALL` deletes nothing on a release-116 cache: the code path for `1KG_ALL`
reads two fields (`minor_allele`, `minor_allele_freq`) that the cache no longer carries, so every variant passes.
Every other population name (`AF`, `1KG_AFR`, `gnomADe`, …) reads a live column and filters as documented.
This is the only finding in three days of local runs that a careful read could not have produced, and it is the
reason to keep one local VEP install: not to characterise options, but to catch the page being wrong.

## 6. What this changes in the priority table

Sourced from the page, not from a run. **Applied 2026-09-14/15** unless marked open:

1. **Do not recommend any option in the removes-rows class from a factor value.** The form's own instruction is
   "if you aren't sure, don't use any of these options!" That removes `frequency` from
   `analysis_goal.population-frequency` (the four AF *column* options in the same list already answer the question),
   `coding_only` from `region_focus.coding`, and `most_severe` from `analysis_goal.basic-consequence`.
2. **Price `pick`, `pick_allele`, `per_gene`, `summary` as `not_applicable`** so the resolver blocks them from the
   table rather than from a special-case function. They are never recommended today, so no configuration moves.
3. **Add the two missing conflict edges** so the checker sees what the page sees.
4. **`core_type`** — OPEN by decision (David, 2026-09-14): it is the form's default and now sits under ALREADY ON,
   so the user is never told to change it. Its value question (Likhitha, row 11) stays with the mentors.
5. **`distance`** — OPEN: unpriced, on by default at 5000, listed under ALREADY ON. Left at the form default.
6. **AVI and ProtVar** — applied 2026-09-13 as add-ons. blosum62 and ancestral_allele priced 2026-09-15 (add-ons);
   blosum62 moved to Ensembl's `conservation` category and out of the pathogenicity line.
7. **Species data** — applied 2026-09-15: `generation_config/species_data.json` from Ensembl's own sources, gated
   like assembly; `species_frequency` added for the four species with files; removals printed by default.

## 7. Evaluation rule going forward

An option's cost class comes from §1 of this file. A recommendation error is scored by class — a missed
add-fields option costs a column; a volunteered removes-rows option costs data — not by counting options.
The page is the ground truth for behaviour; a local run is only for confirming the page where there is a
specific reason to doubt it.
