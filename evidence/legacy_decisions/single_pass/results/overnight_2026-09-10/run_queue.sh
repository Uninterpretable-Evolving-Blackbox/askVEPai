#!/bin/zsh
# Overnight queue, 2026-09-10. Sequential on purpose: temp-0 determinism holds only at concurrency 1.
# Apple M5 Max 128 GB, Ollama local, OLLAMA_CONTEXT_LENGTH=16384 (checked via launchctl at 22:55).
export NO_PROXY=localhost,127.0.0.1
cd /Users/david/Desktop/GSoC_WORK
OUT=work/results/overnight_2026-09-10
H=work/harness
step() { echo "\n##### $(date '+%F %T')  $1" | tee -a $OUT/queue.log; }

# 1. Repeat the four-arm ablation twice more on 26b. The draft call sets no seed or temperature
#    (stream_response), so repeats measure the SHIPPED path's own spread; the single arm is fixed-seed.
step "1a four-arm ablation, 26b, repeat 2"
python3 -u $H/pass_and_corpus_ablation.py --model gemma4:26b --json $OUT/pass_corpus_ablation_26b_rep2.json > $OUT/pass_corpus_ablation_26b_rep2.log 2>&1
step "1b four-arm ablation, 26b, repeat 3"
python3 -u $H/pass_and_corpus_ablation.py --model gemma4:26b --json $OUT/pass_corpus_ablation_26b_rep3.json > $OUT/pass_corpus_ablation_26b_rep3.log 2>&1

# 2. Rules vs model vs hinted, per factor, 26b.
step "2 rules_vs_model, 26b"
python3 -u $H/rules_vs_model.py --model gemma4:26b --json $OUT/rules_vs_model_26b.json > $OUT/rules_vs_model_26b.log 2>&1

# 3. Single-pass ladder: factor accuracy + e2e F1 + species + single-vs-two, e4b then e2b.
for M in gemma4:e4b gemma4:e2b; do
  T=${M#gemma4:}
  step "3 full_eval_singlepass, $M"
  python3 -u $H/full_eval_singlepass.py --model $M --seeds 42,43,44 --json $OUT/singlepass_eval_$T.json > $OUT/singlepass_eval_$T.log 2>&1
  step "3 singlepass_vs_twopass, $M"
  python3 -u $H/singlepass_vs_twopass.py --model $M --json $OUT/singlepass_vs_twopass_$T.json > $OUT/singlepass_vs_twopass_$T.log 2>&1
done

# 4. Four-arm ablation on e4b: does one pass help the laptop model as much as the big one?
step "4 four-arm ablation, e4b"
python3 -u $H/pass_and_corpus_ablation.py --model gemma4:e4b --json $OUT/pass_corpus_ablation_e4b.json > $OUT/pass_corpus_ablation_e4b.log 2>&1

# 5. Rules vs model on e4b, so the hint arm is priced on the laptop rung too.
step "5 rules_vs_model, e4b"
python3 -u $H/rules_vs_model.py --model gemma4:e4b --json $OUT/rules_vs_model_e4b.json > $OUT/rules_vs_model_e4b.log 2>&1

step "QUEUE DONE"
