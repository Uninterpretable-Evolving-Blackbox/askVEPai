# `legacy_decisions/` — why the system is built this way

One folder per design decision the current system follows. Below, for each decision, every experiment
in its folder: what it showed and what it led to. Each folder's own README names the result file behind
every number. Measurements of the current system are in [`../current_evidence/`](../current_evidence/README.md);
experiments whose conclusion was reversed are in [`../legacy_superseded/`](../legacy_superseded/).

The conclusions all hold for the current system. Four scripts ran on an earlier version and do not run as
they are, because they import the old evaluator (now `vep_ai_demo/legacy/evaluate.py`):
`model_choice/eval_factor_set.py`, `model_choice/run_parallel_eval.py`, `generation/persona_ablation.py`
and `generation/teacher_sweep.py`. Scripts that import `genlib` need the generation code, which is kept in
the private working repository.

| | folder | decision |
|---|---|---|
| D1 | [`model_choice/`](model_choice/) | `gemma4:26b`, run locally |
| D2 | [`factor_scheme/`](factor_scheme/) | five factors replace the seven use cases |
| D3 | [`single_pass/`](single_pass/) | one model call; the draft call is gone |
| D4 | [`classifier/`](classifier/) | the model reads all five factors, species included, with reasoning on |
| D5 | [`missing_facts/`](missing_facts/) | a missing fact is assumed out loud, or asked for |
| D6 | [`species_data/`](species_data/) | which options exist for which species comes from Ensembl's own lists |
| D7 | [`output_effects/`](output_effects/) | an option is judged by what it does to VEP's output |
| D8 | [`priority_table/`](priority_table/) | the priority table's tiers, as corrected by the mentors' review |
| D9 | [`generation/`](generation/) | how the 31 review scenarios were generated |

---

## D1 · `gemma4:26b`, run locally

**Not current evidence:** these scored the old two-call design, or the one-call design before today's prompt.

Local, because patient cohorts cannot leave the building and Ensembl's tools are open source.

| file | what it showed | what it led to |
|---|---|---|
| `run_parallel_eval.py` | with all examples in the prompt, 5 seeds: 26b 84%, 12b 78%, e4b 65% (Exp 10) | 12b and e4b dropped |
| `reparse_bare_fix.py` | re-reads Exp 10's raw calls after an option-name fix | the corrected Exp 10 column |
| `eval_factor_set.py` | the size ladder: 26b 88.0, e4b 80.3, e2b 66.7 enable-F1 (Exp 19) | 26b kept over the smaller Gemma 4 models |
| `../single_pass/full_eval_singlepass.py` | with one model call, e4b gets 19/31 factor tuples exact; e2b cannot produce parseable answers on 7 rows | smaller models not viable on the single-call design either |

## D2 · five factors replace the seven use cases

**Not current evidence:** scored on the draft call, which the tool no longer makes, against an older priority table.

| file | what it showed | what it led to |
|---|---|---|
| `results/colab_2026-09-04/` (run by `../model_choice/eval_factor_set.py`) | enable-F1: no factors 69.9 → factors from the model 88.0 → the true factors 89.0 (Exp 17) | the configuration is priced by five factors; the model's factor mistakes cost about one point |

## D3 · one model call; the draft call is gone

**Not current evidence:** the comparison is with the two-call design, which no longer exists.

The tool used to make a second call, a "draft" of the configuration for a checker to repair.

| file | what it showed | what it led to |
|---|---|---|
| `results/pass2_authority_2026-09-09/README.md` | an empty or hostile draft gives the same 20 RECOMMENDED options: the checker rebuilds them from the factors | the draft has no say over the RECOMMENDED set |
| `pass_and_corpus_ablation.py` | F1: one call 0.898, two calls 0.870 or lower (26b, 3 repeats); e4b the same way round (Exp 20) | the draft call dropped (2026-09-14) |
| `class_weighted_f1.py` | the same comparison weighted by option class: 0.942 vs 0.936 or lower | the same conclusion |
| `singlepass_vs_twopass.py` | one call's options are a subset of two calls' on 31/31 scenarios; 17.9 s → 1.2 s | the draft only adds options, at 15 times the time |
| `results/final_2026-09-15/` | re-run on the 09-15 priority table: 0 row-deleting extras with one call, 5–7 with two | the conclusion holds after the table changed |

## D4 · the model reads all five factors, species included, with reasoning on

**Not current evidence:** run on earlier prompts, before species came from the model, or through an endpoint that ignored "reasoning off".

