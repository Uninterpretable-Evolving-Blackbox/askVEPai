# `legacy/`: nothing in here is used by the default path

Every file in this directory is kept as a record. **None of it is imported, read or executed on the
default path.** Only `--two-pass` loads `two_pass.py` and reads `training_examples.json`. If you are
reviewing the tool, you can skip this folder entirely; the whole tool is `../vep_assistant.py` plus
the five JSON files and `ensembl_docs/` beside it.

Moved here 2026-09-22.

## `two_pass.py` — the stage-B draft path, as code

The ~1,150 lines that made the second model call: example retrieval (keyword and embedding), the draft
prompt builder, the `✓/✗ [source: id]` marker parser and its citation audit, the override report, and
the structured-JSON assembler. Moved out of `vep_assistant.py` verbatim on 2026-09-22.

Not imported by a default run. It loads only when `--two-pass` is passed, or when a harness calls one
of the eleven names the engine serves through its module `__getattr__` (`extract_recommendations`,
`build_option_aliases`, `build_system_prompt`, ...). It binds the engine's namespace into itself at
load, so the functions run unchanged.

Why it is here and not deleted: it is the comparison path Exp 20 was measured on, and two scripts
in `../../evidence/legacy_decisions/single_pass/` (`singlepass_vs_twopass.py`,
`pass_and_corpus_ablation.py`) still run it.

## `evaluate.py` — the stage-B benchmark

1,124 lines. Scores the **two-pass** design that was the default until 2026-09-14. Imported by
nothing, and cited as the reproduction path for no numbered experiment in `EXPERIMENTS.md` (private
working repository; the harness scripts do that).

Four things in it describe a system that no longer exists:

| it assumes | since |
|---|---|
| a `retrieval → prompt → LLM → parse` draft call | 2026-09-14: one call, prose → factor tuple |
| a `critical` tier weighted 3× | 2026-08-19: the tier was deleted; the bucket is always empty |
| a `semantic` retrieval condition | 2026-09-16: `--semantic` removed, the branch is unreachable |
| gold from the seven-use-case table | 2026-09-13: retired; its snapshot is in `../../evidence/legacy_superseded/use_cases/` |

Its headline metric is **enable-F1**, which Exp 20 records as *undefined on the default path* —
it scored the draft, and there is no draft.

## `training_examples.json` — 23 Claude-written scenarios from June

The in-context corpus for the stage-B draft call: a scenario in prose, a full configuration typed
out by hand, and one of the seven retired use-case labels. Written by an LLM as a stand-in before
any gold existed -- the same lineage as the Opus silver set that `EXPERIMENTS.md` withdrew.

The default path never reads it. Only `--two-pass` does, as the draft's examples; with the file
absent that path runs on an empty corpus (`load_knowledge_base` returns `[]`). The 31 scenarios
every published number is measured on are a different file,
`../../evidence/current_evidence/cases/iced.json`, and carry the five factor labels this one predates.

## `VEP_web_documentation.pdf`

2.4 MB. Not in either repository (`*.pdf` is gitignored); it is on the development machine only.
Ensembl's own web-VEP documentation, downloaded in June 2026 as a reference while the option
catalogue was being built. Read only by `evidence/current_evidence/chat_models_20_cases.py --pdf`
(experiment 6). The catalogue's grounding is recorded in `../../reference/ensembl_docs_116/`
instead, with the URL and fetch date per file.

## `results/`

In the private working repository only, not the public one. 1,773 files of saved output: 1,749
`vep_recommend_*.md` (June to September 2026), 9 `vep_explain_*.md` (from March 2026), 12 files
under `attribution/`, and `evaluation_results_qwen2.5_{3b,7b,14b}.md` for a model family the project
no longer uses (`gemma4:26b` has been the model since June). Kept because they are the only copy of
what the tool printed at those dates.

## What replaced all of this

| dead thing here | what does the job now |
|---|---|
| `evaluate.py` | `../../evidence/current_evidence/factors_31_review_scenarios.py` (the tuple), `factors_150_tricky_cases.py` (600 queries), `../../evidence/legacy_decisions/single_pass/class_weighted_f1.py` (scoring by what an error does to the output) |
| the PDF | `../../reference/ensembl_docs_116/`, parsed by `build_output_effects_dossier.py` (private working repository) |
| qwen results | `../../evidence/current_evidence/results/` — `gemma4:26b` throughout |
