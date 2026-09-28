# VEP Assistant Evaluation Results

**Date:** 2026-06-21T20:15:31.498059
**Model:** gemma4:e4b
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
| Options detected | 5 en / 0 dis | 12 en / 1 dis | 13 en / 1 dis | 5 en / 2 dis |
| Enable precision | 74% ± 16% | 74% ± 16% | 71% ± 11% | 17% ± 15% |
| Enable recall | 29% ± 13% | 63% ± 34% | 72% ± 18% | 6% ± 3% |
| Enable F1 | 41% ± 14% | 60% ± 27% | 71% ± 12% | 8% ± 5% |
| Enable F1 (priority-weighted) | 39% ± 14% | 62% ± 28% | 74% ± 13% | 10% ± 6% |
| Disable precision | n/a | 89% ± 19% | 89% ± 19% | 78% ± 19% |
| Disable recall | 0% ± 0% | 60% ± 55% | 60% ± 55% | 60% ± 55% |
| Disable F1 | n/a | 93% ± 12% | 93% ± 12% | 87% ± 12% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.6 | 0.0 | 3.8 | 0.0 |
| Use case detected | unknown (20% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 90% ± 7% | 86% ± 4% | 82% ± 10% |

### test_rare_disease_splice_region
**Query:** A rare disease patient has a variant near an exon-intron boundary. I want to assess whether it disrupts splicing as part of the diagnostic workup.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 9 en / 1 dis | 12 en / 1 dis | 5 en / 1 dis |
| Enable precision | 65% ± 22% | 59% ± 28% | 53% ± 16% | 37% ± 24% |
| Enable recall | 20% ± 4% | 42% ± 26% | 58% ± 23% | 18% ± 13% |
| Enable F1 | 30% ± 6% | 42% ± 22% | 55% ± 18% | 23% ± 15% |
| Enable F1 (priority-weighted) | 29% ± 5% | 45% ± 25% | 59% ± 19% | 22% ± 14% |
| Disable precision | 0% ± 0% | 42% ± 12% | 44% ± 10% | 0% ± 0% |
| Disable recall | 0% ± 0% | 40% ± 55% | 60% ± 55% | 0% ± 0% |
| Disable F1 | 0% ± 0% | 58% ± 12% | 61% ± 10% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 3.4 | 1.6 | 0.0 |
| Use case detected | non_human (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 87% ± 6% | 85% ± 6% | 84% ± 18% |

### test_somatic_tumour_wes
**Query:** I'm analysing somatic variants from tumour whole-exome sequencing of cancer patients, called with Mutect2. What VEP options should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 14 en / 2 dis | 12 en / 2 dis | 4 en / 1 dis |
| Enable precision | 45% ± 12% | 45% ± 9% | 72% ± 7% | 35% ± 38% |
| Enable recall | 14% ± 9% | 62% ± 15% | 88% ± 18% | 16% ± 15% |
| Enable F1 | 21% ± 11% | 51% ± 6% | 79% ± 10% | 22% ± 21% |
| Enable F1 (priority-weighted) | 29% ± 11% | 60% ± 7% | 83% ± 12% | 18% ± 19% |
| Disable precision | n/a | 61% ± 10% | 72% ± 25% | 25% ± 35% |
| Disable recall | 0% ± 0% | 50% ± 50% | 60% ± 55% | 10% ± 22% |
| Disable F1 | n/a | 70% ± 17% | 82% ± 17% | 25% ± 35% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.2 | 7.4 | 1.4 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (60% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 83% ± 10% | 83% ± 7% | 70% ± 5% |

### test_regulatory_noncoding_gwas
**Query:** My GWAS hits are mostly in intergenic and intronic regions. I want to understand their potential regulatory effects.

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 6 en / 1 dis | 9 en / 5 dis | 5 en / 4 dis |
| Enable precision | 77% ± 22% | 61% ± 28% | 62% ± 11% | 30% ± 5% |
| Enable recall | 30% ± 7% | 47% ± 38% | 90% ± 15% | 23% ± 9% |
| Enable F1 | 41% ± 8% | 51% ± 20% | 73% ± 11% | 26% ± 7% |
| Enable F1 (priority-weighted) | 52% ± 10% | 58% ± 17% | 78% ± 14% | 31% ± 5% |
| Disable precision | 0% ± 0% | 21% ± 25% | 56% ± 9% | 8% ± 18% |
| Disable recall | 0% ± 0% | 13% ± 18% | 93% ± 15% | 13% ± 30% |
| Disable F1 | 0% ± 0% | 18% ± 21% | 70% ± 11% | 10% ± 22% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.2 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (0% correct) | regulatory_noncoding (60% correct) | regulatory_noncoding (80% correct) | regulatory_noncoding (80% correct) |
| Citation rate | 0% ± 0% | 79% ± 17% | 71% ± 5% | 78% ± 14% |

### test_population_allele_frequencies
**Query:** I want to annotate a large cohort VCF with population allele frequencies to compare variant frequencies across populations.

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 8 en / 2 dis | 8 en / 2 dis | 4 en / 4 dis |
| Enable precision | 38% ± 11% | 53% ± 23% | 62% ± 37% | 92% ± 11% |
| Enable recall | 20% ± 8% | 60% ± 21% | 66% ± 36% | 54% ± 6% |
| Enable F1 | 26% ± 9% | 56% ± 22% | 63% ± 35% | 68% ± 5% |
| Enable F1 (priority-weighted) | 31% ± 11% | 63% ± 19% | 69% ± 32% | 70% ± 4% |
| Disable precision | n/a | 7% ± 12% | 40% ± 35% | 0% ± 0% |
| Disable recall | 0% ± 0% | 7% ± 15% | 40% ± 55% | 0% ± 0% |
| Disable F1 | n/a | 8% ± 14% | 50% ± 43% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.8 | 0.0 |
| Use case detected | population_genetics (60% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 84% ± 7% | 78% ± 8% | 90% ± 14% |

### test_non_human_mouse_crispr
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 12 en / 1 dis | 9 en / 5 dis | 6 en / 4 dis |
| Enable precision | 36% ± 25% | 50% ± 13% | 78% ± 16% | 28% ± 7% |
| Enable recall | 20% ± 13% | 83% ± 16% | 97% ± 6% | 23% ± 19% |
| Enable F1 | 24% ± 15% | 62% ± 13% | 85% ± 12% | 23% ± 11% |
| Enable F1 (priority-weighted) | 33% ± 20% | 71% ± 12% | 89% ± 9% | 30% ± 16% |
| Disable precision | n/a | 27% ± 46% | 46% ± 28% | 0% ± 0% |
| Disable recall | 0% ± 0% | 16% ± 36% | 56% ± 38% | 0% ± 0% |
| Disable F1 | n/a | 27% ± 46% | 50% ± 31% | 0% ± 0% |
| Species violations | 1.2 | 3.6 | 0.8 | 2.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (0% correct) | rare_disease_germline (20% correct) | structural_variants (40% correct) | rare_disease_germline (0% correct) |
| Citation rate | 0% ± 0% | 74% ± 8% | 82% ± 11% | 66% ± 11% |

*Species violations (Without KB):* none

*Species violations (With KB (keyword)):* {'alphamissense', 'polyphen', 'af', 'cadd', 'tsl', 'clinvar'}

*Species violations (With KB (all examples)):* {'frequency', 'clinvar', 'polyphen', 'cadd'}

*Species violations (With KB (semantic)):* {'mutfunc'}

### test_quick_lookup_rsid
**Query:** I just want to look up a single variant by its rsID — its gene, consequence, and clinical significance.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 1 en / 0 dis | 5 en / 3 dis | 6 en / 1 dis | 2 en / 4 dis |
| Enable precision | 0% ± 0% | 74% ± 35% | 16% ± 16% | 93% ± 15% |
| Enable recall | 0% ± 0% | 70% ± 33% | 30% ± 33% | 55% ± 27% |
| Enable F1 | 0% ± 0% | 66% ± 31% | 21% ± 21% | 66% ± 22% |
| Enable F1 (priority-weighted) | 0% ± 0% | 68% ± 30% | 24% ± 23% | 73% ± 19% |
| Disable precision | 0% ± 0% | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable recall | n/a | n/a | n/a | n/a |
| Disable F1 | n/a | n/a | n/a | n/a |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (80% correct) | quick_lookup (100% correct) | quick_lookup (80% correct) |
| Citation rate | 0% ± 0% | 78% ± 11% | 87% ± 8% | 57% ± 21% |

### test_rare_disease_trio
**Query:** We sequenced a parent-child trio (exome) to find de novo variants causing a paediatric disorder. Which VEP options for clinical interpretation?

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 12 en / 1 dis | 11 en / 2 dis | 8 en / 3 dis |
| Enable precision | 67% ± 5% | 60% ± 13% | 84% ± 8% | 8% ± 8% |
| Enable recall | 20% ± 6% | 51% ± 25% | 69% ± 16% | 4% ± 4% |
| Enable F1 | 30% ± 7% | 54% ± 20% | 75% ± 13% | 6% ± 5% |
| Enable F1 (priority-weighted) | 30% ± 10% | 54% ± 21% | 76% ± 15% | 7% ± 6% |
| Disable precision | n/a | 100% ± 0% | 93% ± 15% | 33% ± 47% |
| Disable recall | 0% ± 0% | 40% ± 42% | 80% ± 27% | 40% ± 55% |
| Disable F1 | n/a | 78% ± 19% | 83% ± 17% | 36% ± 50% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 2.8 | 0.0 | 0.0 |
| Use case detected | population_genetics (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 7% | 85% ± 3% | 69% ± 7% |

### test_somatic_tumor_only
**Query:** Tumor-only WES with no matched normal. I need to annotate somatic candidates and aggressively filter likely germline variants by population frequency.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 0 dis | 15 en / 1 dis | 12 en / 2 dis | 7 en / 3 dis |
| Enable precision | 55% ± 16% | 60% ± 9% | 81% ± 19% | 62% ± 12% |
| Enable recall | 16% ± 8% | 80% ± 12% | 84% ± 16% | 36% ± 0% |
| Enable F1 | 25% ± 11% | 68% ± 9% | 81% ± 16% | 46% ± 3% |
| Enable F1 (priority-weighted) | 32% ± 11% | 76% ± 10% | 86% ± 13% | 44% ± 2% |
| Disable precision | n/a | 56% ± 51% | 92% ± 17% | 61% ± 24% |
| Disable recall | 0% ± 0% | 30% ± 45% | 80% ± 45% | 80% ± 27% |
| Disable F1 | n/a | 49% ± 43% | 95% ± 10% | 67% ± 22% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 3.2 | 0.0 | 0.0 |
| Use case detected | structural_variants (40% correct) | somatic_cancer (80% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 7% | 83% ± 6% | 85% ± 12% |

### test_somatic_ctdna
**Query:** ctDNA / liquid-biopsy somatic variants from a cancer patient, low VAF. Annotate for clinical actionability.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 10 en / 1 dis | 8 en / 1 dis | 9 en / 2 dis |
| Enable precision | 67% ± 47% | 55% ± 12% | 71% ± 20% | 23% ± 1% |
| Enable recall | 10% ± 7% | 56% ± 34% | 52% ± 31% | 20% ± 0% |
| Enable F1 | 17% ± 12% | 52% ± 26% | 54% ± 23% | 21% ± 1% |
| Enable F1 (priority-weighted) | 23% ± 14% | 58% ± 29% | 61% ± 21% | 26% ± 3% |
| Disable precision | n/a | 100% ± 0% | 100% ± 0% | 0% ± 0% |
| Disable recall | 0% ± 0% | 40% ± 42% | 50% ± 50% | 0% ± 0% |
| Disable F1 | n/a | 78% ± 19% | 89% ± 19% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 3.0 | 0.0 |
| Use case detected | somatic_cancer (80% correct) | somatic_cancer (100% correct) | somatic_cancer (80% correct) | rare_disease_germline (40% correct) |
| Citation rate | 0% ± 0% | 87% ± 6% | 83% ± 2% | 56% ± 13% |

### test_regulatory_promoter
**Query:** Variants in promoter/enhancer regions from ATAC-seq peaks - which target genes and regulatory features do they hit?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 9 en / 2 dis | 7 en / 5 dis | 4 en / 6 dis |
| Enable precision | 93% ± 15% | 55% ± 20% | 80% ± 15% | 28% ± 5% |
| Enable recall | 26% ± 6% | 66% ± 13% | 80% ± 8% | 14% ± 0% |
| Enable F1 | 40% ± 8% | 58% ± 13% | 79% ± 10% | 19% ± 1% |
| Enable F1 (priority-weighted) | 49% ± 10% | 66% ± 9% | 82% ± 9% | 25% ± 1% |
| Disable precision | n/a | 60% ± 0% | 39% ± 24% | 17% ± 4% |
| Disable recall | 0% ± 0% | 40% ± 55% | 80% ± 45% | 33% ± 0% |
| Disable F1 | n/a | 75% ± 0% | 52% ± 30% | 23% ± 4% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 82% ± 17% | 78% ± 8% | 95% ± 12% |

### test_regulatory_tfbs
**Query:** Do my non-coding GWAS SNPs overlap transcription factor binding sites or other regulatory features?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 9 en / 3 dis | 9 en / 3 dis | 4 en / 1 dis |
| Enable precision | 88% ± 25% | 54% ± 12% | 57% ± 10% | 42% ± 37% |
| Enable recall | 32% ± 23% | 96% ± 9% | 96% ± 9% | 28% ± 18% |
| Enable F1 | 54% ± 19% | 68% ± 11% | 71% ± 9% | 29% ± 17% |
| Enable F1 (priority-weighted) | 63% ± 18% | 76% ± 6% | 79% ± 5% | 35% ± 20% |
| Disable precision | n/a | 34% ± 34% | 55% ± 6% | 0% ± 0% |
| Disable recall | 0% ± 0% | 47% ± 51% | 60% ± 43% | 0% ± 0% |
| Disable F1 | n/a | 39% ± 40% | 62% ± 17% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.6 | 0.0 |
| Use case detected | population_genetics (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (80% correct) | rare_disease_germline (60% correct) |
| Citation rate | 0% ± 0% | 73% ± 5% | 73% ± 2% | 86% ± 14% |

### test_population_ancestry
**Query:** Comparing variant allele frequencies across continental populations in a cohort. Which frequency annotations should I turn on?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 7 en / 2 dis | 7 en / 2 dis | 5 en / 4 dis |
| Enable precision | 37% ± 22% | 65% ± 27% | 57% ± 40% | 100% ± 0% |
| Enable recall | 11% ± 6% | 66% ± 26% | 57% ± 35% | 66% ± 8% |
| Enable F1 | 17% ± 10% | 65% ± 26% | 57% ± 37% | 79% ± 6% |
| Enable F1 (priority-weighted) | 20% ± 11% | 68% ± 24% | 62% ± 33% | 80% ± 6% |
| Disable precision | n/a | 42% ± 52% | 58% ± 12% | 0% ± 0% |
| Disable recall | 0% ± 0% | 20% ± 30% | 33% ± 47% | 0% ± 0% |
| Disable F1 | n/a | 36% ± 41% | 67% ± 0% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 1.6 | 0.0 |
| Use case detected | population_genetics (80% correct) | population_genetics (100% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 11% | 78% ± 14% | 86% ± 15% |

### test_population_large_wgs
**Query:** Annotating a very large WGS cohort VCF (~2M variants) is painfully slow. How do I keep it efficient while still getting gene and frequency annotation?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 3 en / 1 dis | 6 en / 3 dis | 10 en / 2 dis | 3 en / 6 dis |
| Enable precision | 25% ± 14% | 48% ± 33% | 30% ± 14% | 57% ± 40% |
| Enable recall | 16% ± 9% | 44% ± 22% | 52% ± 11% | 20% ± 0% |
| Enable F1 | 19% ± 11% | 39% ± 16% | 37% ± 13% | 27% ± 6% |
| Enable F1 (priority-weighted) | 27% ± 15% | 44% ± 16% | 44% ± 9% | 25% ± 3% |
| Disable precision | 0% ± 0% | 6% ± 10% | 0% ± 0% | 29% ± 9% |
| Disable recall | 0% ± 0% | 7% ± 15% | 0% ± 0% | 60% ± 15% |
| Disable F1 | 0% ± 0% | 7% ± 13% | 0% ± 0% | 39% ± 10% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.2 | 0.8 | 3.4 | 0.0 |
| Use case detected | structural_variants (0% correct) | rare_disease_germline (60% correct) | population_genetics (100% correct) | rare_disease_germline (40% correct) |
| Citation rate | 0% ± 0% | 72% ± 14% | 71% ± 8% | 78% ± 14% |

### test_structural_longread
**Query:** Large deletions and duplications from long-read WGS (Sniffles). Which genes and regulatory features are disrupted, and how do I filter common SVs?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 6 en / 3 dis | 6 en / 2 dis | 5 en / 4 dis |
| Enable precision | 83% ± 24% | 72% ± 23% | 75% ± 23% | 62% ± 13% |
| Enable recall | 20% ± 8% | 54% ± 31% | 54% ± 37% | 43% ± 0% |
| Enable F1 | 31% ± 10% | 56% ± 26% | 51% ± 24% | 50% ± 4% |
| Enable F1 (priority-weighted) | 40% ± 5% | 63% ± 24% | 62% ± 23% | 54% ± 4% |
| Disable precision | n/a | 73% ± 12% | 60% ± 42% | 23% ± 3% |
| Disable recall | 0% ± 0% | 55% ± 51% | 25% ± 18% | 25% ± 0% |
| Disable F1 | n/a | 81% ± 13% | 35% ± 24% | 24% ± 2% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.8 | 0.0 |
| Use case detected | structural_variants (100% correct) | regulatory_noncoding (0% correct) | regulatory_noncoding (0% correct) | regulatory_noncoding (20% correct) |
| Citation rate | 0% ± 0% | 91% ± 6% | 82% ± 5% | 74% ± 20% |

### test_structural_cnv
**Query:** CNV calls from a SNP array - which genes do the copy-number gains/losses affect, and are they common in the population?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 9 en / 3 dis | 6 en / 4 dis | 5 en / 2 dis |
| Enable precision | 57% ± 43% | 52% ± 13% | 72% ± 17% | 32% ± 14% |
| Enable recall | 16% ± 9% | 92% ± 11% | 76% ± 33% | 32% ± 11% |
| Enable F1 | 24% ± 14% | 66% ± 12% | 67% ± 20% | 32% ± 12% |
| Enable F1 (priority-weighted) | 33% ± 18% | 77% ± 11% | 74% ± 19% | 44% ± 13% |
| Disable precision | n/a | 72% ± 10% | 65% ± 22% | 0% ± 0% |
| Disable recall | 0% ± 0% | 50% ± 47% | 65% ± 49% | 0% ± 0% |
| Disable F1 | n/a | 77% ± 11% | 72% ± 29% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | population_genetics (0% correct) | population_genetics (20% correct) | structural_variants (100% correct) | population_genetics (0% correct) |
| Citation rate | 0% ± 0% | 84% ± 10% | 85% ± 9% | 89% ± 15% |

### test_structural_clinical
**Query:** Clinically interpret structural variants (dels/dups) from a rare-disease WGS case - pathogenic vs benign, filter common ones.

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 9 en / 3 dis | 6 en / 3 dis | 4 en / 4 dis |
| Enable precision | 31% ± 24% | 45% ± 10% | 72% ± 31% | 49% ± 16% |
| Enable recall | 10% ± 9% | 70% ± 14% | 50% ± 20% | 30% ± 7% |
| Enable F1 | 18% ± 12% | 55% ± 11% | 52% ± 12% | 37% ± 9% |
| Enable F1 (priority-weighted) | 23% ± 17% | 64% ± 14% | 62% ± 13% | 45% ± 7% |
| Disable precision | n/a | 52% ± 36% | 43% ± 0% | 0% ± 0% |
| Disable recall | 0% ± 0% | 60% ± 55% | 40% ± 55% | 0% ± 0% |
| Disable F1 | n/a | 62% ± 41% | 60% ± 0% | 0% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 2.6 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | rare_disease_germline (0% correct) | rare_disease_germline (0% correct) | rare_disease_germline (0% correct) |
| Citation rate | 0% ± 0% | 82% ± 7% | 84% ± 8% | 84% ± 25% |

### test_non_human_zebrafish
**Query:** Zebrafish (Danio rerio) variants from a mutagenesis screen against GRCz11. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 9 en / 4 dis | 8 en / 6 dis | 4 en / 4 dis |
| Enable precision | 45% ± 8% | 66% ± 24% | 90% ± 6% | 68% ± 19% |
| Enable recall | 23% ± 8% | 69% ± 33% | 97% ± 6% | 34% ± 22% |
| Enable F1 | 29% ± 6% | 59% ± 23% | 93% ± 5% | 42% ± 14% |
| Enable F1 (priority-weighted) | 41% ± 7% | 65% ± 21% | 94% ± 4% | 46% ± 19% |
| Disable precision | n/a | 58% ± 14% | 63% ± 12% | 0% ± 0% |
| Disable recall | 0% ± 0% | 44% ± 43% | 76% ± 33% | 0% ± 0% |
| Disable F1 | n/a | 64% ± 17% | 68% ± 21% | 0% ± 0% |
| Species violations | 1.2 | 1.2 | 0.0 | 0.2 |
| Conflict violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (20% correct) | structural_variants (0% correct) | non_human (40% correct) | population_genetics (20% correct) |
| Citation rate | 0% ± 0% | 86% ± 12% | 80% ± 9% | 72% ± 17% |

*Species violations (Without KB):* {'cadd'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_non_human_rat
**Query:** Rat (Rattus norvegicus) WGS variants from a knockout model. Which VEP options apply?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 4 en / 0 dis | 10 en / 4 dis | 8 en / 7 dis | 6 en / 4 dis |
| Enable precision | 46% ± 32% | 66% ± 9% | 75% ± 10% | 33% ± 7% |
| Enable recall | 20% ± 8% | 89% ± 12% | 80% ± 8% | 29% ± 10% |
| Enable F1 | 25% ± 8% | 75% ± 7% | 77% ± 7% | 30% ± 7% |
| Enable F1 (priority-weighted) | 37% ± 8% | 79% ± 7% | 80% ± 7% | 37% ± 11% |
| Disable precision | n/a | 52% ± 36% | 62% ± 7% | 0% ± 0% |
| Disable recall | 0% ± 0% | 44% ± 46% | 84% ± 9% | 0% ± 0% |
| Disable F1 | n/a | 52% ± 38% | 71% ± 6% | 0% ± 0% |
| Species violations | 1.4 | 0.6 | 0.0 | 1.2 |
| Conflict violations | 0.2 | 0.0 | 0.8 | 0.0 |
| Use case detected | non_human (60% correct) | non_human (80% correct) | structural_variants (60% correct) | population_genetics (40% correct) |
| Citation rate | 0% ± 0% | 88% ± 5% | 82% ± 11% | 77% ± 9% |

*Species violations (Without KB):* {'gnomad_sv', 'polyphen', 'cadd'}

*Species violations (With KB (keyword)):* {'clinvar', 'polyphen', 'cadd'}

*Species violations (With KB (all examples)):* none

*Species violations (With KB (semantic)):* none

### test_quick_lookup_batch
**Query:** I have a short list of rsIDs and just want their gene, consequence, and ClinVar significance - nothing heavy.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) |
|--------|---|---|---|---|
| Options detected | 2 en / 0 dis | 6 en / 3 dis | 4 en / 2 dis | 5 en / 4 dis |
| Enable precision | 37% ± 22% | 71% ± 32% | 87% ± 30% | 82% ± 25% |
| Enable recall | 20% ± 11% | 80% ± 33% | 65% ± 38% | 85% ± 14% |
| Enable F1 | 26% ± 15% | 66% ± 27% | 65% ± 32% | 81% ± 14% |
| Enable F1 (priority-weighted) | 30% ± 17% | 70% ± 26% | 68% ± 29% | 85% ± 11% |
| Disable precision | n/a | 37% ± 42% | 73% ± 9% | 32% ± 11% |
| Disable recall | 0% ± 0% | 27% ± 38% | 27% ± 37% | 23% ± 15% |
| Disable F1 | n/a | 34% ± 40% | 70% ± 4% | 31% ± 9% |
| Species violations | 0.0 | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.4 | 0.0 | 0.0 |
| Use case detected | quick_lookup (20% correct) | population_genetics (80% correct) | population_genetics (40% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 83% ± 7% | 92% ± 8% | 78% ± 11% |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | With KB (semantic) | Δ (keyword vs bare) | Δ (all examples vs bare) | Δ (semantic vs bare) |
|--------|---|---|---|---|---|---|---|
| Enable F1 | 27% | 59% | 65% | 37% | +32% | +38% | +10% |
| Enable F1 (priority-weighted) | 33% | 64% | 70% | 40% | +31% | +37% | +7% |
| Disable F1 | 0% | 53% | 65% | 18% | +53% | +65% | +18% |
| Enable Precision | 53% | 59% | 67% | 49% | +6% | +14% | -4% |
| Enable Recall | 19% | 67% | 71% | 32% | +48% | +52% | +13% |
| Species violations (total) | 3.8 | 5.4 | 0.8 | 3.4 | +1.6 | -3 | -0.4 |
| Conflict violations (total) | 3.4 | 20.6 | 17.8 | 0 | +17.2 | +14.4 | -3.4 |
| Use case accuracy | 7/20 (35%) | 15/20 (75%) | 15/20 (75%) | 12/20 (60%) | +8 | +8 | +5 |
| Citation rate (avg) | 0% | 83% | 81% | 78% | +83% | +81% | +78% |
