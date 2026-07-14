# `work/` — project map

GSoC work built on top of the runnable engine in [`../vep_ai_demo/`](../vep_ai_demo/). The top-level
[`../README.md`](../README.md) is the front door; this folder holds the expanded knowledge base, the
evaluation harness, the experiment record, and the research/design docs. This file is the directory map.

## The engine (one level up)

- **`../vep_ai_demo/`** — the core engine, not a throwaway demo despite the name: `vep_assistant.py`
  (retrieval, the `✓/✗ [source:]` parser, the constraint checker, the structured-JSON assembler) and
  `evaluate.py`. Everything in `work/` imports this.

## Knowledge base & schema

- **`vep_options_expanded.json`** — the 58-option catalogue (from Ensembl release/115), the system's factual
  grounding; consumed via the `VEP_OPTIONS_FILE` env var.
- **`id_migration.json`** — id map from the demo's 26 options to the expanded 58.
- **`output_schema/`** — the click-to-apply JSON schema + a validated example + design doc.

## Experiment harness

- **`harness/`** — all the evaluation/experiment scripts:
  - `run_parallel_eval.py` — the main leave-one-out eval (bare / keyword / all-examples / semantic).
  - `score_metrics.py` — offline scorer (critical-recall, category-cover, over-recommendation) from raw logs.
  - `run_attribution.py` — the KB-faithfulness / attribution study.
  - `run_example_sweep.py`, `run_order_sensitivity.py` — corpus-size and example-order experiments.
  - `aggregate_results.py`, `compute_run_sd.py`, `rescore_offline.py` — aggregation / mean±SD / offline re-score.
  - `structured_pilot.py`, `assemble_catalogue.py` — structured-output pilot and the catalogue builder.
  - `run_experiment.sh`, `run_exp6*.sh`, `run_order_experiment.sh` — turnkey drivers.

## Examples & evaluation set

- **`preliminary_examples/silver_reference_set.json`** — the current reference set: 30 examples keyed to the
  factor taxonomy, documentation-grounded and checker-clean, each query verified to express its factors (with
  `silver_reference_review.csv` for markup and `SILVER_REFERENCE_README.md`). Awaiting validation → gold; the
  factor-keyed leave-one-out evaluation runs on this.
- **`preliminary_examples/simulated_gold_examples.json`** — legacy (23 examples on the earlier 7-use-case
  scheme). Kept, not deleted: it is the substrate of the historical experiments (`EXPERIMENTS.md`) and the
  generation pipeline's in-context corpus. Superseded *for evaluation* by the silver set above.
- Also: the bootstrap set, real-forum-query sets, and `validate_examples.py`.

## Research & docs

- **`research/`** — the design proposals (`taxonomy_proposal.md`, `generation_pipeline_proposal.md`) and the
  model landscape.
- **`EXPERIMENTS.md`** — the full experiment ledger.

## Outputs (git-ignored — regenerable)

- **`results/`, `results_fixedparser/`, `results_noex/`** — evaluation outputs, written via `VEP_RESULTS_DIR`.

## Running things (env-var contract)

Scripts select the knowledge base / examples / results via env vars, so they work from anywhere:

```bash
VEP_OPTIONS_FILE=work/vep_options_expanded.json \
VEP_EXAMPLES_FILE=work/preliminary_examples/simulated_gold_examples.json \
python work/harness/run_parallel_eval.py --model gemma4:26b --runs 5 --concurrency 1
```
