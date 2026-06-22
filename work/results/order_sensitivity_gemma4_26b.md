# Example-Order Sensitivity Experiment

- **Model:** `gemma4:26b`
- **KB:** 20 examples / 58 options (leave-one-out; scored example never in prompt)
- **Test queries:** 20
- **Orderings:** 10 random shuffles (seeds 0..9) + 1 natural/default order
- **Conditions:** all, semantic (semantic top-k=8)
- **Decoding:** temperature=0.0, runs/ordering=1, LLM seed=42 (held FIXED across orderings)
- **Headline metric:** priority-weighted Enable F1 (`enable_f1_weighted`), leave-one-out, averaged over the 20 queries.

> One ordering = one data point. The spread (SD / min-max) ACROSS orderings is the order-sensitivity result. The set of examples is held fixed; only their order varies. The 20-example gold set is SIMULATED -> directional, not a benchmark.

## Summary: variability across orderings

| Condition | Metric | mean | SD | min | max | range | default |
|---|---|---|---|---|---|---|---|
| all | enable_f1_weighted | 87.7% | 1.6% | 84.6% | 90.6% | 6.0% | 87.6% |
| all | enable_recall_weighted | 93.3% | 2.8% | 87.2% | 95.7% | 8.5% | 95.4% |
| all | enable_f1 | 85.3% | 1.5% | 83.1% | 88.5% | 5.4% | 84.2% |
| semantic | enable_f1_weighted | 60.0% | 6.9% | 48.8% | 68.7% | 19.9% | 54.4% |
| semantic | enable_recall_weighted | 55.9% | 8.5% | 42.2% | 69.1% | 27.0% | 48.7% |
| semantic | enable_f1 | 56.8% | 7.1% | 45.6% | 65.7% | 20.1% | 50.9% |

## Per-ordering detail: `all`

| ordering | enable_f1_weighted | enable_recall_weighted | enable_f1 |
|---|---|---|---|
| default | 87.6% | 95.4% | 84.2% |
| s0 | 88.4% | 95.1% | 85.8% |
| s1 | 87.3% | 94.6% | 85.0% |
| s2 | 86.3% | 95.3% | 83.2% |
| s3 | 87.1% | 91.5% | 85.7% |
| s4 | 88.3% | 95.0% | 85.7% |
| s5 | 87.5% | 92.2% | 85.6% |
| s6 | 90.6% | 95.7% | 88.5% |
| s7 | 87.8% | 90.8% | 85.1% |
| s8 | 84.6% | 87.2% | 83.1% |
| s9 | 89.4% | 95.7% | 85.3% |

## Per-ordering detail: `semantic`

| ordering | enable_f1_weighted | enable_recall_weighted | enable_f1 |
|---|---|---|---|
| default | 54.4% | 48.7% | 50.9% |
| s0 | 68.7% | 66.9% | 65.7% |
| s1 | 57.8% | 53.2% | 54.9% |
| s2 | 65.9% | 60.9% | 63.5% |
| s3 | 48.8% | 42.2% | 45.6% |
| s4 | 63.2% | 57.3% | 59.5% |
| s5 | 52.5% | 48.0% | 48.8% |
| s6 | 68.6% | 69.1% | 65.3% |
| s7 | 61.3% | 59.0% | 57.7% |
| s8 | 59.7% | 53.9% | 57.0% |
| s9 | 53.5% | 48.3% | 49.6% |

## How to read this

- **Small SD / range (e.g. within +-1-2% Enable F1):** order is not a major lever for this pipeline; the fixed file order is fine and the standard `--runs` decoding-noise SD already bounds it.
- **Large SD / range:** order matters (the paper's §4.7 finding reproduces here). Pin a canonical order in the protocol and treat order as a logged variable; consider reporting results as mean +- SD over orderings, not a single run.
- **Comparing `all` vs `semantic`:** they show different NUMBERS of examples (19 LOO vs top-8), so a difference in SD reflects BOTH count and retrieval, not order alone -- interpret as 'order sensitivity of each condition as configured', not a controlled count comparison.