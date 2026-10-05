# `legacy_superseded/` — what the current system replaced

Nothing here is used by the tool. Each folder is an earlier design, or a way of testing, that has since been
replaced. Below, for each folder: why it no longer applies, what its files did, and what replaced them.
The experiment ledger (`EXPERIMENTS.md`, private working repository) cites these files for
its earlier numbers; most of their result files stay on the development machine in `../local_runs/`.
Several scripts here no longer run.

Designs whose conclusion still holds are in [`../legacy_decisions/`](../legacy_decisions/README.md).

| folder | period | replaced by |
|---|---|---|
| [`prototype/`](prototype/) | to 2026-06 | the catalogue built from Ensembl's sources, and the 31 review scenarios |
| [`use_cases/`](use_cases/) | 2026-06 → 07-15 | the five factors ([D2](../legacy_decisions/README.md#d2--five-factors-replace-the-seven-use-cases)) |
| [`two_pass/`](two_pass/) | 07-15 → 09-09 | one model call ([D3](../legacy_decisions/README.md#d3--one-model-call-the-draft-call-is-gone)) |
| [`keyword_traps/`](keyword_traps/) | 09-10 → 09-15 | experiment 1 of [`../current_evidence/`](../current_evidence/README.md) |
| [`remote_guard/`](remote_guard/) | 09-06 → 09-23 | running everything locally |
| [`old_docs/`](old_docs/) | to 09-23 | [`../../README.md`](../../README.md) |

---

## `prototype/` · the inherited demo

**No longer applies:** the demo's examples and option ids are gone, and the tool puts no examples in its prompt.

| files | what they did | replaced by |
|---|---|---|
| `bootstrap_examples.json`, `test_queries.json`, `preliminary_examples_README.md` | the demo's 7 worked examples and 7 test queries | the 31 review scenarios (`../current_evidence/cases/iced.json`) |
| `validate_examples.py` | checked those examples against the catalogue and the checker | — |
| `id_migration.json` | mapped the demo's option ids to the new catalogue | the catalogue built from Ensembl's sources |

## `use_cases/` · the seven use cases

**No longer applies:** the tool no longer sorts a question into one of seven use cases, and its prompt no longer carries worked examples. Five factors decide the configuration.

| files | what they did | replaced by |
|---|---|---|
| `run_experiment.sh`, `aggregate_results.py`, `compute_run_sd.py`, `rescore_offline.py`, `score_metrics.py` | ran and scored the use-case prompt across models (Exp 3, 7, 10) | D1's model choice and D2's factor-priced scoring |
| `run_example_sweep.py`, `run_order_sensitivity.py`, `run_order_experiment.sh` | how many worked examples to include, and in what order (Exp 2, 9) | a prompt without examples (D4) |
| `run_attribution.py`, `run_exp6.sh`, `run_exp6_seeds.sh` | whether each recommendation came from the knowledge base or from the model's memory (Exp 5, 6) | the priority table decides every option |
| `structured_pilot.py`, `build_output_json.py`, `output_schema/` | had the model write the whole recommendation as JSON: 16 of 40 answers were valid (Exp 8) | the model returns only the five factors; code builds the configuration |
| `author_reference_set.py`, `silver_reference_*`, `SILVER_REFERENCE_README.md` | a reference set drafted for the mentors to confirm; withdrawn | the 31 review scenarios the mentors reviewed (D8, D9) |
| `test_queries_sim.json`, `real_queries_biostars.json`, `real_queries_smoke.json`, `run_user_queries.py` | test questions of that period, and a script to run one set | the experiments in `../current_evidence/` |
| `bench_latency.py` | timed the full prompt → model → parser → checker path | the one-user timing in experiment 1 |
| `show_tiered_output.py` | a first mock-up of splitting the output into core options and add-ons | the RECOMMENDED / OPTIONAL / ALREADY ON output (D7) |
| `priority_by_use_case_snapshot.json`, `catalogue_skeleton.json` | the use-case priority table and the first catalogue plan | `../../vep_ai_demo/priority_by_factor.json` and the catalogue |
| `AUDIT_PROMPTS.md` and `meeting_notes_2026-06-23.md` (private working repository), `EXPERIMENT_SUMMARY.md` | documents of that period | — |

## `two_pass/` · the two-call design

**No longer applies:** the tool makes one model call; these planned and ran the design with a second, "draft" call.

| files | what they did | replaced by |
|---|---|---|
| `PROGRESS.md`, `action_plan_2026-08-03.md`, `action_plan_2026-08-11.md`; `READING_ORDER.md` (private working repository) | the progress log, reading order and plans of that period | [`../../README.md`](../../README.md) |
| `colab_eval.md`, `colab_tunnel.md`, `resume_attribution.sh` | running the experiments on a remote Colab GPU | every run on the local machine |
| `prompting_literature.md` | prompt-writing literature and what applied to the tool at the time | — |
| `playground.html` | a generated page for trying the tool | none; the web interface is Ensembl's to build |

## `keyword_traps/` · 24 hand-written traps

**No longer applies:** 24 cases written freely, uneven across factors and tricks, and no species; a clean score bounded the error rate only below about 12%.

| files | what they did | replaced by |
|---|---|---|
| `factor_traps.py` | 24 questions whose cue word points the wrong way: the model got 24/24, a keyword rule 6/24 (Exp 21) | the trap version of experiment 1 |
| `factor_pairs.py` | the same 24 sentences with the trap taken out | the twin version of experiment 1 |
| `checklist_matrix.py` | laid the existing cases out by capability and test type | the design of experiment 1 |

## `remote_guard/` · the remote-GPU guard

**No longer applies:** every run is local on a 128 GB machine, so the guard only blocked runs.

| files | what they did | replaced by |
|---|---|---|
| `_remote_guard.py` | refused any model call aimed at this machine, after a call meant for a remote GPU froze a 17 GB laptop | nothing; no script imports it |

## `old_docs/` · documents frozen at a date

**No longer applies:** each describes the project as it stood on its date.

| files | what they did | replaced by |
|---|---|---|
| `STATUS.md` | where the project stood, 2026-09-15 | `../../README.md` |
| `harness_README_2026-09-22.md` | the scripts folder before the reorganisation | the READMEs of `../current_evidence/` and `../legacy_decisions/` |
| `overnight_2026-09-23.md` | the overnight run whose reasoning-on results are in `../current_evidence/results/` | — |

## Reasoning off, then on again

Exp 15 (2026-08-03) turned reasoning off in the classifier: 5.8 times faster, no measured cost. On
2026-09-20 it went back on: on the same prompt the 150 tricky cases scored 148 with reasoning on and 138
with it off ([D4](../legacy_decisions/README.md#d4--the-model-reads-all-five-factors-species-included-with-reasoning-on)).

## Former names

Older result files, handovers and the experiment ledger use the names on the left.

| former name | today | when |
|---|---|---|
| `factor_grid.py` | `../current_evidence/factors_150_tricky_cases.py` | 2026-09-23 |
| `factor_accuracy.py` | `../current_evidence/factors_31_review_scenarios.py` | 2026-09-23 |
| `organism_naming.py`, then `organism_121_names.py` | `../current_evidence/organism_754_names.py`; the 121-organism sample is its `--sample-121` | 2026-09-23, 2026-09-26 |
| `species_option_accuracy.py` | `../legacy_decisions/species_data/species_options_scan_vs_model.py` | 2026-09-23 |
| `rules_vs_model.py` in `current_evidence/` | `../legacy_decisions/classifier/rules_vs_model.py` | 2026-09-23 |
| `fallback_e2e.py` in `legacy_decisions/missing_facts/` | `../current_evidence/missing_facts_78_rewrites.py` | 2026-09-28 |
| `grid_species_shipped.py` (overnight folder, untracked) | `../current_evidence/factors_150_species_through_tool.py` | 2026-09-28 |
| `grid_settings_score.py` (work/harness/exp, untracked) | `../current_evidence/factors_150_settings_effect.py` | 2026-09-28 |
| `rerun_2026-09-27/`: `grid_{on,off}_r{1,2,3}.json`, `grid_species_off_r{1,2,3}.json`, `fallback_e2e_r{1,2,3}.json`, `factor_accuracy.json`, `mentor_queries.json` (local run folder) | `../legacy_decisions/classifier/results/`: `factors_150_tricky_cases_reasoning_{on,off}_before_case_fixes_repeat{1,2,3}.json`, `factors_150_species_through_tool_reasoning_off_before_case_fixes_repeat{1,2,3}.json`; `../current_evidence/results/`: `missing_facts_78_rewrites_reasoning_on_repeat{1,2,3}.json`, `factors_31_review_scenarios_reasoning_on_repeat1.json`, `mentor_queries_reasoning_on_repeat1.json` | 2026-09-28, 2026-09-30 |
| reader `shipped` / `think`, in file names too | `reasoning_off` / `reasoning_on` | 2026-09-23 |
| result suffix `_v2prompt` | `_before_organism_field` (the prompt of 09-16) | 2026-09-28 |
| `organism_all_names_*` results | `organism_754_names_*` | 2026-09-26 |
| `data/iced.json`, `data/ablated_queries.json` | `../current_evidence/cases/iced.json`, `../current_evidence/cases/ablated_queries.json` | 2026-09-28 |
| `data/real_queries_fetched.json`, `data/real_queries_draw_log.json` | `../legacy_decisions/missing_facts/real_queries_fetched.json`, `../legacy_decisions/missing_facts/real_queries_draw_log.json` | 2026-09-28 |
| `data/simulated_gold_examples.json` | `../../vep_ai_demo/legacy/training_examples.json` (the same 23 examples) | 2026-09-28 |

The mentor-query results with reasoning on in `../current_evidence/results/` are the overnight run of
2026-09-23 (engine `51912b2`), copied from the untracked `work/results/overnight_2026-09-23/`; its README is
`old_docs/overnight_2026-09-23.md`. The 31-scenario files there hold the same answers as that run
(reasoning on) and as the 2026-09-28 run with engine `9dd3140` (reasoning off), re-scored on 2026-09-30
against the six corrected labels. The 150-case files there (tricky cases, species through the tool,
settings effect) are the 2026-09-30 runs on the fixed cases. The runs they replaced, the overnight 143/150
among them, are in `../legacy_decisions/classifier/results/` (`*_before_case_fixes*`, `*_before_relabelling*`).
