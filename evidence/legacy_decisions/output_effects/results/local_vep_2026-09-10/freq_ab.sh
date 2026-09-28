#!/bin/bash
set -u
cd /Users/david/Desktop/GSoC_WORK/tools_local/vep_local
D=/Users/david/Desktop/GSoC_WORK/tools_local/vep_local
# ENV.sh derives its own dir from $0, which is THIS script when sourced, so set the paths directly.
export PERL5LIB="$D/Bio-DB-HTS/blib/lib:$D/Bio-DB-HTS/blib/arch:$D/bioperl-live:$D/ensembl/modules:$D/ensembl-variation/modules:$D/ensembl-funcgen/modules:$D/ensembl-io/modules:$D/ensembl-vep/modules"
export VEP_DIR="$D/ensembl-vep"
export VEP_CACHE="$D/cache"
S=/tmp/claude-501/-Users-david-Desktop-GSoC-WORK/54e0841b-df8d-4f3a-ae66-cbe0b390c426/scratchpad
BASE=(--offline --cache --dir_cache "$VEP_CACHE" --assembly GRCh38
      --input_file "$S/cohort12.vcf" --format vcf --tab --force_overwrite --no_stats)
run () {
  local n="$1"; shift
  perl "$VEP_DIR/vep" "${BASE[@]}" --output_file "$S/f_$n.tsv" "$@" > "$S/f_$n.log" 2>&1
  if [ ! -s "$S/f_$n.tsv" ]; then printf "%-22s FAILED (see f_%s.log)\n" "$n" "$n"; return; fi
  local v r
  v=$(grep -v '^#' "$S/f_$n.tsv" | cut -f1 | sort -u | wc -l | tr -d ' ')
  r=$(grep -vc '^#' "$S/f_$n.tsv")
  printf "%-22s variants %2s/12   rows %5s\n" "$n" "$v" "$r"
}
FREQ=(--check_frequency --freq_filter exclude --freq_gt_lt gt --freq_freq 0.01)
run baseline
run 1KG_ALL "${FREQ[@]}" --freq_pop 1KG_ALL
run AF      "${FREQ[@]}" --freq_pop AF
run 1KG_AFR "${FREQ[@]}" --freq_pop 1KG_AFR
run gnomADe "${FREQ[@]}" --freq_pop gnomADe
run AA      "${FREQ[@]}" --freq_pop AA
