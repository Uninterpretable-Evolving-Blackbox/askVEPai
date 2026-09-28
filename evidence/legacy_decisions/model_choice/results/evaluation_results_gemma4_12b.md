# VEP Assistant Evaluation Results

**Date:** 2026-06-22T02:29:17.501815
**Model:** gemma4:12b
**Runs per configuration:** 5
**Seeds:** 42, 43, 44, 45, 46
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
| Options detected | 10 en / 0 dis | 23 en / 4 dis | 17 en / 2 dis | 7 en / 1 dis |
| Enable precision | 61% ± 14% | 42% ± 8% | 56% ± 7% | 12% ± 1% |
| Enable recall | 46% ± 0% | 72% ± 9% | 71% ± 29% | 6% ± 3% |
| Enable F1 | 52% ± 5% | 53% ± 7% | 59% ± 14% | 9% ± 0% |
| Enable F1 (priority-weighted) | 53% ± 5% | 59% ± 7% | 64% ± 15% | 11% ± 0% |
| Disable precision | n/a | 61% ± 24% | 72% ± 25% | 22% ± 38% |
| Disable recall | 0% ± 0% | 100% ± 0% | 60% ± 55% | 20% ± 45% |
| Disable F1 | n/a | 74% ± 17% | 82% ± 17% | 27% ± 46% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 2.2 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (40% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (80% correct) |
| Citation rate | 0% ± 0% | 91% ± 7% | 97% ± 5% | 80% ± 45% |

### test_rare_disease_splice_region
**Query:** A rare disease patient has a variant near an exon-intron boundary. I want to assess whether it disrupts splicing as part of the diagnostic workup.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 1 dis | 15 en / 4 dis | 15 en / 2 dis | 7 en / 3 dis |
| Enable precision | 54% ± 36% | 57% ± 8% | 62% ± 7% | 42% ± 5% |
| Enable recall | 22% ± 14% | 76% ± 5% | 82% ± 9% | 27% ± 0% |
| Enable F1 | 30% ± 17% | 65% ± 7% | 70% ± 5% | 33% ± 2% |
| Enable F1 (priority-weighted) | 29% ± 17% | 68% ± 7% | 74% ± 4% | 32% ± 1% |
| Disable precision | 0% ± 0% | 28% ± 13% | 46% ± 8% | 12% ± 16% |
| Disable recall | 0% ± 0% | 100% ± 0% | 80% ± 45% | 40% ± 55% |
| Disable F1 | 0% ± 0% | 43% ± 14% | 62% ± 8% | 18% ± 25% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.8 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 12% | 91% ± 9% | 96% ± 9% |

### test_somatic_tumour_wes
**Query:** I'm analysing somatic variants from tumour whole-exome sequencing of cancer patients, called with Mutect2. What VEP options should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 10 en / 2 dis | 9 en / 2 dis | 5 en / 2 dis |
| Enable precision | 41% ± 19% | 41% ± 7% | 79% ± 5% | 34% ± 5% |
| Enable recall | 24% ± 19% | 42% ± 34% | 70% ± 40% | 16% ± 9% |
| Enable F1 | 29% ± 20% | 43% ± 19% | 83% ± 6% | 25% ± 1% |
| Enable F1 (priority-weighted) | 38% ± 21% | 46% ± 21% | 85% ± 9% | 14% ± 0% |
| Disable precision | n/a | 52% ± 13% | 79% ± 25% | 13% ± 23% |
| Disable recall | 0% ± 0% | 60% ± 55% | 80% ± 45% | 20% ± 45% |
| Disable F1 | n/a | 68% ± 11% | 87% ± 16% | 19% ± 33% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (80% correct) | unknown (80% correct) | somatic_cancer (80% correct) |
| Citation rate | 0% ± 0% | 73% ± 42% | 70% ± 40% | 76% ± 43% |

### test_regulatory_noncoding_gwas
**Query:** My GWAS hits are mostly in intergenic and intronic regions. I want to understand their potential regulatory effects.

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 8 en / 3 dis | 10 en / 5 dis | 6 en / 3 dis |
| Enable precision | 40% ± 18% | 41% ± 4% | 56% ± 6% | 20% ± 3% |
| Enable recall | 30% ± 7% | 57% ± 32% | 93% ± 9% | 20% ± 7% |
| Enable F1 | 33% ± 9% | 52% ± 3% | 70% ± 6% | 20% ± 5% |
| Enable F1 (priority-weighted) | 46% ± 9% | 53% ± 3% | 72% ± 7% | 26% ± 5% |
| Disable precision | n/a | 42% ± 16% | 59% ± 10% | 0% ± 0% |
| Disable recall | 0% ± 0% | 40% ± 37% | 100% ± 0% | 0% ± 0% |
| Disable F1 | n/a | 44% ± 21% | 74% ± 8% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.4 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (80% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 74% ± 42% | 91% ± 9% | 94% ± 8% |

### test_population_allele_frequencies
**Query:** I want to annotate a large cohort VCF with population allele frequencies to compare variant frequencies across populations.

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 4 en / 3 dis | 7 en / 6 dis | 4 en / 6 dis |
| Enable precision | 26% ± 18% | 96% ± 8% | 86% ± 2% | 95% ± 11% |
| Enable recall | 14% ± 10% | 57% ± 32% | 91% ± 13% | 51% ± 8% |
| Enable F1 | 18% ± 13% | 82% ± 3% | 89% ± 7% | 67% ± 9% |
| Enable F1 (priority-weighted) | 23% ± 15% | 80% ± 2% | 90% ± 7% | 67% ± 9% |
| Disable precision | 0% ± 0% | 23% ± 29% | 53% ± 7% | 0% ± 0% |
| Disable recall | 0% ± 0% | 27% ± 43% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 27% ± 36% | 69% ± 6% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | unknown (80% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 70% ± 39% | 95% ± 4% | 89% ± 11% |

### test_non_human_mouse_crispr
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 10 en / 9 dis | 12 en / 9 dis | 2 en / 6 dis |
| Enable precision | 34% ± 11% | 65% ± 12% | 52% ± 20% | 38% ± 15% |
| Enable recall | 14% ± 0% | 89% ± 12% | 83% ± 12% | 11% ± 6% |
| Enable F1 | 20% ± 2% | 74% ± 10% | 63% ± 17% | 20% ± 3% |
| Enable F1 (priority-weighted) | 31% ± 2% | 76% ± 10% | 68% ± 15% | 22% ± 2% |
| Disable precision | 0% ± 0% | 54% ± 17% | 60% ± 15% | 0% ± 0% |
| Disable recall | 0% ± 0% | 96% ± 9% | 96% ± 9% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 68% ± 14% | 73% ± 13% | 0% ± 0% |
| Species violations | 0.8 | 0.2 | 0.8 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (20% correct) | non_human (80% correct) | non_human (80% correct) | population_genetics (40% correct) |
| Citation rate | 0% ± 0% | 90% ± 5% | 100% ± 0% | 80% ± 45% |

*Species violations (Without KB):* none

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* {'ccds'}

*Species violations (With KB (semantic)):* none

### test_quick_lookup_rsid
**Query:** I just want to look up a single variant by its rsID — its gene, consequence, and clinical significance.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 1 en / 0 dis | 4 en / 5 dis | 4 en / 6 dis | 2 en / 8 dis |
| Enable precision | 42% ± 52% | 89% ± 21% | 92% ± 18% | 90% ± 22% |
| Enable recall | 10% ± 14% | 80% ± 45% | 90% ± 14% | 50% ± 0% |
| Enable F1 | 22% ± 20% | 93% ± 14% | 90% ± 15% | 63% ± 7% |
| Enable F1 (priority-weighted) | 26% ± 24% | 95% ± 10% | 90% ± 15% | 72% ± 7% |
| Disable precision | n/a | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable recall | n/a | n/a | n/a | n/a |
| Disable F1 | n/a | n/a | n/a | n/a |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | unknown (60% correct) | quick_lookup (80% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 74% ± 41% | 92% ± 7% | 98% ± 6% |

### test_rare_disease_trio
**Query:** We sequenced a parent-child trio (exome) to find de novo variants causing a paediatric disorder. Which VEP options for clinical interpretation?

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 0 dis | 21 en / 3 dis | 16 en / 2 dis | 9 en / 1 dis |
| Enable precision | 68% ± 9% | 57% ± 10% | 70% ± 9% | 11% ± 1% |
| Enable recall | 34% ± 11% | 81% ± 4% | 81% ± 6% | 7% ± 0% |
| Enable F1 | 45% ± 11% | 67% ± 8% | 75% ± 7% | 9% ± 0% |
| Enable F1 (priority-weighted) | 44% ± 13% | 70% ± 8% | 79% ± 7% | 11% ± 0% |
| Disable precision | 0% ± 0% | 78% ± 30% | 77% ± 29% | 33% ± 58% |
| Disable recall | 0% ± 0% | 100% ± 0% | 80% ± 45% | 20% ± 45% |
| Disable F1 | 0% ± 0% | 85% ± 21% | 84% ± 20% | 33% ± 58% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 93% ± 8% | 92% ± 5% | 89% ± 12% |

### test_somatic_tumor_only
**Query:** Tumor-only WES with no matched normal. I need to annotate somatic candidates and aggressively filter likely germline variants by population frequency.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 10 en / 2 dis | 9 en / 2 dis | 7 en / 2 dis |
| Enable precision | 46% ± 12% | 87% ± 9% | 87% ± 9% | 59% ± 4% |
| Enable recall | 24% ± 17% | 78% ± 8% | 71% ± 40% | 36% ± 0% |
| Enable F1 | 30% ± 17% | 82% ± 5% | 88% ± 6% | 45% ± 1% |
| Enable F1 (priority-weighted) | 37% ± 17% | 83% ± 5% | 90% ± 6% | 43% ± 1% |
| Disable precision | n/a | 100% ± 0% | 92% ± 17% | 67% ± 31% |
| Disable recall | 0% ± 0% | 80% ± 45% | 80% ± 45% | 50% ± 0% |
| Disable F1 | n/a | 100% ± 0% | 95% ± 10% | 55% ± 12% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (60% correct) | somatic_cancer (100% correct) | somatic_cancer (80% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 2% | 75% ± 42% | 89% ± 6% |

### test_somatic_ctdna
**Query:** ctDNA / liquid-biopsy somatic variants from a cancer patient, low VAF. Annotate for clinical actionability.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 11 en / 3 dis | 11 en / 2 dis | 6 en / 5 dis |
| Enable precision | 64% ± 21% | 75% ± 22% | 73% ± 20% | 38% ± 8% |
| Enable recall | 20% ± 17% | 82% ± 13% | 76% ± 43% | 22% ± 4% |
| Enable F1 | 27% ± 16% | 78% ± 18% | 82% ± 13% | 28% ± 6% |
| Enable F1 (priority-weighted) | 35% ± 16% | 78% ± 15% | 84% ± 11% | 29% ± 7% |
| Disable precision | n/a | 88% ± 27% | 85% ± 30% | 6% ± 13% |
| Disable recall | 0% ± 0% | 100% ± 0% | 80% ± 45% | 20% ± 45% |
| Disable F1 | n/a | 91% ± 19% | 89% ± 21% | 9% ± 20% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (20% correct) | somatic_cancer (100% correct) | somatic_cancer (80% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 91% ± 9% | 70% ± 40% | 77% ± 17% |

### test_regulatory_promoter
**Query:** Variants in promoter/enhancer regions from ATAC-seq peaks - which target genes and regulatory features do they hit?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 9 en / 7 dis | 8 en / 5 dis | 3 en / 5 dis |
| Enable precision | 74% ± 34% | 56% ± 10% | 81% ± 16% | 25% ± 0% |
| Enable recall | 20% ± 13% | 69% ± 12% | 86% ± 14% | 11% ± 6% |
| Enable F1 | 35% ± 9% | 61% ± 8% | 82% ± 12% | 18% ± 0% |
| Enable F1 (priority-weighted) | 42% ± 7% | 62% ± 8% | 83% ± 12% | 24% ± 0% |
| Disable precision | n/a | 46% ± 4% | 58% ± 4% | 17% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 27% ± 15% |
| Disable F1 | n/a | 63% ± 4% | 73% ± 4% | 22% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | unknown (80% correct) |
| Citation rate | 0% ± 0% | 95% ± 9% | 87% ± 8% | 76% ± 43% |

### test_regulatory_tfbs
**Query:** Do my non-coding GWAS SNPs overlap transcription factor binding sites or other regulatory features?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 8 en / 5 dis | 6 en / 4 dis | 5 en / 4 dis |
| Enable precision | 40% ± 22% | 55% ± 14% | 62% ± 0% | 40% ± 8% |
| Enable recall | 24% ± 17% | 80% ± 0% | 80% ± 45% | 40% ± 0% |
| Enable F1 | 29% ± 18% | 64% ± 11% | 77% ± 0% | 40% ± 4% |
| Enable F1 (priority-weighted) | 38% ± 23% | 65% ± 9% | 80% ± 0% | 43% ± 4% |
| Disable precision | 100% ± 0% | 66% ± 23% | 60% ± 0% | 0% ± 0% |
| Disable recall | 7% ± 15% | 100% ± 0% | 80% ± 45% | 0% ± 0% |
| Disable F1 | 50% ± 0% | 77% ± 16% | 75% ± 0% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | unknown (80% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 98% ± 4% | 75% ± 42% | 93% ± 10% |

### test_population_ancestry
**Query:** Comparing variant allele frequencies across continental populations in a cohort. Which frequency annotations should I turn on?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 6 en / 5 dis | 7 en / 5 dis | 5 en / 5 dis |
| Enable precision | 33% ± 20% | 100% ± 0% | 100% ± 0% | 100% ± 0% |
| Enable recall | 20% ± 16% | 89% ± 6% | 94% ± 8% | 71% ± 0% |
| Enable F1 | 23% ± 15% | 94% ± 3% | 97% ± 4% | 83% ± 0% |
| Enable F1 (priority-weighted) | 29% ± 20% | 93% ± 4% | 97% ± 5% | 85% ± 0% |
| Disable precision | n/a | 57% ± 7% | 58% ± 4% | 0% ± 0% |
| Disable recall | 0% ± 0% | 87% ± 18% | 100% ± 0% | 0% ± 0% |
| Disable F1 | n/a | 68% ± 7% | 73% ± 4% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.2 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (20% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (80% correct) |
| Citation rate | 0% ± 0% | 92% ± 8% | 98% ± 4% | 98% ± 6% |

### test_population_large_wgs
**Query:** Annotating a very large WGS cohort VCF (~2M variants) is painfully slow. How do I keep it efficient while still getting gene and frequency annotation?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 7 en / 6 dis | 7 en / 5 dis | 1 en / 9 dis |
| Enable precision | 31% ± 12% | 46% ± 6% | 40% ± 8% | 87% ± 30% |
| Enable recall | 20% ± 0% | 64% ± 9% | 56% ± 9% | 20% ± 0% |
| Enable F1 | 24% ± 3% | 53% ± 6% | 47% ± 8% | 32% ± 4% |
| Enable F1 (priority-weighted) | 33% ± 3% | 51% ± 6% | 46% ± 7% | 28% ± 2% |
| Disable precision | n/a | 26% ± 11% | 17% ± 10% | 18% ± 10% |
| Disable recall | 0% ± 0% | 53% ± 30% | 33% ± 24% | 53% ± 30% |
| Disable F1 | n/a | 34% ± 16% | 22% ± 14% | 27% ± 15% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (0% correct) | population_genetics (100% correct) | quick_lookup (0% correct) |
| Citation rate | 0% ± 0% | 98% ± 3% | 90% ± 9% | 97% ± 7% |

### test_structural_longread
**Query:** Large deletions and duplications from long-read WGS (Sniffles). Which genes and regulatory features are disrupted, and how do I filter common SVs?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 6 en / 6 dis | 9 en / 7 dis | 6 en / 4 dis |
| Enable precision | 49% ± 35% | 73% ± 11% | 68% ± 8% | 50% ± 0% |
| Enable recall | 31% ± 19% | 60% ± 12% | 83% ± 6% | 43% ± 0% |
| Enable F1 | 37% ± 22% | 65% ± 11% | 74% ± 7% | 46% ± 0% |
| Enable F1 (priority-weighted) | 46% ± 28% | 64% ± 13% | 81% ± 8% | 50% ± 0% |
| Disable precision | n/a | 61% ± 13% | 65% ± 17% | 25% ± 0% |
| Disable recall | 0% ± 0% | 90% ± 14% | 100% ± 0% | 25% ± 0% |
| Disable F1 | n/a | 72% ± 12% | 78% ± 13% | 25% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | regulatory_noncoding (60% correct) | regulatory_noncoding (80% correct) | regulatory_noncoding (40% correct) |
| Citation rate | 0% ± 0% | 84% ± 10% | 89% ± 4% | 91% ± 8% |

### test_structural_cnv
**Query:** CNV calls from a SNP array - which genes do the copy-number gains/losses affect, and are they common in the population?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 1 en / 0 dis | 6 en / 5 dis | 6 en / 5 dis | 5 en / 3 dis |
| Enable precision | 29% ± 34% | 55% ± 15% | 73% ± 9% | 38% ± 9% |
| Enable recall | 12% ± 18% | 60% ± 37% | 92% ± 11% | 36% ± 9% |
| Enable F1 | 20% ± 24% | 61% ± 8% | 81% ± 7% | 37% ± 9% |
| Enable F1 (priority-weighted) | 27% ± 33% | 66% ± 13% | 84% ± 9% | 47% ± 8% |
| Disable precision | n/a | 70% ± 25% | 69% ± 15% | 0% ± 0% |
| Disable recall | 0% ± 0% | 75% ± 43% | 85% ± 34% | 0% ± 0% |
| Disable F1 | n/a | 77% ± 13% | 75% ± 24% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | population_genetics (20% correct) | unknown (60% correct) | structural_variants (80% correct) | structural_variants (20% correct) |
| Citation rate | 0% ± 0% | 74% ± 42% | 100% ± 0% | 97% ± 7% |

### test_structural_clinical
**Query:** Clinically interpret structural variants (dels/dups) from a rare-disease WGS case - pathogenic vs benign, filter common ones.

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 6 en / 5 dis | 9 en / 6 dis | 3 en / 5 dis |
| Enable precision | 33% ± 20% | 69% ± 22% | 68% ± 20% | 50% ± 0% |
| Enable recall | 27% ± 22% | 60% ± 35% | 90% ± 9% | 27% ± 15% |
| Enable F1 | 27% ± 19% | 70% ± 10% | 76% ± 16% | 40% ± 0% |
| Enable F1 (priority-weighted) | 38% ± 26% | 74% ± 10% | 82% ± 12% | 48% ± 0% |
| Disable precision | n/a | 38% ± 11% | 53% ± 7% | 0% ± 0% |
| Disable recall | 0% ± 0% | 60% ± 55% | 100% ± 0% | 0% ± 0% |
| Disable F1 | n/a | 55% ± 12% | 69% ± 6% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | structural_variants (80% correct) | structural_variants (100% correct) | unknown (20% correct) |
| Citation rate | 0% ± 0% | 76% ± 42% | 93% ± 4% | 75% ± 43% |

### test_non_human_zebrafish
**Query:** Zebrafish (Danio rerio) variants from a mutagenesis screen against GRCz11. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 7 en / 5 dis | 11 en / 9 dis | 2 en / 8 dis |
| Enable precision | 36% ± 22% | 45% ± 9% | 68% ± 21% | 87% ± 18% |
| Enable recall | 20% ± 8% | 46% ± 42% | 97% ± 6% | 29% ± 0% |
| Enable F1 | 25% ± 11% | 56% ± 9% | 79% ± 15% | 43% ± 2% |
| Enable F1 (priority-weighted) | 36% ± 11% | 60% ± 8% | 83% ± 12% | 44% ± 1% |
| Disable precision | 0% ± 0% | 52% ± 17% | 62% ± 26% | 0% ± 0% |
| Disable recall | 0% ± 0% | 52% ± 48% | 96% ± 9% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 65% ± 16% | 73% ± 21% | 0% ± 0% |
| Species violations | 0.8 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (60% correct) | non_human (60% correct) | somatic_cancer (80% correct) | non_human (40% correct) |
| Citation rate | 0% ± 0% | 56% ± 51% | 96% ± 7% | 95% ± 11% |

*Species violations (Without KB):* {'gnomad_sv'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_non_human_rat
**Query:** Rat (Rattus norvegicus) WGS variants from a knockout model. Which VEP options apply?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 7 en / 7 dis | 9 en / 13 dis | 2 en / 6 dis |
| Enable precision | 37% ± 7% | 48% ± 3% | 74% ± 18% | 71% ± 21% |
| Enable recall | 14% ± 0% | 46% ± 44% | 94% ± 8% | 23% ± 13% |
| Enable F1 | 20% ± 1% | 59% ± 7% | 82% ± 14% | 40% ± 3% |
| Enable F1 (priority-weighted) | 32% ± 1% | 62% ± 10% | 86% ± 12% | 42% ± 2% |
| Disable precision | 0% ± 0% | 43% ± 11% | 48% ± 22% | 0% ± 0% |
| Disable recall | 0% ± 0% | 56% ± 52% | 96% ± 9% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 58% ± 12% | 62% ± 22% | 0% ± 0% |
| Species violations | 0.4 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 0.0 | 0.0 | 0.0 |
| Use case detected | non_human (80% correct) | unknown (60% correct) | non_human (100% correct) | non_human (40% correct) |
| Citation rate | 0% ± 0% | 60% ± 55% | 95% ± 5% | 77% ± 43% |

### test_quick_lookup_batch
**Query:** I have a short list of rsIDs and just want their gene, consequence, and ClinVar significance - nothing heavy.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 1 en / 1 dis | 4 en / 15 dis | 4 en / 5 dis | 3 en / 4 dis |
| Enable precision | 44% ± 10% | 85% ± 21% | 100% ± 0% | 50% ± 0% |
| Enable recall | 15% ± 14% | 85% ± 34% | 100% ± 0% | 40% ± 22% |
| Enable F1 | 32% ± 3% | 79% ± 25% | 100% ± 0% | 50% ± 0% |
| Enable F1 (priority-weighted) | 36% ± 2% | 78% ± 27% | 100% ± 0% | 57% ± 0% |
| Disable precision | 22% ± 38% | 56% ± 30% | 63% ± 13% | 19% ± 4% |
| Disable recall | 7% ± 15% | 67% ± 24% | 53% ± 22% | 13% ± 7% |
| Disable F1 | 15% ± 26% | 54% ± 24% | 56% ± 19% | 18% ± 2% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (80% correct) | quick_lookup (100% correct) | unknown (80% correct) |
| Citation rate | 0% ± 0% | 94% ± 4% | 98% ± 4% | 75% ± 42% |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) | Δ (keyword vs bare) | Δ (all examples vs bare) | Δ (semantic vs bare) |
|--------|---|---|---|---|---|---|---|
| Enable F1 | 29% | 68% | 78% | 37% | +39% | +49% | +8% |
| Enable F1 (priority-weighted) | 36% | 69% | 81% | 40% | +33% | +45% | +4% |
| Disable F1 | 8% | 64% | 72% | 13% | +56% | +64% | +5% |
| Enable Precision | 44% | 64% | 72% | 52% | +20% | +28% | +8% |
| Enable Recall | 22% | 69% | 84% | 29% | +47% | +62% | +7% |
| Species violations (total) | 2 | 0.2 | 0.8 | 0 | -1.8 | -1.2 | -2 |
| Conflict violations (total) | 9.4 | 0 | 0 | 0 | -9.4 | -9.4 | -9.4 |
| Use case accuracy | 6/20 (30%) | 19/20 (95%) | 20/20 (100%) | 13/20 (65%) | +13 | +14 | +7 |
| Citation rate (avg) | 0% | 83% | 90% | 87% | +83% | +90% | +87% |
