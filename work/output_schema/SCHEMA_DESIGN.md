# Structured JSON Output Schema (proposal §4.4)

The demo emits free-text markdown. The GSoC deliverable is a **structured JSON output** that maps each per-option decision to the Ensembl VEP web form so the frontend can offer **click-to-apply**. This document defines that schema and, critically, the **field-name mapping** that makes click-to-apply work.

Files:
- `vep_recommendation.schema.json` — JSON Schema (2020-12) for the output.
- `example_output.json` — a worked somatic-cancer example (validates against the schema).

## Why this shape

Each recommendation carries three coordinated addresses for the same decision:
1. `web_form_section` — one of the 6 canonical `CONFIG_SECTIONS` ids (`VEPConstants.pm`): `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters`, `advanced`. Tells the frontend **which collapsible section** to open.
2. `web_form_field` — the **HTML control `name` attribute** in `InputForm.pm`. Tells the frontend **which control to toggle/set**.
3. `cli_flag` — the equivalent command-line flag, for users who run VEP from the CLI and for the `generated_command`.

Plus `action` (`enable` / `disable` / `set_value`) and `value` for non-checkbox controls.

## Field-name mapping rules (derived from `InputForm.pm`)

This is the part that must be exact for click-to-apply. Rules, in priority order:

| Control kind | `web_form_field` | `action` / `value` | Examples |
|---|---|---|---|
| Native checkbox | the option id | `enable` / `disable` | `symbol`, `hgvs`, `af_gnomade`, `pubmed`, `biotype`, `tsl`, `mane`, `canonical`, `domains`, `coding_only` |
| Native dropdown / radiolist | the option id | `set_value` + `value` | `sift`=`b\|p\|s`, `polyphen`=`b\|p\|s`, `check_existing`=`yes\|no\|no_allele`, `shift_3prime`=`shift_3prime\|shift_genomic`, `buffer_size`=`5000`, `frequency`=`common\|advanced` |
| Native string | the option id | `set_value` + `value` | `distance`=`1000` |
| Transcript database | `core_type` | `set_value` + `value` | `core_type`=`core\|gencode_basic\|gencode_primary\|refseq\|merged` |
| **Restrict results** (one dropdown, name=`summary`) | `summary` | `set_value` + `value` | the catalogue ids `pick`/`pick_allele`/`per_gene`/`summary`/`most_severe` all set `web_form_field='summary'`, `value=<that id>` |
| **Plugin** | `plugin_<Key>` | `enable` or `set_value`=`plugin_<Key>` | `cadd`→`plugin_CADD`, `revel`→`plugin_REVEL`, `alphamissense`→`plugin_AlphaMissense`, `dbnsfp`→`plugin_dbNSFP`, `spliceai`→`plugin_SpliceAI` |
| **Species-scoped control** (runtime suffix) | `<base>_<Species>` | per kind | `regulatory`→`regulatory_Homo_sapiens`, `cell_type`→`cell_type_Homo_sapiens` |
| **Custom dataset** | `custom_<id>` | `enable` | `gnomad_sv`→`custom_homo_sapiens_gnomAD_SV` |

Notes / edge cases:
- **`clinvar`** has no standalone control: ClinVar significance is reported through co-located variants, so its `web_form_field` is `check_existing` (and it `depends_on` it). The frontend highlights `check_existing`.
- **Species suffix.** `regulatory`/`cell_type` field names include the species (e.g. `regulatory_Homo_sapiens`). The emitter appends `_<Species>` using the resolved species; the schema documents the base name. The plugin key uses the canonical case from `vep_plugins_web_config.txt` (e.g. `CADD`, `dbNSFP`, `AlphaMissense`).
- **`core_type` default** (`core`, Ensembl transcripts) has no CLI flag; only `refseq`/`merged`/`gencode_basic`/`gencode_primary` emit a flag.

## Click-to-apply flow

1. Recommender produces JSON conforming to this schema.
2. Deterministic constraint checker runs (species/conflict/dependency) and the **post-correction** option set is what is serialised — so `recommendations` never contains a species- or conflict-invalid combination, and `constraint_check.passed` records the outcome.
3. Frontend iterates `recommendations`: open `web_form_section`, locate the `web_form_field` control, apply `action`/`value`. Plugin fields first set the `plugin_<Key>` enable radio, then any plugin sub-params.
4. `generated_command` mirrors the same final set for CLI users.

## Compatibility

This schema is **additive** to the demo: it standardises the output the pipeline already produces (use case, per-option enable/disable, citations, command). The catalogue's `web_form_section` + `cli_flag` feed directly into it; the only new derivation is `web_form_field` (table above), which is computed from the option id + `source_type` at emit time and does not require new KB fields.

## Open questions for mentor

- Confirm the click-to-apply contract against the **beta.ensembl.org** frontend (field names may differ from the classic `InputForm.pm`).
- Decide whether `core_type` should live under a dedicated top-level address rather than being folded into `advanced` (see catalogue report).
- Confirm plugin sub-parameter naming (`plugin_<Key>_<param>`) for plugins that need data-file paths (CADD, dbNSFP, SpliceAI).
