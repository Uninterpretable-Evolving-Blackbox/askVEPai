#!/usr/bin/env python3
"""A balanced trap/twin grid: 5 factors x 5 trick types x 6 cases = 150 pairs, 300 queries.

WHY. `factor_traps.py` and `factor_pairs.py` hold 24 pairs written freely, 5-7 per factor, no
species, and no rule for which tricks or which truth values each factor gets. A 24/24 there bounds the
failure rate only below ~12% (rule of three), and the counts per trick are uneven. This file fixes the
design before anything is run:

  GRID       every (factor, trick) cell has exactly 6 cases.
  TRUTH      within a cell the trap's true value is balanced: 3/3 for the binary factors, 2/2/2 for
             analysis_goal. The twin's true value is always the value the cue word points to, so twins
             are balanced the same way.
  TWIN       each trap has one twin: the same clause with the trick removed, so the cue word now means
             what it says and the correct answer flips. Same background, same sentence order.
  BACKGROUND the four non-target factors are stated plainly and chosen by a greedy balancer over the
             valid factor combinations (factors.json exclusions applied to BOTH the trap and the twin
             tuple), so the 300 full tuples spread across the combination space instead of clustering.

Method basis (see HANDOVER / the 2026-09-16 write-up):
  - trap  = CheckList INV test (Ribeiro et al., ACL 2020): a change that should not move the answer.
  - twin  = contrast set (Gardner et al., Findings of EMNLP 2020): a small edit that flips the label;
            scored as a pair ("contrast consistency": right on both).

STATED LIMITS
  - The frames below are synthetic: generated for this test, not collected from users, as were the 24
    originals. The labels need a person to check them: `--export` writes
    work/results/factor_grid_cases_<style>.csv for that.
  - Many frames state the true value next to the trick ("not a mouse study: the samples are human").
    That is the natural way such text is written, and it makes those cases easier than an implicit one.
  - Each clause is a single target factor; cross-talk with the background is limited by per-frame
    constraints (e.g. a frame that mentions a child forces human background).

  python3 work/harness/factor_grid.py --export          # write the case list only, no model
  NO_PROXY=localhost,127.0.0.1 python3 work/harness/factor_grid.py [--model gemma4:26b] [--seeds 42]
"""
import argparse
import csv
import itertools
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "harness"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

FACTORS = ["species", "origin", "variant_size_class", "region_focus", "analysis_goal"]
MULTI = {"variant_size_class", "region_focus", "analysis_goal"}
TRICKS = ["negation", "word_sense", "tool_name", "attachment", "domain"]
TRICK_MEANING = {
    "negation":   "the cue word is negated or disclaimed",
    "word_sense": "the cue word is used in another sense (idiom, ordinary English)",
    "tool_name":  "the cue word is the name of a tool, database or resource",
    "attachment": "the cue word is real but describes something other than this data",
    "domain":     "the cue word is literal but biology says the other value",
}

H, N = "human", "non-human"
G, S = "germline", "somatic"
SM, SV = "small", "structural-CNV"
C, R = "coding", "regulatory-noncoding"
B, CL, P = "basic-consequence", "clinical-interpretation", "population-frequency"
HUMAN = {"species": H}

# (trap truth, trap clause, twin truth, twin clause, background constraints)
F = {}

# ------------------------------------------------------------------------------------------ species
F["species", "negation"] = [
    (H, "Not a mouse study: the samples are from human volunteers", N,
        "A mouse study: the samples are from laboratory mice", {}),
    (H, "No zebrafish involved this time, the DNA is from people in our volunteer cohort", N,
        "Zebrafish only this time, the DNA is from our fish facility", {}),
    (H, "We are not working with dog genomes here; the reads are human", N,
        "We are working with dog genomes here; the reads are canine", {}),
    (N, "Not human data: the reads come from our pig herd", H,
        "Human data: the reads come from our volunteer donors", {}),
    (N, "Nothing from people in this set, it is all chicken lines", H,
        "Everything is from people in this set, no chicken lines", {}),
    (N, "These aren't Homo sapiens samples, they are Rattus norvegicus", H,
        "These are Homo sapiens samples, not Rattus norvegicus", {}),
]
F["species", "word_sense"] = [
    (H, "I've been going down a rabbit hole with these human exomes", N,
        "I've been going through these rabbit exomes from the colony", {}),
    (H, "Our guinea pig for the new pipeline is a set of human genomes", N,
        "Our guinea pig colony genomes are the set for the new pipeline", {}),
    (H, "Getting consent for these human samples was a cat-and-mouse chase", N,
        "Getting these cat and mouse samples was a chase", {}),
    (N, "We need human-readable output for these zebrafish variants", H,
        "We need readable output for these human variants", {}),
    (N, "Human error aside, these calls are from the cattle herd", H,
        "Error aside, these calls are from human donors", {}),
    (N, "After hundreds of man-hours the goat genomes are finally called", H,
        "After hundreds of hours the donors' human genomes are finally called", {}),
]
F["species", "tool_name"] = [
    (H, "Expression was quantified with Salmon beforehand, and the samples are human", N,
        "The samples are Atlantic salmon from the fish farm", {}),
    (H, "Phased with Beagle; the genomes are human", N,
        "The genomes are from beagles in the kennel colony", {}),
    (H, "Scripts are Python and pandas, all human data", N,
        "All data are from the pandas at the zoo", {}),
    (N, "Terms were mapped with the Human Phenotype Ontology, but the animals are zebrafish mutants", H,
        "Terms were mapped with the Human Phenotype Ontology for these human donors", {}),
    (N, "Cross-checked against the Human Protein Atlas; the tissue is from pigs", H,
        "Cross-checked against the Human Protein Atlas; the tissue is from human donors", {}),
    (N, "The pipeline is called HumanSeq internally, but it runs on chicken samples", H,
        "The pipeline runs on human samples", {}),
]
F["species", "attachment"] = [
    (H, "My supervisor works on mouse models, but my samples are human", N,
        "My supervisor works on mouse models and so do I: these are mouse samples", {}),
    (H, "The variants were first reported in a zebrafish screen; ours are from human donors", N,
        "The variants come from our zebrafish screen, fish embryos", {}),
    (H, "We followed a protocol written for pig tissue, but the DNA is human", N,
        "We followed a protocol for pig tissue, and the DNA is porcine", {}),
    (N, "The grant is for human health, but the sequencing is on sheep", H,
        "The grant is for human health, and the sequencing is on human volunteers", {}),
    (N, "Reads were checked for human contamination and those were removed; what is left is mouse", H,
        "Reads were checked for mouse contamination and those were removed; what is left is human", {}),
    (N, "Our collaborators do human genetics; we sent them these rat genomes", H,
        "Our collaborators do human genetics; these are their human genomes", {}),
]
F["species", "domain"] = [
    (H, "Human cells grown inside a mouse host; the reads were filtered to the grafted cells", N,
        "Cells from the mouse host; the reads were filtered to the host genome", {}),
    (H, "iPSCs from volunteer skin biopsies grown on mouse feeder cells, feeder reads removed", N,
        "The mouse feeder cells themselves, iPSC reads removed", {}),
    (H, "Neanderthal-introgressed segments in present-day Europeans", N,
        "The Neanderthal genome itself, from the Vindija bone", {}),
    (N, "A humanised mouse line; the genome we sequenced is the mouse's own", H,
        "The human graft from a humanised mouse line; we sequenced only the human cells", {}),
    (N, "Genomes from man's best friend: our kennel of Labradors", H,
        "Genomes from the kennel owners themselves, not their Labradors", {}),
    (N, "Transgenic mice carrying a human transgene; we sequenced the mice", H,
        "People carrying the same gene as the transgene; we sequenced the people", {}),
]

