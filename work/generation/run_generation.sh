#!/usr/bin/env bash
# Turnkey driver for the gold-example generation pipeline (Stages 0-6; Stage 7 Web-VEP is out of scope).
# Wires the VEP_* env vars to the expanded catalogue + simulated corpus and runs the stages in order.
#
#   bash work/generation/run_generation.sh [N] [MODEL] [SEED] [FACTOR_MODEL]
# e.g.
#   bash work/generation/run_generation.sh 6 gemma4:26b 42
#
# The SEED is for REPRODUCIBILITY, not statistics: this produces a deliverable (a review set), not an
# experiment, so there is nothing to average over and one seeded run is the whole job. Multi-seed belongs
# to the ablations (teacher_sweep.py / persona_ablation.py), which measure a difference.
#
# FACTOR_MODEL is the query<->factor round-trip checker and defaults to a model DIFFERENT from the teacher:
# the teacher wrote the query, so letting it also certify that the query expresses the factors is
# self-checking. filter_candidates.py's --factor-model help requires a cross-check, so the driver passes
# a different model here by default.
#
# Requires a local Ollama server running with the model pulled.
set -euo pipefail

# N = distinct balanced factor cells. 31 gives all factor floors >=15 after the SV exclusions; the
# coverage top-up (--cover) then adds ~11 distinct rows to bring every priced option to >=8. Net ~42
# distinct rows — no duplicate configs.
N="${1:-31}"
MODEL="${2:-gemma4:26b}"
SEED="${3:-42}"
FACTOR_MODEL="${4:-gemma4:12b}"

if [ "$FACTOR_MODEL" = "$MODEL" ]; then
    echo "WARNING: factor-checker == teacher ($MODEL) — the query round-trip is self-checking." >&2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/work/generation"
export VEP_OPTIONS_FILE="$ROOT/work/vep_options_expanded.json"
export VEP_EXAMPLES_FILE="$ROOT/work/preliminary_examples/simulated_gold_examples.json"
# Pin hash seed so set-iteration order (hence any diagnostic path) is bit-reproducible across runs.
# (The emitted configs are already order-independent; this stabilises the diagnostics too.)
export PYTHONHASHSEED=0
cd "$GEN"
mkdir -p candidates

echo "### Stage 0 — seed provisional priority_by_factor.json"
python seed_priorities.py

echo; echo "### Stage 1 — sample factor tuples (N=$N balanced, seed=$SEED)"
# COVER (the option-coverage top-up) is OFF by default. It seemed principled — "exercise every priced
# option >=K times so the mentor can validate its priority" — but it was measured to add NO validation
# value: the unit the mentor validates is the (option x factor-value) CELL, and the balanced draw alone
# already covers 60 of 61 priced cells (the 61st is unreachable). The top-up added 11 rows and 0 new cells
# — pure redundancy (same option, same tier, already-covered context), +35% review burden, and a
# human/coding/clinical distribution tilt. Set COVER=8 to re-enable if you specifically want repeated
# looks at contentious options; otherwise the balanced draw is the honest set.
python sample_factors.py --n "$N" --seed "$SEED" --cover "${COVER:-0}" --out candidates/tuples.json

echo; echo "### Stage 2 — resolve deterministic configs"
python resolve_config.py --tuples candidates/tuples.json --out candidates/resolved.json

echo; echo "### Stage 3 — generate natural-language queries (teacher=$MODEL)"
python generate_queries.py --in candidates/resolved.json --out candidates/queried.json \
    --model "$MODEL" --seed "$SEED" --concurrency 1

echo; echo "### Stage 4 — automated gates (+ LLM judge; factor round-trip cross-checked by $FACTOR_MODEL)"
python filter_candidates.py --in candidates/queried.json --out candidates/filtered.json \
    --judge-model "$MODEL" --factor-model "$FACTOR_MODEL"

echo; echo "### Stage 5 — ICE usefulness screen (student=$MODEL)"
python ice_screen.py --in candidates/filtered.json --out candidates/iced.json --student "$MODEL" --seed "$SEED"

echo; echo "### Stage 6 — export review queue + provenance"
python export_for_review.py --in candidates/iced.json --outdir candidates/review

echo; echo "Done. Review candidates in work/generation/candidates/review/ (all PENDING, provisional config)."
