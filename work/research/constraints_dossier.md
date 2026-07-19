I now have all the grounding needed. The InputForm.pm source is decisive on the structural facts (the `summary` dropdown makes pick/pick_allele/per_gene/summary/most_severe a single mutually-exclusive control; cell_type lives inside the regulatory dropdown's `cell` value; af-group fields are nested under `_stt_yes`/`_stt_allele` classes downstream of check_existing). Here is the constraint graph.

# VEP Constraint Graph (release/115)

Grounding key: `IF` = InputForm.pm, `OV` = Object_VEP.pm get_form_details, `DOC` = vep_options.html.

---

## 1) HUMAN-ONLY OPTIONS (block for non-human queries)

These must be disabled/hidden when the selected species is not `Homo_sapiens`. Justification is the InputForm `field_class` gate (`_stt_Homo_sapiens` or a `if (first {value eq 'Homo_sapiens'})` guard) or a human-only data source.

### Native fields gated to human in source

| id | CLI flag | Source justification |
|---|---|---|
| `af` | `--af` | IF L574-587: built only inside `if (first { value eq 'Homo_sapiens' })`, wrapped in `_stt_Homo_sapiens` div. 1000G data. |
| `af_1kg` | `--af_1kg` | IF L588-592: same human-only block (`_stt_Homo_sapiens`). |
| `af_gnomade` | `--af_gnomade` | IF L593-598: same human-only block. gnomAD human-only. |
| `af_gnomadg` | `--af_gnomadg` | IF L599-605: same human-only block. gnomAD human-only. |
| `pubmed` | `--pubmed` | IF L609-617: built inside the `_stt_Homo_sapiens` human block. |
| `var_synonyms` | `--var_synonyms` | IF L471-483: `field_class` div `_stt_Homo_sapiens _stt_Sus_scrofa` -> human + pig only (NOT all-species). Block for species other than human/pig. |
| `tsl` | `--tsl` | IF L674-682: `field_class` includes `_stt_Homo_sapiens` and is added only `if (first {value eq 'Homo_sapiens'})`. |
| `appris` | `--appris` | IF L684-692: same human-only `if` guard + `_stt_Homo_sapiens`. |
| `mane` | `--mane` | IF L694-702: same human-only `if` guard + `_stt_Homo_sapiens`. MANE is human-only. (Correct demo `mane_select` -> `mane`.) |
| `frequency` | `--check_frequency` (+freq_pop/freq_freq/freq_gt_lt/freq_filter) | IF L298-337: entire field built only `if (first {value eq 'Homo_sapiens'})`, `field_class _stt_Homo_sapiens`. 1000G/ESP populations. |
| `polyphen` | `--polyphen [b/p/s]` | IF L901-933: PolyPhen field added only when a species has `variation->{POLYPHEN}`; in practice human-only data source. OV L322 confirms. |
| `ccds` | `--ccds` | IF L400-407: `field_class _stt_Homo_sapiens _stt_Mus_musculus ...` -> human + mouse only. Block for species other than human/mouse. |

### Plugins that are human-only data sources (block for non-human)

From the AUTHORITATIVE plugin list; each is a human-data plugin (no non-human precomputed data), so `source_type=plugin`, `web_form_section=predictions` (pathogenicity) or `additional_annotations`:

- `CADD` (human GRCh37/GRCh38)
- `REVEL` (human missense)
- `AlphaMissense` (human GRCh38 missense)
- `dbNSFP` (human)
- `ClinPred` (human)
- `EVE` (human)
- `Mastermind` (human literature/variant DB)
- `Geno2MP` (human)
- `LOEUF` (human gene constraint)
- `DosageSensitivity` (human)
- `OpenTargets` (human)
- `dbscSNV` (human splicing scores)
- `SpliceAI` (human precomputed GRCh37/38)
- `EVE`, `MaveDB`, `Enformer`, `UTRAnnotator`, `RiboseqORFs`, `AlphaMissense` — human-data. (Note: `MaxEntScan` and `Blosum62` are sequence/matrix-based and are NOT human-only; `AncestralAllele`, `Paralogues`, `GO`, `Phenotypes`, `IntAct`, `NMD` depend on available species data.)

### Custom datasets (human-only, block non-human)

- `gnomAD_SV` (human, section: variants_frequency_data) — custom config.
- `GENCODE_promoter` (human, section: additional_annotations/regulatory).
- `AllOfUs` (human, section: variants_frequency_data).

### NOT human-only (do not block) — explicit notes
- `SIFT` (`--sift`) — multi-species. IF L901/908 adds it whenever ANY species has `variation->{SIFT}`; `field_class _stt_sift`, not `_stt_Homo_sapiens`. Set `species_restriction: "species with SIFT data"`, NOT human-only. (Correct any catalogue entry that marks SIFT human-only.)
- `regulatory`/`cell_type` (`--regulatory`/`--cell_type`) — human + mouse + other species with a regulatory build. IF L756 gates by per-species `regulatory` flag (`_stt_<species>`), not human. Set `species_restriction: "species with regulatory build"`.
- `gene_phenotype`, `check_existing`, `symbol`, `transcript_version`, `protein`, `uniprot`, `hgvs`, `biotype`, `numbers`, `canonical`, `distance`, `mirna`, `domains`, `coding_only`, `core_type`, `buffer_size`, `shift_3prime`, `failed` — all species (no `_stt_Homo_sapiens` gate).
  - Caveat: `clinvar` significance rides on `check_existing` and is human-only as a *data* matter, but the control itself (`check_existing`) is all-species. Do not model `clinvar` as its own native checkbox; it is `source_type=derived` from check_existing/co-located variants.

---

## 2) CONFLICTS (mutually-exclusive sets) → `conflicts_with[]`

### A. "Restrict results" dropdown — single control, mutually-exclusive VALUES
Source: IF L348-363 and OV L395-406 — one form field `name="summary"`, label "Restrict results", section `filters`. Its values are radio-exclusive by construction (a dropdown can hold only one value). Model these five as one mutually-exclusive group; selecting any one excludes the others:

```
pick        <-> pick_allele, per_gene, summary, most_severe
pick_allele <-> pick, per_gene, summary, most_severe
per_gene    <-> pick, pick_allele, summary, most_severe
summary     <-> pick, pick_allele, per_gene, most_severe
most_severe <-> pick, pick_allele, per_gene, summary
```
Reason: single web control "Restrict results" (`summary` field) holding one value (DOC: pick vs severity-based filtering are alternative strategies; the form enforces one). The "no" / "Show all results" value is the absence of restriction (not a conflict participant).

### B. summary / most_severe suppress per-transcript annotation
Source: DOC verbatim — `--most_severe` and `--summary`: "Transcript-specific columns will be left blank." Therefore each conflicts with every per-transcript annotation option:

```
most_severe <-> sift, polyphen, hgvs, domains, symbol, protein, ccds, uniprot,
                biotype, numbers, tsl, appris, mane, canonical,
                <all missense/transcript plugins: CADD, REVEL, AlphaMissense, dbNSFP, SpliceAI, MaxEntScan, dbscSNV, ...>
summary     <-> (same set as most_severe)
```
Reason: most_severe/summary blank out transcript-specific columns, so requesting transcript-level annotations is meaningless/contradictory. (`pick`/`pick_allele`/`per_gene` do NOT suppress these — DOC `--pick`: "including transcript-specific columns" — so they do NOT conflict with sift/polyphen/hgvs/etc. Correct the demo, which wrongly listed canonical/mane/symbol/protein conflicting with pick only via most_severe/summary; keep them only against most_severe & summary.)

### C. Transcript-database (`core_type`) — mutually-exclusive VALUES
Source: IF L207-216 — one `radiolist` field `name="core_type"` (value: core | gencode_basic | gencode_primary | refseq | merged). DOC confirms `--refseq`/`--merged`/`--gencode_basic`/`--gencode_primary` are a mutually-exclusive group.
```
core <-> gencode_basic <-> gencode_primary <-> refseq <-> merged   (all pairwise exclusive; one value only)
```
(Correct demo `transcript_set` -> `core_type`.)

### D. Frequency filter populations / cell_type
`freq_pop` (single value) and per-species regulatory dropdown (`regulatory_<sp>` value no|reg|cell) are each single-valued controls — internally exclusive, not cross-option conflicts.

---

## 3) DEPENDENCIES → `depends_on[]`

### Depend on `check_existing` (co-located short variants)
Source: IF — `af`, `af_1kg`, `af_gnomade`, `af_gnomadg`, `pubmed`, `var_synonyms`, `failed` all carry `field_class [_stt_yes _stt_allele]` (L480-481, 616, 629, 565, 583), i.e. they are shown only when `check_existing` (the `_stt` dropdown, value `yes`/`no_allele` = "allele") is enabled. DOC confirms these report data "for any known co-located variant" and require check_existing. ClinVar significance likewise.

```
af           depends_on: check_existing   (reason: AF reported only for co-located known variants; _stt_yes/_stt_allele gate)
af_1kg       depends_on: check_existing
af_gnomade   depends_on: check_existing
af_gnomadg   depends_on: check_existing
pubmed       depends_on: check_existing   (PubMed IDs "of co-located variants"; _stt_yes/_stt_allele)
var_synonyms depends_on: check_existing   (synonyms "for co-located variants"; _stt_yes/_stt_allele; AND human/pig species)
failed       depends_on: check_existing   (DOC: "When checking for co-located variants ... exclude variants flagged as failed"; _stt_yes/_stt_allele)
clinvar      depends_on: check_existing   (derived: CLIN_SIG comes via co-located variant lookup; not a standalone control)
```

### Regulatory dependency
Source: IF L771-798 — `cell_type_<sp>` element is rendered under `element_class "_stt_cell_<sp>"`, which is only active when the `regulatory_<sp>` dropdown value = `cell` ("Yes and limit by cell type"). So in the web form cell_type is reachable only through the regulatory control's `cell` value. DOC does not state a hard CLI requirement, but the form makes it dependent.
```
cell_type   depends_on: regulatory   (reason: cell_type field only exposed when regulatory dropdown = "cell"; IF _stt_cell_<sp> gate)
```

### Protein-coding / missense consequence dependency
Source: OV L313/L324 — SIFT/PolyPhen "for missense variants"; missense predictor plugins operate on protein-coding consequences only. Model as a soft dependency (recommender gate, not a CLI requirement): apply only to missense/coding variants.
```
sift          depends_on: <missense/protein-coding consequence>   (OV: "for missense variants")
polyphen      depends_on: <missense/protein-coding consequence>
revel         depends_on: <missense consequence>
alphamissense depends_on: <missense consequence>
dbNSFP        depends_on: <missense/coding consequence>
domains       depends_on: <protein-coding consequence>            (OV: overlapping protein domains)
```
(These have no required CLI predecessor flag; the dependency is biological/consequence-class. If your checker only models flag-level depends_on, omit these and instead enforce via `coding_only`/consequence context.)

---

## Summary of corrections to apply to vep_options.json
- `transcript_set` -> `core_type` (section `advanced`/pre-section transcript db; mutually-exclusive values, not a boolean).
- `mane_select` -> `mane` (section `additional_annotations`, human-only).
- `gnomad_af` -> split into `af_gnomade` + `af_gnomadg` (both human-only, both depends_on check_existing).
- `af_1kg` (continental) is distinct from `af` (1000G global MAF); both human-only, both depends_on check_existing.
- `pick`/`pick_allele`/`per_gene`/`summary`/`most_severe` = values of one `summary` ("Restrict results") control in section `filters`; encode as mutually-exclusive entries, not separate checkboxes.
- `cadd`/`revel`/`alphamissense`/`spliceai`/`maxentscan`/`dbNSFP` -> `source_type=plugin` (predictions/additional_annotations), not native.
- `clinvar` -> `source_type=derived` (via check_existing); depends_on check_existing; not a standalone checkbox.
- Remove the demo's incorrect `conflicts_with` of `mane`/`canonical`/`symbol`/`protein` with `pick` — they only conflict with `most_severe` and `summary`.
- Fix `sift.species_restriction` -> "species with SIFT data" (multi-species), not human-only.
- All `web_form_section` values must be one of: `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters`, `advanced`.

Relevant source files: `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/VEP/InputForm.pm`, `/Users/davidgao/Desktop/GSoC_WORK/ensembl_source/Object_VEP.pm`, `/Users/davidgao/Desktop/GSoC_WORK/vep_ai_demo/vep_options.json`.