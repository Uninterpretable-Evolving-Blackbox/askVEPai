# `work/` — GSoC deliverables, harness & data

GSoC work product built on top of the runnable demo (`../vep_ai_demo/`). The top-level
[`../README.md`](../README.md) is the project front door; this folder holds the expanded knowledge base,
the evaluation harness, and the experiment record.

> **Layout note:** scripts live flat at `work/` on purpose — the run-wrappers and each script's import
> logic (`Path(__file__).parents[1] / "vep_ai_demo"`) assume `work/<script>.py`. The logged, reproducible
> run commands depend on that.

## The experiment report

[`EXPERIMENTS.md`](EXPERIMENTS.md) — the detailed ledger of every experiment (1–9): protocol, rationale,
results, caveats, and provenance. **Start here for the science.**

## Evaluation harness (Python) + wrappers (shell)

| File | Purpose | Used by |
|---|---|---|
| `run_parallel_eval.py` | Parallel leave-one-out eval, 4 conditions (bare/keyword/all/semantic). | Exp 1, 3 |
| `run_example_sweep.py` | Corpus-size sweep (stratified subsample, N=2→19). | Exp 2 |
| `run_attribution.py` | Per-recommendation KB-faithfulness (occlusion ablation). | Exp 5, 6 |
| `run_order_sensitivity.py` | Example-ORDER sensitivity (N shuffles of a fixed set, greedy, mean±SD). | Exp 9 |
| `structured_pilot.py` | Structured-JSON-output feasibility pilot (negative result). | Exp 8 |
| `score_metrics.py` | Offline clinical metrics (critical-recall, category-cover) from raw logs. | Exp 3 |
| `rescore_offline.py` | Re-score logged responses with corrected parser/metrics (no GPU). | Exp 7 |
| `compute_run_sd.py` | Run-level mean ± SD across runs, re-parsed from logged responses. | README tables |
| `aggregate_results.py` | Cross-model crossover table from `results/`. | — |
| `assemble_catalogue.py` | Rebuild + validate `vep_options_expanded.json`. | catalogue |
| `run_experiment.sh` | Turnkey wrapper: 4-condition eval across models. | Exp 1 |
| `run_order_experiment.sh` | Wrapper for `run_order_sensitivity.py` on the 20-example set. | Exp 9 |
| `run_exp6.sh`, `run_exp6_seeds.sh` | Wrappers for the attribution runs. | Exp 6 |

All harness scripts honour the env vars `VEP_OPTIONS_FILE`, `VEP_EXAMPLES_FILE`, `VEP_TESTSET_FILE`,
`VEP_RESULTS_DIR`, `OLLAMA_BASE_URL`. Unset → the demo KB (26 options / 8 examples); set → the expanded
58-option catalogue + 20-example set. `run_experiment.sh` / `run_order_experiment.sh` set them for you.

## Data

| File / dir | Contents |
|---|---|
| `vep_options_expanded.json` | The 58-option VEP catalogue (source-grounded from Ensembl). |
| `id_migration.json` | demo(26) → expanded id map. |
| `preliminary_examples/` | `simulated_gold_examples.json` (20, the eval set) + `test_queries_sim.json`; `bootstrap_examples.json` (7) + `test_queries.json`; `real_queries_*` (Exp 6b); `validate_examples.py` (the data "tests"). |
| `output_schema/` | Structured JSON output design: JSON Schema + example + the field→web-form mapping rules. |

## Results

| Dir / file | Contents |
|---|---|
| `results/order_sensitivity_gemma4_26b.md` | Exp 9 (example-order sensitivity) report. |
| `results_fixedparser/evaluation_results_gemma4_26b_RESCORED.md` | The headline corrected eval (Exp 7). |
| `results_fixedparser/attribution/*.json` | Aggregated attribution results (Exp 5, 6). |

Bulky raw run logs (`*_raw.jsonl`, `results/raw/`) are git-ignored — they are regenerable from the logged
commands in `EXPERIMENTS.md`.

## Research & design proposals

| File | What it is |
|---|---|
| [`research/taxonomy_proposal.md`](research/taxonomy_proposal.md) | Factor-based use-case taxonomy (mentor review). |
| [`research/generation_pipeline_proposal.md`](research/generation_pipeline_proposal.md) | Literature-grounded gold-example generation pipeline (mentor data-generation plan). |

## Validate the data ("tests")

```bash
# 7 bootstrap examples against the 58-option catalogue + constraint checker (expect ALL PASS)
python work/preliminary_examples/validate_examples.py

# the 20-example simulated gold set
VEP_EXAMPLES_FILE=work/preliminary_examples/simulated_gold_examples.json \
  python work/preliminary_examples/validate_examples.py
```
