#!/bin/zsh
# Follow-up to run_queue.sh: waits for QUEUE DONE, then the species arm suggested by the general
# session (species-removed rewrites, rule vs model vs hinted). Separate file so the live queue is
# never edited while zsh is reading it.
export NO_PROXY=localhost,127.0.0.1
cd /Users/david/Desktop/GSoC_WORK
OUT=work/results/overnight_2026-09-10
H=work/harness
step() { echo "\n##### $(date '+%F %T')  $1" | tee -a $OUT/queue.log; }

until grep -q 'QUEUE DONE' $OUT/queue.log; do sleep 30; done

step "6a species_rule_vs_model smoke, 26b, 2 rows"
python3 -u $H/species_rule_vs_model.py --model gemma4:26b --limit 2 --json $OUT/species_smoke.json > $OUT/species_smoke.log 2>&1
step "6b species_rule_vs_model, 26b"
python3 -u $H/species_rule_vs_model.py --model gemma4:26b --json $OUT/species_rule_vs_model_26b.json > $OUT/species_rule_vs_model_26b.log 2>&1
step "6c species_rule_vs_model, e4b"
python3 -u $H/species_rule_vs_model.py --model gemma4:e4b --json $OUT/species_rule_vs_model_e4b.json > $OUT/species_rule_vs_model_e4b.log 2>&1

step "FOLLOWUP DONE"
