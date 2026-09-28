#!/usr/bin/env bash
# Sloppy, realistic queries for poking the system by hand.
#
# Each block is: what it SHOULD read, then the query. Run the whole file, or copy one line.
# Expected values are what a careful reader would say -- where a factor is genuinely unstated the
# note says "unstated -> assumed X", because that is the tool exercising its assume policy, not a miss.
#
#   bash evidence/legacy_decisions/missing_facts/try_queries.sh            # all of them
#   bash evidence/legacy_decisions/missing_facts/try_queries.sh 7          # just number 7
#
# Origin note: nothing said about origin means the tool ASSUMES somatic (the danger-audit default),
# so a query that never mentions tumour or inheritance should read somatic, not germline.

cd "$(dirname "$0")/../../../vep_ai_demo" || exit 1
export NO_PROXY=localhost,127.0.0.1
export VEP_MODEL=gemma4:26b VEP_FACTOR_MODEL=gemma4:26b

Q=()
E=()

# ---------- APPARENT: everything stated plainly. Controls. --------------------------------------
E+=("species=human  origin=germline  size=small  region=coding  goal=clinical-interpretation")
Q+=("Human germline exome, SNVs and indels in coding regions, GRCh38. I need pathogenicity assessment for a rare disease diagnosis.")

E+=("species=human  origin=somatic  size=structural-CNV  region=coding  goal=clinical-interpretation")
Q+=("Somatic structural variants and CNVs from a human tumour biopsy, protein-coding impact, looking for drivers.")

E+=("species=non-human  origin=germline  size=small  region=regulatory-noncoding  goal=basic-consequence")
Q+=("Mouse germline SNVs and short indels in enhancers and promoters, I just want the regulatory consequences.")

# ---------- NOT APPARENT: the facts are there but buried in ordinary prose -----------------------
E+=("species=non-human  origin=somatic  size=small  region=coding  goal=basic-consequence      [the sample IS the mouse tissue]")
Q+=("hey so i got some vcf back from our mouse experiment, its the tumour tissue not the normal, theres like snps and a few small indels, i just wanna know what genes theyre in and whether they break the protein")

E+=("species=human  origin=germline  size=small  region=coding  goal=population-frequency      [\"how common\" is the goal]")
Q+=("my supervisor wants to know how common these are in the general population before we take it further. theyre from a patient exome, single base changes in exons")

E+=("species=human  origin=germline  size=structural-CNV  region=coding  goal=basic-consequence      [spanning several exons = SV]")
Q+=("we have blood samples from a family, the changes are big deletions and duplications spanning several exons, inherited through the mother. what do they actually do")

E+=("species=human  origin=somatic  size=small+structural-CNV  region=UNSTATED->both  goal=clinical-interpretation      [two runs]")
Q+=("human tumour sample, we've got both the small mutations and some large copy number changes in the same callset, need to work out whats driving it")

E+=("species=non-human  origin=UNSTATED->somatic  size=small  region=coding  goal=basic-consequence")
Q+=("so we sequenced a bunch of zebra finches for a behaviour study and got a load of snvs, wanna see which ones land in protein coding stuff")

# ---------- TRAPS: a keyword fires and is wrong ---------------------------------------------------
E+=("species=human  origin=germline  size=UNSTATED->both  region=regulatory-noncoding  goal=UNSTATED->basic-consequence      [\"rabbit hole\" is an idiom]")
Q+=("ok so we went down a bit of a rabbit hole with this one but its just human wgs, germline, and were mostly interested in promoters and enhancers")

E+=("species=human  origin=germline  size=small  region=coding  goal=clinical-interpretation      [\"guinea pig\" is an idiom]")
Q+=("i got used as a guinea pig for the new pipeline lol. anyway its human blood, inherited variants, coding snvs, want clinvar and predictions")

E+=("species=human  origin=germline  size=small  region=coding  goal=clinical-interpretation      [\"mouse\" is negated]")
Q+=("not a mouse study btw, its human. coding snvs, germline, i want to check clinvar and the pathogenicity scores")

E+=("species=human  origin=UNSTATED->somatic  size=small  region=coding  goal=UNSTATED->basic-consequence      [Salmon is the tool]")
Q+=("we ran salmon first for the expression side, but now i need the exome coding snvs annotated, human, from patients")

E+=("species=human  origin=germline  size=small  region=coding  goal=clinical-interpretation      [CNVs negated]")
Q+=("no cnvs or svs were called on this one, its snvs and indels only, human germline exome, coding, clinical interpretation please")

E+=("species=human  origin=germline  size=small  region=coding  goal=basic-consequence      [\"cancer\" is the registry]")
Q+=("healthy controls recruited through a cancer registry, human exome, coding snvs, just the basic consequences")

E+=("species=human  origin=germline  size=small  region=coding  goal=clinical-interpretation      [1bp dup is SMALL]")
Q+=("theres a 1bp duplication and a handful of single base deletions, human rare disease exome, coding, want pathogenicity")

# ---------- UNDERSPECIFIED: should assume and say so, or ask ---------------------------------------
E+=("ALL FIVE UNSTATED -> human / somatic / both sizes / both regions / basic-consequence, all assumed")
Q+=("ive got a vcf, what should i turn on")

E+=("species=human  origin=germline  size=UNSTATED->both  region=coding  goal=clinical-interpretation      [two runs]")
Q+=("human germline data, coding regions, i want to know if anything is pathogenic")

# ---------- OUT OF SCOPE: should stop, not configure ------------------------------------------------
E+=("NO TUPLE — request_type=vep-support, should refuse")
Q+=("why is my vep output showing NA for everything in the SIFT column")

E+=("NO TUPLE — request_type=not-vep, should refuse")
Q+=("hiya")

E+=("NO TUPLE — request_type=vep-support, should refuse")
Q+=("how do i install the offline cache for vep on a mac, it keeps failing on the perl bit")

run_one() {
  local i=$1
  echo ""
  echo "════════════════════════════════════════════════════════════════════════"
  echo " #$((i+1))  EXPECT: ${E[$i]}"
  echo " QUERY:  ${Q[$i]}"
  echo "════════════════════════════════════════════════════════════════════════"
  python3 vep_assistant.py "${Q[$i]}"
}

if [ -n "$1" ]; then
  run_one $(( $1 - 1 ))
else
  for i in "${!Q[@]}"; do run_one "$i"; done
fi
