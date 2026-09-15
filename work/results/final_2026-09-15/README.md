# Final runs on the table as of 2026-09-15

**Results** (26b local; sets seeded, timings NOT representative — see below):

| run | result |
|---|---|
| four-arm ablation, plain F1 with form defaults excluded on both sides | single **0.858**, two_23 0.840, two_31loo 0.830, two_none 0.829 |
| class-weighted F1 (`harness/class_weighted_f1.py`) | single **0.900**, two_23 0.862, two_31loo 0.836, two_none 0.842; row-deleting extras 0 / 5 / 7 / 7 |
| factor accuracy, 3 seeds | species 31 (rule) · origin 28 · size 30 · region 31 · goal 24 · **exact 21/31** · e2e F1 **0.970 ± 0.000** |
| fallback end to end, 78 pure ablations | 76/78 disclosed; the same two cue-carrying rows as 2026-09-14 |
| 31-row single vs two | single ⊆ two **31/31 at the option level** (harness prints 30/31: the type-grouped predictor line differs in membership, a rendering artifact); draft adds 1.2/row: nmd ×5, uniprot ×3, frequency ×2, coding_only ×2 |

**Timing anomaly.** The queue ran 00:25 → 11:29 for what took ~45 minutes on 2026-09-09/10; mean
latency came out 41.9 s (two-pass) and 2.1 s (single) against 17.9 / 1.2 s four days earlier on the
same machine. Something contended for the GPU overnight. Every set is seeded at temperature 0 and stands;
do not quote these latencies.

## The exact queue

Launched 00:25 BST, sequential, gemma4:26b local (Ollama 0.33.3, M5 Max), context 16384, seed 42 / temp 0.
Plain F1 in the four-arm ablation now EXCLUDES the form's 16 ticked-by-default options on both sides (see EXPERIMENTS.md Exp 20).

```bash
#!/bin/bash
cd /Users/david/Desktop/GSoC_WORK
export NO_PROXY=localhost,127.0.0.1 VEP_ALLOW_LOCAL_MODEL=1 OLLAMA_BASE_URL=http://localhost:11434/v1 PYTHONHASHSEED=0
R=work/results/final_2026-09-15
echo "START $(date)" > $R/queue.log
echo "== four-arm pass x corpus ablation, 26b, final table ==" >> $R/queue.log
python3 -u work/harness/pass_and_corpus_ablation.py --model gemma4:26b --json $R/pass_corpus_ablation_26b.json > $R/pass_corpus_ablation_26b.log 2>&1; echo "ablation done $(date) exit=$?" >> $R/queue.log
echo "== factor accuracy, 3 seeds ==" >> $R/queue.log
python3 -u work/harness/factor_accuracy.py --model gemma4:26b --seeds 42,43,44 --json $R/factor_accuracy_26b.json > $R/factor_accuracy_26b.log 2>&1; echo "factor_accuracy done $(date) exit=$?" >> $R/queue.log
echo "== fallback e2e, 78 pure ablations ==" >> $R/queue.log
python3 -u work/harness/fallback_e2e.py --model gemma4:26b --json $R/fallback_e2e_26b.json > $R/fallback_e2e_26b.log 2>&1; echo "fallback done $(date) exit=$?" >> $R/queue.log
echo "== 31-row single vs two ==" >> $R/queue.log
python3 -u work/harness/singlepass_vs_twopass.py --model gemma4:26b --json $R/singlepass_vs_twopass_26b.json > $R/singlepass_vs_twopass_26b.log 2>&1; echo "svt done $(date) exit=$?" >> $R/queue.log
echo "ALL DONE $(date)" >> $R/queue.log
```