# ------------------------------------------------------------------------------------------- origin
F["origin", "negation"] = [
    (G, "Not a tumour study, these variants are inherited", S,
        "A tumour study, these variants are acquired in the tumour", {}),
    (G, "Nothing somatic here: constitutional calls from blood", S,
        "Only somatic calls here, nothing constitutional from blood", {}),
    (G, "The variants were not acquired, they were passed down in the family", S,
        "The variants were acquired, not passed down in the family", HUMAN),
    (S, "These are not inherited; they arose in the tumour", G,
        "These are inherited; they did not arise in a tumour", {}),
    (S, "No germline calls in this set, only mutations from the lesion", G,
        "Only germline calls in this set, no mutations from a lesion", {}),
    (S, "We didn't sequence the family, only the biopsy's acquired changes", G,
        "We sequenced the family, no acquired biopsy changes", HUMAN),
]
F["origin", "word_sense"] = [
    (G, "The project has metastasised into three labs; the calls are inherited variants from family trios", S,
        "The tumour has metastasised to three sites; the calls are acquired variants from the lesions", HUMAN),
    (G, "This cancer of a pipeline finally ran; the variants are inherited from the parents", S,
        "This cancer pipeline finally ran; the variants were acquired in the tumour", HUMAN),
    (G, "The donor, a Cancer by star sign, gave blood for this constitutional panel", S,
        "The donor with cancer gave a tumour biopsy for this somatic panel", HUMAN),
    (S, "The whole lab family pitched in; the calls are acquired mutations from tumour biopsies", G,
        "The whole family pitched in; the calls are inherited variants from the parents", HUMAN),
    (S, "Our inherited legacy code handles these somatic tumour calls", G,
        "Our code handles these variants inherited from the parents", HUMAN),
    (S, "We rebuilt the analysis de novo; the variants were acquired in tumour cells", G,
        "The variants arose de novo in the child, not in tumour cells", HUMAN),
]
F["origin", "tool_name"] = [
    (G, "We keep COSMIC open for lookups, but these are inherited variants from blood", S,
        "These come straight from COSMIC tumour samples, acquired variants", {}),
    (G, "The Mutect2 install failed, so HaplotypeCaller ran on the family's blood samples", S,
        "Mutect2 ran on the tumour-normal pairs", HUMAN),
    (G, "The TCGA portal was only used for reference downloads; our calls are inherited, from parents and child", S,
        "Our calls were downloaded from the TCGA portal: acquired tumour mutations", HUMAN),
    (S, "DeepTrio is installed but unused; the calls came from Mutect2 on tumour biopsies", G,
        "DeepTrio made the calls on the parent-child trio", HUMAN),
    (S, "The GATK germline best-practices page got us started, but these calls are acquired tumour mutations", G,
        "The GATK germline best-practices pipeline produced these inherited calls from blood", {}),
    (S, "PLINK is on the server from an old family study; these are acquired mutations from tumour tissue", G,
        "PLINK processed this family study; these are variants inherited from the parents", HUMAN),
]
F["origin", "attachment"] = [
    (G, "Healthy controls recruited through a cancer registry; inherited variants from blood", S,
        "Tumour samples from a cancer registry; acquired variants from the lesions", HUMAN),
    (G, "The grandmother had a tumour removed decades ago; these variants are inherited from the parents", S,
        "The grandmother's tumour was removed decades ago; these variants were acquired in that tumour", HUMAN),
    (G, "The tumour half of the batch was dropped; only matched normal blood remains, inherited variants", S,
        "The normal half of the batch was dropped; only the tumour remains, acquired variants", {}),
    (S, "The donor's parents gave blood too, but these are the acquired mutations in the donor's tumour", G,
        "The donor's parents gave blood too, and these are the inherited variants they passed on", HUMAN),
    (S, "The grant came from an inherited-traits charity, but the variants were acquired in tumour tissue", G,
        "The grant came from an inherited-traits charity, and the variants are inherited from the parents", HUMAN),
    (S, "Our previous paper was a germline trio study; this one is acquired tumour mutations", G,
        "Our previous paper was a tumour study; this one is a germline trio", {}),
]
F["origin", "domain"] = [
    (S, "De novo mutations arising in a glioma, sequenced from the tumour only", G,
        "De novo mutations in a child, confirmed absent from both parents' blood", HUMAN),
    (S, "Clonal haematopoiesis mutations found in blood from older donors", G,
        "Variants found in blood from older donors and in their children too", HUMAN),
    (S, "Mosaic mutations in brain tissue that are absent from blood and from the parents", G,
        "Mutations present in brain tissue, in blood and in one parent", HUMAN),
    (G, "A TP53 variant present in blood, saliva and every tissue of the carriers, including their tumours", S,
        "A TP53 mutation present only in the tumour, absent from blood and saliva", HUMAN),
    (G, "A tumour suppressor gene variant carried by all three generations of the family", S,
        "A tumour suppressor gene mutation found only in the lesion, not in the family", HUMAN),
    (G, "Variants shared by identical twins, one of whom later developed a tumour", S,
        "Variants found only in the tumour of one twin and absent from the other twin", HUMAN),
]

