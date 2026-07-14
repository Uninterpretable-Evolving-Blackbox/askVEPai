#!/usr/bin/env bash
# Fire the real-project experiment: expanded 58-option catalogue + bootstrap
# examples (leave-one-out), 4 retrieval conditions (bare / keyword / all-examples
# / semantic), multi-run mean±SD, across model sizes.
#
# Requires a WORKING Ollama with its inference runner + (ideally) Metal GPU —
# i.e. the official app from ollama.com, NOT a partial Homebrew bottle.
#
# Usage:
#   bash run_experiment.sh                          # default: gemma4 e4b/12b/26b, 3 runs
#   bash run_experiment.sh "gemma4:e4b" 1           # quick smoke test (1 model, 1 run)
#   bash run_experiment.sh "gemma4:e4b gemma4:12b gemma4:26b qwen2.5:7b" 3
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO="$ROOT/vep_ai_demo"
PY="${PYTHON:-python3}"

export VEP_OPTIONS_FILE="$ROOT/work/vep_options_expanded.json"
export VEP_EXAMPLES_FILE="$ROOT/work/preliminary_examples/bootstrap_examples.json"
export VEP_TESTSET_FILE="$ROOT/work/preliminary_examples/test_queries.json"
export VEP_RESULTS_DIR="$ROOT/work/results"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434/v1}"

MODELS="${1:-gemma4:e4b gemma4:12b gemma4:26b}"
RUNS="${2:-3}"

# ---------------- preflight (fail fast before any long run) ----------------
echo "── Preflight ──────────────────────────────────────────────"
fail=0
if curl -s "${OLLAMA_BASE_URL%/v1}/api/version" >/dev/null 2>&1; then
  echo "✓ Ollama reachable: $(curl -s "${OLLAMA_BASE_URL%/v1}/api/version")"
else
  echo "✗ Ollama not reachable on :11434 — start the official Ollama app (or 'ollama serve')."; fail=1
fi
"$PY" - <<'PY' || fail=1
import importlib.util as u, sys
miss=[m for m in ("openai","sentence_transformers") if u.find_spec(m) is None]
print("✗ missing python modules: "+", ".join(miss)) if miss else print("✓ python deps: openai, sentence-transformers")
sys.exit(1 if miss else 0)
PY
for f in "$VEP_OPTIONS_FILE" "$VEP_EXAMPLES_FILE" "$VEP_TESTSET_FILE"; do
  [ -f "$f" ] && echo "✓ $(basename "$f")" || { echo "✗ missing $f"; fail=1; }
done
[ "$fail" -eq 0 ] || { echo "── Preflight FAILED — fix the above, then re-run. ──"; exit 1; }
echo "Tip: a quick 'ollama run gemma4:e4b \"hi\"' should be fast (>30 tok/s) on Metal;"
echo "     if it's ~10 tok/s you're on CPU and 26B will be very slow."
echo

echo "Catalogue : 58 options   Examples: 7 bootstrap (leave-one-out)"
echo "Models    : $MODELS"
echo "Runs      : $RUNS   Conditions: bare / keyword / all-examples / semantic"
echo "Calls/model: 7 queries × 4 conditions × $RUNS runs = $((7*4*RUNS))"
echo "Results -> $VEP_RESULTS_DIR"
echo

cd "$DEMO"
for m in $MODELS; do
  echo "==================== $m ===================="
  ollama pull "$m"
  "$PY" evaluate.py --model "$m" --semantic --all-examples --runs "$RUNS"
  echo
done
echo "Done. Reports: $VEP_RESULTS_DIR/evaluation_results_*.md"