| file | what it showed | what it led to |
|---|---|---|
| `rules_vs_model.py` | a keyword rule per factor gets 9/31 factor tuples exact, the model 22/31 | no keyword layer; the rule stays as the baseline in experiment 1 of `../current_evidence/` |
| `species_rule_vs_model.py` | species wording removed: the model says unstated 14/14, the keyword scan says human 11/14 | species read by the model, not the scan (2026-09-16) |
| `results/factor_grid_natural_shipped.json` | species traps: model 29/30, keyword scan 17/30 | the same |
| `species_recall_hint.py` | showing the model the scan's matches adds no recall: 42/42 either way | the species hint off by default |
| `fewshot_classifier.py` | exact factor tuples fall from 22 to 12 as examples are added to the prompt | a prompt without examples |
| `results/factor_grid_natural_shipped_v2draft1.json` | the first rewrite of the prompt scored 129/150: it filled in goal and origin nobody stated | rejected; the prompt now says an unstated fact stays unstated |
| `results/factors_150_tricky_cases_reasoning_{on,off}_before_organism_field.json` | 150 tricky cases on one prompt: reasoning on 148/150, off 138/150 | reasoning back on (2026-09-20) |
| `results/factor_grid_{natural,terse}_shipped.json`, `results/factor_grid_think_seq20.json` | wording style changes nothing (138 vs 139/150); running calls in parallel changes nothing (20/20) | the 150 cases are run in conversational wording, 8 at a time |
| `results/factors_150_*_before_case_fixes*.json` | the 150 tricky cases before any hand fix, four runs: reasoning on 143, 141, 142, 142; off 135 in all four (species through the tool) | 21 case fixes; the runs on the fixed cases are experiment 1 of `../current_evidence/` |
| `results/factors_150_*_first_12_case_fixes*.json` | the same after the first 12 fixes: reasoning on 145, off 135 (species through the tool) | the other 9 fixes |
| `results/factors_31_review_scenarios_reasoning_*_before_relabelling*.json` | the 31 scenarios scored on the labels before six were corrected: on 29/31 F1 0.960, off 30/31 F1 0.967 | the same answers re-scored on the corrected labels are experiment 2 of `../current_evidence/` |

## D5 · a missing fact is assumed out loud, or asked for

**Not current evidence:** the defaults were priced on an older priority table and catalogue. The tool's behaviour today is experiment 5 of `../current_evidence/`.

The design is `reprompting_proposal.md` (private working repository).

| file | what it showed | what it led to |
|---|---|---|
| `fetch_real_queries.py`, `measure_underspecification.py` | 7 of 8 real questions from Ensembl's issue trackers leave out a fact that changes the configuration (goal 4, region 4, size 3) | missing facts are the normal case, so the tool needs a rule for each |
| `ablate_queries.py` | 78 rewrites of the 31 scenarios with one fact removed, each checked to have lost only that fact (`../current_evidence/cases/ablated_queries.json`) | the test set for everything below |
| `score_ablations.py` | the options lost when each fact is missing, by tier | which missing facts matter most |
| `default_direction_sweep.py` | every possible default priced both ways; species → human over-includes 3.62 columns and loses 0.38 | the defaults: human, somatic, both sizes, both regions |
| `default_candidates_output.py` | the same on real VEP output | the same |
| `results/reprompting/` | only the goal has no safe default; asking about it interrupts 12 of 78 | ask for the goal only |
| `score_try_queries.py`, `try_queries.sh` | 19 of 20 carelessly written scenarios read correctly | the rules hold on untidy wording |
| `try_reprompting.py` | shows asking and assuming as a user meets them | a demonstration, no figure |

## D6 · which options exist for which species comes from Ensembl's own lists

**Not current evidence:** the comparison is with the name scan the engine no longer uses, on the earlier 121-organism sample.

| file | what it showed | what it led to |
|---|---|---|
| Ensembl's pages and config files (`../../reference/`), built into each option's `species` list by our builders (private working repository) | seven of our catalogue's species claims disagreed with Ensembl's lists | Ensembl's lists win (2026-09-20) |
| `species_options_scan_vs_model.py`, `results/organism_121_names_*` | options offered from the organism the model names: right 242/242; from a name scan of the text: 222/242 | the engine takes the organism from the model (2026-09-22) |

## D7 · an option is judged by what it does to VEP's output

**Not current evidence:** these measure VEP itself (real runs and Ensembl's pages), not the tool.

| file | what it showed | what it led to |
|---|---|---|
| `run_vep_ab.py` | at cohort scale, clinical → basic loses 19 output columns; population → basic loses none | recommendations are scored by the columns and rows they change, not by counting option names |
| `run_vep_rest.py` | all 17 options that can be checked deliver on a five-class variant panel | the same |
| `exp_output_loss.py` | what dropping each option costs in VEP's output | the same |
| `build_output_effects_dossier.py` (private working repository) | each option's output fields and conflicts, from Ensembl's release-116 pages | the same; options the form already ticks are shown once as ALREADY ON |
| `local_option_sweep.py`, `results/local_vep_2026-09-10/` | every option one at a time on a local VEP; the frequency check at its default population deletes nothing | the same |
| `results/leak_rate_*` | the restrict-results options delete rows (per_gene: 334 → 19) | those options are never switched on silently |

## D8 · the priority table's tiers, as corrected by the mentors' review

**Not current evidence:** a review of the table, not a measurement of the tool; the F1 0.796 predates the species-list changes of 2026-09-20.

| file | what it showed | what it led to |
|---|---|---|
| `mentor_review/` round 1 (sheet, queue, `DECISIONS.md`) and the returned round-1 sheet (private working repository) | the mentor's verdicts on 31 scenarios in three tiers | the table's entries corrected |
| `mentor_review/` round 2, `retitle_review_two_tier.py` | the Ensembl team's comments | two tiers: critical merged into RECOMMENDED, DEFAULT renamed RECOMMENDED (2026-08-19) |
| `build_mentor_gold.py` (private working repository) | the table against the reviewer's own round-1 answers: F1 0.796 | a check, no change |

## D9 · how the 31 review scenarios were generated

**Not current evidence:** about how the test scenarios were written, not about the tool; run in July.

| file | what it showed | what it led to |
|---|---|---|
| `teacher_sweep.py` | four models writing the scenario text (e4b, 12b, 26b, 31b) are within noise | `gemma4:26b` writes them |
| `persona_ablation.py` | who is asking adds no measurable variety | the persona kept, for realism |

Scripts that call the model read `OLLAMA_BASE_URL`. Scripts that import one another across folders add the
other folder to `sys.path` at the top.