# ------------------------------------------------------------------------------------- variant size
F["variant_size_class", "negation"] = [
    (SM, "No CNVs or SVs were called, only SNVs and short indels", SV,
        "Only CNVs and SVs were called, no SNVs or short indels", {}),
    (SM, "Nothing structural here, just single-base changes", SV,
        "Only structural changes here, no single-base changes", {}),
    (SM, "Not large rearrangements: short indels under 20 bp", SV,
        "Large rearrangements, not short indels under 20 bp", {}),
    (SV, "No point mutations in this callset; it is copy-number gains and losses", SM,
        "Point mutations in this callset, no copy-number gains or losses", {}),
    (SV, "We skipped the SNVs entirely and kept the multi-kilobase deletions", SM,
        "We kept the SNVs and skipped the multi-kilobase deletions", {}),
    (SV, "These aren't indels; they are inversions and translocations", SM,
        "These are indels, not inversions or translocations", {}),
]
F["variant_size_class", "word_sense"] = [
    (SM, "SNVs with a possible structural effect on the protein", SV,
        "Structural variants spanning the protein's gene", {}),
    (SM, "A large number of single-nucleotide variants", SV,
        "A number of large multi-exon deletions and duplications", {}),
    (SM, "A copy of the SNV calls sent over by the core facility", SV,
        "Copy-number calls sent over by the core facility", {}),
    (SV, "At this point we only have copy-number gains and losses", SM,
        "We only have point mutations", {}),
    (SV, "Short on time, so just the megabase-scale deletions for now", SM,
        "Just the short indels and SNVs for now", {}),
    (SV, "Every single call is a CNV", SM,
        "Every call is a single-nucleotide change", {}),
]
F["variant_size_class", "tool_name"] = [
    (SM, "Manta was run but produced nothing, so we only have SNVs and indels from DeepVariant", SV,
        "Manta was run and produced the structural variant calls we are using", {}),
    (SM, "The CNVkit container is on our server, unused; these are SNVs from HaplotypeCaller", SV,
        "CNVkit made these copy-number calls", {}),
    (SM, "We looked at the Database of Genomic Variants track for context, but our calls are point mutations", SV,
        "Our calls are large structural variants like those in the Database of Genomic Variants", {}),
    (SV, "DeepVariant was only used for QC; the calls are large deletions and duplications from Delly", SM,
        "DeepVariant made these SNV and small indel calls", {}),
    (SV, "FreeBayes is in the workflow, but we are annotating the Delly structural calls", SM,
        "We are annotating the FreeBayes SNV and indel calls", {}),
    (SV, "dbSNP IDs are in the header from an old template, but these are CNVs", SM,
        "These are dbSNP-annotated SNVs", {}),
]
F["variant_size_class", "attachment"] = [
    (SM, "The lab next door studies structural variants; ours are single-nucleotide changes", SV,
        "Our lab studies structural variants; these are ours", {}),
    (SM, "The gene sits in a known large-deletion region, but our variants are SNVs within it", SV,
        "Our variants are the large deletions covering the gene", {}),
    (SM, "The reference paper was about CNVs; we are following up with SNV calls", SV,
        "We are following up that paper with our own CNV calls", {}),
    (SV, "The SNV array data was discarded; the remaining calls are large duplications", SM,
        "The duplications were discarded; the remaining calls are from the SNV array", {}),
    (SV, "Our last project was on indels; this callset is megabase copy-number changes", SM,
        "Our last project was on copy-number changes; this callset is indels", {}),
    (SV, "Breakpoints were confirmed by Sanger reads at single-base resolution; the events are 50 kb deletions", SM,
        "The events are single-base substitutions confirmed by Sanger reads", {}),
]
F["variant_size_class", "domain"] = [
    (SM, "A 1-bp duplication and a couple of single-base deletions", SV,
        "A 2 Mb duplication and several whole-gene deletions", {}),
    (SM, "A 3-bp in-frame deletion", SV,
        "A 300-kb deletion", {}),
    (SM, "Insertions of two or three bases", SV,
        "Mobile-element insertions several kilobases long", {}),
    (SV, "A single copy of the whole gene lost", SM,
        "A single base changed in the gene", {}),
    (SV, "Chromosome-arm gains detected with a SNP array", SM,
        "SNPs genotyped with a SNP array", {}),
    (SV, "An Alu insertion of about 300 bases", SM,
        "A 2-base insertion", {}),
]

