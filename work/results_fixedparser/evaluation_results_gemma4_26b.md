# VEP Assistant Evaluation Results

**Date:** 2026-06-08T01:44:52.727342
**Model:** gemma4:26b
**Runs per configuration:** 3
**Seeds:** 42, 43, 44
**Temperature:** 0.7
**Max tokens:** 4096
**Evaluation mode:** Leave-one-out (ground truth example excluded from retrieval corpus)

## Per-Query Results

### test_rare_disease_exome_clinical
**Query:** I have germline exome variants from a patient with a suspected rare Mendelian disorder. I want to identify potentially pathogenic coding variants for clinical interpretation.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 11 en / 1 dis | 17 en / 2 dis | 15 en / 2 dis | 10 en / 2 dis |
| Enable precision | 47% ± 9% | 57% ± 8% | 82% ± 2% | 10% ± 1% |
| Enable recall | 38% ± 8% | 74% ± 4% | 92% ± 8% | 8% ± 0% |
| Enable F1 | 42% ± 8% | 64% ± 5% | 87% ± 3% | 9% ± 0% |
| Enable F1 (priority-weighted) | 44% ± 6% | 70% ± 7% | 89% ± 2% | 11% ± 0% |
| Disable precision | 0% ± 0% | 89% ± 19% | 89% ± 19% | 100% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 93% ± 12% | 93% ± 12% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | rare_disease_germline (33% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 4% | 83% ± 5% | 73% ± 4% |

### test_rare_disease_splice_region
**Query:** A rare disease patient has a variant near an exon-intron boundary. I want to assess whether it disrupts splicing as part of the diagnostic workup.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 12 en / 3 dis | 14 en / 2 dis | 7 en / 2 dis |
| Enable precision | 48% ± 4% | 66% ± 11% | 66% ± 8% | 43% ± 0% |
| Enable recall | 21% ± 5% | 70% ± 5% | 85% ± 5% | 27% ± 0% |
| Enable F1 | 29% ± 4% | 68% ± 8% | 74% ± 5% | 33% ± 0% |
| Enable F1 (priority-weighted) | 30% ± 5% | 70% ± 9% | 77% ± 6% | 32% ± 0% |
| Disable precision | 0% ± 0% | 39% ± 10% | 50% ± 0% | 50% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 56% ± 10% | 67% ± 0% | 67% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 84% ± 4% | 84% ± 4% | 67% ± 4% |

### test_somatic_tumour_wes
**Query:** I'm analysing somatic variants from tumour whole-exome sequencing of cancer patients, called with Mutect2. What VEP options should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 9 en / 0 dis | 15 en / 2 dis | 15 en / 2 dis | 7 en / 2 dis |
| Enable precision | 35% ± 6% | 44% ± 6% | 69% ± 7% | 29% ± 4% |
| Enable recall | 30% ± 10% | 67% ± 15% | 100% ± 0% | 20% ± 0% |
| Enable F1 | 31% ± 4% | 52% ± 8% | 81% ± 5% | 24% ± 1% |
| Enable F1 (priority-weighted) | 40% ± 4% | 58% ± 9% | 85% ± 4% | 14% ± 0% |
| Disable precision | 0% ± 0% | 83% ± 29% | 100% ± 0% | 56% ± 51% |
| Disable recall | 0% ± 0% | 83% ± 29% | 100% ± 0% | 67% ± 58% |
| Disable F1 | 0% ± 0% | 83% ± 29% | 100% ± 0% | 60% ± 53% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 91% ± 8% | 86% ± 7% | 84% ± 4% |

### test_regulatory_noncoding_gwas
**Query:** My GWAS hits are mostly in intergenic and intronic regions. I want to understand their potential regulatory effects.

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 8 en / 3 dis | 7 en / 5 dis | 6 en / 3 dis |
| Enable precision | 37% ± 27% | 61% ± 11% | 79% ± 10% | 32% ± 3% |
| Enable recall | 28% ± 10% | 78% ± 10% | 94% ± 10% | 33% ± 0% |
| Enable F1 | 30% ± 15% | 68% ± 10% | 85% ± 6% | 32% ± 1% |
| Enable F1 (priority-weighted) | 42% ± 15% | 69% ± 10% | 88% ± 5% | 37% ± 1% |
| Disable precision | 0% ± 0% | 58% ± 14% | 65% ± 9% | 0% ± 0% |
| Disable recall | 0% ± 0% | 56% ± 38% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 55% ± 26% | 79% ± 6% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.7 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 81% ± 6% | 83% ± 6% | 87% ± 13% |

### test_population_allele_frequencies
**Query:** I want to annotate a large cohort VCF with population allele frequencies to compare variant frequencies across populations.

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 8 en / 1 dis | 7 en / 3 dis | 8 en / 5 dis | 4 en / 6 dis |
| Enable precision | 20% ± 2% | 77% ± 6% | 88% ± 0% | 100% ± 0% |
| Enable recall | 24% ± 8% | 76% ± 8% | 100% ± 0% | 57% ± 0% |
| Enable F1 | 21% ± 4% | 76% ± 4% | 93% ± 0% | 73% ± 0% |
| Enable F1 (priority-weighted) | 31% ± 8% | 78% ± 4% | 95% ± 0% | 73% ± 0% |
| Disable precision | 0% ± 0% | 0% ± 0% | 65% ± 9% | 0% ± 0% |
| Disable recall | 0% ± 0% | 0% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 0% ± 0% | 79% ± 6% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.7 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 68% ± 8% | 94% ± 5% | 90% ± 8% |

### test_non_human_mouse_crispr
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 2 dis | 9 en / 6 dis | 8 en / 6 dis | 4 en / 5 dis |
| Enable precision | 30% ± 12% | 56% ± 12% | 80% ± 7% | 23% ± 3% |
| Enable recall | 24% ± 8% | 71% ± 0% | 95% ± 8% | 14% ± 0% |
| Enable F1 | 26% ± 10% | 62% ± 8% | 87% ± 7% | 18% ± 1% |
| Enable F1 (priority-weighted) | 38% ± 10% | 69% ± 7% | 91% ± 5% | 21% ± 1% |
| Disable precision | 7% ± 12% | 73% ± 14% | 79% ± 7% | 0% ± 0% |
| Disable recall | 7% ± 12% | 87% ± 12% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 7% ± 12% | 79% ± 12% | 88% ± 4% | 0% ± 0% |
| Species violations | 2.3 | 0.7 | 0.3 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | non_human (33% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 92% ± 0% | 88% ± 4% | 82% ± 17% |

*Species violations (Without KB):* {'cadd', 'polyphen'}

*Species violations (With KB (keyword)):* {'ccds'}

*Species violations (With KB (all examples)):* {'ccds'}

*Species violations (With KB (semantic)):* none

### test_quick_lookup_rsid
**Query:** I just want to look up a single variant by its rsID — its gene, consequence, and clinical significance.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 2 dis | 4 en / 6 dis | 4 en / 6 dis | 2 en / 7 dis |
| Enable precision | 60% ± 37% | 100% ± 0% | 100% ± 0% | 83% ± 29% |
| Enable recall | 33% ± 14% | 100% ± 0% | 100% ± 0% | 42% ± 14% |
| Enable F1 | 37% ± 3% | 100% ± 0% | 100% ± 0% | 56% ± 19% |
| Enable F1 (priority-weighted) | 44% ± 2% | 100% ± 0% | 100% ± 0% | 63% ± 20% |
| Disable precision | 0% ± 0% | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable recall | 0% ± 0% | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 5% | 94% ± 6% | 92% ± 7% |

### test_rare_disease_trio
**Query:** We sequenced a parent-child trio (exome) to find de novo variants causing a paediatric disorder. Which VEP options for clinical interpretation?

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 11 en / 0 dis | 15 en / 2 dis | 14 en / 2 dis | 10 en / 0 dis |
| Enable precision | 49% ± 6% | 64% ± 4% | 88% ± 8% | 13% ± 6% |
| Enable recall | 38% ± 4% | 69% ± 4% | 88% ± 8% | 10% ± 4% |
| Enable F1 | 43% ± 2% | 67% ± 4% | 88% ± 8% | 11% ± 5% |
| Enable F1 (priority-weighted) | 45% ± 6% | 71% ± 3% | 90% ± 8% | 14% ± 6% |
| Disable precision | 0% ± 0% | 89% ± 19% | 89% ± 19% | 0% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 93% ± 12% | 93% ± 12% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | non_human (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 3% | 85% ± 3% | 65% ± 6% |

### test_somatic_tumor_only
**Query:** Tumor-only WES with no matched normal. I need to annotate somatic candidates and aggressively filter likely germline variants by population frequency.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 1 dis | 12 en / 2 dis | 12 en / 2 dis | 7 en / 2 dis |
| Enable precision | 48% ± 3% | 78% ± 9% | 90% ± 12% | 57% ± 0% |
| Enable recall | 30% ± 5% | 82% ± 9% | 94% ± 5% | 36% ± 0% |
| Enable F1 | 37% ± 3% | 79% ± 1% | 91% ± 7% | 44% ± 0% |
| Enable F1 (priority-weighted) | 42% ± 4% | 84% ± 4% | 94% ± 6% | 42% ± 0% |
| Disable precision | 0% ± 0% | 100% ± 0% | 100% ± 0% | 44% ± 10% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 50% ± 0% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 100% ± 0% | 47% ± 6% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | non_human (0% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 3% | 86% ± 1% | 83% ± 15% |

### test_somatic_ctdna
**Query:** ctDNA / liquid-biopsy somatic variants from a cancer patient, low VAF. Annotate for clinical actionability.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 0 dis | 13 en / 2 dis | 12 en / 2 dis | 9 en / 2 dis |
| Enable precision | 55% ± 21% | 63% ± 5% | 76% ± 11% | 23% ± 3% |
| Enable recall | 33% ± 12% | 80% ± 0% | 93% ± 6% | 20% ± 0% |
| Enable F1 | 39% ± 10% | 71% ± 3% | 84% ± 8% | 21% ± 1% |
| Enable F1 (priority-weighted) | 47% ± 9% | 78% ± 6% | 84% ± 9% | 25% ± 2% |
| Disable precision | 0% ± 0% | 100% ± 0% | 100% ± 0% | 17% ± 29% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 33% ± 58% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 100% ± 0% | 22% ± 38% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 3.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 84% ± 2% | 81% ± 2% | 62% ± 0% |

### test_regulatory_promoter
**Query:** Variants in promoter/enhancer regions from ATAC-seq peaks - which target genes and regulatory features do they hit?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 8 en / 4 dis | 7 en / 4 dis | 4 en / 5 dis |
| Enable precision | 33% ± 33% | 64% ± 19% | 100% ± 0% | 23% ± 3% |
| Enable recall | 19% ± 16% | 71% ± 14% | 95% ± 8% | 14% ± 0% |
| Enable F1 | 24% ± 21% | 67% ± 17% | 97% ± 4% | 18% ± 1% |
| Enable F1 (priority-weighted) | 31% ± 27% | 68% ± 14% | 98% ± 4% | 24% ± 1% |
| Disable precision | 33% ± 58% | 67% ± 8% | 78% ± 20% | 19% ± 5% |
| Disable recall | 11% ± 19% | 89% ± 19% | 100% ± 0% | 33% ± 0% |
| Disable F1 | 17% ± 29% | 76% ± 10% | 87% ± 13% | 24% ± 4% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 79% ± 1% | 71% ± 11% | 89% ± 19% |

### test_regulatory_tfbs
**Query:** Do my non-coding GWAS SNPs overlap transcription factor binding sites or other regulatory features?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 8 en / 3 dis | 7 en / 4 dis | 6 en / 4 dis |
| Enable precision | 33% ± 0% | 58% ± 7% | 71% ± 0% | 32% ± 3% |
| Enable recall | 27% ± 12% | 93% ± 12% | 100% ± 0% | 40% ± 0% |
| Enable F1 | 29% ± 7% | 72% ± 9% | 83% ± 0% | 35% ± 2% |
| Enable F1 (priority-weighted) | 40% ± 10% | 76% ± 12% | 86% ± 0% | 39% ± 2% |
| Disable precision | 0% ± 0% | 92% ± 14% | 75% ± 0% | 17% ± 29% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 22% ± 38% |
| Disable F1 | 0% ± 0% | 95% ± 8% | 86% ± 0% | 19% ± 33% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.3 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 6% | 78% ± 4% | 95% ± 8% |

### test_population_ancestry
**Query:** Comparing variant allele frequencies across continental populations in a cohort. Which frequency annotations should I turn on?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 1 dis | 6 en / 2 dis | 7 en / 4 dis | 5 en / 2 dis |
| Enable precision | 48% ± 4% | 95% ± 8% | 96% ± 7% | 100% ± 0% |
| Enable recall | 29% ± 14% | 86% ± 0% | 90% ± 8% | 71% ± 0% |
| Enable F1 | 34% ± 11% | 90% ± 4% | 93% ± 1% | 83% ± 0% |
| Enable F1 (priority-weighted) | 41% ± 15% | 91% ± 1% | 93% ± 2% | 85% ± 0% |
| Disable precision | 22% ± 38% | 67% ± 58% | 83% ± 14% | 0% ± 0% |
| Disable recall | 22% ± 38% | 67% ± 58% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 22% ± 38% | 67% ± 58% | 90% ± 8% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 2% | 93% ± 12% | 100% ± 0% |

### test_population_large_wgs
**Query:** Annotating a very large WGS cohort VCF (~2M variants) is painfully slow. How do I keep it efficient while still getting gene and frequency annotation?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 1 dis | 4 en / 4 dis | 8 en / 6 dis | 1 en / 9 dis |
| Enable precision | 20% ± 5% | 78% ± 19% | 57% ± 8% | 100% ± 0% |
| Enable recall | 27% ± 12% | 60% ± 35% | 87% ± 12% | 20% ± 0% |
| Enable F1 | 22% ± 7% | 60% ± 23% | 69% ± 6% | 33% ± 0% |
| Enable F1 (priority-weighted) | 34% ± 7% | 59% ± 17% | 65% ± 4% | 29% ± 0% |
| Disable precision | 0% ± 0% | 19% ± 20% | 29% ± 8% | 22% ± 0% |
| Disable recall | 0% ± 0% | 33% ± 33% | 56% ± 19% | 67% ± 0% |
| Disable F1 | 0% ± 0% | 24% ± 25% | 38% ± 11% | 33% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (67% correct) | population_genetics (67% correct) | quick_lookup (33% correct) |
| Citation rate | 0% ± 0% | 53% ± 46% | 83% ± 11% | 94% ± 10% |

### test_structural_longread
**Query:** Large deletions and duplications from long-read WGS (Sniffles). Which genes and regulatory features are disrupted, and how do I filter common SVs?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 7 en / 4 dis | 7 en / 5 dis | 5 en / 4 dis |
| Enable precision | 49% ± 11% | 73% ± 2% | 90% ± 8% | 67% ± 8% |
| Enable recall | 38% ± 8% | 76% ± 8% | 86% ± 0% | 48% ± 8% |
| Enable F1 | 42% ± 7% | 74% ± 5% | 88% ± 4% | 55% ± 6% |
| Enable F1 (priority-weighted) | 50% ± 12% | 80% ± 8% | 92% ± 4% | 60% ± 9% |
| Disable precision | 0% ± 0% | 100% ± 0% | 87% ± 12% | 28% ± 5% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 25% ± 0% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 93% ± 6% | 26% ± 2% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.7 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | structural_variants (100% correct) | structural_variants (100% correct) | structural_variants (100% correct) |
| Citation rate | 0% ± 0% | 94% ± 6% | 83% ± 7% | 90% ± 8% |

### test_structural_cnv
**Query:** CNV calls from a SNP array - which genes do the copy-number gains/losses affect, and are they common in the population?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 7 en / 3 dis | 6 en / 5 dis | 6 en / 3 dis |
| Enable precision | 21% ± 19% | 60% ± 5% | 74% ± 9% | 32% ± 3% |
| Enable recall | 27% ± 31% | 80% ± 0% | 93% ± 12% | 40% ± 0% |
| Enable F1 | 23% ± 23% | 69% ± 3% | 82% ± 9% | 35% ± 2% |
| Enable F1 (priority-weighted) | 32% ± 31% | 72% ± 2% | 90% ± 7% | 47% ± 1% |
| Disable precision | 0% ± 0% | 100% ± 0% | 87% ± 12% | 0% ± 0% |
| Disable recall | 0% ± 0% | 83% ± 14% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 90% ± 8% | 93% ± 6% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | population_genetics (33% correct) | structural_variants (67% correct) | structural_variants (100% correct) | structural_variants (33% correct) |
| Citation rate | 0% ± 0% | 93% ± 6% | 94% ± 6% | 94% ± 10% |

### test_structural_clinical
**Query:** Clinically interpret structural variants (dels/dups) from a rare-disease WGS case - pathogenic vs benign, filter common ones.

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 1 dis | 8 en / 4 dis | 9 en / 4 dis | 5 en / 5 dis |
| Enable precision | 20% ± 0% | 45% ± 12% | 66% ± 10% | 52% ± 4% |
| Enable recall | 22% ± 10% | 61% ± 10% | 94% ± 10% | 44% ± 19% |
| Enable F1 | 20% ± 4% | 52% ± 11% | 77% ± 10% | 47% ± 12% |
| Enable F1 (priority-weighted) | 32% ± 4% | 59% ± 7% | 87% ± 7% | 57% ± 17% |
| Disable precision | 33% ± 58% | 62% ± 4% | 70% ± 9% | 8% ± 14% |
| Disable recall | 11% ± 19% | 89% ± 19% | 100% ± 0% | 11% ± 19% |
| Disable F1 | 17% ± 29% | 72% ± 5% | 82% ± 6% | 10% ± 16% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | rare_disease_germline (67% correct) | structural_variants (100% correct) | structural_variants (67% correct) |
| Citation rate | 0% ± 0% | 95% ± 4% | 89% ± 5% | 86% ± 13% |

### test_non_human_zebrafish
**Query:** Zebrafish (Danio rerio) variants from a mutagenesis screen against GRCz11. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 10 en / 0 dis | 8 en / 9 dis | 8 en / 6 dis | 3 en / 7 dis |
| Enable precision | 27% ± 14% | 64% ± 17% | 84% ± 6% | 78% ± 19% |
| Enable recall | 33% ± 8% | 71% ± 14% | 100% ± 0% | 29% ± 0% |
| Enable F1 | 29% ± 12% | 67% ± 15% | 91% ± 3% | 41% ± 3% |
| Enable F1 (priority-weighted) | 42% ± 13% | 69% ± 14% | 94% ± 4% | 43% ± 1% |
| Disable precision | 0% ± 0% | 55% ± 9% | 79% ± 7% | 0% ± 0% |
| Disable recall | 0% ± 0% | 93% ± 12% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 69% ± 7% | 88% ± 4% | 0% ± 0% |
| Species violations | 4.3 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 3.7 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (67% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 98% ± 4% | 95% ± 4% | 78% ± 20% |

*Species violations (Without KB):* {'cadd', 'spliceai', 'mutfunc', 'gnomad_sv', 'polyphen'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_non_human_rat
**Query:** Rat (Rattus norvegicus) WGS variants from a knockout model. Which VEP options apply?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 10 en / 1 dis | 9 en / 10 dis | 8 en / 6 dis | 3 en / 6 dis |
| Enable precision | 22% ± 4% | 62% ± 11% | 84% ± 6% | 61% ± 10% |
| Enable recall | 33% ± 8% | 81% ± 22% | 100% ± 0% | 29% ± 0% |
| Enable F1 | 27% ± 6% | 69% ± 12% | 91% ± 3% | 39% ± 2% |
| Enable F1 (priority-weighted) | 40% ± 7% | 71% ± 12% | 93% ± 3% | 41% ± 1% |
| Disable precision | 0% ± 0% | 51% ± 20% | 85% ± 14% | 0% ± 0% |
| Disable recall | 0% ± 0% | 93% ± 12% | 93% ± 12% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 65% ± 20% | 88% ± 4% | 0% ± 0% |
| Species violations | 4.3 | 0.3 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (33% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 98% ± 3% | 92% ± 8% | 90% ± 16% |

*Species violations (Without KB):* {'cadd', 'clinvar', 'frequency', 'spliceai'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_quick_lookup_batch
**Query:** I have a short list of rsIDs and just want their gene, consequence, and ClinVar significance - nothing heavy.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 2 dis | 4 en / 3 dis | 4 en / 5 dis | 3 en / 4 dis |
| Enable precision | 11% ± 10% | 100% ± 0% | 100% ± 0% | 89% ± 19% |
| Enable recall | 17% ± 14% | 100% ± 0% | 100% ± 0% | 58% ± 14% |
| Enable F1 | 13% ± 12% | 100% ± 0% | 100% ± 0% | 70% ± 15% |
| Enable F1 (priority-weighted) | 19% ± 17% | 100% ± 0% | 100% ± 0% | 77% ± 11% |
| Disable precision | 17% ± 29% | 33% ± 0% | 93% ± 12% | 28% ± 5% |
| Disable recall | 11% ± 19% | 17% ± 0% | 72% ± 10% | 17% ± 0% |
| Disable F1 | 13% ± 23% | 22% ± 0% | 81% ± 9% | 21% ± 1% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 1% | 87% ± 4% | 83% ± 17% |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) | Δ (keyword vs bare) | Δ (all examples vs bare) | Δ (semantic vs bare) |
|--------|---|---|---|---|---|---|---|
| Enable F1 | 30% | 71% | 87% | 39% | +41% | +57% | +9% |
| Enable F1 (priority-weighted) | 38% | 75% | 90% | 42% | +36% | +51% | +3% |
| Disable F1 | 4% | 67% | 81% | 21% | +63% | +77% | +18% |
| Enable Precision | 36% | 68% | 82% | 52% | +33% | +46% | +17% |
| Enable Recall | 29% | 77% | 94% | 33% | +49% | +66% | +4% |
| Species violations (total) | 11 | 1 | 1 | 0 | -10 | -10 | -11 |
| Conflict violations (total) | 7 | 0 | 0 | 0 | -7 | -7 | -7 |
| Use case accuracy | 5/20 (25%) | 20/20 (100%) | 20/20 (100%) | 18/20 (90%) | +15 | +15 | +13 |
| Citation rate (avg) | 0% | 86% | 86% | 84% | +86% | +86% | +84% |
