#!/bin/zsh
export NO_PROXY=localhost,127.0.0.1
cd /Users/david/Desktop/GSoC_WORK
OUT=work/results/overnight_2026-09-10
until grep -q 'FOLLOWUP DONE' $OUT/queue.log; do sleep 30; done
echo "\n##### $(date '+%F %T')  7 probe e2b failures" | tee -a $OUT/queue.log
python3 -u $OUT/probe_e2b_failures.py > $OUT/probe_e2b_failures.log 2>&1
echo "\n##### $(date '+%F %T')  PROBE DONE" | tee -a $OUT/queue.log
