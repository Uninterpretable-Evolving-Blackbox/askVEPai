# VEP Assistant Evaluation Results

**Date:** 2026-06-24T07:49:52.713188
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

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 10 en / 1 dis | 16 en / 2 dis | 16 en / 2 dis |
| Enable precision | 50% ± 12% | 60% ± 4% | 79% ± 8% |
| Enable recall | 40% ± 14% | 74% ± 13% | 95% ± 4% |
| Enable F1 | 44% ± 12% | 65% ± 4% | 86% ± 4% |
| Enable F1 (priority-weighted) | 45% ± 11% | 72% ± 4% | 90% ± 5% |
| Disable precision | 0% ± 0% | 93% ± 15% | 93% ± 15% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 96% ± 9% | 96% ± 9% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 90% ± 2% | 89% ± 3% |

### test_rare_disease_splice_region
**Query:** A rare disease patient has a variant near an exon-intron boundary. I want to assess whether it disrupts splicing as part of the diagnostic workup.

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 1 dis | 13 en / 2 dis | 13 en / 2 dis |
| Enable precision | 45% ± 9% | 64% ± 5% | 68% ± 9% |
| Enable recall | 27% ± 9% | 75% ± 4% | 78% ± 5% |
| Enable F1 | 34% ± 10% | 69% ± 4% | 72% ± 6% |
| Enable F1 (priority-weighted) | 35% ± 11% | 71% ± 5% | 77% ± 5% |
| Disable precision | 0% ± 0% | 43% ± 9% | 50% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 60% ± 9% | 67% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 |
| Use case detected | population_genetics (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 82% ± 6% | 86% ± 5% |

### test_somatic_tumour_wes
**Query:** I'm analysing somatic variants from tumour whole-exome sequencing of cancer patients, called with Mutect2. What VEP options should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 11 en / 0 dis | 15 en / 2 dis | 12 en / 2 dis |
| Enable precision | 40% ± 6% | 43% ± 2% | 79% ± 13% |
| Enable recall | 46% ± 15% | 66% ± 11% | 92% ± 8% |
| Enable F1 | 42% ± 9% | 52% ± 4% | 85% ± 9% |
| Enable F1 (priority-weighted) | 53% ± 11% | 57% ± 5% | 86% ± 7% |
| Disable precision | 0% ± 0% | 87% ± 18% | 100% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 92% ± 11% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.2 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (100% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 85% ± 8% | 86% ± 4% |

### test_regulatory_noncoding_gwas
**Query:** My GWAS hits are mostly in intergenic and intronic regions. I want to understand their potential regulatory effects.

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 8 en / 0 dis | 8 en / 3 dis | 7 en / 5 dis |
| Enable precision | 29% ± 15% | 53% ± 7% | 76% ± 15% |
| Enable recall | 37% ± 14% | 73% ± 9% | 90% ± 22% |
| Enable F1 | 32% ± 14% | 61% ± 7% | 83% ± 18% |
| Enable F1 (priority-weighted) | 46% ± 14% | 62% ± 5% | 84% ± 17% |
| Disable precision | 0% ± 0% | 50% ± 18% | 60% ± 0% |
| Disable recall | 0% ± 0% | 47% ± 30% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 47% ± 22% | 75% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 1.6 | 0.0 | 0.0 |
| Use case detected | structural_variants (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 82% ± 7% | 86% ± 11% |

### test_population_allele_frequencies
**Query:** I want to annotate a large cohort VCF with population allele frequencies to compare variant frequencies across populations.

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 8 en / 1 dis | 7 en / 2 dis | 8 en / 5 dis |
| Enable precision | 29% ± 11% | 78% ± 9% | 86% ± 4% |
| Enable recall | 34% ± 19% | 80% ± 13% | 100% ± 0% |
| Enable F1 | 31% ± 14% | 79% ± 8% | 92% ± 3% |
| Enable F1 (priority-weighted) | 40% ± 17% | 80% ± 8% | 94% ± 2% |
| Disable precision | 0% ± 0% | 0% ± 0% | 66% ± 8% |
| Disable recall | 0% ± 0% | 0% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 0% ± 0% | 79% ± 6% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 0.0 | 0.0 |
| Use case detected | unknown (20% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 78% ± 7% | 90% ± 7% |

### test_non_human_mouse_crispr
**Query:** We performed CRISPR knockouts in mouse embryonic stem cells and called variants from WGS against the GRCm39 reference. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 1 dis | 10 en / 5 dis | 9 en / 7 dis |
| Enable precision | 28% ± 11% | 52% ± 9% | 71% ± 6% |
| Enable recall | 29% ± 17% | 74% ± 19% | 91% ± 8% |
| Enable F1 | 28% ± 14% | 61% ± 13% | 80% ± 7% |
| Enable F1 (priority-weighted) | 39% ± 14% | 67% ± 13% | 86% ± 4% |
| Disable precision | 0% ± 0% | 81% ± 2% | 74% ± 5% |
| Disable recall | 0% ± 0% | 88% ± 11% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 84% ± 6% | 85% ± 3% |
| Species violations | 2.8 | 1.0 | 0.6 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 92% ± 9% | 96% ± 4% |

*Species violations (Without KB):* {'gnomad_sv', 'spliceai', 'cadd'}

*Species violations (With KB (keyword)):* {'ccds'}

*Species violations (With KB (all examples)):* {'ccds'}

### test_quick_lookup_rsid
**Query:** I just want to look up a single variant by its rsID — its gene, consequence, and clinical significance.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 6 en / 3 dis | 5 en / 5 dis | 4 en / 6 dis |
| Enable precision | 25% ± 18% | 91% ± 19% | 100% ± 0% |
| Enable recall | 40% ± 34% | 100% ± 0% | 95% ± 11% |
| Enable F1 | 30% ± 23% | 95% ± 12% | 97% ± 6% |
| Enable F1 (priority-weighted) | 36% ± 25% | 95% ± 10% | 96% ± 8% |
| Disable precision | 0% ± 0% | 0% ± 0% | 0% ± 0% |
| Disable recall | n/a | n/a | n/a |
| Disable F1 | n/a | n/a | n/a |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 86% ± 7% | 90% ± 7% |

### test_rare_disease_trio
**Query:** We sequenced a parent-child trio (exome) to find de novo variants causing a paediatric disorder. Which VEP options for clinical interpretation?

**Source:** [simulated](simulated)

**Ground truth use case:** rare_disease_germline

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 9 en / 1 dis | 16 en / 2 dis | 19 en / 2 dis |
| Enable precision | 50% ± 5% | 70% ± 15% | 71% ± 18% |
| Enable recall | 31% ± 12% | 76% ± 11% | 89% ± 4% |
| Enable F1 | 38% ± 10% | 72% ± 12% | 77% ± 11% |
| Enable F1 (priority-weighted) | 41% ± 10% | 77% ± 10% | 82% ± 8% |
| Disable precision | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | rare_disease_germline (100% correct) | rare_disease_germline (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 4% | 87% ± 2% |

### test_somatic_tumor_only
**Query:** Tumor-only WES with no matched normal. I need to annotate somatic candidates and aggressively filter likely germline variants by population frequency.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 0 dis | 13 en / 2 dis | 11 en / 2 dis |
| Enable precision | 49% ± 11% | 70% ± 16% | 90% ± 8% |
| Enable recall | 33% ± 10% | 80% ± 8% | 91% ± 0% |
| Enable F1 | 39% ± 11% | 74% ± 10% | 90% ± 4% |
| Enable F1 (priority-weighted) | 48% ± 12% | 77% ± 9% | 94% ± 3% |
| Disable precision | n/a | 93% ± 15% | 100% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | n/a | 96% ± 9% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | somatic_cancer (40% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 84% ± 4% | 86% ± 6% |

### test_somatic_ctdna
**Query:** ctDNA / liquid-biopsy somatic variants from a cancer patient, low VAF. Annotate for clinical actionability.

**Source:** [simulated](simulated)

**Ground truth use case:** somatic_cancer

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 0 dis | 11 en / 2 dis | 12 en / 2 dis |
| Enable precision | 51% ± 11% | 69% ± 11% | 82% ± 14% |
| Enable recall | 36% ± 11% | 74% ± 5% | 98% ± 4% |
| Enable F1 | 42% ± 10% | 72% ± 8% | 89% ± 10% |
| Enable F1 (priority-weighted) | 51% ± 11% | 75% ± 8% | 91% ± 9% |
| Disable precision | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | rare_disease_germline (80% correct) | somatic_cancer (100% correct) | somatic_cancer (100% correct) |
| Citation rate | 0% ± 0% | 87% ± 4% | 86% ± 4% |

### test_regulatory_promoter
**Query:** Variants in promoter/enhancer regions from ATAC-seq peaks - which target genes and regulatory features do they hit?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 6 en / 1 dis | 7 en / 4 dis | 7 en / 4 dis |
| Enable precision | 43% ± 4% | 73% ± 6% | 89% ± 11% |
| Enable recall | 34% ± 8% | 69% ± 6% | 86% ± 0% |
| Enable F1 | 38% ± 6% | 71% ± 6% | 87% ± 5% |
| Enable F1 (priority-weighted) | 50% ± 6% | 72% ± 4% | 89% ± 4% |
| Disable precision | 67% ± 58% | 60% ± 11% | 74% ± 16% |
| Disable recall | 20% ± 30% | 80% ± 18% | 100% ± 0% |
| Disable F1 | 43% ± 40% | 68% ± 12% | 84% ± 10% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 80% ± 17% | 82% ± 1% |

### test_regulatory_tfbs
**Query:** Do my non-coding GWAS SNPs overlap transcription factor binding sites or other regulatory features?

**Source:** [simulated](simulated)

**Ground truth use case:** regulatory_noncoding

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 5 en / 0 dis | 7 en / 3 dis | 7 en / 4 dis |
| Enable precision | 39% ± 7% | 71% ± 8% | 68% ± 5% |
| Enable recall | 40% ± 0% | 96% ± 9% | 100% ± 0% |
| Enable F1 | 39% ± 3% | 81% ± 7% | 81% ± 4% |
| Enable F1 (priority-weighted) | 55% ± 2% | 84% ± 8% | 84% ± 3% |
| Disable precision | 0% ± 0% | 100% ± 0% | 74% ± 16% |
| Disable recall | 0% ± 0% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 100% ± 0% | 84% ± 10% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | regulatory_noncoding (100% correct) | regulatory_noncoding (100% correct) |
| Citation rate | 0% ± 0% | 80% ± 6% | 84% ± 10% |

### test_population_ancestry
**Query:** Comparing variant allele frequencies across continental populations in a cohort. Which frequency annotations should I turn on?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 2 dis | 7 en / 3 dis | 8 en / 4 dis |
| Enable precision | 30% ± 12% | 100% ± 0% | 92% ± 7% |
| Enable recall | 31% ± 12% | 94% ± 8% | 100% ± 0% |
| Enable F1 | 30% ± 11% | 97% ± 4% | 96% ± 4% |
| Enable F1 (priority-weighted) | 41% ± 13% | 97% ± 5% | 97% ± 3% |
| Disable precision | 50% ± 41% | 95% ± 11% | 85% ± 14% |
| Disable recall | 27% ± 28% | 100% ± 0% | 100% ± 0% |
| Disable F1 | 37% ± 26% | 97% ± 6% | 91% ± 8% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (40% correct) | population_genetics (100% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 96% ± 6% | 94% ± 8% |

### test_population_large_wgs
**Query:** Annotating a very large WGS cohort VCF (~2M variants) is painfully slow. How do I keep it efficient while still getting gene and frequency annotation?

**Source:** [simulated](simulated)

**Ground truth use case:** population_genetics

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 1 dis | 5 en / 4 dis | 8 en / 6 dis |
| Enable precision | 22% ± 5% | 65% ± 11% | 52% ± 8% |
| Enable recall | 32% ± 18% | 68% ± 39% | 84% ± 17% |
| Enable F1 | 25% ± 8% | 73% ± 6% | 64% ± 11% |
| Enable F1 (priority-weighted) | 36% ± 9% | 69% ± 5% | 62% ± 10% |
| Disable precision | 0% ± 0% | 34% ± 14% | 28% ± 20% |
| Disable recall | 0% ± 0% | 40% ± 28% | 53% ± 38% |
| Disable F1 | 0% ± 0% | 40% ± 16% | 37% ± 26% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | unknown (40% correct) | population_genetics (100% correct) |
| Citation rate | 0% ± 0% | 61% ± 35% | 84% ± 7% |

### test_structural_longread
**Query:** Large deletions and duplications from long-read WGS (Sniffles). Which genes and regulatory features are disrupted, and how do I filter common SVs?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 6 en / 0 dis | 6 en / 4 dis | 7 en / 5 dis |
| Enable precision | 47% ± 8% | 80% ± 14% | 84% ± 5% |
| Enable recall | 43% ± 10% | 71% ± 0% | 86% ± 0% |
| Enable F1 | 44% ± 8% | 75% ± 6% | 85% ± 3% |
| Enable F1 (priority-weighted) | 60% ± 5% | 77% ± 4% | 88% ± 1% |
| Disable precision | n/a | 90% ± 22% | 84% ± 9% |
| Disable recall | 0% ± 0% | 95% ± 11% | 100% ± 0% |
| Disable F1 | n/a | 92% ± 18% | 91% ± 5% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.4 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | population_genetics (80% correct) | structural_variants (100% correct) |
| Citation rate | 0% ± 0% | 89% ± 11% | 94% ± 5% |

### test_structural_cnv
**Query:** CNV calls from a SNP array - which genes do the copy-number gains/losses affect, and are they common in the population?

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 5 en / 0 dis | 7 en / 4 dis | 7 en / 4 dis |
| Enable precision | 58% ± 32% | 60% ± 7% | 70% ± 2% |
| Enable recall | 44% ± 22% | 80% ± 0% | 96% ± 9% |
| Enable F1 | 47% ± 21% | 68% ± 5% | 81% ± 5% |
| Enable F1 (priority-weighted) | 57% ± 28% | 72% ± 4% | 89% ± 7% |
| Disable precision | 0% ± 0% | 85% ± 14% | 87% ± 12% |
| Disable recall | 0% ± 0% | 80% ± 11% | 95% ± 11% |
| Disable F1 | 0% ± 0% | 82% ± 11% | 91% ± 10% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 |
| Use case detected | structural_variants (80% correct) | structural_variants (100% correct) | structural_variants (100% correct) |
| Citation rate | 0% ± 0% | 94% ± 5% | 86% ± 7% |

### test_structural_clinical
**Query:** Clinically interpret structural variants (dels/dups) from a rare-disease WGS case - pathogenic vs benign, filter common ones.

**Source:** [simulated](simulated)

**Ground truth use case:** structural_variants

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 6 en / 0 dis | 9 en / 5 dis | 8 en / 5 dis |
| Enable precision | 44% ± 25% | 51% ± 8% | 66% ± 5% |
| Enable recall | 37% ± 22% | 77% ± 15% | 90% ± 9% |
| Enable F1 | 39% ± 23% | 61% ± 9% | 76% ± 3% |
| Enable F1 (priority-weighted) | 50% ± 22% | 67% ± 11% | 85% ± 4% |
| Disable precision | 100% ± 0% | 58% ± 4% | 59% ± 15% |
| Disable recall | 7% ± 15% | 93% ± 15% | 100% ± 0% |
| Disable F1 | 50% ± 0% | 71% ± 8% | 73% ± 12% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (100% correct) | structural_variants (60% correct) | structural_variants (100% correct) |
| Citation rate | 0% ± 0% | 96% ± 6% | 91% ± 3% |

### test_non_human_zebrafish
**Query:** Zebrafish (Danio rerio) variants from a mutagenesis screen against GRCz11. What VEP settings should I use?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 10 en / 0 dis | 9 en / 6 dis | 8 en / 6 dis |
| Enable precision | 28% ± 10% | 63% ± 13% | 87% ± 1% |
| Enable recall | 37% ± 19% | 83% ± 12% | 97% ± 6% |
| Enable F1 | 31% ± 10% | 71% ± 10% | 92% ± 3% |
| Enable F1 (priority-weighted) | 42% ± 13% | 78% ± 10% | 95% ± 3% |
| Disable precision | 0% ± 0% | 67% ± 19% | 84% ± 18% |
| Disable recall | 0% ± 0% | 76% ± 22% | 100% ± 0% |
| Disable F1 | 0% ± 0% | 70% ± 16% | 91% ± 12% |
| Species violations | 4.2 | 0.4 | 0.0 |
| Conflict violations | 1.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (40% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 93% ± 5% | 97% ± 4% |

*Species violations (Without KB):* {'cadd', 'polyphen', 'mutfunc'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

### test_non_human_rat
**Query:** Rat (Rattus norvegicus) WGS variants from a knockout model. Which VEP options apply?

**Source:** [simulated](simulated)

**Ground truth use case:** non_human

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 10 en / 1 dis | 8 en / 7 dis | 8 en / 7 dis |
| Enable precision | 27% ± 10% | 66% ± 7% | 83% ± 14% |
| Enable recall | 40% ± 12% | 77% ± 8% | 97% ± 6% |
| Enable F1 | 32% ± 11% | 71% ± 5% | 89% ± 7% |
| Enable F1 (priority-weighted) | 45% ± 11% | 76% ± 5% | 92% ± 6% |
| Disable precision | 100% ± 0% | 66% ± 14% | 73% ± 11% |
| Disable recall | 20% ± 20% | 84% ± 9% | 100% ± 0% |
| Disable F1 | 49% ± 14% | 73% ± 8% | 84% ± 8% |
| Species violations | 4.6 | 0.0 | 0.0 |
| Conflict violations | 0.0 | 0.0 | 0.0 |
| Use case detected | structural_variants (40% correct) | non_human (100% correct) | non_human (100% correct) |
| Citation rate | 0% ± 0% | 97% ± 5% | 97% ± 4% |

*Species violations (Without KB):* {'gnomad_sv', 'polyphen', 'mutfunc', 'cadd', 'spliceai', 'revel'}

*Species violations (With KB (keyword)):* none

*Species violations (With KB (all examples)):* none

### test_quick_lookup_batch
**Query:** I have a short list of rsIDs and just want their gene, consequence, and ClinVar significance - nothing heavy.

**Source:** [simulated](simulated)

**Ground truth use case:** quick_lookup

| Metric | Without KB | With KB (keyword) | With KB (all examples) |
|--------|---|---|---|
| Options detected | 7 en / 2 dis | 4 en / 3 dis | 4 en / 5 dis |
| Enable precision | 12% ± 11% | 92% ± 11% | 100% ± 0% |
| Enable recall | 25% ± 25% | 95% ± 11% | 100% ± 0% |
| Enable F1 | 16% ± 15% | 93% ± 7% | 100% ± 0% |
| Enable F1 (priority-weighted) | 21% ± 19% | 93% ± 7% | 100% ± 0% |
| Disable precision | 12% ± 25% | 35% ± 9% | 79% ± 14% |
| Disable recall | 3% ± 7% | 17% ± 0% | 60% ± 9% |
| Disable F1 | 6% ± 12% | 22% ± 2% | 68% ± 10% |
| Species violations | 0.0 | 0.0 | 0.0 |
| Conflict violations | 0.6 | 0.0 | 0.0 |
| Use case detected | unknown (0% correct) | quick_lookup (100% correct) | quick_lookup (100% correct) |
| Citation rate | 0% ± 0% | 88% ± 7% | 88% ± 8% |

## Summary

| Metric | Without KB | With KB (keyword) | With KB (all examples) | Δ (keyword vs bare) | Δ (all examples vs bare) |
|--------|---|---|---|---|---|
| Enable F1 | 35% | 73% | 85% | +38% | +50% |
| Enable F1 (priority-weighted) | 45% | 76% | 88% | +31% | +44% |
| Disable F1 | 11% | 73% | 84% | +62% | +73% |
| Enable Precision | 37% | 69% | 80% | +31% | +42% |
| Enable Recall | 36% | 79% | 93% | +43% | +57% |
| Species violations (total) | 11.6 | 1.4 | 0.6 | -10.2 | -11 |
| Conflict violations (total) | 6.4 | 0 | 0 | -6.4 | -6.4 |
| Use case accuracy | 5/20 (25%) | 19/20 (95%) | 20/20 (100%) | +14 | +15 |
| Citation rate (avg) | 0% | 86% | 89% | +86% | +89% |
