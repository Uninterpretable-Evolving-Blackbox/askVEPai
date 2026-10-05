# D6 · which options exist for which species comes from Ensembl's own lists

The factor table knows only human / non-human. Per-species availability (SIFT for human and 11 other species,
PolyPhen human only, frequency files for four species, each plugin's species list) comes from Ensembl's
pages and config files, and the checker removes an option the species lacks, saying why.

| what | source (in `../../../reference/`) | builder | output |
|---|---|---|---|
| SIFT / PolyPhen species | `ensembl_docs_116/protein_function.html` | `build_species_data.py` | `species_data.json` |
| form gating (CCDS, variant synonyms), frequency files | `ensembl_source/VEP/InputForm.pm`, `ensembl_source/vep_custom_web_config.json` | same | same |
| per-plugin species lists, release 116 | `ensembl_source/vep_plugins_species_config_116.txt` | `build_plugin_species.py` | same, `plugin_species` |
| the 356-species name index | Ensembl REST | `build_species_index.py` | `../../../vep_ai_demo/species_index.json` |

2026-09-23: `build_species_data.py` and `species_data.json` no longer exist. Every list above now sits in
the `species` field of its option in `../../../vep_ai_demo/vep_options.json`, with the source named in the
option's `provenance`; `build_plugin_species.py` writes the plugin rows there directly. The builders are kept in
the private working repository.

Seven disagreements with our own catalogue prose were resolved in Ensembl's favour on 2026-09-20.
Six changed how often an option appears over the 252 factor combinations (cadd and utrannotator as
RECOMMENDED, the other four as OPTIONAL), before → after:

| option | before → after |
|---|---|
| cadd | 72 → 144 |
| utrannotator | 56 → 112 |
| maxentscan | 96 → 48 |
| paralogues | 64 → 32 |
| ancestral_allele | 96 → 48 |
| mutfunc | 32 → 64 |

One rule was retired: `non-human + clinical-interpretation → maxentscan` (MaxEntScan is human only); it is kept
under `_conditional_rules_retired` in `../../../vep_ai_demo/factors.json` (handover 2026-09-22 §1.5, not published).

No experiment folder of its own: the evidence is Ensembl's text, and the check is the test suite.

## The organism for these lookups comes from the model (2026-09-22)

Added 2026-09-23. Which organism the lookups use decides which list the user gets. Until engine commit
`51912b2` the checker scanned the query for the first organism name; since then it takes the organism
the model names, and scans only when the model names none.

| organism used for the lookup | organism right | offered options right | with a decoy organism |
|---|---|---|---|
| the name scan (before `51912b2`) | 174/242 | 222/242 | 103/121 |
| **the organism the model returns (today)** | 241/242 | **242/242** | 121/121 |

Replayed on 2026-09-28 through the engine with whole-word name matching and species grouped by Ensembl
taxon (`results/species_options_scan_vs_model_2026-09-28.json`): the scan's lists 226/242 right, the
model's 242/242; the model's organism 239/242, because a strain Ensembl files under its own taxon now
counts as its own species. The decision stands. The figures above and below are the 2026-09-23 run.

The scan's 20 wrong lists involve SIFT 18 times, CADD 8 and IntAct 6: "guinea pig" is scanned as pig
and gets CADD; "not a mouse study: our pig herd" gets mouse's list. The model's one wrong organism
("samples come from a drill", no name returned) still gets the right list, because the drill has no
species lists this scenario uses.

Fixed scenario: non-human, germline, small variants, coding, clinical interpretation. No model call: it
replays the organism answers saved by the 121-organism sample (`../../current_evidence/organism_754_names.py
--sample-121`, then called `organism_121_names.py`); those results are in `results/organism_121_names_*`.
The full run over all 754 names is in `../../current_evidence/`.

| script | result |
|---|---|
| [`species_options_scan_vs_model.py`](species_options_scan_vs_model.py) (was `current_evidence/species_option_accuracy.py`) | [`results/species_options_scan_vs_model.json`](results/species_options_scan_vs_model.json) |
