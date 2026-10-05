# D4 · the classifier: why the model reads every factor, including species

The measurements of the classifier as it runs today (the 150-case grid, organism naming, the 31
scenarios, reasoning on vs off) are in [`../../current_evidence/`](../../current_evidence/README.md). This folder holds the
experiments that decided its shape.

| decision | number | script | file |
|---|---|---|---|
| no keyword layer | keyword rule 9/31 exact tuples vs model 22/31 | `rules_vs_model.py` | `../single_pass/results/overnight_2026-09-10/rules_vs_model_26b.json` |
| species from the model, not the scan (2026-09-16) | species traps: model 29/30, keyword scan 17/30 | `../../current_evidence/factors_150_tricky_cases.py`, then `factor_grid.py` (v1 prompt) | `results/factor_grid_natural_shipped.json` |
| | species text removed: model says unstated 14/14, scan says human 11/14 | `species_rule_vs_model.py` | `../single_pass/results/overnight_2026-09-10/species_rule_vs_model_26b.json` |
| prompt v2 wording | first v2 draft 129/150, rejected: it filled in goal and origin nobody stated | `../../current_evidence/factors_150_tricky_cases.py`, then `factor_grid.py` | `results/factor_grid_natural_shipped_v2draft1.json` |
| species hint off by default | the hint adds no recall: 42/42 either way | `species_recall_hint.py` | `results/species_recall_hint.json` |
| zero-shot prompt | exact tuples fall 22 → 12 as examples are added | `fewshot_classifier.py` | `results/fewshot_classifier.json` |

**Limits.** `rules_vs_model.py` and `species_rule_vs_model.py` call the model through the `/v1`
endpoint, which ignores `think=False`, so their model arms reasoned. `species_recall_hint.json`'s saved
`correct` field holds a scoring that was withdrawn; the quoted figure is recomputed from `rows`.
`fewshot_classifier.json` is confounded (handover 2026-09-10, not published) and was not re-run.

`rules_vs_model.py` is still imported by `../../current_evidence/factors_150_tricky_cases.py` for its keyword baseline.
`results/` also holds the grid runs that current_evidence no longer cites: reasoning off on prompt v1
in the natural and terse wordings (138 vs 139/150: wording style does not matter), 20 cases run one at a
time with reasoning on, 20/20, to check that running calls in parallel changes nothing
(`factor_grid_think_seq20.json`), and the aborted reasoning-on v1 run
(`factor_grid_natural_think_v1prompt_PARTIAL.log`, no JSON). These runs predate the 2026-09-23 renaming and keep the old script's name: in them
`shipped` means reasoning off and `think` reasoning on.

## Reasoning back on (2026-09-20)

The runs that turned classifier reasoning back on, moved here from `../../current_evidence/` on
2026-09-28 when the overnight run of 2026-09-23 (today's prompt and engine) replaced them there.

| run | reasoning on | reasoning off | files |
|---|---|---|---|
| 150 tricky cases, all four right, 09-16 (before the prompt asked for the organism) | 148/150, 4.0 s a query | 138/150, 0.9 s | `results/factors_150_tricky_cases_reasoning_{on,off}_before_organism_field.json` |
| 150 tricky cases, 09-20 (prompt with the organism field) | 142/150 | not run | `results/factors_150_tricky_cases_reasoning_on_2026-09-20.json` |
| 31 review scenarios, same configuration as the true labels, seed 42 | 29/31, F1 0.975 (09-20) | 30/31, F1 0.982 (09-17, before the organism field) | `results/factors_31_review_scenarios_reasoning_on_2026-09-20.json`, `results/factors_31_review_scenarios_reasoning_off_before_organism_field.json` |

The 148 vs 138 pair decided it: on the same prompt, reasoning off missed three species twins, three
unstated origins and two traps that reasoning on got right.

## The 150 cases before the case fixes, the 31 scenarios before the relabelling

Moved here from `../../current_evidence/results/`, where the runs on the fixed cases and the corrected
labels replaced them. Same prompt and model as experiments 1 and 2 there.

| run | reasoning on | reasoning off | files |
|---|---|---|---|
| 150 tricky cases, all four right, before any case fix | 143 (repeats 141, 142, 142) | 135 in all four runs, species through the tool | `results/factors_150_{tricky_cases,species_through_tool}_reasoning_{on,off}_before_case_fixes[_repeat1,2,3].json` |
| the same, RECOMMENDED unchanged by the misreads | 148 (147, 148, 146) | not scored | `results/factors_150_settings_effect_reasoning_on_before_case_fixes.json` |
| 150 tricky cases after the first 12 fixes | 145 through the tool (raw 146; a repeat, raw only, 143); RECOMMENDED unchanged 148 | 135 through the tool (raw 125) | `results/factors_150_*_first_12_case_fixes[_repeat1].json` |
| 31 review scenarios, same RECOMMENDED, labels before six were corrected | 29/31, F1 0.960, 21/31 exact | 30/31, F1 0.967, 22/31 exact | `results/factors_31_review_scenarios_reasoning_{on,off}_before_relabelling[_repeat1].json` |

Before the fixes, six misses recurred in all four reasoning-on runs: spec-doma-2 trap, orig-word-3 absent,
anal-word-1 trap, anal-tool-4 absent, anal-doma-4 trap and anal-doma-5 trap. The case fixes score
anal-doma-4 and anal-doma-5 right on clinical + frequency as well.
