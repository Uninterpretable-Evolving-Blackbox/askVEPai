#!/bin/bash
# Experiment 6 — SEED-ROBUSTNESS replication (overnight, unattended).
#
# WHY: Exp 6 ran at a single seed (42). The per-recommendation metric is deterministic *given a seed*
# (concurrency=1), so the principled way to get a mean +/- SD (discipline rule 4) is to re-run at
# additional seeds — the variation comes from the seed, not from sampling. This run adds seeds 123 and 7
# so every Exp 6 number (combined / description / examples / real) becomes a 3-seed estimate, and tells
# us whether the headline 79% is robust to the arbitrary seed choice or an artefact of seed 42.
#
# ORDER = by value, for graceful degradation if the machine is reclaimed early:
#   headline (combined + real) at both extra seeds FIRST, then the decomposition (description/examples).
# RESILIENT: no `set -e` — a failed phase is logged and the run continues; each phase writes its own
# tagged output file, so partial completion still yields usable, non-overwritten results.
#
# PRECONDITION: the native arm64 Ollama server must already be running (this script does not manage it).
# Determinism REQUIRES --concurrency 1 (see EXPERIMENTS.md Exp 6 / run_attribution.py docstring).

ROOT=/Users/davidgao/Desktop/GSoC_WORK
cd "$ROOT/vep_ai_demo"
export VEP_OPTIONS_FILE="$ROOT/work/vep_options_expanded.json"
export VEP_EXAMPLES_FILE="$ROOT/work/preliminary_examples/simulated_gold_examples.json"
export VEP_RESULTS_DIR="$ROOT/work/results_fixedparser"
export OLLAMA_BASE_URL="http://localhost:11434/v1"
SYN="$ROOT/work/preliminary_examples/test_queries_sim.json"     # 20 synthetic LOO queries
REAL="$ROOT/work/preliminary_examples/real_queries_biostars.json"  # 20 real forum queries (no LOO)
M=gemma4:26b

run() { # args: <mode> <seed> <testset> <tag>
  echo "===== phase mode=$1 seed=$2 tag=$4 $(date) ====="
  VEP_TESTSET_FILE="$3" python3 -u "$ROOT/work/harness/run_attribution.py" \
    --model "$M" --queries 0 --mode "$1" --concurrency 1 --seed "$2" --tag "$4" \
    || echo "!!! PHASE FAILED mode=$1 seed=$2 $(date)"
}

echo "##### EXP6 SEED-ROBUSTNESS START $(date) #####"
# --- headline first: combined + real at both extra seeds (-> 3-seed headline incl. existing seed 42) ---
run combined 123 "$SYN"  s123
run combined 123 "$REAL" real_s123      # real-query generalization is combined-mode only
run combined 7   "$SYN"  s7
run combined 7   "$REAL" real_s7
# --- then decomposition robustness (description / examples) at the extra seeds ---
run description 123 "$SYN" s123
run examples    123 "$SYN" s123
run description 7   "$SYN" s7
run examples    7   "$SYN" s7
echo "##### EXP6 SEED-ROBUSTNESS DONE $(date) #####"
