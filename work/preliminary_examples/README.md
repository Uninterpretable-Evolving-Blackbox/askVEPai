# Preliminary (bootstrap) training examples

A **finite, high-confidence** set of (query → VEP configuration) examples to start preliminary
experiments **while the mentor's official gold-standard data is pending**. These are deliberately
*not* called gold-standard — they are my defensible best-effort, to be replaced/augmented by the
mentor's curated set.

- **`bootstrap_examples.json`** — 7 examples in the same schema as the demo's `training_examples.json`, but using the **expanded catalogue ids** (`work/vep_options_expanded.json`).
- **`validate_examples.py`** — reproduces the confidence check below.

## The bar for inclusion ("confident in setting")

An example was included only if **all** held:
1. **Unambiguous use case** — the scenario maps cleanly to one of the 7 categories.
2. **Defensible from first principles** — every enabled/disabled option follows from VEP best practice + the catalogue's own metadata (species rules, conflicts, dependencies), not lab-specific taste.
3. **Machine-verified** — passes the deterministic constraint checker with **zero species/conflict violations** and **dependencies already satisfied** (no auto-corrections needed). All 7 pass.

## The set (7 examples, 6 of the 7 categories)

| id | category | confidence | the defensible core |
|----|----------|-----------|---------------------|
| `rare_disease_exome_clinical` | rare_disease_germline | high | identifiers + MANE/canonical + SIFT/PolyPhen/CADD + ClinVar + gnomAD; keep per-transcript detail |
| `rare_disease_splice_region` | rare_disease_germline | high | SpliceAI + exon/intron numbers + clinical identifiers + gnomAD |
| `somatic_tumour_wes` | somatic_cancer | high | known-variant flagging (COSMIC) + pathogenicity + gnomAD germline filter |
| `regulatory_noncoding_gwas` | regulatory_noncoding | medium-high | regulatory build is the differentiator; missense predictors N/A |
| `population_allele_frequencies` | population_genetics | high | all four frequency sources (1000G global/continental, gnomAD ex/genome) |
| `non_human_mouse_crispr` | non_human | high | species-agnostic only; **withholds** all human-only tools (the species-safety test case) |
| `quick_lookup_rsid` | quick_lookup | high | minimal: symbol + check_existing + ClinVar + HGVS |

## What I deliberately EXCLUDED (lower confidence → leave for the mentor)

- **`structural_variants`** — SV annotation (overlap handling, `gnomad_sv`, which fields) is specialised; I am not confident enough to set a defensible config without guidance. **No example provided.**
- **Choice among redundant missense predictors** — CADD/REVEL/AlphaMissense/ClinPred/EVE overlap. I enable the standard SIFT/PolyPhen/CADD and leave the rest out rather than guess a "best" combination.
- **Extra splice predictors** — SpliceAI is included as the standard; MaxEntScan/dbscSNV are reasonable but left out as a judgment call.
- **Regulatory-impact plugins** — Enformer/UTRAnnotator could help non-coding analysis but are a lower-confidence add.
- **Exact value-level details** — gnomAD exome-vs-genome emphasis, frequency thresholds, SIFT mode (`b`/`p`/`s`) — set to sensible defaults but these are exactly what gold-standard data should calibrate.
- **`priority_by_use_case`** in the catalogue remains provisional (see `../CATALOGUE_REPORT.md`); these examples are the evidence that should later calibrate it.

## Running a preliminary experiment with this set

The demo's `vep_assistant.py` / `evaluate.py` load `vep_options.json` + `training_examples.json` from
their own directory. To run on **(expanded catalogue + these bootstrap examples)** without disturbing the
demo, point the pipeline at these files (a thin wrapper, not yet written) and:

1. **Pull a model** (currently deferred): e.g. `ollama pull gemma4:12b` (or the demo baseline `qwen2.5:7b`).
2. Run leave-one-out evaluation over the 7 examples; with the priority-weighted F1 + the hardened checker already in place.

> Note: actual runs are blocked only on pulling a local model. The example set itself is ready.
