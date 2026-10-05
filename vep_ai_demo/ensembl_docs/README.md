# Ensembl's own option and plugin pages, parsed

`vep_options_parsed.json` and `vep_plugins_parsed.json` are the release-116 `vep_options.html` and
`vep_plugins.html` pages (jun2026.archive.ensembl.org), parsed to one record per flag or plugin.
`--explain` takes the Output columns from these files; the description it prints is the catalogue's,
quoted from Ensembl with its source. The saved pages are in `reference/ensembl_docs_116/` at the
repository root (`../../reference/ensembl_docs_116/`); its README gives the URLs, the fetch date and
how they were parsed.
