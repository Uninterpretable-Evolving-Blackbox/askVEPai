#!/bin/bash
set -u
D=/Users/david/Desktop/GSoC_WORK/tools_local/vep_local
export PERL5LIB="$D/Bio-DB-HTS/blib/lib:$D/Bio-DB-HTS/blib/arch:$D/bioperl-live:$D/ensembl/modules:$D/ensembl-variation/modules:$D/ensembl-funcgen/modules:$D/ensembl-io/modules:$D/ensembl-vep/modules"
VEP_DIR="$D/ensembl-vep"; VEP_CACHE="$D/cache"
S=/tmp/claude-501/-Users-david-Desktop-GSoC-WORK/54e0841b-df8d-4f3a-ae66-cbe0b390c426/scratchpad
BASE=(--offline --cache --dir_cache "$VEP_CACHE" --assembly GRCh38
      --input_file "$S/cohort12.vcf" --format vcf --tab --force_overwrite --no_stats)
run () {
  local n="$1"; shift
  perl "$VEP_DIR/vep" "${BASE[@]}" --output_file "$S/r_$n.tsv" "$@" > "$S/r_$n.log" 2>&1
  if [ ! -s "$S/r_$n.tsv" ]; then printf "%-16s FAILED: %s\n" "$n" "$(grep -i error "$S/r_$n.log" | head -1)"; return; fi
  local v r c
  v=$(grep -v '^#' "$S/r_$n.tsv" | cut -f1 | sort -u | wc -l | tr -d ' ')
  r=$(grep -vc '^#' "$S/r_$n.tsv")
  c=$(grep -m1 '^#Uploaded' "$S/r_$n.tsv" | tr '\t' '\n' | wc -l | tr -d ' ')
  printf "%-16s variants %2s/12  rows %5s  cols %3s\n" "$n" "$v" "$r" "$c"
}
echo "--- ROW-AFFECTING (the four REST could not measure) ---"
run baseline
run coding_only  --coding_only
run most_severe  --most_severe
run pick         --pick
run per_gene     --per_gene
run summary      --summary
echo
echo "--- the five REST returns unasked, here switched OFF vs ON ---"
run cols_off
run sift_on      --sift b
run polyphen_on  --polyphen b
run symbol_on    --symbol
run biotype_on   --biotype
run clinvar_on   --check_existing
