# `legacy/` — nothing in here is used by the tool

**Not imported, read or executed on any path the shipped assistant takes.** If you are reviewing
the tool, skip this folder: the whole tool is `../vep_assistant.py` plus the JSON files beside it.

Moved here 2026-09-22.

## `evaluate.py` — the stage-B benchmark

1,102 lines. Scores the **two-pass** design that was the default until 2026-09-14. Imported by
nothing, and cited as the reproduction path for no numbered experiment in `../../work/EXPERIMENTS.md`
(the harness scripts under `../../work/harness/` do that).

Four things in it describe a system that no longer exists:

| it assumes | since |
|---|---|
| a `retrieval → prompt → LLM → parse` draft call | 2026-09-14: one call, prose → factor tuple |
| a `critical` tier weighted 3× | 2026-08-19: the tier was deleted; the bucket is always empty |
| a `semantic` retrieval condition | 2026-09-16: `--semantic` removed, the branch is unreachable |
| gold from the seven-use-case table | 2026-09-13: retired |

Its headline metric is **enable-F1**, which Experiment 20 records as *undefined on the default
path* — it scored the draft, and there is no draft. Do not quote a number from this file.

## What measures the current system instead

| | |
|---|---|
| does the model read the question right | `../../work/harness/exp/factor_accuracy.py` (31 rows), `factor_grid.py` (600 queries) |
| does an error actually cost the user anything | `../../work/harness/exp/class_weighted_f1.py` |
| is the table what the mentors asked for | `../../work/harness/build/build_mentor_gold.py` |
