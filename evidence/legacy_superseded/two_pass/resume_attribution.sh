#!/bin/bash
# The three attribution runs that did not complete on 2026-09-04.
#
#   bash evidence/legacy_superseded/two_pass/resume_attribution.sh https://<new>.trycloudflare.com
#
# Jobs 3 and 4 never ran that day (the tunnel returned HTTP 530). Job 2 failed on a real
# EmptyCompletionError: _MAX_TOKENS was 4096, sized for the shipped path where reasoning is off, and a
# reasoning model spends that whole budget thinking. Thinking calls now get 16384. THAT FIX IS
# UNTESTED, so this script proves it on one call before spending 45 minutes on the assumption.
set -u
URL="${1:?give the tunnel URL, e.g. https://foo.trycloudflare.com}"
cd "$(dirname "$0")/../../.." || exit 1
export OLLAMA_BASE_URL="${URL%/}/v1"
export VEP_OPTIONS_FILE=$PWD/vep_ai_demo/vep_options.json
export VEP_EXAMPLES_FILE=$PWD/work/preliminary_examples/simulated_gold_examples.json
PY=/opt/anaconda3/bin/python3
D=evidence/local_runs/results/colab_resume
export VEP_RESULTS_DIR=$PWD/$D/attribution
mkdir -p "$VEP_RESULTS_DIR"

echo "=== [$(date +%H:%M)] PRECHECK: does think=low return content at the raised cap? ==="
$PY - <<'EOF' || { echo "PRECHECK FAILED — not starting the long runs"; exit 1; }
import sys, json, time, urllib.request
sys.path.insert(0, "vep_ai_demo")
import vep_assistant as va, evaluate as ev
body = {"model": "gemma4:26b", "stream": False, "keep_alive": -1, "think": "low",
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "options": {"num_predict": ev._cap_for("low"), "temperature": 0.0, "seed": 42}}
req = urllib.request.Request(va._native_chat_url(), data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    m = json.loads(r.read().decode()).get("message", {})
c, th = m.get("content") or "", m.get("thinking") or ""
print(f"  cap={ev._cap_for('low')}  content={len(c)} chars  thinking={len(th)} chars  {time.time()-t:.0f}s")
if not c.strip():
    print("  STILL EMPTY -> the token cap was not the cause; do not run the arms yet")
    raise SystemExit(1)
print("  content returned -> the fix holds")
EOF

run () {  # name, testset, mode, think
  # --tag is the job name: jobs 1 and 3 are both `combined` on the same model, so without a tag
  # they would write the SAME {model}_{mode}.json and the second would overwrite the first.
  echo "=== [$(date +%H:%M)] $1 ==="
  VEP_TESTSET_FILE=$PWD/$2 $PY evidence/legacy_superseded/use_cases/run_attribution.py \
      --model gemma4:26b --queries 0 --mode "$3" --concurrency 1 --seed 42 --think "$4" \
      --tag "$1" \
      > "$D/$1.log" 2>&1
  echo "    exit $?  -> $D/$1.log"
}

run attr_combined_low evidence/legacy_superseded/use_cases/test_queries_sim.json combined low
run attr_examples_low evidence/legacy_superseded/use_cases/test_queries_sim.json examples low
run attr_6b_real      data/real_testset_8.json   combined off

echo "=== [$(date +%H:%M)] DONE ==="
ls -la "$VEP_RESULTS_DIR" 2>/dev/null
