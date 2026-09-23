# Ensembl's own option and plugin pages, parsed

`vep_options_parsed.json` and `vep_plugins_parsed.json` are the release-116 `vep_options.html` and
`vep_plugins.html` pages (jun2026.archive.ensembl.org), parsed to one record per flag or plugin. The
engine reads them for the "Ensembl: …" lines in `--explain`. The saved pages and the parser live in the
evidence repository under `work/research/ensembl_docs_116/`.
