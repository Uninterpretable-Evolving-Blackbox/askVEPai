# Official Ensembl VEP documentation, release 116 — fetched 2026-09-13

Raw HTML and the parsed JSON derived from it. Source of record for `output_effects_dossier.md` (private working repository).

| file | URL | what |
|---|---|---|
| `vep_options.html` | https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html | every CLI flag: description, output fields, default, "Incompatible with" |
| `vep_plugins.html` | https://www.ensembl.org/info/docs/tools/vep/script/vep_plugins.html | every plugin: blurb, category |
| `vep_online_input.html` | https://www.ensembl.org/info/docs/tools/vep/online/input.html | the WEB FORM: each control, its CLI equivalent, the form's own warnings |
| `protein_function.html` | https://www.ensembl.org/info/genome/variation/prediction/protein_function.html (saved from jun2026.archive.ensembl.org, release 116) | which species have SIFT / PolyPhen. Saved by 2026-09-15. |
| `vep_online_results.html` | Ensembl/public-plugins release/116, the results-page documentation | the "filter on the results page" wording. Saved 2026-09-23. |

All three `www.ensembl.org` URLs return **308 → `jun2026.archive.ensembl.org`** as of 2026-09-13, the same
archive move the form itself made (`evidence/legacy_superseded/old_docs/STATUS.md`). The archive copies are what is saved here.

Parsed with the inline scripts recorded in `build_output_effects_dossier.py` (private working repository). Re-fetch and
re-parse when the release changes; diff the JSON to see what moved.

`form_layout_live.json`, `form_species_check_2026-09-28.json` and `grch37_form_plugins_2026-09-23.json` are readings
of the live form; each records its own URL and date (`_url` or `_pages`, `_read_on`).
