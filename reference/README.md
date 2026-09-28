# `reference/` — Ensembl's material, not ours

| folder | what |
|---|---|
| `ensembl_docs_116/` | the release-116 options, web-form, plugins and protein-function pages, saved, plus their parsed JSON. The engine's `--explain` quotes these |
| `ensembl_source/` | `InputForm.pm`, `Object_VEP.pm`, `VEPConstants.pm`, the web custom-annotation config (release 115) and `plugin_config.txt` (release 116). The species-data builders read them. `vep_web_interface_reference.md` is our summary of the form, kept beside its sources |

Third-party reading (PDFs) sits in `interp_reading/` and `systems_reading/` on the development machine,
gitignored.

The Ensembl files are Ensembl's own (EMBL-EBI), copied unchanged from
[Ensembl/public-plugins](https://github.com/Ensembl/public-plugins) and
[Ensembl/VEP_plugins](https://github.com/Ensembl/VEP_plugins), which are distributed under the Apache
License 2.0. `ensembl_source/README_sources.md` gives each file's source and release.
