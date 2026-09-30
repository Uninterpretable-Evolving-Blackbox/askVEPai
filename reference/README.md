# `reference/` — the Ensembl material the engine is derived from

Every fact the engine states about VEP comes from a file here. The option catalogue
(`../vep_ai_demo/vep_options.json`) records, in each option's `provenance`, the file and line each fact
came from. These are Ensembl's files, not ours; the one exception is `vep_web_interface_reference.md`.

## What each engine file is derived from

| engine file (`../vep_ai_demo/`) | derived from | what it took |
|---|---|---|
| `vep_options.json`, 70 options | `ensembl_docs_116/vep_options.html`, `vep_online_input.html`, `vep_plugins.html` | each option's name and description, in Ensembl's words for 68 of the 70 |
| | `ensembl_source/VEP/InputForm.pm`, `Object_VEP.pm`, and `ensembl_source/release_116/InputForm.pm` | which controls the web form has, their on/off defaults, labels, and which species see them (SIFT, RefSeq, variant synonyms) |
| | `ensembl_docs_116/form_layout_live.json`, `form_species_check_2026-09-28.json` | which section of the live form each control sits in, and what the rendered form showed for each species and build |
| | `ensembl_source/vep_plugins_web_config.txt`, `release_116/vep_plugins_web_config.txt` | which plugins the web form offers |
| | `ensembl_source/vep_plugins_species_config_116.txt` | which species each plugin supports |
| | `ensembl_source/vep_custom_web_config.json`, `release_116/vep_custom_web_config.json` | the frequency and custom-annotation files, and their species and builds |
| | `ensembl_docs_116/grch37_form_plugins_2026-09-23.json` | which plugins the GRCh37 form offers |
| `ensembl_docs/vep_options_parsed.json`, `vep_plugins_parsed.json` | copies of the same files in `ensembl_docs_116/` | what `--explain` quotes |
| `vep_consequences.json` | Ensembl's "Calculated variant consequences" page, release 116 (URL in the file's `_source`) | the 41 consequence terms, their order and IMPACT |
| `species_index.json` | Ensembl REST `/info/species`, saved as `ensembl_source/rest_info_species_2026-09-28.json` | the species, their common names and Ensembl's aliases |
| `hgnc_symbols.json` | HGNC's approved-symbol list (source in `ensembl_source/README_sources.md`) | 45,016 human gene symbols |

`factors.json` (the five factors) and `priority_by_factor.json` (the priority table) are not derived from
Ensembl; they are the project's own design.

## Folders

| folder | what |
|---|---|
| `ensembl_docs_116/` | Ensembl's release-116 options, web-form, plugins, results and protein-function pages, saved, with their parsed JSON, a reading of the live form, and `form_species_check_2026-09-28.json`, what the rendered form showed for each species and build on that day. Sources and dates in its README |
| `ensembl_source/` | the web form's code (`InputForm.pm`, `Object_VEP.pm`, `VEPConstants.pm`), the web custom-annotation config (release 115), the plugin configs (release 116) and the saved REST species list. `release_116/` holds the release-116 `InputForm.pm`, custom-annotation config and web plugin config from `Ensembl/public-plugins` branch `release/116`; the options added or corrected on 2026-09-28 cite them. Sources and dates in `README_sources.md`. `vep_web_interface_reference.md` is our summary of the form, kept beside its sources |

## Licence

The Ensembl files are Ensembl's own (EMBL-EBI), copied unchanged from
[Ensembl/public-plugins](https://github.com/Ensembl/public-plugins) and
[Ensembl/VEP_plugins](https://github.com/Ensembl/VEP_plugins), which are distributed under the Apache
License 2.0.
