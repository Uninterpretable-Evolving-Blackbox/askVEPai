# `legacy/` — nothing in here is used by the tool

Every file in this directory is kept as a record. **None of it is imported, read or executed on
any path the shipped assistant takes.** If you are reviewing the tool, you can skip this folder
entirely; the whole tool is `../vep_assistant.py` plus the four JSON files beside it.

Moved here 2026-09-22.

## `evaluate.py` — the stage-B benchmark

1,102 lines. Scores the **two-pass** design that was the default until 2026-09-14. Imported by
nothing, and cited as the reproduction path for no numbered experiment in `../../work/EXPERIMENTS.md`
(the harness scripts do that).

Four things in it describe a system that no longer exists:

| it assumes | since |
|---|---|
| a `retrieval → prompt → LLM → parse` draft call | 2026-09-14: one call, prose → factor tuple |
| a `critical` tier weighted 3× | 2026-08-19: the tier was deleted; the bucket is always empty |
| a `semantic` retrieval condition | 2026-09-16: `--semantic` removed, the branch is unreachable |
| gold from the seven-use-case table | 2026-09-13: retired; its snapshot is in `work/harness/legacy/` |

Its headline metric is **enable-F1**, which Exp 20 records as *undefined on the default path* —
it scored the draft, and there is no draft.

## `training_examples.json` — 23 Claude-written scenarios from June

The in-context corpus for the stage-B draft call: a scenario in prose, a full configuration typed
out by hand, and one of the seven retired use-case labels. Written by an LLM as a stand-in before
any gold existed -- the same lineage as the Opus silver set that `EXPERIMENTS.md` withdrew.

The default path never reads it. Only `--two-pass` does, as the draft's examples; with the file
absent that path runs on an empty corpus (`load_knowledge_base` returns `[]`). The 31 scenarios
every published number is measured on are a different file, `work/generation/candidates/iced.json`,
and carry the five factor labels this one predates.

## `VEP_web_documentation.pdf`

2.4 MB. Ensembl's own web-VEP documentation, downloaded in June 2026 as a reference while the
option catalogue was being built. Read by no code. The catalogue's grounding is recorded in
`../../work/research/ensembl_docs_116/` instead, with the URL and fetch date per file.

## `results/`

17 files of saved output: `vep_explain_*.md` from March 2026, and
`evaluation_results_qwen2.5_{3b,7b,14b}.md` for a model family the project no longer uses
(`gemma4:26b` has been the model since June). Kept because they are the only copy of what the
tool printed at those dates.

## What replaced all of this

| dead thing here | what does the job now |
|---|---|
| `evaluate.py` | `work/harness/exp/factor_accuracy.py` (the tuple), `factor_grid.py` (600 queries), `class_weighted_f1.py` (scoring by what an error does to the output) |
| the PDF | `work/research/ensembl_docs_116/`, parsed by `work/harness/build/build_output_effects_dossier.py` |
| qwen results | `work/results/` — `gemma4:26b` throughout |