# ------------------------------------------------------------------------------------------- region
F["region_focus", "negation"] = [
    (C, "Nothing intronic or intergenic, only exonic protein-altering changes", R,
        "Only intronic and intergenic changes, nothing exonic or protein-altering", {}),
    (C, "We are not looking at promoters; coding sequence only", R,
        "We are looking at promoters, not coding sequence", {}),
    (C, "No enhancer variants in scope, just changes inside coding exons", R,
        "Enhancer variants only, not changes inside coding exons", {}),
    (R, "Not in the coding sequence; they sit in enhancers", C,
        "In the coding sequence; not in enhancers", {}),
    (R, "None of these touch exons, all are in upstream regulatory elements", C,
        "All of these touch exons, none are in upstream regulatory elements", {}),
    (R, "We excluded protein-coding regions and kept promoter and UTR hits", C,
        "We kept protein-coding regions and excluded promoter and UTR hits", {}),
]
F["region_focus", "word_sense"] = [
    (C, "A real enhancer for our grant: the variants sit in protein-coding exons", R,
        "A real enhancer region: the variants sit there, outside exons", {}),
    (C, "My supervisor is a big promoter of this project; the variants are in coding exons", R,
        "The variants are in a gene promoter, outside the coding exons", {}),
    (C, "For regulatory approval we only report coding-sequence changes", R,
        "For regulatory elements we only report non-coding changes", {}),
    (R, "The coding in our pipeline is messy, but the variants are all in enhancers", C,
        "The coding sequence holds all the variants, none are in enhancers", {}),
    (R, "In the frame of this project, the variants are intergenic and in enhancers", C,
        "In-frame variants inside the coding sequence", {}),
    (R, "The translation of the protocol is done; the variants are in UTRs and promoters", C,
        "The variants affect translation of the protein, inside the coding sequence", {}),
]
F["region_focus", "tool_name"] = [
    (C, "We used the ENCODE browser for figures, but the variants are in coding exons", R,
        "The variants are in ENCODE regulatory elements", {}),
    (C, "The Regulatory Build track loads by default, but our variants are protein-coding", R,
        "Our variants are in the Regulatory Build's promoter and enhancer features", {}),
    (C, "JASPAR was cited in the old draft; these variants are exonic", R,
        "These variants disrupt JASPAR transcription-factor motifs outside genes", {}),
    (R, "UniProt was open in another tab; the variants are in enhancers", C,
        "The variants change residues listed in UniProt, inside coding exons", {}),
    (R, "The CCDS set was the old default in our config; our variants are intergenic", C,
        "Our variants fall in CCDS coding exons", {}),
    (R, "Pfam came up in lab meeting, but these are promoter variants", C,
        "These variants fall inside Pfam protein domains", {}),
]
F["region_focus", "attachment"] = [
    (C, "The paper we follow was about enhancers; our variants are in coding exons", R,
        "Like the paper, our variants are in enhancers", {}),
    (C, "The gene's promoter was characterised last year; we are annotating its exonic changes", R,
        "We are annotating the changes in that promoter", {}),
    (C, "The intergenic controls were filtered out; only protein-coding variants remain", R,
        "The protein-coding controls were filtered out; only intergenic variants remain", {}),
    (R, "The exome capture kit was for another study; our variants are in distal enhancers", C,
        "Our variants come from the exome capture, in coding exons", {}),
    (R, "We named the file coding_variants out of habit; they are in promoters", C,
        "The file coding_variants holds exonic variants", {}),
    (R, "Our collaborators study protein structure; these variants are in introns and UTRs", C,
        "These variants change protein structure, inside the coding sequence", {}),
]
F["region_focus", "domain"] = [
    (C, "Variants at the 5' end of the open reading frame, right after the start codon", R,
        "Variants in the 5' UTR, just before the start codon", {}),
    (C, "Variants in the coding exons of the regulatory-subunit gene PRKAR1A", R,
        "Variants in the regulatory region upstream of PRKAR1A", {}),
    (C, "Amino-acid changes in the DNA-binding domain of a transcription factor", R,
        "Changes in the DNA motifs that the transcription factor binds", {}),
    (R, "Variants in the promoter of a protein-coding gene", C,
        "Variants in the exons of a protein-coding gene", {}),
    (R, "Deep intronic variants within a protein-coding gene's locus", C,
        "Exonic variants within a protein-coding gene's locus", {}),
    (R, "Variants in microRNA genes, which are transcribed but never translated", C,
        "Variants in genes that are transcribed and translated into protein", {}),
]

# ------------------------------------------------------------------------------------ analysis goal
# Per cell: trap truth B (cue CL), B (cue P), CL (cue B), CL (cue P), P (cue CL), P (cue B).
F["analysis_goal", "negation"] = [
    (B, "No clinical question here, I just want to know which genes and transcripts they hit", CL,
        "A clinical question here, not just which genes and transcripts they hit", {}),
    (B, "Frequencies don't matter for this, just the consequence of each variant", P,
        "Only frequencies matter for this, not the consequence of each variant", HUMAN),
    (CL, "Not a quick consequence lookup; I need to know which are disease-causing", B,
        "A quick consequence lookup; I don't need to know which are disease-causing", {}),
    (CL, "Not after population frequencies; the question is whether any are pathogenic", P,
        "After population frequencies; the question is not whether any are pathogenic", HUMAN),
    (P, "We're not diagnosing anyone; we want allele frequencies across ancestries", CL,
        "We're diagnosing someone; we don't want allele frequencies across ancestries", HUMAN),
    (P, "Not just what they hit: how common each one is in gnomAD populations", B,
        "Just what they hit, not how common each one is in gnomAD populations", HUMAN),
]
F["analysis_goal", "word_sense"] = [
    (B, "Run it with clinical precision please, just the consequence types", CL,
        "Run a clinical interpretation please, not just the consequence types", {}),
    (B, "Our growing lab population needs a quick answer: which transcripts are hit", P,
        "Our population study needs frequencies, not which transcripts are hit", HUMAN),
    (CL, "Basic question maybe, but are any of these pathogenic?", B,
        "Basic question: what consequence does each have, nothing about pathogenicity", {}),
    (CL, "Common sense says check which ones could cause the disease", P,
        "Check how common they are in populations, not whether they cause disease", HUMAN),
    (P, "I'm pathologically curious how frequent these are across populations", CL,
        "I want the pathology read: are these disease-causing, not how frequent they are", HUMAN),
    (P, "As a consequence of reviewer 2, we need allele frequencies in each population", B,
        "We need the consequence of each variant, not allele frequencies", HUMAN),
]
F["analysis_goal", "tool_name"] = [
    (B, "ClinVar is bookmarked but not needed; just the consequence per transcript", CL,
        "ClinVar significance is needed, not just the consequence per transcript", {}),
    (B, "gnomAD is down anyway; I only want what each variant hits", P,
        "I only want the gnomAD frequencies, not what each variant hits", HUMAN),
    (CL, "SnpEff gave us consequences already; now we need to know which are pathogenic", B,
        "We need SnpEff-style consequences, nothing about pathogenicity", {}),
    (CL, "The 1000 Genomes browser tab was left open by accident; the aim is pathogenicity", P,
        "The aim is 1000 Genomes allele frequencies, not pathogenicity", HUMAN),
    (P, "OMIM is on the reading list, but this analysis is about allele frequencies across populations", CL,
        "This analysis is about OMIM disease links, not allele frequencies", HUMAN),
    (P, "The Sequence Ontology poster is on our wall; what we need is population allele frequencies", B,
        "What we need is Sequence Ontology consequence terms, not population allele frequencies", HUMAN),
]
F["analysis_goal", "attachment"] = [
    (B, "The clinical team will interpret later; from me they just want the consequence types", CL,
        "The clinical team wants me to interpret pathogenicity, not just the consequence types", {}),
    (B, "A population geneticist will do frequencies afterwards; my part is only which genes are hit", P,
        "My part is the population frequencies, not which genes are hit", HUMAN),
    (CL, "The first-year student did the quick consequence pass; I need to decide which are pathogenic", B,
        "I need the quick consequence pass; the pathogenicity decision is someone else's", {}),
    (CL, "Last year's paper reported the allele frequencies; this year we assess pathogenicity", P,
        "This year we report the allele frequencies; pathogenicity was last year's paper", HUMAN),
    (P, "The diagnosis was made elsewhere; our job is frequency across populations", CL,
        "Our job is the diagnosis; frequency across populations was done elsewhere", HUMAN),
    (P, "The consequences were annotated in a previous release; we now need population frequencies", B,
        "We now need the consequences; population frequencies were done in a previous release", HUMAN),
]
F["analysis_goal", "domain"] = [
    (B, "These disease genes are for a teaching exercise: students just label each variant's consequence", CL,
        "These disease genes are for a diagnosis: which variants are pathogenic?", {}),
    (B, "Variants from a population cohort, but all I need is the consequence class for each", P,
        "Variants from a population cohort, and all I need is how frequent each is", HUMAN),
    (CL, "Just one question about these variants: could any explain the seizure phenotype?", B,
        "Just one question about these variants: what consequence does each have?", {}),
    (CL, "The variant is common in one ancestry; is it benign or pathogenic in our case?", P,
        "How common is the variant in each ancestry?", HUMAN),
    (P, "Carrier frequency of a recessive disease allele across populations", CL,
        "Whether this recessive disease allele caused the child's condition", {"species": H, "origin": G}),
    (P, "Just count how often each allele appears across ancestries", B,
        "Just tell me what each allele does to its transcript", HUMAN),
]

