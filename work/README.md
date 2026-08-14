# `work/` — project map

Everything for Ask VEPai beyond the runnable demo. **Start with `STATUS.md` (the one-page "where are
we"), then `research/` for the design rationale.** This file is the directory map.

## The engine (one level up)

- **`../vep_ai_demo/`** — the **core engine**, not a throwaway demo despite the name: `vep_assistant.py`
  (retrieval, the `✓/✗ [source:]` parser, the constraint checker, structured-JSON assembler) and
  `evaluate.py`. **Everything in `work/` imports this.** It is a nested git repo with its own remote.

## Knowledge base & schema

- **`vep_options_expanded.json`** — the **65-option** catalogue (from Ensembl release/115). The system's
  factual grounding; consumed via the `VEP_OPTIONS_FILE` env var. (`EXPERIMENTS.md` reports runs against
  a 58-option cut of it and says so.)
- **`id_migration.json`** — id map from the demo's 26 options to the expanded catalogue.
- **`output_schema/`** — the click-to-apply JSON schema + a validated example + design doc.
- **`ensembl_source/`** — the real Ensembl `public-plugins` release/115 files (ground truth for the catalogue).

## Generation pipeline (build the gold data)

- **`generation/`** — the reproducible `(query → config)` example generator (Stages 0–6): sampler → resolver
  → query generator → gates → ICE screen → review export, plus `verify_pipeline.py` (**36** no-GPU checks,
  seconds) and `run_generation.sh`. Self-contained; see `generation/README.md`.
- **`generation/generation_config/factors.json`** — the factor scheme **the engine reads**. Cardinality
  (`select: single|multi`) and the hard-gate flags live here, not in code. Kept byte-identical to
  `../vep_ai_demo/factors.json`; edit one and copy it across.

## Experiment harness (evaluate)

- **`harness/`** — all the evaluation/experiment scripts (moved here from the top level):
  - `run_parallel_eval.py` — the main leave-one-out eval (bare/keyword/all/semantic conditions).
  - `score_metrics.py` — offline scorer (crit-recall, category-cover, over-rec) from raw logs.
  - `run_attribution.py` — the KB-faithfulness / attribution study (Exp 5–6).
  - `run_example_sweep.py`, `run_order_sensitivity.py` — corpus-size and example-order experiments.
  - `aggregate_results.py`, `compute_run_sd.py`, `rescore_offline.py` — aggregation / mean±SD / offline re-score.
  - `structured_pilot.py`, `assemble_catalogue.py` — structured-output pilot, catalogue builder.
  - `run_experiment.sh`, `run_exp6*.sh`, `run_order_experiment.sh` — turnkey drivers.
  - **What a question leaves unsaid** (the assume/ask policy — `research/reprompting_proposal.md`):
    - `try_reprompting.py` — meet the behaviour as a user would; `--why` for the audit view, `--factors`
      to skip the model entirely.
    - `ask_rate.py` — **how often the tool interrupts**, per candidate policy, on the same 78 clean
      ablations. No model, seconds. Reproduces the historical figures and refuses to run if it has
      drifted from what the engine actually does. Read this before arguing with an ask-rate number.
    - `defaults_evidence.py` — **why each guessed value is that value**, re-derived and asserted. The
      four defaults were chosen by four different methods (sweep · danger audit · ablation · judgement)
      and this keeps them apart and executable. A failure means a published number stopped matching the
      priority table, not necessarily that the code is wrong.
    - `ablate_queries.py` — builds the 124 ablations (78 clean) the two above are scored on.
    - `fetch_real_queries.py` — verbatim tracker fetch, per-body SHA-256, `--verify` re-fetch.
    - `measure_underspecification.py` — what real questions leave open. `--rescore` re-prints the
      headlines from the saved readings with no model, which is what makes the scoring rule arguable.
    - `test_user_context.py` — the 15 checks on stated context (species/origin/size/assembly) beating
      the classifier, and on the assembly gate surviving `restore_missing_critical`.

## Examples & evaluation set

- **`../generation/candidates/iced.json`** — **the evaluation set**: the 31 generated scenarios, keyed to
  the factor taxonomy and checker-clean by construction. `harness/eval_factor_set.py --set` runs the
  factor-keyed leave-one-out on this, and it is the set the review sheet was exported from.
- **`preliminary_examples/ablated_queries.json`** — the 124 controlled ablations (78 clean) built from
  those 31 by deleting one stated fact at a time. What `ask_rate.py` and `defaults_evidence.py` score on.
- **`preliminary_examples/simulated_gold_examples.json`** — **LEGACY** (23 examples on the abandoned
  7-use-case scheme). Kept, not deleted, because it is (a) the substrate of the historical experiments
  (`EXPERIMENTS.md`, Exp 1–13) and (b) still the generation pipeline's in-context corpus (`genlib.py`
  default).
- **`preliminary_examples/real_queries_fetched.json`** — 43 tracker issues pulled verbatim with a
  per-body SHA-256; 8 are configuration questions. `real_queries_biostars.json` beside it is
  **WITHDRAWN** and kept only so the correction stays on the record — do not cite it.
- Also under `preliminary_examples/`: the bootstrap set and `validate_examples.py`.

## Research & docs

- **`research/`** — the design proposals (`taxonomy_proposal.md`, `generation_pipeline_proposal.md`), the
  literature grounding (`LITERATURE.md`, `CITATION_VERIFICATION.md`), the model landscape, and the reading
  lists (`interp_reading/`, `systems_reading/`).
- **`webapp/`** — the web front-end (`app.py`).
- **Top-level docs:** `STATUS.md` (where the project stands) and `EXPERIMENTS.md` (the experiment
  ledger — every number, with the command that produced it).

## Outputs (git-ignored — regenerable)

- **`results/`, `results_fixedparser/`, `results_noex/`** — evaluation outputs per experiment. Written via
  `VEP_RESULTS_DIR`; not tracked in this repo.

## Running things (env-var contract)

Scripts select the KB/examples/results via env vars, so they work from anywhere:

```bash
VEP_OPTIONS_FILE=work/vep_options_expanded.json \
VEP_EXAMPLES_FILE=work/preliminary_examples/simulated_gold_examples.json \
python work/harness/run_parallel_eval.py --model gemma4:26b --runs 5 --concurrency 1
```
