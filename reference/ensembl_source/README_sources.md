# Where each file here came from

| file | source | fetched | what it is |
|---|---|---|---|
| `vep_plugins_web_config.txt` | Ensembl public-plugins (web deployment) | earlier snapshot | which plugins the WEB FORM offers (`available => 1`) |
| `vep_plugins_species_config_116.txt` | https://raw.githubusercontent.com/Ensembl/VEP_plugins/release/116/plugin_config.txt | 2026-09-20 | which SPECIES each plugin supports (`species` field). Every plugin here is `available => 0`; the web deployment overrides that, so this file cannot say what is on the form. Pointer from Likhitha, 2026-09-16 meeting. |
| `hgnc_non_alt_loci_set_2026-09-18.txt` | https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/non_alt_loci_set.txt (HGNC, last-modified 2026-09-18) | 2026-09-23 | approved human gene symbols (45,036). Ensembl takes human gene names from HGNC. `build_hgnc_symbols.py` (private working repository) reduces it to `vep_ai_demo/hgnc_symbols.json` for the out-of-scope gene-filter note. Downloaded with David's approval. Not tracked (17 MB); fetch it from the URL. |