# --------------------------------------------------------------------------------------- background
ANIMALS = ["mouse", "zebrafish", "dog", "pig", "chicken", "cattle", "rat", "sheep"]
BG = {
    ("species", H): ["human", "human samples", "Homo sapiens data"],
    ("species", N): ["{a} samples", "{a} data", "from {a}"],
    ("origin", G): ["germline", "inherited variants", "constitutional calls"],
    ("origin", S): ["somatic calls", "acquired somatic variants", "somatic mutations"],
    ("variant_size_class", SM): ["SNVs and small indels", "point mutations and short indels",
                                  "single-nucleotide variants"],
    ("variant_size_class", SV): ["structural variants", "CNVs and large deletions",
                                  "copy-number and structural calls"],
    ("region_focus", C): ["coding regions", "protein-coding exons", "in coding sequence"],
    ("region_focus", R): ["regulatory regions", "promoters and enhancers", "non-coding regulatory elements"],
    ("analysis_goal", B): ["just the consequence types", "what each one hits, nothing more",
                           "basic consequence annotation"],
    ("analysis_goal", CL): ["clinical interpretation", "pathogenicity assessment",
                            "is any of it pathogenic"],
    ("analysis_goal", P): ["population allele frequencies", "how common they are in populations",
                           "frequency lookup across populations"],
}
VALUES = {"species": [H, N], "origin": [G, S], "variant_size_class": [SM, SV],
          "region_focus": [C, R], "analysis_goal": [B, CL, P]}
EXCLUSIONS = [{"species": N, "analysis_goal": P}, {"species": N, "variant_size_class": SV}]


# Natural-speech background: one "what data" sentence and one "what I want" sentence, written the way
# people type questions, instead of a comma list. Each factor contributes a piece; the target factor's
# piece is left out, because the trick clause carries it.
NAT_OPENERS = ["So I've got", "We have", "I'm working with", "Our lab just got back", "I've got a VCF of",
               "Hi, we called", "I'm trying to annotate", "Basically we have"]
NAT_ORIGIN = {G: ["germline", "inherited", "constitutional"], S: ["somatic", "acquired somatic", "tumour-derived somatic"]}
NAT_SIZE = {SM: ["SNVs and small indels", "point mutations and a few short indels", "single-nucleotide changes"],
            SV: ["structural variants", "CNVs and some big deletions", "copy-number changes and other large SVs"],
            None: ["variants", "calls", "a batch of variants"]}
NAT_SPECIES = {H: ["from human samples", "from human donors", "from Homo sapiens samples"],
               N: ["from {a}", "from our {a} samples", "from {a} tissue"]}
NAT_REGION = {C: ["and they're mostly in coding exons", "mostly in protein-coding regions",
                  "and I only care about the ones in coding sequence"],
              R: ["and they're mostly in promoters and enhancers", "mostly in regulatory regions",
                  "and I only care about the non-coding regulatory ones"]}
NAT_GOAL = {B: ["All I really want is to know what each one hits.", "I just need the basic consequences, nothing fancy.",
                "Can you just tell me the consequence types?"],
            CL: ["I need to work out if any of them are pathogenic.", "The goal is clinical interpretation.",
                 "Are any of these likely to be disease-causing?"],
            P: ["I want to see how common they are across populations.",
                "Mainly I'm after allele frequencies in different populations.",
                "How frequent are these in population databases?"]}


def natural_background(bg, animal, rng):
    origin = rng.choice(NAT_ORIGIN[bg["origin"]]) + " " if "origin" in bg else ""
    size = rng.choice(NAT_SIZE[bg.get("variant_size_class")])
    if origin and size.startswith("a batch"):
        size = "variants"
    if origin.startswith("tumour") and size == "calls":
        size = "variants"
    species = (" " + rng.choice(NAT_SPECIES[bg["species"]]).format(a=animal)) if "species" in bg else ""
    region = (", " + rng.choice(NAT_REGION[bg["region_focus"]])) if "region_focus" in bg else ""
    data = f"{rng.choice(NAT_OPENERS)} {origin}{size}{species}{region}."
    goal = rng.choice(NAT_GOAL[bg["analysis_goal"]]) if "analysis_goal" in bg else ""
    return data, goal


