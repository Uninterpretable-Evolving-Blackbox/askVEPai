# `tests/` — run every session, no model, seconds

| script | checks |
|---|---|
| `verify_pipeline.py` | 79 invariants: config integrity, gates, the priority table file, species data |
| `test_user_context.py` | 15: a fact the user states beats the classifier; the assembly gate |
| `defaults_evidence.py` | 28: every guessed default still matches the evidence given for it |
| `ask_rate.py` | how often the tool interrupts, per policy; shipped 12/78 |
| `result_filter_note.py` | the note for gene-list and loss-of-function requests fires on the mentors' four queries and stays quiet on every stored test query |
| `species_by_organism.py` | every option shown to a user exists for the organism named: every organism in the species index × every factor tuple |
| `engine_regressions.py` | 52: the engine defects of the 2026-09-27 audit stay fixed (organism names on whole words, CADD file by species, taxon species keys, both builds named, `--full` and the size files, a failed model call, the seed) |
| `printed_output_guard.py` | what the tool prints, over 2,268 runs with the model stubbed; `--snapshot` before an engine change, `--snapshot … --diff` after, to see every line it moved |

`verify_pipeline`, `test_user_context`, `defaults_evidence`, `engine_regressions` and `ask_rate` run in CI (`.github/workflows/suites.yml`).
