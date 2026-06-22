# VEP Assistant Evaluation Results

**Date:** 2026-03-21T14:39:24.243883
**Model:** qwen2.5:14b
**Temperature:** 0.7
**Max tokens:** 4096
**Evaluation mode:** Leave-one-out (ground truth example excluded from retrieval corpus)

## Per-Query Results

### test_rare_disease
**Query:** I use VEP to annotate my VCF. I have exome data from a rare disease patient and I would like to know if there is a way, if a variant has a high impact in a non-canonical transcript, to keep it and the annotations in the canonical. What options should I enable for clinical reporting?

**Source:** [https://www.biostars.org/p/9517871/](https://www.biostars.org/p/9517871/)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 2 dis | 10 en / 1 dis | 15 en / 2 dis | 15 en / 0 dis |
| Enable precision | 67% | 90% | 80% | 73% |
| Enable recall | 12% | 56% | 75% | 69% |
| Enable F1 | 21% | 69% | 77% | 71% |
| Disable precision | 0% | 100% | 100% | 0% |
| Disable recall | 0% | 10% | 20% | 0% |
| Disable F1 | 0% | 18% | 33% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 0 | 7 |
| Use case detected | unknown (incorrect) | rare_disease_germline (correct) | rare_disease_germline (correct) | rare_disease_germline (correct) |
| Citation rate | 0% (0/3 cited) | 94% (17/18 cited) | 87% (26/30 cited) | 95% (20/21 cited) |

### test_non_human
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 9 en / 0 dis | 20 en / 0 dis | 16 en / 0 dis | 11 en / 0 dis |
| Enable precision | 44% | 35% | 44% | 55% |
| Enable recall | 44% | 78% | 78% | 67% |
| Enable F1 | 44% | 48% | 56% | 60% |
| Disable precision | 0% | 0% | 0% | 0% |
| Disable recall | 0% | 0% | 0% | 0% |
| Disable F1 | 0% | 0% | 0% | 0% |
| Species violations | 2 | 10 | 7 | 3 |
| Conflict violations | 0 | 0 | 0 | 0 |
| Use case detected | non_human (correct) | rare_disease_germline (incorrect) | rare_disease_germline (incorrect) | non_human (correct) |
| Citation rate | 0% (0/0 cited) | 93% (26/28 cited) | 100% (26/26 cited) | 94% (15/16 cited) |

*Species violations (Without KB):* {'clinvar_sv', 'polyphen'}

*Species violations (With KB (keyword)):* {'clinvar_sv', 'clinvar', 'revel', 'cadd', 'gnomad_af', 'mane_select', 'alphamissense', 'af_1kg', 'polyphen', 'spliceai'}

*Species violations (With KB (all examples)):* {'clinvar_sv', 'clinvar', 'cadd', 'mane_select', 'alphamissense', 'polyphen', 'spliceai'}

*Species violations (With KB (semantic)):* {'gnomad_af', 'revel', 'cadd'}

### test_regulatory
**Query:** I have a set of GWAS hits in non-coding regions — mostly intronic and intergenic SNPs. I need to figure out if any overlap regulatory elements and identify possible target genes.

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 9 en / 0 dis | 14 en / 0 dis | 6 en / 0 dis |
| Enable precision | 33% | 44% | 43% | 50% |
| Enable recall | 11% | 44% | 67% | 33% |
| Enable F1 | 17% | 44% | 52% | 40% |
| Disable precision | 0% | 0% | 0% | 0% |
| Disable recall | 0% | 0% | 0% | 0% |
| Disable F1 | 0% | 0% | 0% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 0 | 0 |
| Use case detected | non_human (incorrect) | regulatory_noncoding (correct) | regulatory_noncoding (correct) | regulatory_noncoding (correct) |
| Citation rate | 0% (0/1 cited) | 100% (25/25 cited) | 100% (26/26 cited) | 88% (7/8 cited) |

### test_structural
**Query:** Does VEP do a good job at annotating structural variants from CNVkit, Manta, Lumpy? I have large deletions and duplications and need to identify clinically relevant SVs and filter out common ones.

**Source:** [https://www.biostars.org/p/181819/](https://www.biostars.org/p/181819/)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 1 en / 0 dis | 11 en / 0 dis | 17 en / 0 dis | 5 en / 0 dis |
| Enable precision | 100% | 64% | 47% | 20% |
| Enable recall | 10% | 70% | 80% | 10% |
| Enable F1 | 18% | 67% | 59% | 13% |
| Disable precision | 0% | 0% | 0% | 0% |
| Disable recall | 0% | 0% | 0% | 0% |
| Disable F1 | 0% | 0% | 0% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 0 | 0 |
| Use case detected | structural_variants (correct) | structural_variants (correct) | structural_variants (correct) | structural_variants (correct) |
| Citation rate | 0% (0/1 cited) | 100% (18/18 cited) | 100% (23/23 cited) | 100% (9/9 cited) |

### test_somatic_cancer
**Query:** I'm relatively new to analyzing variants data generated by WES in a cohort of cancer patients. I've called variants using Mutect2 and now I want to annotate these variants with information such as whether they are known variants in dbSNP and their pathogenicity prediction, whether it's known in ExAC etc. What VEP options should I use?

**Source:** [https://www.biostars.org/p/9479508/](https://www.biostars.org/p/9479508/)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 9 en / 0 dis | 14 en / 0 dis | 14 en / 1 dis | 5 en / 0 dis |
| Enable precision | 89% | 93% | 71% | 80% |
| Enable recall | 57% | 93% | 71% | 29% |
| Enable F1 | 70% | 93% | 71% | 42% |
| Disable precision | 0% | 0% | 0% | 0% |
| Disable recall | 0% | 0% | 0% | 0% |
| Disable F1 | 0% | 0% | 0% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 6 | 0 |
| Use case detected | non_human (incorrect) | somatic_cancer (correct) | rare_disease_germline (incorrect) | somatic_cancer (correct) |
| Citation rate | 0% (0/1 cited) | 100% (23/23 cited) | 100% (26/26 cited) | 100% (9/9 cited) |

### test_population_large_vcf
**Query:** I am trying to annotate WGS VCF files through VEP, and even on multi-threading the process is painfully slow. The VCF sizes range between 1-1.5 Gb with about 2 million variants. Apart from gene and functional impact level annotation, I am using VEP plugins for CADD and gnomAD genome based frequencies. What options do you recommend?

**Source:** [https://www.biostars.org/p/336474/](https://www.biostars.org/p/336474/)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 15 en / 0 dis | 12 en / 3 dis | 11 en / 0 dis |
| Enable precision | 33% | 33% | 25% | 45% |
| Enable recall | 14% | 71% | 43% | 71% |
| Enable F1 | 20% | 45% | 32% | 56% |
| Disable precision | 0% | 0% | 67% | 0% |
| Disable recall | 0% | 0% | 11% | 0% |
| Disable F1 | 0% | 0% | 18% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 3 | 0 |
| Use case detected | unknown (incorrect) | population_genetics (correct) | population_genetics (correct) | rare_disease_germline (incorrect) |
| Citation rate | 0% (0/0 cited) | 100% (20/20 cited) | 85% (17/20 cited) | 85% (11/13 cited) |

### test_quick
**Query:** Does anyone know how gnomAD allele frequencies as outputted by Ensembl's VEP should be interpreted? I just want to quickly look up a single variant — rs1799945 — and check if it is clinically significant.

**Source:** [https://www.biostars.org/p/355992/](https://www.biostars.org/p/355992/)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 9 en / 0 dis | 13 en / 1 dis | 3 en / 1 dis |
| Enable precision | 67% | 78% | 77% | 100% |
| Enable recall | 14% | 50% | 71% | 21% |
| Enable F1 | 24% | 61% | 74% | 35% |
| Disable precision | 0% | 0% | 0% | 0% |
| Disable recall | 0% | 0% | 0% | 0% |
| Disable F1 | 0% | 0% | 0% | 0% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 1 | 0 | 0 | 0 |
| Use case detected | non_human (incorrect) | structural_variants (incorrect) | quick_lookup (correct) | quick_lookup (correct) |
| Citation rate | 0% (0/2 cited) | 100% (22/22 cited) | 100% (24/24 cited) | 71% (5/7 cited) |

### test_splice
**Query:** I have a list of intronic variants near splice junctions from whole exome sequencing of rare disease patients. I want to predict which ones might disrupt splicing.

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 11 en / 0 dis | 11 en / 0 dis | 16 en / 2 dis | 10 en / 1 dis |
| Enable precision | 64% | 82% | 56% | 70% |
| Enable recall | 50% | 64% | 64% | 50% |
| Enable F1 | 56% | 72% | 60% | 58% |
| Disable precision | 0% | 0% | 100% | 100% |
| Disable recall | 0% | 0% | 17% | 8% |
| Disable F1 | 0% | 0% | 29% | 15% |
| Species violations | 0 | 0 | 0 | 0 |
| Conflict violations | 0 | 0 | 7 | 0 |
| Use case detected | unknown (incorrect) | rare_disease_germline (correct) | rare_disease_germline (correct) | rare_disease_germline (correct) |
| Citation rate | 0% (0/0 cited) | 100% (24/24 cited) | 90% (26/29 cited) | 89% (16/18 cited) |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) | Δ (keyword vs bare) | Δ (all examples vs bare) | Δ (semantic vs bare) |
|--------|---|---|---|---|---|---|---|
| Enable F1 | 34% | 62% | 60% | 47% | +29% | +27% | +13% |
| Disable F1 | 0% | 2% | 10% | 2% | +2% | +10% | +2% |
| Enable Precision | 62% | 65% | 55% | 62% | +3% | -7% | -0% |
| Enable Recall | 27% | 66% | 69% | 44% | +39% | +42% | +17% |
| Species violations (total) | 2 | 10 | 7 | 3 | +8 | +5 | +1 |
| Conflict violations (total) | 1 | 0 | 16 | 7 | -1 | +15 | +6 |
| Use case accuracy | 2/8 (25%) | 6/8 (75%) | 6/8 (75%) | 7/8 (88%) | +4 | +4 | +5 |
| Citation rate (avg) | 0% | 98% | 95% | 90% | +98% | +95% | +90% |
