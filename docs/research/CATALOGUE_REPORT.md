# Phase 1 — Expanded VEP Web-Form Option Catalogue

**Status:** complete (provisional priorities pending gold-standard data).
**Output:** `vep_options_expanded.json` — **58 options** (38 native fields, 19 web-exposed plugins, 1 custom dataset), spanning all 6 canonical web-form sections.
**Demo baseline:** 26 options → **+32 added, 20 corrected, 14 kept-and-fixed**.

This catalogue replaces the demo's 26-option knowledge base, rebuilt to match the **actual Ensembl VEP web form** rather than an approximation. Every factual field is grounded in Ensembl `public-plugins` `release/115` source (not model memory), then adversarially verified.

## Sources (ground truth)

Downloaded to `../../ensembl_source/` from `github.com/Ensembl/public-plugins@release/115`:

| File | What it provided |
|------|------------------|
| `Web/VEPConstants.pm` | The 6 canonical `CONFIG_SECTIONS` ids + titles |
| `Component/Tools/VEP/InputForm.pm` | Real form structure: every native field, its section/subsection, defaults, and **species restrictions** (via `_stt_Homo_sapiens` field classes) |
| `Web/Object/VEP.pm` (`get_form_details`) | Exact web labels, helptips, and dropdown value lists |
| `conf/vep_plugins_web_config.txt` | The exact 26 web-exposed plugins |
| `conf/vep_custom_web_config.json` | Custom datasets (gnomAD-SV, AllOfUs, GENCODE promoters) |
| Live docs | `vep_options.html`, `vep_plugins.html` (CLI flags, plugin data sources) |

## The 6 canonical web-form sections

`identifiers` · `variants_frequency_data` · `additional_annotations` · `predictions` · `filters` · `advanced`

The demo used ad-hoc `web_form_section` strings (e.g. "Transcript set", "Identifiers and transcript information"). All entries now map to one of these 6 ids, enabling the click-to-apply frontend mapping (proposal §4.4).

## Key corrections vs the demo (real errors fixed)

1. **Plugins ≠ native fields.** CADD, REVEL, AlphaMissense, SpliceAI, MaxEntScan, dbNSFP were modelled as native checkboxes. They are **VEP plugins** (`--plugin X`), now `source_type: plugin` in `predictions`/`additional_annotations`.
2. **"Restrict results" is one dropdown.** `pick / pick_allele / per_gene / summary / most_severe` are mutually-exclusive **values of a single control**, not independent checkboxes. Modelled as conflicting entries in `filters`, with `summary`/`most_severe` declared to conflict with every per-transcript annotation.
3. **gnomAD split.** `gnomad_af` → `af_gnomade` (exomes) + `af_gnomadg` (genomes).
4. **1000G disambiguated.** `af` (global MAF, default ON) vs `af_1kg` (continental) — the demo conflated them.
5. **Renames to real web/CLI names.** `transcript_set` → `core_type`; `mane_select` → `mane` (CLI `--mane`, not `--mane_select`).
6. **Defaults fixed from source.** e.g. `hgvs`, `protein` are OFF by default on the web form (no `checked` key in `InputForm.pm`) — the brief implied ON.
7. **Dependencies captured.** Frequency/citation/synonym fields (`af`, `af_1kg`, `af_gnomade`, `af_gnomadg`, `pubmed`, `var_synonyms`, `failed`, `clinvar`) `depends_on: [check_existing]`; `cell_type depends_on [regulatory]`.
8. **17 missing native fields added:** `transcript_version, ccds, protein, uniprot, var_synonyms, af, pubmed, failed, biotype, numbers, tsl, appris, distance, mirna, coding_only, frequency, buffer_size, shift_3prime`.

## Adversarial verification

Each entry was checked by an independent verifier prompted to **refute** its factual fields against the source. **8 issues found, all resolved:**

| Option | Severity | Fix |
|--------|----------|-----|
| `gene_phenotype` | **major** | No native `gene_phenotype` web field exists — phenotype data comes via the **Phenotypes plugin**. Removed (superseded by the `phenotypes` entry). |
| `alphamissense` | minor | species_restriction → "human only (GRCh37 and GRCh38)" (was GRCh38-only) |
| `shift_3prime` | minor | name → "Right align variants prior to consequence calculation" |
| `mirna` | minor | name → "miRNA structure" |
| `geno2mp` | minor | field is `HPO_CT`, not `HPO_count` |
| `check_existing` | minor | description corrected to source helptip |
| `coding_only` | minor | description/side_effects corrected |
| `core_type` | minor | **documented limitation** (see below) |

## Compatibility + correctness tests (passed)

Ran the demo's own functions against the new catalogue:
- `build_option_aliases` → 130 aliases; `compress_options` → 58 lines, no `KeyError`; semantic fields (`when_to_use`/`when_not_to_use`) present on all; `get_confidence` works.
- **Species correctness:** mouse query → 6 human-only options (CADD, AlphaMissense, ClinVar, REVEL, PolyPhen, gnomAD-exomes) blocked; multi-species options (SIFT, biotype, symbol) correctly kept.
- **Conflict correctness:** `most_severe` correctly yields to per-transcript detail (SIFT, PolyPhen, HGVS, MANE, symbol).

Schema is identical to the demo's contract (`id, name, cli_flag, web_form_section, category, description, when_to_use, when_not_to_use, use_case_tags, priority_by_use_case, species_restriction, depends_on, conflicts_with, side_effects`) plus harmless metadata (`source_type, is_new, web_form_subsection, web_default, provenance`). **Drop-in compatible.**

## Known limitations / decisions (for mentor review)

- **`core_type` section.** The transcript-database radiolist is rendered as a top-level/pre-section field in `get_cacheable_form_node`, not inside any of the 6 `CONFIG_SECTIONS`. Mapped to `advanced` as least-wrong within the enum; flagged in `provenance`. Worth a frontend-mapping decision with the mentor.
- **`priority_by_use_case` is provisional.** Grounded in VEP best practice, but these per-use-case priorities are exactly what the gold-standard examples should calibrate. Treat as a starting point.
- **Deferred (documented, not lost):** lower-priority plugins (GO, AncestralAllele, OpenTargets, IntAct, MaveDB, RiboseqORFs, Blosum62) and customs (AllOfUs, GENCODE_promoter) were held back to stay near the ~55 target. Adding them reaches the full 26-plugin surface — a fast follow.
- **Frequency sub-controls** (`freq_pop/freq_freq/freq_gt_lt/freq_filter`) are modelled as children of the single `frequency` entry, not separate options.

## Provenance artifacts

`research/` holds the four source-grounded research dossiers (native fields, plugins, constraints/species, model landscape) and `catalogue_skeleton.json`. `assemble_catalogue.py` reproduces `vep_options_expanded.json` from the workflow output.
