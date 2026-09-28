# Form defaults: `web_default_on` / `web_default_value` against Ensembl's code

Checked 2026-09-22, all 68 catalogue options. **68 MATCH, 0 MISMATCH, 0 NOT FOUND.** This replaced the
`web_default` prose and `_web_default_basis` fields, deleted from the catalogue the same day.

Sources (all under `work/ensembl_source/`, gitignored): **IF** `VEP/InputForm.pm` · **OV** `Object_VEP.pm` ·
**SC** `vep_plugins_species_config_116.txt` (VEP_plugins release/116 `plugin_config.txt`) · **WC**
`vep_plugins_web_config.txt` · **DOC** `work/research/ensembl_docs_116/vep_online_input.html`.

Plugins: WC lists 26 of them with only `"available" => 1` and no `enabled` key; SC sets `"enabled" => 0`
for all 28 catalogue plugins, and the form reads `enabled` at IF:1139 (radiolist plugins) and IF:1175
(checkbox plugins). A native checkbox with no `'checked'` key is read as unchecked (`ccds`, `protein`,
`uniprot`, `hgvs`); the Form element classes that render it are not on disk.

| id | on | value | source |
|---|---|---|---|
| core_type | T | core | IF:213 `'value' => 'core'` (shown only for species with RefSeq, IF:206) |
| hgvs | F | | IF:425-431, no `checked` key |
| af_gnomade | F | | IF:598 `'checked' => 0` |
| tsl | T | | IF:681 `'checked' => 1` (human only, IF:682) |
| domains | F | | IF:745 `'checked' => 0` |
| frequency | F | no | IF:308 `'value' => 'no'` (human only) |
| most_severe | F | | IF:353 `'value' => 'no'` (Restrict results dropdown) |
| dbnsfp | F | | WC:2-4; SC:16 `"enabled" => 0` → IF:1139 |
| loeuf | F | | WC:6; SC:1734 → IF:1175 |
| mastermind | F | | WC:50; SC:1375 → IF:1175 |
| symbol | T | | IF:388 `'checked' => 1` |
| check_existing | T | yes | IF:466 `'value' => 'yes'` |
| af_gnomadg | F | | IF:604 `'checked' => 0` |
| appris | T | | IF:691 `'checked' => 1` (human only) |
| regulatory | T | | IF:779 `'value' => 'reg'` |
| coding_only | F | | IF:345 `'checked' => 0` |
| buffer_size | T | 5000 | IF:971 `'value' => '5000'` |
| clinpred | F | | WC:96; SC:959 → IF:1175 |
| dosage_sensitivity | F | | WC:66; SC:1714 → IF:1175 |
| geno2mp | F | | WC:38; SC:1347 → IF:1175 |
| transcript_version | T | | IF:397 `'checked' => 1` |
| clinvar | T | | via check_existing, IF:466 |
| pubmed | T | | IF:615 `'checked' => 1` |
| mane | T | | IF:701 `'checked' => 1` (human only) |
| cell_type | F | | IF:779 regulatory defaults to `'reg'`, not `'cell'` |
| pick | F | | IF:353 `'value' => 'no'` |
| shift_3prime | F | no | IF:980 `'value' => 'no'` |
| eve | F | | WC:30; SC:982 → IF:1175 |
| nmd | F | | WC:70; SC:1784 → IF:1175 |
| phenotypes | F | | WC:34; SC:1306 → IF:1175 |
| ccds | F | | IF:400-407, no `checked` key |
| var_synonyms | F | | IF:479 `'checked' => 0` |
| failed | F | | IF:628 `'checked' => 0` |
| canonical | F | | IF:711 `'checked' => 0` |
| pick_allele | F | | IF:353 `'value' => 'no'` |
| cadd | F | | WC:26; SC:660 → IF:1139 |
| spliceai | F | | WC:46; SC:1146 → IF:1139 |
| utrannotator | F | | WC:78; SC:1795 → IF:1175 |
| enformer | F | | WC:74; SC:2006 → IF:1175 |
| protein | F | | IF:409-415, no `checked` key |
| af | T | | IF:586 `'checked' => 1` |
| biotype | T | | IF:662 `'checked' => 1` |
| distance | T | 5000 | IF:719 → OV:288 `MAX_DISTANCE_FROM_TRANSCRIPT` (constant not on disk); DOC:621 `value="5000"` |
| sift | T | b | IF:916 `'value' => 'b'` |
| per_gene | F | | IF:353 `'value' => 'no'` |
| revel | F | | WC:93; SC:931 → IF:1175 |
| maxentscan | F | | WC:14; SC:1117 → IF:1175 |
| paralogues | F | | WC:99; SC:1002 → IF:1139 |
| gnomad_sv | F | | `vep_custom_web_config.json`:40 → IF:508 `'value' => 'no'` |
| uniprot | F | | IF:417-423, no `checked` key |
| af_1kg | F | | IF:592 `'checked' => 0` |
| numbers | F | | IF:671 `'checked' => 0` |
| mirna | F | | IF:729 `'checked' => 0` |
| polyphen | T | b | IF:930 `'value' => 'b'` |
| summary | F | no | IF:353 `'value' => 'no'` |
| alphamissense | F | | WC:90; SC:612 → IF:1175 |
| dbscsnv | F | | WC:10; SC:1077 → IF:1175 |
| mutfunc | F | | WC:62; SC:1932 → IF:1139 |
| ancestral_allele | F | | WC:22; SC:1246 → IF:1175 |
| blosum62 | F | | WC:18; SC:1188 → IF:1175 |
| go | F | | WC:42; SC:1319 → IF:1175 |
| intact | F | | WC:54; SC:1851 → IF:1139 |
| mavedb | F | | WC:58; SC:1896 → IF:1175 |
| opentargets | F | | WC:82; SC:1432 → IF:1175 |
| riboseqorfs | F | | WC:86; SC:1816 → IF:1175 |
| avi | F | | not in WC; SC:640 `"enabled" => 0`; DOC:820 unchecked |
| protvar | F | | not in WC; SC:1969 `"enabled" => 0`; DOC:632 `value="no" checked` |
| species_frequency | F | | IF:541 `'checked' => 0` |

## Inconsistencies found, not changed (they change printed output)

- `regulatory`: `web_default_value` is null; the code's value is `'reg'` (IF:779).
- Restrict results: `summary` carries `web_default_value` `"no"`; `most_severe`, `pick`, `pick_allele`,
  `per_gene` carry null. All five are values of one dropdown (IF:348-363).
- Species-gated "on": `tsl`, `appris`, `mane`, `ccds`, `af*`, `pubmed`, `frequency` hold for human only;
  `core_type` for RefSeq species; `sift`, `polyphen` for species with that data.
