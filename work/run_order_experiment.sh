#!/usr/bin/env bash
# Example-ORDER sensitivity experiment (see work/run_order_sensitivity.py).
# Reproduces Agarwal et al. 2024 §4.7 for our task: hold the example SET fixed,
# vary only the ORDER, report mean±SD of leave-one-out priority-weighted Enable F1
# ACROSS orderings.
#
# Uses the 20-example SIMULATED gold set (the larger set -> order can matter under
# all-examples). The set is synthetic -> results are directional, not a benchmark.
#
# Usage:
#   bash run_order_experiment.sh                              # gemma4:26b, all+semantic, 10 shuffles, greedy
#   bash run_order_experiment.sh "gemma4:26b" 10              # 1 model, 10 shuffles
#   bash run_order_experiment.sh "gemma4:12b gemma4:26b" 10 all,semantic 8
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"

export VEP_OPTIONS_FILE="$ROOT/work/vep_options_expanded.json"
export VEP_EXAMPLES_FILE="$ROOT/work/preliminary_examples/simulated_gold_examples.json"
export VEP_TESTSET_FILE="$ROOT/work/preliminary_examples/test_queries_sim.json"
export VEP_RESULTS_DIR="$ROOT/work/results"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434/v1}"

MODELS="${1:-gemma4:26b}"
SHUFFLES="${2:-10}"
CONDITIONS="${3:-all,semantic}"
SEMANTIC_TOPK="${4:-8}"
CONCURRENCY="${CONCURRENCY:-4}"

# ---------------- preflight (fail fast) ----------------
echo "── Preflight ──────────────────────────────────────────────"
fail=0
if curl -s "${OLLAMA_BASE_URL%/v1}/api/version" >/dev/null 2>&1; then
  echo "✓ Ollama reachable: $(curl -s "${OLLAMA_BASE_URL%/v1}/api/version")"
else
  echo "✗ Ollama not reachable on :11434 — start the official Ollama app (or 'ollama serve')."; fail=1
fi
for f in "$VEP_OPTIONS_FILE" "$VEP_EXAMPLES_FILE" "$VEP_TESTSET_FILE"; do
  [ -f "$f" ] && echo "✓ $(basename "$f")" || { echo "✗ missing $f"; fail=1; }
done
[ "$fail" -eq 0 ] || { echo "── Preflight FAILED — fix the above, then re-run. ──"; exit 1; }
echo

echo "Order-sensitivity experiment (greedy, LLM seed fixed; only example ORDER varies)"
echo "Example set: 20 SIMULATED gold (leave-one-out -> 19 shown for all-examples)"
echo "Models     : $MODELS"
echo "Shuffles   : $SHUFFLES   Conditions: $CONDITIONS   semantic top-k: $SEMANTIC_TOPK"
echo "Results -> $VEP_RESULTS_DIR/order_sensitivity_*.md"
echo

for m in $MODELS; do
  echo "==================== $m ===================="
  ollama pull "$m"
  "$PY" "$ROOT/work/run_order_sensitivity.py" \
      --model "$m" \
      --conditions "$CONDITIONS" \
      --shuffles "$SHUFFLES" \
      --semantic-topk "$SEMANTIC_TOPK" \
      --temperature 0.0 \
      --concurrency "$CONCURRENCY"
  echo
done
echo "Done. Reports: $VEP_RESULTS_DIR/order_sensitivity_*.md"
