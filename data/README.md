# `data/` — the review scenarios and test sets

The engine's own data (option catalogue, factor scheme, priority table, species index) lives only in
`../vep_ai_demo/`, the one copy. This folder holds what the engine does not ship.

| file | what it is | read by |
|---|---|---|
| `priority_by_factor_NOTES.md` | why each entry of `../vep_ai_demo/priority_by_factor.json` is what it is, with the mentors' words | people |
| `iced.json` | the 31 review rows every published figure is scored on | tests, evidence scripts |
| `ablated_queries.json` | the 31 rows with one fact removed (78 clean) | tests |
| `real_queries_fetched.json`, `real_queries_draw_log.json`, `real_testset_8.json` | Ensembl issue-tracker questions, fetched verbatim with hashes | tests, evidence |
| `simulated_gold_examples.json` | the 23 stage-B examples, still the pipeline's example corpus | pipeline |

`build/` regenerates data files from their sources; the catalogue and species-index builders write the
engine's copies in `../vep_ai_demo/` directly.

`species_data.json` and its builder `build/build_species_data.py` were deleted on 2026-09-23 (merged from
main): the engine's catalogue carries each option's species list, with its source in `provenance`.

The mentors' returned review sheets and the round-2 configuration tab are kept in the private working
repository, with the mentor correspondence.
