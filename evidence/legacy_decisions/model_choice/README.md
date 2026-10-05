# D1 · `gemma4:26b`, run locally

Local, because patient cohorts cannot leave the building and Ensembl's tools are open source. 26b, because the
smaller Gemma 4 models lose accuracy and consistency and are not faster at the e4b rung.

| number | experiment | script | file |
|---|---|---|---|
| 26b all-examples 84% ± 2, 12b 78%, e4b 65% (5 seeds) | Exp 10, stage B | `run_parallel_eval.py` | `results/evaluation_results_gemma4_{26b,12b,e4b}.md`, raw calls in `results/raw/` |
| 26b 88.0 ± 0.2, e4b 80.3 ± 1.2, e2b 66.3 ± 0.3 enable-F1 | Exp 19, 2026-09-08 | `eval_factor_set.py` | 26b: `../factor_scheme/results/colab_2026-09-04/enable_f1_live_inferred.json`; e4b: `results/exp19_ladder_partial.log` (seeds 42, 43) + `results/exp19_ladder_gemma4_e4b_seed44.json`; e2b: `results/exp19_ladder_gemma4_e2b.json` |
| single-pass e4b: exact tuple 19/31, F1 0.927; e2b: 7 rows unparseable | overnight 2026-09-10 | `../single_pass/full_eval_singlepass.py` | `../single_pass/results/overnight_2026-09-10/singlepass_eval_{e4b,e2b}.json`, `probe_e2b_failures.log` |

**Limits.**
- Exp 10 and Exp 19 score enable-F1 on the draft call, which the tool stopped making on 2026-09-14
  (Exp 20). The single-pass row is the figure for the path users run today.
- Exp 10's `bare` column predates the 2026-07-15 alias fix; the corrected column comes from the raw logs
  in `results/raw/` through `reparse_bare_fix.py`. The script's Exp 4/7 and Exp 11 rows read
  `../../local_runs/`, on the development machine only.
- `run_parallel_eval.py` and `eval_factor_set.py` import `evaluate`, which moved to
  `vep_ai_demo/legacy/` on 2026-09-22. Neither starts until that import is updated.

Which model writes the review scenarios (Exp 12) is a separate choice: [`../generation/`](../generation/).
