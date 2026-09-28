# D5 · a fact the user did not state is assumed out loud, or asked for

When a factor is missing the tool takes a decided default and prints that it did (species → human,
origin → somatic, both sizes, both regions), or asks, for `analysis_goal` only. How the tool does this
today is experiment 5 in [`../../current_evidence/`](../../current_evidence/README.md). The design is in
[`../../../docs/research/reprompting_proposal.md`](../../../docs/research/reprompting_proposal.md).

| number | experiment | script | file |
|---|---|---|---|
| 78 clean rewrites of the 31 rows with one fact removed; with species, 95/155 clean on 3 seeds | Exp 18 | `ablate_queries.py` | `../../../data/ablated_queries.json` (the 78, read by the tests); `results/ablated_queries_rerun*.json`, `results/species_ablation_2026-09-07/` |
| options lost per removed fact, by tier | Exp 16/18 | `score_ablations.py` | computed at run time |
| every default priced both ways; species → human over-includes 3.62 columns, loses 0.38 | Exp 23 | `default_direction_sweep.py` | `results/default_direction_sweep.json` |
| the same, on real VEP output | Exp 23 | `default_candidates_output.py` | `results/default_species_mouse.json`, `results/default_region_focus.json` |
| the decided default is reached AND disclosed on 76/78; species 14/14 (2026-09-15) | Exp 24 | `../../current_evidence/missing_facts_78_rewrites.py` (then `fallback_e2e.py`) | `../single_pass/results/final_2026-09-15/fallback_e2e_26b.json` |
| the tool asks on 12 of 78, all `analysis_goal` | — | — | `results/reprompting/ask_rate.txt`, `results/reprompting/ask_rate_by_row_shipped.txt` |
| what 8 real tracker questions leave unstated | — | `fetch_real_queries.py`, `measure_underspecification.py` | `results/underspecification_measurement.json` |
| 19 of 20 sloppy hand-written scenarios read correctly | — | `score_try_queries.py` (`try_queries.sh` runs them by hand) | `results/try_queries_scored.json` |

`try_reprompting.py` shows the assume/ask behaviour as a user meets it.

**Limits.** `fallback_e2e_26b.json` and `try_queries_scored.json` predate species-from-the-model
(2026-09-16). With reasoning on, 4 of the 30 grid cases with the goal removed come back as
`basic-consequence`, so the tool does not ask (handover 2026-09-22 §5.1, open).