# PLAIN statements of each value, for the MFT variant. Three wordings each, picked per case.
PLAIN = {
    ("species", H): ["The samples are human", "These are human samples", "It's all human data"],
    ("species", N): ["The samples are from {a}", "These are {a} samples", "It's all {a} data"],
    ("origin", G): ["The variants are germline", "These are inherited germline variants", "They're constitutional calls"],
    ("origin", S): ["The variants are somatic", "These are somatic mutations", "They were acquired somatically"],
    ("variant_size_class", SM): ["They're SNVs and short indels", "These are small variants, SNVs and indels",
                                 "It's point mutations only"],
    ("variant_size_class", SV): ["They're structural variants and CNVs", "These are large deletions and duplications",
                                 "It's copy-number and structural calls only"],
    ("region_focus", C): ["They're in coding regions", "I care about the protein-coding exons", "Focus on coding sequence"],
    ("region_focus", R): ["They're in regulatory regions", "I care about promoters and enhancers",
                          "Focus on non-coding regulatory elements"],
    ("analysis_goal", B): ["I just want the consequence of each variant", "Only the basic consequence types, please",
                           "Just tell me what each one hits"],
    ("analysis_goal", CL): ["I need clinical interpretation", "I want to know which are pathogenic",
                            "The aim is pathogenicity assessment"],
    ("analysis_goal", P): ["I want population allele frequencies", "Show me how common they are in populations",
                           "The aim is frequency lookup across populations"],
}
TEST_TYPES = ("plain", "trap", "twin", "absent")
TEST_MEANING = {
    "plain":  "MFT: the fact stated plainly",
    "trap":   "INV: a misleading cue word; the answer must not move",
    "twin":   "DIR: the same clause with the trick removed; the answer must flip",
    "absent": "the fact removed; the answer must be unstated",
}

def valid(t):
    return not any(all(t.get(k) == v for k, v in ex.items()) for ex in EXCLUSIONS)


def truth_val(f, v):
    return [v] if f in MULTI else v


def build(seed=20260916, style="natural"):
    rng = random.Random(seed)
    full_use, value_use = Counter(), Counter()
    cases = []
    for f in FACTORS:
        others = [o for o in FACTORS if o != f]
        for trick in TRICKS:
            frames = F[f, trick]
            assert len(frames) == 6, (f, trick, len(frames))
            for i, (t_truth, t_text, w_truth, w_text, cons) in enumerate(frames):
                assert t_truth != w_truth, (f, trick, i)
                cands = []
                for combo in itertools.product(*[VALUES[o] for o in others]):
                    bg = dict(zip(others, combo))
                    if any(bg.get(k) != v for k, v in cons.items() if k != f):
                        continue
                    tt, wt = dict(bg, **{f: t_truth}), dict(bg, **{f: w_truth})
                    if valid(tt) and valid(wt):
                        cands.append(bg)
                rng.shuffle(cands)

                def cost(bg):
                    tt = tuple(dict(bg, **{f: t_truth})[k] for k in FACTORS)
                    wt = tuple(dict(bg, **{f: w_truth})[k] for k in FACTORS)
                    return (full_use[tt] + full_use[wt], sum(value_use[(k, v)] for k, v in bg.items()))
                bg = min(cands, key=cost)
                for tr in (t_truth, w_truth):
                    full_use[tuple(dict(bg, **{f: tr})[k] for k in FACTORS)] += 1
                for k, v in bg.items():
                    value_use[(k, v)] += 2

                animal = rng.choice(ANIMALS)
                if style == "terse":
                    frags = [rng.choice(BG[k, v]).format(a=animal) for k, v in bg.items()]
                    rng.shuffle(frags)
                    bg_text = ", ".join(frags)
                    trick_first = rng.random() < 0.5

                    def compose(clause, bg_text=bg_text, trick_first=trick_first):
                        b = bg_text[0].upper() + bg_text[1:] + "."
                        if not clause:
                            return b
                        clause = clause.rstrip(".?") + ("?" if clause.endswith("?") else ".")
                        return f"{clause} {b}" if trick_first else f"{b} {clause}"
                else:
                    data, goal = natural_background(bg, animal, rng)
                    order = rng.randrange(3)
                    if order == 1 and data.startswith("Hi, "):       # a greeting only opens a message
                        data = "W" + data[5:]

                    def compose(clause, data=data, goal=goal, order=order):
                        if clause:
                            clause = clause.rstrip(".?") + ("?" if clause.endswith("?") else ".")
                        parts = {0: [data, clause, goal], 1: [clause, data, goal],
                                 2: [data, goal, clause]}[order]
                        return " ".join(p for p in parts if p)
                plain_text = rng.choice(PLAIN[f, t_truth]).format(a=animal)
                cases.append({
                    "id": f"{f[:4]}-{trick[:4]}-{i + 1}",
                    "factor": f, "trick": trick,
                    "plain_query": compose(plain_text), "plain_truth": truth_val(f, t_truth),
                    "trap_query": compose(t_text), "trap_truth": truth_val(f, t_truth),
                    "twin_query": compose(w_text), "twin_truth": truth_val(f, w_truth),
                    "absent_query": compose(""), "absent_truth": [] if f in MULTI else "unstated",
                    "background": {k: truth_val(k, v) for k, v in bg.items()},
                })
    return cases, full_use


def norm(v):
    if isinstance(v, list):
        return tuple(sorted(v))
    return (v,) if v and v != "unstated" else ()


