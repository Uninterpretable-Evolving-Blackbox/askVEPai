#!/bin/bash
# Experiment 6 — attribution decomposition (6a) + real-query generalization (6b).
# Determinism: concurrency=1 + fixed seed (batched inference is non-deterministic even at temp=0).
set -euo pipefail
ROOT=/Users/davidgao/Desktop/GSoC_WORK
cd "$ROOT/vep_ai_demo"
export VEP_OPTIONS_FILE="$ROOT/work/vep_options_expanded.json"
export VEP_EXAMPLES_FILE="$ROOT/work/preliminary_examples/simulated_gold_examples.json"
export VEP_RESULTS_DIR="$ROOT/work/results_fixedparser"
export OLLAMA_BASE_URL="http://localhost:11434/v1"
SEED=42; CC=1; M=gemma4:26b
ADIR="$VEP_RESULTS_DIR/attribution"
mkdir -p "$ADIR"
# preserve the noisy concurrency-4 pilot before combined-20 overwrites it
[ -f "$ADIR/gemma4_26b_combined.json" ] && cp "$ADIR/gemma4_26b_combined.json" "$ADIR/gemma4_26b_combined_pilot7_cc4.json" || true

echo "===== EXP6 START $(date) seed=$SEED concurrency=$CC ====="

# 6a — KB-component decomposition on the full 20-query simulated set (LOO), three ablation modes.
export VEP_TESTSET_FILE="$ROOT/work/preliminary_examples/test_queries_sim.json"
for MODE in combined description examples; do
  echo "===== 6a ${MODE}-20 $(date) ====="
  python3 -u "$ROOT/work/run_attribution.py" --model $M --queries 0 --mode $MODE --concurrency $CC --seed $SEED
done

# 6b — real-query generalization (no LOO; gold-free metric), combined mode only.
export VEP_TESTSET_FILE="$ROOT/work/preliminary_examples/real_queries_biostars.json"
echo "===== 6b real-combined $(date) ====="
python3 -u "$ROOT/work/run_attribution.py" --model $M --queries 0 --mode combined --concurrency $CC --seed $SEED --tag real

echo "===== EXP6 DONE $(date) ====="
