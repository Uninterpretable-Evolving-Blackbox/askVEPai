# Overnight runs, 2026-09-23, on `main` as pushed

Engine `51912b2`, private `79cf591`, public `5df328f`; all three matched `origin/main` with clean trees.
gemma4:26b local (Ollama 0.33.3, M5 Max), context 16384, temperature 0, seed 42 (42,43,44 for
factor accuracy and the mentor queries, as in `final_2026-09-15`). Reasoning ON (the shipped default)
unless marked off. Queue 00:06 → 01:53; the exact commands are `run_queue.sh`, timings `queue.log`.

Harness changes present during the run (uncommitted): `fallback_e2e.py` regex accepts the value-only
`Assumed X = Y` line printed since 2026-09-15 (it matched nothing before); `species_by_organism.py` and
`mentor_queries.py` are new.

| run | result | before |
|---|---|---|
| verify_pipeline / test_user_context / defaults_evidence | 79 / 15 / 28 pass | same |
| ask_rate | shipped 12/78, all analysis_goal | 12/78 |
| check_round2_ready | all pass, 3 OURS | same |
| species_by_organism (no model) | switched on: 0 off-list of 424,664; add-ons offered: 43,136 off-list (intact 31,776, mutfunc 11,360); every non-human organism hit | new |
| mentor queries, 3 seeds | see below | by hand, unsaved |
| factor accuracy, 31 rows | exact 21/31 label, 29/31 config; e2e F1 0.960 ± 0.000 | 09-15: 21/31, 0.970 (hint on, prompt v1) |
| fallback e2e, 78 | 73/78 disclosed; FILLED origin 2, region 1, goal 2 | 09-15: 76/78 (reasoning off) |
| grid, reasoning on | all four 143/150 (plain 150, trap 146, twin 150, absent 147) | 09-20: 142 |
| grid, reasoning off, raw read | 126/150; species all-four 17/30 | 09-16: 138 (before the organism field) |
| grid species, through `infer_factors` | off 26/30, on 29/30 | — |
| organism naming, on | name 120/121 plain, 121/121 decoy; binary 241/242 | same |
| organism naming, off | name 120/121, 121/121; binary raw 222/242, 19 name/binary disagreements the derive rule resolves | same |
| four-arm ablation, plain F1 (form defaults excluded) | single 0.940, two_31loo 0.932, two_none 0.918, two_23 0.916 | 09-15: 0.858 / 0.830 / 0.829 / 0.840 |
| class-weighted F1 | single 0.962, two_31loo 0.965, two_none 0.912, two_23 0.906; row-deleting extras 0/0/6/6 | 09-15: single 0.900 |

**Grid reasoning-off.** `factor_grid.py` scores `parse_factor_classification`, which does not apply the
rule in `infer_factors` that a named non-human organism sets species to non-human. Re-reading the 30
species cases through `infer_factors` (`grid_species_shipped.py`, seed 42, 8 workers) gives 26/30
all-four off and 29/30 on. On that basis the shipped reasoning-off path is about 135/150, not 126.
The reasoning-on figure is unaffected (the rule is a no-op there).

**Mentor queries** (apply_defaults off, so `unstated` is visible):

| query | origin | analysis_goal | stable |
|---|---|---|---|
| colorectal cancer genes | somatic ×3 | clinical ×3 | yes |
| breast cancer genes | unstated (42), somatic (43, 44) | clinical ×3 | no |
| BRCA1, BRCA2 | unstated ×3 | basic-consequence ×3 (filled by the model) | yes |
| LoF, hereditary cancer panel | germline ×3 | clinical ×3 | yes |

Species unstated on all four (human assumed and disclosed downstream); size and region empty on all.

**Not comparable across dates:** the F1 golds are resolved from the current table, which changed
(plugin species lists, CCDS dropped, single authored priority table), so 0.940 vs 0.858 mixes a table
change with any model change.

CLI answers saved by the tool during the queue (205 files) were moved out of `vep_ai_demo/results/`.
