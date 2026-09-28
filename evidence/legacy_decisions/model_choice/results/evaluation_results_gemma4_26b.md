# VEP Assistant Evaluation Results

**Date:** 2026-06-22T05:57:06.597959
**Model:** gemma4:26b
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
| Options detected | 9 en / 1 dis | 17 en / 2 dis | 18 en / 2 dis | 9 en / 2 dis |
| Enable precision | 53% ± 13% | 60% ± 5% | 67% ± 7% | 11% ± 1% |
| Enable recall | 37% ± 10% | 80% ± 12% | 92% ± 9% | 8% ± 0% |
| Enable F1 | 43% ± 10% | 68% ± 4% | 77% ± 4% | 9% ± 0% |
| Enable F1 (priority-weighted) | 45% ± 10% | 75% ± 4% | 82% ± 4% | 11% ± 0% |
| Disable precision | 33% ± 58% | 87% ± 18% | 93% ± 15% | 100% ± 0% |
| Disable recall | 10% ± 22% | 100% ± 0% | 100% ± 0% | 80% ± 45% |
| Disable F1 | 22% ± 38% | 92% ± 11% | 96% ± 9% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (20% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 4% | 86% ± 3% | 75% ± 4% |

### test_rare_disease_splice_region
**Query:** A rare disease patient has a variant near an exon-intron boundary. I want to assess whether it disrupts splicing as part of the diagnostic workup.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 12 en / 2 dis | 14 en / 2 dis | 7 en / 3 dis |
| Enable precision | 48% ± 9% | 66% ± 11% | 64% ± 7% | 39% ± 6% |
| Enable recall | 22% ± 5% | 71% ± 8% | 80% ± 4% | 25% ± 4% |
| Enable F1 | 29% ± 5% | 68% ± 7% | 71% ± 3% | 31% ± 4% |
| Enable F1 (priority-weighted) | 30% ± 3% | 71% ± 7% | 74% ± 4% | 30% ± 4% |
| Disable precision | 0% ± 0% | 43% ± 9% | 50% ± 0% | 32% ± 21% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 80% ± 45% |
| Disable F1 | 0% ± 0% | 60% ± 9% | 67% ± 0% | 45% ± 27% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.8 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 4% | 82% ± 3% | 85% ± 14% |

### test_somatic_tumour_wes
**Query:** I'm analysing somatic variants from tumour whole-exome sequencing of cancer patients, called with Mutect2. What VEP options should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 9 en / 1 dis | 18 en / 2 dis | 12 en / 2 dis | 7 en / 2 dis |
| Enable precision | 42% ± 8% | 42% ± 4% | 78% ± 9% | 27% ± 4% |
| Enable recall | 38% ± 15% | 74% ± 11% | 96% ± 5% | 20% ± 0% |
| Enable F1 | 40% ± 12% | 54% ± 5% | 86% ± 5% | 23% ± 1% |
| Enable F1 (priority-weighted) | 49% ± 15% | 58% ± 5% | 87% ± 4% | 14% ± 0% |
| Disable precision | 0% ± 0% | 90% ± 22% | 100% ± 0% | 53% ± 51% |
| Disable recall | 0% ± 0% | 80% ± 27% | 100% ± 0% | 60% ± 55% |
| Disable F1 | 0% ± 0% | 83% ± 24% | 100% ± 0% | 56% ± 52% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.4 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 7% | 87% ± 4% | 81% ± 13% |

### test_regulatory_noncoding_gwas
**Query:** My GWAS hits are mostly in intergenic and intronic regions. I want to understand their potential regulatory effects.

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 9 en / 3 dis | 7 en / 5 dis | 6 en / 3 dis |
| Enable precision | 46% ± 20% | 49% ± 11% | 79% ± 7% | 30% ± 10% |
| Enable recall | 37% ± 7% | 73% ± 9% | 97% ± 7% | 30% ± 7% |
| Enable F1 | 39% ± 7% | 58% ± 10% | 87% ± 6% | 30% ± 8% |
| Enable F1 (priority-weighted) | 52% ± 7% | 61% ± 10% | 88% ± 7% | 35% ± 7% |
| Disable precision | 0% ± 0% | 48% ± 19% | 60% ± 0% | 13% ± 30% |
| Disable recall | 0% ± 0% | 47% ± 18% | 100% ± 0% | 13% ± 30% |
| Disable F1 | 0% ± 0% | 47% ± 18% | 75% ± 0% | 13% ± 30% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 5% | 86% ± 12% | 92% ± 11% |

### test_population_allele_frequencies
**Query:** I want to annotate a large cohort VCF with population allele frequencies to compare variant frequencies across populations.

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 1 dis | 8 en / 2 dis | 8 en / 4 dis | 4 en / 5 dis |
| Enable precision | 29% ± 10% | 71% ± 10% | 86% ± 4% | 96% ± 9% |
| Enable recall | 23% ± 8% | 77% ± 8% | 100% ± 0% | 57% ± 0% |
| Enable F1 | 25% ± 8% | 74% ± 8% | 92% ± 3% | 72% ± 3% |
| Enable F1 (priority-weighted) | 33% ± 10% | 77% ± 8% | 94% ± 2% | 72% ± 2% |
| Disable precision | 0% ± 0% | 0% ± 0% | 77% ± 14% | 0% ± 0% |
| Disable recall | 0% ± 0% | 0% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 0% ± 0% | 86% ± 9% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 78% ± 7% | 89% ± 3% | 94% ± 8% |

### test_non_human_mouse_crispr
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 0 dis | 9 en / 6 dis | 10 en / 6 dis | 4 en / 5 dis |
| Enable precision | 28% ± 6% | 62% ± 12% | 62% ± 10% | 24% ± 6% |
| Enable recall | 29% ± 14% | 74% ± 6% | 89% ± 6% | 14% ± 0% |
| Enable F1 | 28% ± 10% | 67% ± 9% | 73% ± 8% | 18% ± 1% |
| Enable F1 (priority-weighted) | 40% ± 11% | 71% ± 10% | 79% ± 9% | 21% ± 1% |
| Disable precision | 0% ± 0% | 70% ± 7% | 80% ± 13% | 0% ± 0% |
| Disable recall | 0% ± 0% | 84% ± 17% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 76% ± 10% | 88% ± 7% | 0% ± 0% |
| Species violations | 3.0 | 1.2 | 1.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (20% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 95% ± 4% | 91% ± 7% | 81% ± 18% |

*Species violations (Without KB):* {'gnomad_sv', 'cadd', 'polyphen', 'mutfunc'}

*Species violations (With KB (keyword)):* {'ccds'}

*Species violations (With KB (all examples)):* {'ccds'}

*Species violations (With KB (semantic)):* none

### test_quick_lookup_rsid
**Query:** I just want to look up a single variant by its rsID — its gene, consequence, and clinical significance.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 1 dis | 4 en / 5 dis | 4 en / 6 dis | 3 en / 7 dis |
| Enable precision | 18% ± 11% | 100% ± 0% | 100% ± 0% | 88% ± 16% |
| Enable recall | 30% ± 27% | 100% ± 0% | 100% ± 0% | 55% ± 11% |
| Enable F1 | 22% ± 15% | 100% ± 0% | 100% ± 0% | 66% ± 6% |
| Enable F1 (priority-weighted) | 28% ± 18% | 100% ± 0% | 100% ± 0% | 74% ± 5% |
| Disable precision | 0% ± 0% | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable recall | n/a | n/a | n/a | n/a |
| Disable F1 | n/a | n/a | n/a | n/a |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 87% ± 5% | 91% ± 1% | 88% ± 8% |

### test_rare_disease_trio
**Query:** We sequenced a parent-child trio (exome) to find de novo variants causing a paediatric disorder. Which VEP options for clinical interpretation?

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 0 dis | 16 en / 2 dis | 17 en / 2 dis | 10 en / 1 dis |
| Enable precision | 54% ± 7% | 70% ± 6% | 74% ± 14% | 12% ± 4% |
| Enable recall | 27% ± 14% | 77% ± 9% | 90% ± 4% | 9% ± 3% |
| Enable F1 | 35% ± 11% | 73% ± 6% | 81% ± 9% | 10% ± 3% |
| Enable F1 (priority-weighted) | 34% ± 12% | 78% ± 6% | 84% ± 7% | 11% ± 1% |
| Disable precision | 0% ± 0% | 100% ± 0% | 93% ± 15% | 50% ± 50% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 40% ± 55% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 96% ± 9% | 56% ± 51% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 1% | 86% ± 3% | 72% ± 7% |

### test_somatic_tumor_only
**Query:** Tumor-only WES with no matched normal. I need to annotate somatic candidates and aggressively filter likely germline variants by population frequency.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 7 en / 0 dis | 12 en / 2 dis | 11 en / 2 dis | 7 en / 3 dis |
| Enable precision | 60% ± 13% | 81% ± 10% | 90% ± 8% | 57% ± 0% |
| Enable recall | 38% ± 16% | 84% ± 4% | 91% ± 0% | 36% ± 0% |
| Enable F1 | 45% ± 14% | 82% ± 4% | 90% ± 4% | 44% ± 0% |
| Enable F1 (priority-weighted) | 52% ± 14% | 87% ± 4% | 93% ± 5% | 42% ± 0% |
| Disable precision | 0% ± 0% | 100% ± 0% | 100% ± 0% | 53% ± 14% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 70% ± 27% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 100% ± 0% | 60% ± 19% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 2% | 79% ± 3% | 75% ± 3% |

### test_somatic_ctdna
**Query:** ctDNA / liquid-biopsy somatic variants from a cancer patient, low VAF. Annotate for clinical actionability.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 11 en / 2 dis | 12 en / 2 dis | 7 en / 3 dis |
| Enable precision | 43% ± 12% | 80% ± 16% | 79% ± 10% | 29% ± 6% |
| Enable recall | 18% ± 8% | 86% ± 11% | 92% ± 4% | 20% ± 0% |
| Enable F1 | 25% ± 10% | 82% ± 12% | 85% ± 7% | 24% ± 2% |
| Enable F1 (priority-weighted) | 33% ± 10% | 84% ± 11% | 87% ± 6% | 25% ± 1% |
| Disable precision | n/a | 100% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable F1 | n/a | 100% ± 0% | 100% ± 0% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 84% ± 4% | 84% ± 5% | 77% ± 14% |

### test_regulatory_promoter
**Query:** Variants in promoter/enhancer regions from ATAC-seq peaks - which target genes and regulatory features do they hit?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 7 en / 5 dis | 8 en / 5 dis | 4 en / 4 dis |
| Enable precision | 60% ± 27% | 76% ± 12% | 84% ± 17% | 31% ± 8% |
| Enable recall | 26% ± 21% | 71% ± 10% | 89% ± 6% | 20% ± 8% |
| Enable F1 | 38% ± 11% | 74% ± 11% | 86% ± 11% | 24% ± 8% |
| Enable F1 (priority-weighted) | 48% ± 13% | 74% ± 9% | 88% ± 10% | 32% ± 10% |
| Disable precision | n/a | 56% ± 5% | 63% ± 7% | 38% ± 16% |
| Disable recall | 0% ± 0% | 87% ± 18% | 100% ± 0% | 53% ± 18% |
| Disable F1 | n/a | 68% ± 10% | 77% ± 5% | 44% ± 18% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 83% ± 12% | 87% ± 10% | 88% ± 16% |

### test_regulatory_tfbs
**Query:** Do my non-coding GWAS SNPs overlap transcription factor binding sites or other regulatory features?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 7 en / 3 dis | 7 en / 4 dis | 6 en / 3 dis |
| Enable precision | 59% ± 8% | 68% ± 6% | 70% ± 4% | 29% ± 0% |
| Enable recall | 36% ± 17% | 92% ± 11% | 100% ± 0% | 32% ± 18% |
| Enable F1 | 43% ± 14% | 78% ± 8% | 82% ± 3% | 33% ± 0% |
| Enable F1 (priority-weighted) | 55% ± 16% | 79% ± 9% | 85% ± 3% | 37% ± 0% |
| Disable precision | 0% ± 0% | 95% ± 11% | 77% ± 14% | 35% ± 49% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 33% ± 47% |
| Disable F1 | 0% ± 0% | 97% ± 6% | 86% ± 9% | 33% ± 45% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 79% ± 7% | 81% ± 13% | 87% ± 7% |

### test_population_ancestry
**Query:** Comparing variant allele frequencies across continental populations in a cohort. Which frequency annotations should I turn on?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 7 en / 3 dis | 8 en / 4 dis | 5 en / 4 dis |
| Enable precision | 49% ± 33% | 100% ± 0% | 85% ± 11% | 100% ± 0% |
| Enable recall | 17% ± 6% | 97% ± 6% | 100% ± 0% | 71% ± 0% |
| Enable F1 | 23% ± 9% | 98% ± 3% | 91% ± 7% | 83% ± 0% |
| Enable F1 (priority-weighted) | 28% ± 9% | 98% ± 4% | 95% ± 4% | 85% ± 0% |
| Disable precision | 0% ± 0% | 93% ± 15% | 57% ± 33% | 0% ± 0% |
| Disable recall | 0% ± 0% | 93% ± 15% | 80% ± 45% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 93% ± 15% | 66% ± 37% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (20% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 93% ± 6% | 91% ± 9% | 97% ± 6% |

### test_population_large_wgs
**Query:** Annotating a very large WGS cohort VCF (~2M variants) is painfully slow. How do I keep it efficient while still getting gene and frequency annotation?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 5 en / 0 dis | 7 en / 4 dis | 8 en / 5 dis | 2 en / 8 dis |
| Enable precision | 19% ± 4% | 52% ± 5% | 62% ± 10% | 95% ± 11% |
| Enable recall | 20% ± 0% | 76% ± 9% | 96% ± 9% | 28% ± 18% |
| Enable F1 | 19% ± 2% | 61% ± 5% | 75% ± 9% | 40% ± 15% |
| Enable F1 (priority-weighted) | 29% ± 1% | 58% ± 4% | 72% ± 10% | 37% ± 18% |
| Disable precision | n/a | 33% ± 28% | 37% ± 11% | 24% ± 10% |
| Disable recall | 0% ± 0% | 47% ± 38% | 60% ± 15% | 60% ± 15% |
| Disable F1 | n/a | 39% ± 32% | 45% ± 12% | 34% ± 11% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.8 | 0.4 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | population_genetics (80% correct) | population_genetics (100% correct) | structural_variants (40% correct) |
| Citation rate | 0% ± 0% | 88% ± 12% | 83% ± 8% | 94% ± 8% |

### test_structural_longread
**Query:** Large deletions and duplications from long-read WGS (Sniffles). Which genes and regulatory features are disrupted, and how do I filter common SVs?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 6 en / 4 dis | 7 en / 5 dis | 5 en / 4 dis |
| Enable precision | 32% ± 19% | 91% ± 13% | 83% ± 14% | 59% ± 10% |
| Enable recall | 26% ± 23% | 77% ± 8% | 86% ± 0% | 43% ± 0% |
| Enable F1 | 27% ± 21% | 83% ± 8% | 84% ± 8% | 49% ± 3% |
| Enable F1 (priority-weighted) | 37% ± 24% | 85% ± 9% | 89% ± 6% | 52% ± 3% |
| Disable precision | n/a | 96% ± 9% | 84% ± 9% | 24% ± 2% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% | 25% ± 0% |
| Disable F1 | n/a | 98% ± 5% | 91% ± 5% | 24% ± 1% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | structural_variants (100% correct) | structural_variants (100% correct) | structural_variants (80% correct) |
| Citation rate | 0% ± 0% | 90% ± 6% | 90% ± 7% | 88% ± 7% |

### test_structural_cnv
**Query:** CNV calls from a SNP array - which genes do the copy-number gains/losses affect, and are they common in the population?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 6 en / 4 dis | 6 en / 5 dis | 4 en / 4 dis |
| Enable precision | 43% ± 42% | 66% ± 9% | 76% ± 6% | 58% ± 24% |
| Enable recall | 16% ± 17% | 80% ± 0% | 96% ± 9% | 40% ± 0% |
| Enable F1 | 25% ± 18% | 72% ± 6% | 84% ± 4% | 46% ± 6% |
| Enable F1 (priority-weighted) | 35% ± 25% | 74% ± 4% | 89% ± 6% | 55% ± 4% |
| Disable precision | 0% ± 0% | 85% ± 22% | 72% ± 17% | 0% ± 0% |
| Disable recall | 0% ± 0% | 85% ± 22% | 85% ± 14% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 85% ± 22% | 78% ± 14% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (40% correct) | population_genetics (80% correct) | structural_variants (100% correct) | structural_variants (100% correct) |
| Citation rate | 0% ± 0% | 90% ± 7% | 94% ± 5% | 80% ± 11% |

### test_structural_clinical
**Query:** Clinically interpret structural variants (dels/dups) from a rare-disease WGS case - pathogenic vs benign, filter common ones.

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 10 en / 5 dis | 7 en / 5 dis | 4 en / 6 dis |
| Enable precision | 29% ± 12% | 44% ± 8% | 70% ± 3% | 53% ± 7% |
| Enable recall | 27% ± 15% | 70% ± 7% | 83% ± 12% | 33% ± 0% |
| Enable F1 | 27% ± 12% | 53% ± 5% | 75% ± 5% | 41% ± 2% |
| Enable F1 (priority-weighted) | 39% ± 14% | 61% ± 3% | 82% ± 7% | 49% ± 2% |
| Disable precision | 50% ± 0% | 63% ± 7% | 56% ± 5% | 0% ± 0% |
| Disable recall | 7% ± 15% | 100% ± 0% | 87% ± 18% | 0% ± 0% |
| Disable F1 | 40% ± 0% | 77% ± 5% | 68% ± 10% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | rare_disease_germline (20% correct) | structural_variants (80% correct) | rare_disease_germline (40% correct) |
| Citation rate | 0% ± 0% | 90% ± 8% | 94% ± 5% | 75% ± 0% |

### test_non_human_zebrafish
**Query:** Zebrafish (Danio rerio) variants from a mutagenesis screen against GRCz11. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 9 en / 6 dis | 9 en / 7 dis | 3 en / 7 dis |
| Enable precision | 33% ± 7% | 59% ± 10% | 80% ± 8% | 67% ± 0% |
| Enable recall | 26% ± 6% | 71% ± 14% | 97% ± 6% | 29% ± 0% |
| Enable F1 | 28% ± 6% | 64% ± 9% | 87% ± 6% | 40% ± 0% |
| Enable F1 (priority-weighted) | 40% ± 5% | 70% ± 11% | 90% ± 7% | 42% ± 0% |
| Disable precision | 0% ± 0% | 76% ± 18% | 71% ± 11% | 0% ± 0% |
| Disable recall | 0% ± 0% | 88% ± 11% | 100% ± 0% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 81% ± 14% | 83% ± 8% | 0% ± 0% |
| Species violations | 2.8 | 0.2 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (40% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 4% | 97% ± 4% | 85% ± 14% |

*Species violations (Without KB):* {'mutfunc', 'gnomad_sv', 'spliceai', 'frequency', 'polyphen'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_non_human_rat
**Query:** Rat (Rattus norvegicus) WGS variants from a knockout model. Which VEP options apply?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 6 en / 0 dis | 8 en / 9 dis | 8 en / 7 dis | 4 en / 6 dis |
| Enable precision | 23% ± 6% | 59% ± 7% | 81% ± 4% | 58% ± 12% |
| Enable recall | 20% ± 8% | 69% ± 12% | 94% ± 8% | 29% ± 0% |
| Enable F1 | 21% ± 6% | 63% ± 6% | 87% ± 1% | 38% ± 3% |
| Enable F1 (priority-weighted) | 33% ± 7% | 65% ± 6% | 90% ± 1% | 41% ± 2% |
| Disable precision | 100% ± 0% | 61% ± 20% | 68% ± 4% | 0% ± 0% |
| Disable recall | 8% ± 11% | 88% ± 11% | 92% ± 11% | 0% ± 0% |
| Disable F1 | 33% ± 0% | 69% ± 16% | 78% ± 5% | 0% ± 0% |
| Species violations | 3.2 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 0.0 | 0.0 | 0.0 |
| Use case detected | non_human (20% correct) | non_human (100% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 99% ± 3% | 96% ± 6% | 91% ± 13% |

*Species violations (Without KB):* {'gnomad_sv', 'spliceai', 'cadd', 'revel', 'polyphen'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_quick_lookup_batch
**Query:** I have a short list of rsIDs and just want their gene, consequence, and ClinVar significance - nothing heavy.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 4 en / 4 dis | 4 en / 4 dis | 3 en / 5 dis |
| Enable precision | 33% ± 43% | 100% ± 0% | 92% ± 11% | 73% ± 25% |
| Enable recall | 15% ± 14% | 100% ± 0% | 100% ± 0% | 60% ± 14% |
| Enable F1 | 18% ± 18% | 100% ± 0% | 96% ± 6% | 66% ± 18% |
| Enable F1 (priority-weighted) | 22% ± 21% | 100% ± 0% | 95% ± 7% | 72% ± 16% |
| Disable precision | n/a | 61% ± 19% | 72% ± 25% | 22% ± 4% |
| Disable recall | 0% ± 0% | 40% ± 19% | 50% ± 24% | 17% ± 0% |
| Disable F1 | n/a | 48% ± 19% | 58% ± 24% | 19% ± 2% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 83% ± 6% | 89% ± 7% | 79% ± 7% |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) | Δ (keyword vs bare) | Δ (all examples vs bare) | Δ (semantic vs bare) |
|--------|---|---|---|---|---|---|---|
| Enable F1 | 30% | 74% | 84% | 39% | +44% | +54% | +9% |
| Enable F1 (priority-weighted) | 38% | 76% | 87% | 42% | +38% | +49% | +4% |
| Disable F1 | 7% | 74% | 81% | 26% | +68% | +74% | +19% |
| Enable Precision | 40% | 70% | 78% | 52% | +30% | +38% | +12% |
| Enable Recall | 26% | 80% | 93% | 33% | +54% | +67% | +7% |
| Species violations (total) | 9 | 1.4 | 1 | 0 | -7.6 | -8 | -9 |
| Conflict violations (total) | 5 | 0.4 | 0 | 0 | -4.6 | -5 | -5 |
| Use case accuracy | 4/20 (20%) | 19/20 (95%) | 20/20 (100%) | 18/20 (90%) | +15 | +16 | +14 |
| Citation rate (avg) | 0% | 87% | 88% | 84% | +87% | +88% | +84% |