def species_of(read, query):
    """What the SHIPPED path would say for species: the model's own answer is ignored when the hint is
    off, and infer_species decides; unstated -> human (the disclosed fallback)."""
    sp = va.infer_species(query)
    return H if sp in ("human", "unknown") else N


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seeds", default="42")
    ap.add_argument("--export", action="store_true", help="write the case list and stop")
    ap.add_argument("--limit", type=int, default=0, help="smoke: first N cases")
    ap.add_argument("--style", choices=("natural", "terse"), default="natural",
                    help="background as conversational sentences (default) or a comma list")
    ap.add_argument("--reader", choices=("shipped", "think", "compat"), default="shipped",
                    help="shipped = native endpoint, reasoning off (what the tool runs); think = same call, "
                         "reasoning on; compat = the old /v1 helper, which reasons")
    ap.add_argument("--workers", type=int, default=1, help="parallel model calls (server needs OLLAMA_NUM_PARALLEL)")
    ap.add_argument("--latency-sample", type=int, default=0,
                    help="after the grid, time this many queries one at a time (single-user latency)")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    cases, full_use = build(style=a.style)
    _pv = "" if va._classifier_prompt_version() == "v1" else "_v2prompt"
    a.json = a.json or str(ROOT / f"work/results/factor_grid_{a.style}_{a.reader}{_pv}.json")
    csv_path = ROOT / f"work/results/factor_grid_cases_{a.style}.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "factor", "trick", "background"]
                   + [x for t in TEST_TYPES for x in (f"{t}_query", f"{t}_truth")] + ["label_ok (fill in)"])
        for c in cases:
            w.writerow([c["id"], c["factor"], c["trick"], json.dumps(c["background"])]
                       + [x for t in TEST_TYPES for x in (c[f"{t}_query"], c[f"{t}_truth"])] + [""])
    n_valid = sum(1 for combo in itertools.product(*[VALUES[k] for k in FACTORS])
                  if valid(dict(zip(FACTORS, combo))))
    print(f"{len(cases)} cases x {len(TEST_TYPES)} test types = {len(cases) * len(TEST_TYPES)} queries "
          f"-> {csv_path.relative_to(ROOT)}")
    print(f"full tuples covered (trap+twin): {len(full_use)} of {n_valid} valid; "
          f"uses per tuple min {min(full_use.values())} max {max(full_use.values())}")
    if a.export:
        return

    from rules_vs_model import model_read, rule_read
    import time
    import urllib.request
    seeds = [int(x) for x in a.seeds.split(",")]
    timings = []                                 # one dict per model call

    def native_read(q, think):
        """The shipped classifier call (_classify_native), inlined so the timing and token counts that
        Ollama returns are kept. Same prompt, endpoint, temperature, seed and token cap."""
        body = {"model": a.model, "stream": False, "keep_alive": va.KEEP_ALIVE, "think": think,
                "messages": va.classifier_messages(q, va.format_species_hint(q) if va._species_hint_on() else ""),
                "options": {"temperature": 0.0, "seed": 42, "num_predict": va._CLASSIFY_MAX_TOKENS}}
        req = urllib.request.Request(va._native_chat_url(), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.loads(r.read())
        msg = d.get("message") or {}
        timings.append({"seconds": round(time.perf_counter() - t0, 3), "eval_count": d.get("eval_count"),
                        "prompt_eval_count": d.get("prompt_eval_count"),
                        "thinking_chars": len(msg.get("thinking") or ""), "done_reason": d.get("done_reason"),
                        "parsed": None})
        parsed = va.parse_factor_classification(msg.get("content") or "")
        timings[-1]["parsed"] = parsed is not None
        return parsed

    if a.reader in ("shipped", "think"):
        # shipped = think False (what the tool runs); think = the same call with reasoning on
        # (what VEP_FACTOR_THINK=1 / --factor-think would do). seed 42 fixed in the call.
        seeds = [42]

        def reader(q, _seed):
            return native_read(q, a.reader == "think")
    else:
        # rules_vs_model.model_read goes through the OpenAI-compatible /v1 endpoint, which (measured
        # 2026-09-16) IGNORES think=False: gemma4:26b reasons first, ~1,700 tokens, ~10-17 s a call.
        # factor_traps.py and factor_pairs.py were run this way. Kept only to reproduce them.
        from openai import OpenAI
        client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                        api_key="ollama")

        def reader(q, seed):
            t0 = time.perf_counter()
            out = model_read(client, a.model, q, seed)
            timings.append({"seconds": round(time.perf_counter() - t0, 3), "parsed": out is not None})
            return out
    run = cases[: a.limit] if a.limit else cases

    maj = {}                                   # always the most common stated value, per factor
    for f in FACTORS:
        cnt = Counter(norm(c[f"{t}_truth"]) for c in cases if c["factor"] == f for t in ("plain", "trap", "twin"))
        maj[f] = cnt.most_common(1)[0][0]

    # All model calls first, optionally in parallel (--workers). Needs the Ollama SERVER to accept
    # parallel requests (OLLAMA_NUM_PARALLEL); otherwise they queue. Per-call seconds recorded under
    # parallel load are NOT single-user latency -- use --latency-sample for that.
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(ci, t, sd) for ci, c in enumerate(run) for t in TEST_TYPES for sd in seeds]
    answers = {}

    def do(job):
        ci, t, sd = job
        return job, reader(run[ci][f"{t}_query"], sd) or {}

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        for job, rec in ex.map(do, jobs):
            answers[job] = rec
            done += 1
            if done % 40 == 0:
                print(f"  ... {done}/{len(jobs)} calls", flush=True)

    rows = []
    for ci, c in enumerate(run):
        f = c["factor"]
        out = {}
        for t in TEST_TYPES:
            q, truth = c[f"{t}_query"], c[f"{t}_truth"]
            reads = [answers[(ci, t, sd)] for sd in seeds]
            vals = [r.get(f) for r in reads]
            rule_val = species_of(None, q) if f == "species" else rule_read(q).get(f)
            out[t] = {"model": vals, "model_ok": all(norm(v) == norm(truth) for v in vals),
                      "background_read_ok": all(norm(reads[0].get(k)) == norm(v) for k, v in c["background"].items()),
                      "rule": rule_val, "rule_ok": norm(rule_val) == norm(truth),
                      "majority_ok": maj[f] == norm(truth)}
        rows.append(dict(c, result=out))
        marks = "".join("+" if out[t]["model_ok"] else "x" for t in TEST_TYPES)
        wrong = "  ".join(f"{t}={out[t]['model'][0]}" for t in TEST_TYPES if not out[t]["model_ok"])
        print(f"  {c['id']:16} {marks}  {wrong}", flush=True)

    latency = None
    if a.latency_sample:
        # Single-user latency: a fixed, evenly spread sample of queries, one at a time, after the grid.
        k = a.latency_sample
        idx = [round(i * (len(run) - 1) / max(1, k - 1)) for i in range(k)]
        sample_q = [run[i][TEST_TYPES[i % len(TEST_TYPES)] + "_query"] for i in idx]
        before = len(timings)
        for q in sample_q:
            reader(q, seeds[0])
        lat = timings[before:]
        del timings[before:]
        secs_l = sorted(t["seconds"] for t in lat)
        latency = {"n": len(lat), "median_s": secs_l[len(secs_l) // 2], "max_s": secs_l[-1],
                   "mean_s": round(sum(secs_l) / len(secs_l), 2),
                   "median_output_tokens": sorted(t.get("eval_count") or 0 for t in lat)[len(lat) // 2],
                   "hit_token_cap": sum(1 for t in lat if t.get("done_reason") == "length")}
        print(f"\n  single-user latency, {len(lat)} sequential calls: median {latency['median_s']} s, "
              f"mean {latency['mean_s']} s, max {latency['max_s']} s, median tokens {latency['median_output_tokens']}")

    n = len(rows)

    def ok(sel, arm, t):
        return sum(r["result"][t][f"{arm}_ok"] for r in sel)

    def allfour(sel, arm):
        return sum(all(r["result"][t][f"{arm}_ok"] for t in TEST_TYPES) for r in sel)

    print(f"\n=== factor grid: {n} cases x 4, {a.model}, style {a.style}, reader {a.reader}, seeds {seeds} ===")
    print("  test types: " + "; ".join(f"{t} = {m}" for t, m in TEST_MEANING.items()))
    print(f"\n  {'arm':10}" + "".join(f"{t:>10}" for t in TEST_TYPES) + f"{'trap+twin':>11}{'all four':>10}")
    for arm in ("model", "rule", "majority"):
        pair = sum(r["result"]["trap"][f"{arm}_ok"] and r["result"]["twin"][f"{arm}_ok"] for r in rows)
        print(f"  {arm:10}" + "".join(f"{ok(rows, arm, t):>6}/{n}" for t in TEST_TYPES)
              + f"{pair:>7}/{n}{allfour(rows, arm):>6}/{n}")
    print("  (rule = keyword rules; for species this is the shipped path, since the hint is off and "
          "infer_species decides species)")

    print("\n  model, by factor (of 30 each)")
    print(f"  {'':20}" + "".join(f"{t:>9}" for t in TEST_TYPES) + f"{'all four':>10}")
    by_factor = {}
    for f in FACTORS:
        sel = [r for r in rows if r["factor"] == f]
        by_factor[f] = {t: ok(sel, "model", t) for t in TEST_TYPES} | {"all_four": allfour(sel, "model"), "n": len(sel)}
        print(f"  {f:20}" + "".join(f"{ok(sel, 'model', t):>6}/{len(sel)}" for t in TEST_TYPES)
              + f"{allfour(sel, 'model'):>6}/{len(sel)}")

    print("\n  model, all four right, by factor x trick (of 6)")
    print(f"  {'':20}" + "".join(f"{t:>12}" for t in TRICKS))
    grid = {}
    for f in FACTORS:
        cells = []
        for tr in TRICKS:
            sel = [r for r in rows if r["factor"] == f and r["trick"] == tr]
            grid[f"{f}|{tr}"] = {t: ok(sel, "model", t) for t in TEST_TYPES} | {"all_four": allfour(sel, "model"), "n": len(sel)}
            cells.append(f"{allfour(sel, 'model')}/{len(sel)}")
        print(f"  {f:20}" + "".join(f"{x:>12}" for x in cells))

    kinds = Counter()
    for r in rows:
        if r["factor"] not in MULTI:
            continue
        for t in TEST_TYPES:
            if r["result"][t]["model_ok"]:
                continue
            got, want = set(r["result"][t]["model"][0] or []), set(r[f"{t}_truth"])
            kinds[f"{t}: " + ("listed extra values (truth included)" if want and want < got else
                              "said something where unstated" if not want else
                              "empty" if not got else "wrong value")] += 1
    if kinds:
        print("\n  multi-select misses: " + "; ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    bg_ok = sum(r["result"][t]["background_read_ok"] for r in rows for t in TEST_TYPES)
    print(f"  background factors all read correctly: {bg_ok}/{4 * n} queries")

    def pct(xs, p):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None
    secs = [t["seconds"] for t in timings]
    timing_summary = {"calls": len(timings), "total_s": round(sum(secs), 1),
                      "mean_s": round(sum(secs) / len(secs), 2) if secs else None,
                      "median_s": pct(secs, 50), "p90_s": pct(secs, 90), "max_s": max(secs) if secs else None}
    toks = [t["eval_count"] for t in timings if t.get("eval_count") is not None]
    if toks:
        timing_summary.update({"median_output_tokens": pct(toks, 50), "p90_output_tokens": pct(toks, 90),
                               "max_output_tokens": max(toks)})
    timing_summary["unparseable"] = sum(1 for t in timings if not t["parsed"])
    timing_summary["hit_token_cap"] = sum(1 for t in timings if t.get("done_reason") == "length")
    print(f"\n  per-call time{' UNDER PARALLEL LOAD (workers=' + str(a.workers) + ')' if a.workers > 1 else ''}: median {timing_summary['median_s']} s, mean {timing_summary['mean_s']} s, "
          f"p90 {timing_summary['p90_s']} s, max {timing_summary['max_s']} s, total {timing_summary['total_s']} s")
    if toks:
        print(f"  output tokens: median {timing_summary['median_output_tokens']}, "
              f"p90 {timing_summary['p90_output_tokens']}, max {timing_summary['max_output_tokens']}")
    print(f"  unparseable answers: {timing_summary['unparseable']}; hit the {va._CLASSIFY_MAX_TOKENS}-token cap: "
          f"{timing_summary['hit_token_cap']}")

    fails = [(r, t) for r in rows for t in TEST_TYPES if not r["result"][t]["model_ok"]]
    if fails:
        print(f"\n  failures ({len(fails)}):")
        for r, t in fails:
            print(f"    {r['id']:16} {t:6} truth {r[t + '_truth']!s:28} read {r['result'][t]['model'][0]}")
            print(f"      {r[t + '_query']}")
    json.dump({"model": a.model, "seeds": seeds, "style": a.style, "reader": a.reader,
               "classifier_prompt": va._classifier_prompt_version(),
               "species_hint": va._species_hint_on(), "n_cases": n,
               "arms": {arm: {t: ok(rows, arm, t) for t in TEST_TYPES} | {"all_four": allfour(rows, arm)}
                        for arm in ("model", "rule", "majority")},
               "by_factor": by_factor, "grid": grid, "workers": a.workers, "timing": timing_summary, "single_user_latency": latency, "timings": timings,
               "rows": rows}, open(a.json, "w"), indent=2)
    print(f"\n  wrote {a.json}")


if __name__ == "__main__":
    main()
