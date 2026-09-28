---
title: "Ask VEPai — Work Progress"
subtitle: "GSoC 2026 · EMBL-EBI · David (Wei) Gao"
date: "Last updated: 2026-07-08"
---

# Ask VEPai — Work Progress

**Project:** Ask VEPai — Provenance-Traced AI Configuration Assistant for Ensembl VEP Web
**Contributor:** David (Wei) Gao · **Mentor:** Likhitha Surapaneni · **Org:** EMBL-EBI (Genome Assembly & Annotation)
**Repo:** `vep_ai_demo/` (cloned) · **Working area:** `GSoC_WORK/`

**Layout:** `vep_ai_demo/` = the runnable demo (code + data + `results/`); `work/` = all deliverables, summaries, research & reference; `PROGRESS.md` + `Ask_VEPai_Progress.docx` = this summary (repo root). See `work/README.md` for the deliverables index.

> Living document. Source of truth is `PROGRESS.md`; the `.docx` is regenerated from it. Provenance tags: **[repo]** (inspected a repo file), **[doc]** (official docs), **[web]** (web search/fetch, with link), **[derived]** (my reasoning/implementation). **§3 = the proposed/target system; §4 = what we have now.** See §12 for the master source list and §13 for the change log.

---

## 1. Status at a glance

| Area | Status |
|------|--------|
| Proposal understood | ✅ |
| Demo repo cloned | ✅ `vep_ai_demo/` |
| Real Ensembl source downloaded (provenance) | ✅ `work/ensembl_source/` (release/115) |
| Phase-1 option catalogue (26 → ~55) | ✅ 58 options, verified |
| Constraint checker hardened | ✅ dependencies + semantic use-case |
| Structured JSON output schema | ✅ designed + validated |
| Eval harness upgraded | ✅ priority-weighted F1 + value scoring |
| Model landscape (incl. Gemma 4) | ✅ researched + headline verified |
| Preliminary bootstrap examples (7, verified) | ✅ `work/preliminary_examples/` |
| Gold-standard examples (8 → 15–20, official) | ⛔ blocked on mentor data |
| Gold-example **generation pipeline** (Stages 0–6) | ✅ built `work/generation/` (provisional config; mentor-gated) |
| Environment (Ollama models, live run) | ✅ native-arm64 Ollama up; gemma4 e4b/12b/26b pulled |

---

## 2. Provenance & methods

- **[repo] Repository inspection.** Downloaded the real Ensembl `public-plugins` `release/115` files that define the VEP web tool and read them directly (`GSoC_WORK/work/ensembl_source/`). Ground truth for the catalogue, section ids, labels/defaults, species rules, and plugin list.
- **[doc] Documentation reading.** Cross-checked CLI flags and plugin data sources against the live VEP docs (`vep_options.html`, `vep_plugins.html`).
- **[web] Web search/fetch.** The model landscape (§6.5) came from a research subagent (web, June 2026); the **headline Gemma 4 claims were independently re-verified by me** against the Ollama library page + Google blog.
- **[derived] Implementation + verification.** Code edits each came with a test run; the catalogue was **adversarially verified** by an independent agent (8 issues found and fixed — §8).

---

## 3. Proposed system — target architecture, scope & roadmap

This is what Ask VEPai is **meant to become** (from the proposal). §4 ("what we currently have") should be read against this target.

### 3.1 The problem & the core idea
The VEP web form exposes a large configuration surface — transcript sets, frequency data, pathogenicity predictors, regulatory annotations, filters, output options, species/assembly — which overwhelms newcomers (clinicians, wet-lab researchers, students) and generates recurring helpdesk queries. **Ask VEPai turns a plain-English description of an analysis into a recommended web-form configuration, with justifications**, running **locally on open-source models** (privacy for patient-cohort queries + alignment with EBI's open principles).

### 3.2 Target architecture — "defense-in-depth"
Full GSoC version (the demo only realises part of this — see §3.5):

```
User scenario (natural language)
  │
  ▼
RAG LAYER  — grounds answers in an editable knowledge base, NOT the model weights
  ├─ Knowledge base : ~55 web options + 15–20 gold-standard examples (JSON)
  ├─ Retrieval      : BGE-small semantic (+ keyword baseline); selective as the KB grows
  ├─ Generation     : local LLM via Ollama (model chosen by a structured comparison)
  └─ Parsing        : extract per-option enable/disable (+ values)
  │
  ▼
CONSTRAINT CHECKER  — deterministic, no ML — the safety net
  ├─ species   : human-only options blocked for non-human queries
  ├─ conflict  : mutually-exclusive options resolved by priority
  └─ dependency: required options auto-enabled
  │
  ▼
STRUCTURED JSON OUTPUT  — each decision mapped to web_form_section + web_form_field
  └─ → "click to apply" on the Ensembl web form   +   a ready-to-run CLI command
  │
  ▼
INTERPRETABILITY LAYER  (cross-cutting)
  ├─ decision trace      : retrieval scores + confidence/priority/species map
  ├─ source citations    : [source: option_id] on every recommendation
  └─ [extended] attribution testing : is each recommendation truly KB-grounded vs stale?
```

**Why this shape (empirical justification, from the demo):** the knowledge base lifts Enable F1 by **+19–30% at every model size** (grounding works), but **species violations persist even at 14B** (the LLM cannot reliably self-police) — so a deterministic checker is **architecturally necessary, not optional**. Structured output enables click-to-apply; the trace + citations make the output trustworthy enough for scientists to act on.

### 3.3 Scope — core vs extended deliverables
- **Core (175 h "Medium"):** expanded KB (~55 options); gold-standard corpus (15–20 examples, 80/20 split); RAG pipeline returning **JSON**; semantic retrieval benchmarked vs keyword; constraint checker (100% species detection); multi-model evaluation report (N=3–5, mean±SD); web-form JSON schema; end-to-end demo; documentation.
- **Extended (stretch / "Large" ~350 h):** **QLoRA** fine-tune a 7B for schema adherence; **attribution testing** (remove a KB entry, re-run, see if the recommendation disappears → grounded vs stale); **FastAPI** POST endpoint; **VEP output explainer** (consequence terms).

### 3.4 Phase roadmap
- **Phase 0 (community bonding):** dev env; review the real web form with mentor; align the JSON schema; audit helpdesk queries.
- **Phase 1:** expand KB → ~55; 15–20 gold-standard examples; finalise schema; 80/20 split.
- **Phase 2:** semantic retrieval + Ollama integration; benchmark model sizes; harden constraint checker; full eval (N=3–5) + report. *(Midterm checkpoint.)*
- **Phase 3:** structured JSON output + web-form mapping; end-to-end demo; documentation.
- **Phase 4 (extended):** QLoRA; attribution testing; FastAPI; output explainer.

### 3.5 Demo prototype vs GSoC target (proposal Table 1, annotated with current progress)

| Component | Demo prototype | GSoC target | Where it stands now |
|-----------|----------------|-------------|---------------------|
| Model | Qwen2.5 3B/7B/14B | chosen by structured comparison | model brief done (Gemma 4 12B / Qwen3.x / Mistral); **not pulled** |
| Compute | M3 8GB / M5 Max 128GB | M5 Max 128GB | ✅ on the M5 Max |
| Knowledge base | 26 options, 8 examples | ~55 options, 15–20 examples | **58 options ✅**; examples ⛔ blocked |
| Retrieval | keyword + BGE-small | optimised for the larger KB | unchanged (works) |
| Output format | free-text markdown | structured JSON → web form | **schema designed ✅**; emitter pending |
| Constraint checker | species + conflict | + dependency, hardened | **done ✅** |
| Evaluation | 8 queries, N=1, 6 metrics | 15–20 queries, N=3–5, mean±SD | **priority-weighted F1 added ✅**; bigger set ⛔ blocked |
| Fine-tuning | none | QLoRA on a 7B [extended] | not started |

---

## 4. What we currently have — architecture & component walkthrough

**Mental model: defense-in-depth RAG.** The slogan: **the LLM proposes, deterministic Python disposes.** This is the *implemented* pipeline (a subset of §3.2).

**Flow of one query:**

```
User scenario
  → [B2] Retrieval ........... pick the few most relevant examples/options
  → [B3] Prompt assembly ..... compress KB + worked examples + strict output format
  → [B4] LLM generation ...... local model (Ollama) drafts the recommendation
  → [B5] Response parsing .... turn free text into machine sets {enable},{disable}
  → [B6] Constraint checker .. species / conflict / dependency — auto-corrected
  → [B7] Output .............. free-text now; [B8] structured JSON schema designed
        └ [B9] Interpretability (decision trace + [source:] citations) runs alongside
Separate mode: [B10] VEP output explainer (explains result annotations, not options)
Offline:       [B11] Evaluation harness (leave-one-out, 6 metrics, multi-run)
```

Each block — where it lives, its role, and the intuition:

### B1 · Knowledge base (the data)
- **Where:** `vep_options.json` (demo, 26) / `work/vep_options_expanded.json` (new, 58); `training_examples.json` (8 scenario→config triples); `vep_consequences.json` (41 Sequence-Ontology terms). Loaded by `load_knowledge_base()` / `load_consequences()`.
- **Role:** the factual grounding. Each option carries `cli_flag`, `web_form_section`, `species_restriction`, `conflicts_with`, `depends_on`, `priority_by_use_case`, etc.
- **Intuition:** in RAG the model's knowledge lives in **editable JSON, not the weights** — a quarterly VEP change is a JSON edit, not a retrain. The same metadata also powers the deterministic checker (B6), so the data both grounds the LLM *and* drives the safety net.

### B2 · Retrieval
- **Where:** `retrieve_examples_keyword` (word overlap); `retrieve_examples_semantic` + `retrieve_options_semantic` (BGE-small-en-v1.5 cosine, lazy-loaded).
- **Role:** select the top-2 most relevant worked examples (and, in semantic mode, top-10 options) for the prompt.
- **Intuition:** small local models have limited context — you can't paste all 58 options + every example each time. Retrieval shows the model the few examples that *resemble* the query (few-shot grounding). Keyword wins at small KB sizes; semantic becomes necessary as the KB outgrows the context budget.

### B3 · Prompt assembly
- **Where:** `build_system_prompt`, `compress_options`, `format_example`.
- **Role:** build the system prompt = compressed option reference + retrieved examples + a **strict output-format spec** (`✓/✗ option [source: id] confidence + Reason:`) + rules.
- **Intuition:** compression makes the KB fit; the rigid format makes the free text **parseable** (B5) and **forces citations** (B9). Much of the "structured output" behaviour is achieved here by prompting alone.

### B4 · LLM generation
- **Where:** `stream_response` (Ollama via the OpenAI-compatible API); model from `VEP_MODEL` (default `qwen2.5:3b`).
- **Role:** generate the draft recommendation, streamed.
- **Intuition:** **local + open-source** = privacy (patient-cohort queries never leave the machine) and EBI alignment — a mentor-confirmed requirement.

### B5 · Response parsing
- **Where:** `extract_recommendations`, `build_option_aliases`, `_match_option`.
- **Role:** convert prose into machine sets `{enabled}`, `{disabled}` by fuzzy-matching names/flags/aliases (tables first, then prose, word-boundary matched).
- **Intuition:** the model writes sentences; the checker needs sets. Alias maps (`polyphen2`→`polyphen`, `gnomad`→`gnomad_af`) make extraction robust. **This is the seam** the Phase-1 structured-JSON output (B8) will eventually replace.

### B6 · Constraint checker — the safety net
- **Where:** `check_and_fix_violations` + `infer_species`, `_is_human_only`, `_detect_use_case`, `_get_priority_rank`, `format_violation_warnings`.
- **Role:** deterministic, **no-ML** post-processing: **(a) species** (block human-only options for non-human queries); **(b) conflict** (resolve mutually-exclusive options by priority, then restrictiveness); **(c) dependency** *(added this session)* (auto-enable a required option, species-guarded). Returns violations; warnings shown.
- **Intuition:** the **empirical heart**. Species violations persist *even at 14B*, so a tiny pure-Python function reliably catches the structural errors the LLM misses — generation is fuzzy, the guardrail is exact.

### B7 · Output (current + planned)
- **Where (now):** `save_result` writes recommendation + warnings + generated `vep …` command as markdown to `results/`.
- **Intuition:** human-readable prose today; B8 makes it machine-actionable.

### B8 · Structured JSON output schema *(new, designed — not yet wired)*
- **Where:** `work/output_schema/` (schema, validated example, design doc).
- **Role:** define the JSON the pipeline will emit — each decision mapped to `web_form_section` + `web_form_field` (real `InputForm.pm` control name) + `action`/`value` + `cli_flag`.
- **Intuition:** free-text can't drive a UI; the frontend needs **addresses** to auto-fill the form ("click to apply"). Schema designed/validated; emitter wiring pending mentor sign-off.

### B9 · Interpretability (decision trace + citations)
- **Where:** `print_decision_trace` (`--explain`), `get_confidence`; the `[source: option_id]` tags from B3.
- **Role:** Layer 1 = retrieval scores (which examples chosen, why); Layer 2 = per-option confidence/priority/species map; citations trace each recommendation to a KB entry.
- **Intuition:** **trust requires traceability** — the project's "Provenance-Traced" core. (This trace is *structured*; distinct from the LLM's inline natural-language `Reason:` lines.)

### B10 · VEP output explainer *(separate mode)*
- **Where:** `build_explain_result_prompt`, `run_explain_result`, `vep_consequences.json`; CLI `explain-result`.
- **Role:** a **different** feature — explains VEP *result* annotations (consequence terms like `splice_donor_variant`), **not** why options were recommended.
- **Intuition:** the §3.3 extended goal — help users understand VEP *output*, not just configure its *input*.

### B11 · Evaluation harness *(offline)*
- **Where:** `evaluate.py` — `TEST_QUERIES` (8), `score_response` (P/R/F1 + new **priority-weighted** F1), `measure_citation_rate`, `extract_use_case`, `check_species/conflict_violations`, `get_ground_truth` (leave-one-out), `aggregate_scores` (mean±SD), `generate_report`; new `score_value_accuracy`/`get_ground_truth_values`.
- **Role:** quantify quality across conditions (no-KB / keyword / semantic / all-examples) and model sizes.
- **Intuition:** **leave-one-out** keeps the numbers honest (the scored example is removed from retrieval, so the model can't copy the answer). Priority-weighting makes the score reflect clinical importance, not raw option count.

**Where this session's work plugs into the target (§3.2):** catalogue→**B1**, constraint hardening→**B6**, output schema→**B8**, eval upgrades→**B11**. The blocked gold-standard examples feed **B1/B2** and **B11**.

---

## 5. Environment

- **Machine:** Apple M5 Max, 128 GB, 294 GB free (the proposal's eval box). **[derived]** via `sysctl`. Handles 3B/7B/14B + QLoRA.
- **Python:** 3.12 (anaconda); `openai` and `sentence-transformers` installed (NumPy warnings cosmetic). **[derived]**
- **Ollama:** installed and **running (native-arm64 on Metal, ~180 tok/s)**; `gemma4:{e4b,12b,26b,31b}` +
  `qwen2.5:{3b,7b}` pulled. **26b is the deployed/canonical model.** *(Corrected 2026-07-15 — this line said
  "server not running, no models pulled", which was true when written but has been stale since 2026-06-06;
  every experiment from Exp 1 onward ran on this stack.)*
- **Tooling present:** pandoc 3.9, python-docx, gh (unauthenticated), git.

---

## 6. Completed work (Phase-1 foundation)

New artifacts in `work/`. Demo code edits in `vep_assistant.py` and `evaluate.py` (tested, uncommitted).

### 6.1 Expanded option catalogue — `work/vep_options_expanded.json` (block B1)
- **58 options** (38 native, 19 plugins, 1 custom); all 6 canonical sections; **+32 added, 20 corrected** vs the demo's 26. Schema-compatible; species + conflict logic tested.
- **Source/provenance [repo]:** `InputForm.pm`, `Object_VEP.pm` `get_form_details`, `VEPConstants.pm`, `vep_plugins_web_config.txt`, `vep_custom_web_config.json`; cross-checked vs `vep_options.html` **[doc]**; adversarially verified **[derived]**.
- Docs: `CATALOGUE_REPORT.md`; reproducer: `assemble_catalogue.py`; id map: `id_migration.json`.
- **How `priority_by_use_case` ("criticality") was set — and its provenance.** Each option gets `critical`/`recommended`/`optional`/`not_applicable` *per use case*. (i) For the 14 kept demo options the priorities were **inherited unchanged** from the demo (verified identical for symbol/sift/check_existing/regulatory). (ii) For new/corrected options the build agents assigned them from **VEP best-practice heuristics** using the demo's pattern as a template + the rule "human-only → `non_human = not_applicable`" (held for all 29 human-only options). (iii) **No authoritative Ensembl source ranks option importance per scenario** — so unlike `cli_flag`/`web_form_section`/`species_restriction` (hard-sourced), these are **expert/model judgment, flagged provisional**. They are read downstream by the constraint checker for **conflict resolution** (lower priority loses) and **confidence display**. *Plan:* calibrate them empirically from the gold-standard examples. **[demo-inherited + derived]**

### 6.2 Hardened constraint checker — `vep_assistant.py` (block B6) **[derived]**
- Enforces `depends_on` (auto-enable, species-guarded); `_detect_use_case` respects `--semantic`. Tested on both catalogues. **Motivation [repo]:** demo README listed both as known gaps.

### 6.3 Structured JSON output schema — `work/output_schema/` (block B8) **[repo/derived]**
- Schema + validated example + design doc; maps each decision to `web_form_section` + `web_form_field` + `action`/`value` + `cli_flag`. **Source [repo]:** field `name`s from `InputForm.pm`; sections from `VEPConstants.pm`.

### 6.4 Eval harness upgrade — `evaluate.py` (block B11) **[derived]**
- **Priority-weighted Enable F1** + **value-accuracy scaffolding** (`score_value_accuracy`, `get_ground_truth_values`). Tested. **Motivation [repo]:** demo README "Known limitations".

### 6.5 Model landscape — `work/research/model_landscape.md` **[web]**

Research subagent (web, June 2026); Gemma 4 re-verified by me. Each point + source:

- **Gemma 4 — Apr 2026, Apache 2.0** *(re-verified).* Sizes **E2B / E4B / 12B dense / 26B MoE (3.8B active) / 31B dense** + `-mlx` + `31B-cloud`; day-one Ollama. **Context 128K for E2B/E4B/12B, 256K for 26B/31B.** Sources: [Ollama `gemma4` (fetched)](https://ollama.com/library/gemma4), [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/), [Apache-2.0 overview](https://www.mindstudio.ai/blog/what-is-gemma-4-google-open-weight-model).
- **Recommendation: Gemma 4 12B primary** — best small-dense instruction-following, native JSON + function calling + system prompts, clean license, MLX/Ollama support. **[web/derived]**
- **Qwen3.x (3.5-9B Instruct / 3.6-27B dense), Apache 2.0** — top IFEval-class IF; use Instruct to avoid thinking-mode JSON leak. Sources: [Qwen3.5](https://ollama.com/library/qwen3.5), [Qwen3.6](https://ollama.com/library/qwen3.6), [IFEval](https://llm-stats.com/benchmarks/ifeval), [HF leak](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/18). **[web]**
- **Qwen2.5-7B-Instruct baseline.** Sources: [Ollama](https://ollama.com/library/qwen2.5:7b-instruct), [HF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct). **[web]**
- **Mistral Small 3.2 (24B), Apache 2.0** — diversity pick. Source: [Ollama](https://ollama.com/library/mistral-small3.2). **[web]**
- **Llama 4 — skip for 7B-class** (no small dense, restrictive license, heavy). Sources: [Ollama](https://ollama.com/library/llama4), [Meta](https://ai.meta.com/blog/llama-4-multimodal-intelligence/). **[web]**
- **Phi-4 (14B)/mini (3.8B), MIT.** Sources: [Ollama](https://ollama.com/library/phi4), [Microsoft](https://techcommunity.microsoft.com/blog/educatordeveloperblog/welcome-to-the-new-phi-4-models---microsoft-phi-4-mini--phi-4-multimodal/4386037). **[web]**
- **Ollama JSON-schema via XGrammar `format`** (structural validity only). Source: [Ollama](https://ollama.com/blog/structured-outputs). **[web]**
- **QLoRA on M5 Max via MLX** (export to GGUF). Sources: [MLX QLoRA](https://insiderllm.com/guides/fine-tuning-mac-lora-mlx/), [Gemma 4 + MLX](https://antigravitylab.net/en/articles/antigravity/gemma-4-finetuning-apple-silicon-mlx-guide). **[web]**
- **Confidence:** Gemma 4 verified vs Ollama + Google blog; other specifics indicative — confirm with a live `ollama pull`; the test suite is the tiebreaker.

### 6.6 Research dossiers — `work/research/`
`native_fields_dossier.md`, `plugins_dossier.md`, `constraints_dossier.md`, `catalogue_skeleton.json`. **[repo + doc]**

### 6.8 First experimental results — real system, Metal GPU **[derived, 2026-06-06]**
Ran the **parallel** eval (`work/harness/done/run_parallel_eval.py`, 4 concurrent GPU slots) on the **real system**: 58-option catalogue + **20-example simulated gold set** (`work/preliminary_examples/simulated_gold_examples.json`, all 7 use cases ~3 each, checker-validated), leave-one-out, 3 runs, 4 conditions. Env: native arm64 Ollama on Apple M5 Max Metal (~180 tok/s; the earlier 10 tok/s was an Intel/Rosetta brew build).

**Enable F1 (mean over 20 queries × 3 runs), 5 models** *(rough order only — see confound note)*:

| model | bare | keyword | all-ex | semantic | all − kw |
|-------|------|---------|--------|----------|----------|
| qwen2.5:3b | 31% | 35% | 39% | 33% | +4% |
| gemma4:e4b | 26% | 45% | 49% | 32% | +4% |
| qwen2.5:7b | 33% | 45% | 47% | 36% | +2% |
| gemma4:12b | 26% | 46% | 50% | 29% | +4% |
| gemma4:26b | 31% | **52%** | **55%** | 25% | +3% |

**Conclusions (honest):**
1. **All-examples beats keyword for *every model tested*** (+2 to +4%). **Caveat: this is a model *comparison*, not a clean size sweep** — the set mixes families (Qwen2.5/Gemma4) and architectures (`gemma4:26b` is MoE ~3.8B-active; the rest dense), so it supports only the **universal** claim (all-examples always wins), **not** a size trend (the earlier "+4/+4/+2 shrinking" read was retracted as noise — and the axis is confounded anyway). A clean size effect would need one dense single-family ladder. The all-vs-select crossover, if any, is a **corpus-size** effect → Experiment 2.
2. **Semantic option-filtering (top-10/58) is harmful and worsens with capability:** 33→32→36→29→**25%**. At 26B, semantic (25%) drops **below bare (31%)** — filtering away 48 options actively hurts the capable model. Strong, actionable: do **not** hard-filter options at this KB size.
3. **Bigger = better absolute** but ordering stable (all > keyword ≫ semantic) at all sizes. Best config: **gemma4:26b + all-examples = 55% F1 / 63% priority-weighted / 100% use-case**.
4. **Gemma 4 validated for the proposal:** e4b (~8B-eff) ≈ qwen2.5:7b on keyword and has the best Disable-F1 (13–18%); 12b/26b scale cleanly. e4b = efficiency pick, 26b = quality pick.
5. Raw species/conflict violations persist (up to 63 at 26B-keyword) → all removed by the deterministic checker (defense-in-depth re-validated). Disable-F1 stays low (~1–5%, except e4b) — enable-heavy bias is the next lever. Reports: `work/results/evaluation_results_*.md`; aggregator: `work/harness/done/aggregate_results.py`.

**Full writeup + literature grounding: `work/EXPERIMENTS.md`.** Key context: the all-vs-selective *example* crossover (many-shot ICL) is far above our 20 (~3/class) — at **our estimated ~50–70 examples per class** (a conservative own-estimate; Agarwal 2024's actual per-class saturation, verified from full text 2026-07-12, is higher still at 512–2048/class — see `work/research/CITATION_VERIFICATION.md`). So the example-count sweep (running, gemma4:e4b) **confirms our regime (all-examples dominates), it can't reach the crossover** with a curated gold set. The actionable, in-range finding is the **option-filtering recall failure** (don't hard-filter the 58 options). Refs: [many-shot ICL](https://arxiv.org/html/2404.11018v1), [long-context vs RAG](https://arxiv.org/abs/2501.01880).

### 6.7 Preliminary bootstrap examples — `work/preliminary_examples/` **[derived]**
- **7 high-confidence** (query → config) examples in the demo schema but using **expanded-catalogue ids**, to start preliminary experiments while the mentor's gold-standard data is pending. Covers 6 of the 7 use cases (rare-disease ×2, somatic, regulatory, population, non-human, quick-lookup).
- **Confidence bar (objective):** each references only real catalogue ids and **passes the constraint checker with zero species/conflict violations + dependencies satisfied** — verified by `validate_examples.py` (all 7 pass). The mouse example deliberately withholds all human-only tools (the species-safety test case).
- **Deliberately excluded** (lower confidence → for mentor): `structural_variants`; choice among redundant predictors (REVEL/AlphaMissense/ClinPred/EVE); extra splice/regulatory plugins; exact value-level details. See `work/preliminary_examples/README.md`.
- **To run:** point the pipeline at (expanded catalogue + these examples) and pull a local model — actual runs are blocked only on the (deferred) model pull.

---

## 7. Key findings (real corrections to the demo's model)

Each is sourced in §8.

1. CADD/REVEL/AlphaMissense/SpliceAI/dbNSFP/MaxEntScan are **plugins** (`--plugin X`), not native checkboxes.
2. `pick/per_gene/most_severe/summary` are **values of one "Restrict results" dropdown**.
3. `gnomad_af` → `af_gnomade` + `af_gnomadg`; `transcript_set` → `core_type`; `mane_select` → `mane`.
4. There is **no native `gene_phenotype` field** — phenotype data comes via the Phenotypes plugin.
5. The 6 canonical sections: `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters`, `advanced`.

---

## 8. Corrections (what changed · before → after · why · source)

### 8a. Catalogue corrections vs the demo's 26 options

| Item | Before (demo) | After (corrected) | Why warranted | Source |
|------|---------------|-------------------|---------------|--------|
| Transcript set | id `transcript_set`, ad-hoc section | id `core_type`; values core/gencode_basic/gencode_primary/refseq/merged | Real control is `core_type`; `gencode_primary` missing; default `core` has no flag | **[repo]** `Object_VEP.pm`; `InputForm.pm` |
| MANE | `mane_select`, `--mane_select` | `mane`, `--mane` | Web field is `mane`; flag is `--mane` | **[repo]** `InputForm.pm`/`Object_VEP.pm` |
| gnomAD freq | single `gnomad_af` | `af_gnomade` + `af_gnomadg` | Two distinct form checkboxes | **[repo]** `InputForm.pm` |
| 1000 Genomes | `af_1kg` conflated | `af` (global) + `af_1kg` (continental) | Two separate fields | **[repo]** `InputForm.pm` |
| Predictors | CADD/REVEL/AlphaMissense/SpliceAI/MaxEntScan/dbNSFP as native | `source_type: plugin` | They are plugins | **[repo]** `vep_plugins_web_config.txt` |
| Restrict results | 4 independent options | values of one dropdown (`summary`) | One "Restrict results" dropdown | **[repo]** `InputForm.pm` `_build_filters` |
| Section names | ad-hoc strings | the 6 canonical ids | Enables click-to-apply | **[repo]** `VEPConstants.pm` |
| Defaults | `hgvs`/`protein` implied ON | OFF by default | No `checked` key | **[repo]** `InputForm.pm` |
| Coverage | 26 options | +17 native fields | Real fields absent from demo | **[repo]** `InputForm.pm`+`Object_VEP.pm` |

### 8b. Adversarial-verifier corrections (8 found, all fixed)

| Item | Before | After | Why | Source |
|------|--------|-------|-----|--------|
| `gene_phenotype` (**major**) | native field | **removed** (Phenotypes plugin covers it) | zero source hits for the field; it's plugin-driven | **[repo]** source absent; `vep_plugins_web_config.txt` |
| `shift_3prime` name | "Right align variants in repeats" | "…prior to consequence calculation" | wrong label | **[repo]** `Object_VEP.pm` |
| `mirna` name | "miRNA secondary structure position" | "miRNA structure" | wrong label | **[repo]** `Object_VEP.pm` |
| `alphamissense` species | "human only (GRCh38)" | "human only (GRCh37 and GRCh38)" | data for both assemblies | **[doc]** `vep_plugins.html` |
| `geno2mp` field | `HPO_count` | `HPO_CT` | plugin default is `HPO_CT` | **[doc]** plugins docs |
| `check_existing` / `coding_only` desc | over-specified | corrected to helptip | match source | **[repo]** `Object_VEP.pm` |
| `core_type` section | (n/a) | `advanced` + caveat | pre-section field, not in the 6 | **[repo]** `InputForm.pm` |

### 8c. Model-landscape correction (this update)

| Item | Before (dossier) | After (verified) | Why | Source |
|------|------------------|------------------|-----|--------|
| Gemma 4 12B context | "256K" | **128K** (256K is 26B/31B only) | authoritative Ollama page | **[web]** [Ollama `gemma4`](https://ollama.com/library/gemma4) |
| Gemma 4 12B existence | — | **confirmed real** | a search snippet implied only 4 sizes; the Ollama page confirms 12B | **[web]** [Ollama `gemma4`](https://ollama.com/library/gemma4) |

---

## 9. Blockages

| Blocked item | Blocked on |
|--------------|-----------|
| Official gold-standard examples (15–20) | Mentor's data *(partially mitigated: 7 verified bootstrap examples in `work/preliminary_examples/`)* |
| Swapping expanded catalogue into live `vep_options.json` | Migrating `training_examples.json` ids first (`id_migration.json` prepared) |
| Full multi-model eval (N=3–5) | Gold-standard data + pulling models (deferred) |
| Wiring structured-JSON emission (B8) | Mentor sign-off on click-to-apply contract (open Qs in `SCHEMA_DESIGN.md`) |
| ~~**Running** the experiment (Gemma 4b/12b/26b)~~ **RESOLVED 2026-06-06** | Was blocked on a GPU box: that session was CPU-only and the Intel brew Ollama bottle lacked its runner. Fixed by installing **native-arm64 Ollama** (Metal, ~180 tok/s vs ~10 under Rosetta). Exp 1–13 all ran on it. |
| Empirical priority calibration | Gold-standard examples (then derive priorities from enable-rates) |
| QLoRA / attribution / FastAPI (Phase 4) | Confirmation of Large slot + core finished first |

---

## 10. Decisions needing mentor input

**Resolved (mentor, 2026-07-08):** (1) **`clinical-interpretation` confirmed** as one `analysis_goal` value — it covers pathogenicity + splice + functional-effect evidence together (no separate `functional-mechanism` goal). (2) **Default `analysis_goal` when nothing is implied = `basic-consequence`** (for now). Implementation note: the drives priority table should be updated so `clinical-interpretation` also drives the splice cluster (SpliceAI/MaxEntScan/dbscSNV) + relevant functional-effect plugins, per decision (1).

- `core_type` (transcript DB) is a pre-section field — mapped to `advanced` as least-wrong.
- `priority_by_use_case` values are **provisional** (gold-standard data should calibrate them).
- Deferred plugins/customs (GO, AncestralAllele, OpenTargets, IntAct, MaveDB, RiboseqORFs, Blosum62; AllOfUs, GENCODE-promoter) — real but parked to hit ~55; one JSON edit to add.
- Confirm field names against **beta.ensembl.org** frontend (catalogue built against classic `InputForm.pm` release/115).
- **Which factor-value *combinations* are worth building gold rows for (and in what proportion).** The generation sampler (`work/generation/sample_factors.py`) treats the 5 factors as independent and balances the 11 factor *values*, so a combination is an emergent byproduct of value-balancing — it is **not** curated for plausibility and can produce implausible corners (e.g. `non-human somatic structural-CNV regulatory population-frequency`). Under the composable-factor philosophy (proposal §2–3) no combination is *invalid*, and the hard gates make implausible combos resolve to sensible configs, so this is a **distribution/exclusion** judgment (which scenarios are realistic / worth gold budget), not a hard allowlist — and the mentor should **not** enumerate the ~144 combos. Proposed handling: capture it for free in the review loop (approve/reject per tuple, fed back as sampler reweights) + an optional `exclusions`/`rare`-pair list in `factors.json`; this is adjacent to Ask-1 (scenarios / single-vs-multi-label). NB the gold set is deliberately *balanced* (over-represents rare combos to exercise the species safety net), distinct from the naturalistic OOD query set.

---

## 11. Next steps (proposed)

1. **(unblocked)** Wire the structured-JSON emitter (B8) into `vep_assistant.py` against today's `InputForm.pm` contract.
2. **(template now, fill on data)** Draft 15–20 gold-standard example templates in the new schema.
3. **(on your word)** Set up Ollama + pull Gemma 4 12B (+ a baseline) to re-run the eval.
4. **(after mentor review)** Migrate `training_examples.json` ids and swap the catalogue live; calibrate priorities from the examples.

---

## 12. Sources & provenance (master list)

**[repo] Ensembl `public-plugins` `release/115` (downloaded to `work/ensembl_source/`):**
- [InputForm.pm](https://github.com/Ensembl/public-plugins/blob/release/115/tools/modules/EnsEMBL/Web/Component/Tools/VEP/InputForm.pm) — the web form definition
- [VEPConstants.pm](https://github.com/Ensembl/public-plugins/blob/release/115/tools/modules/EnsEMBL/Web/VEPConstants.pm) — the 6 `CONFIG_SECTIONS`
- [Object/VEP.pm](https://github.com/Ensembl/public-plugins/blob/release/115/tools/modules/EnsEMBL/Web/Object/VEP.pm) — `get_form_details` labels/helptips
- [vep_plugins_web_config.txt](https://github.com/Ensembl/public-plugins/blob/release/115/tools/conf/vep_plugins_web_config.txt) — the 26 web plugins
- [vep_custom_web_config.json](https://github.com/Ensembl/public-plugins/blob/release/115/tools/conf/vep_custom_web_config.json) — custom datasets

**[doc] Ensembl VEP documentation:**
- [VEP command-line options](https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html) · [VEP plugins](https://www.ensembl.org/info/docs/tools/vep/script/vep_plugins.html)

**[web] Model landscape (research subagent, June 2026; Gemma 4 re-verified):**
- [Gemma 4 — Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) · [Gemma 4 on Ollama](https://ollama.com/library/gemma4) · [Gemma 4 Apache-2.0 overview](https://www.mindstudio.ai/blog/what-is-gemma-4-google-open-weight-model)
- [Qwen3.5](https://ollama.com/library/qwen3.5) · [Qwen3.6](https://ollama.com/library/qwen3.6) · [Qwen2.5-7B-Instruct](https://ollama.com/library/qwen2.5:7b-instruct) · [IFEval](https://llm-stats.com/benchmarks/ifeval) · [Qwen3.5 thinking leak (HF)](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/18)
- [Mistral Small 3.2](https://ollama.com/library/mistral-small3.2) · [Llama 4 on Ollama](https://ollama.com/library/llama4) · [Llama 4 — Meta](https://ai.meta.com/blog/llama-4-multimodal-intelligence/) · [Phi-4](https://ollama.com/library/phi4) · [Microsoft Phi-4](https://techcommunity.microsoft.com/blog/educatordeveloperblog/welcome-to-the-new-phi-4-models---microsoft-phi-4-mini--phi-4-multimodal/4386037)
- [Ollama structured outputs (XGrammar)](https://ollama.com/blog/structured-outputs) · [MLX LoRA/QLoRA](https://insiderllm.com/guides/fine-tuning-mac-lora-mlx/) · [Gemma 4 + MLX](https://antigravitylab.net/en/articles/antigravity/gemma-4-finetuning-apple-silicon-mlx-guide)

---

## 13. Change log

- **2026-08-23** — **Prompting-layer literature pass → `work/research/prompting_literature.md`.** Covers the part of the stack `LITERATURE.md` does not: output contract, prompt-format sensitivity, option position, ask-vs-assume, confidence labels, reasoning mode, over-recommendation, eval statistics. Read status is declared per paper (5 read at results level, 13 abstract/landing-page only) per the `CITATION_VERIFICATION.md` bar. Findings that change what we should do: (1) **Exp 8 is worth reopening for the classifier only** — Tam et al. 2024 (arXiv:2408.02442) finds JSON-mode costs GPT-3.5-Turbo 76.6→49.3 on GSM8K but is *competitive or better* on classification, and Ollama exposes schema-constrained decoding via `format`, so the classifier's `_classify_native` call is a one-field A/B; Ray 2026 (arXiv:2605.26128) is the counterweight (validity 61.5→100% while accuracy fell 19.7→11.0%, but on 0.5–1.7B models). Score readings, not validity. (2) **The ±0.6 in `STATUS.md` prices decoding noise and nothing about the prompt** — Sclar et al. ICLR 2024 report a median 6.4-point format spread on GPT-3.5 across 320 formats, which is the same phenomenon as HANDOFF §6's schema-change effect at zero seed spread; a format arm belongs in `eval_factor_set.py` before the tier A/B. (3) **Option order has never been varied** — Liu et al. TACL 2024 give 75.8/53.8/63.2% for gold-first/middle/last at 20 documents, below their own 56.1% closed-book at middle. (4) **Su & Cardie 2026 (arXiv:2605.25284) is the citation for §9 of the re-prompting proposal**: models judge ambiguity at 60–80% but answer directly >95% of the time, and retrieved context makes them ask *less*, so a deterministic ask policy is the right shape. (5) **The `confidence:` field is unvalidated** (Xiong et al. ICLR 2024: verbalized confidence is overconfident) — score it on the 31 rows or drop it. (6) **Miller 2024 says our SEs should be clustered and the tier A/B paired**, and that 31 rows need a power analysis before the A/B, not after. Conformal risk control (Angelopoulos et al.) written down as the eventual shape of must-have recall, with the n=31 and exchangeability limits stated. Nothing applied to code; the doc ends in a 9-row ranked action table and an explicit "my own judgement" section.
- **2026-07-13 (c)** — **Authored a 30-example SILVER reference set for mentor validation → gold** (`work/preliminary_examples/silver_reference_set.json` + `SILVER_REFERENCE_README.md` + `silver_reference_review.csv`). Purpose: (1) validate the per-option priorities (the mentor blocker) via an **independent** doc-grounded rule set (`author_reference_set.py` `doc_priority`, written from the catalogue's release/115 `when_to_use` guidance + a live VEP-docs lookup) — comparing it to the pipeline's `priority_by_factor.json` is the priority-table test; (2) a reference to evaluate the generation pipeline once validated. Balanced (**≥15 per factor value**), **30/30 checker-clean**, **30/30 queries pass the semantic factor round-trip**. Doc-grounded caveats surfaced for the mentor: ACMG BA1 = AF>5% (ClinGen SVI 2018); predictor redundancy (SIFT/PolyPhen/CADD/AlphaMissense — no VEP page ranks them, editorial); and two catalogue gaps — VEP's essential SV output `--overlaps` is absent, and **non-human + population-frequency is unsatisfiable** (gnomAD/1000G human-only). Honest framing: SILVER (Opus-authored, rule-set priority *proposal* rendered as examples), NOT gold until mentor sign-off; every row carries `_review.criticality` (validate), `_review.uncertain` (adjudicate), and the query-factor recovery. Plan: mentor validates ~30 (approve/edit/reject per row) → gold → pipeline scales beyond it with mentor spot-checks (the pipeline's justification).
- **2026-07-13 (b)** — **Replaced the Stage-4 factor check's keyword matching with a SEMANTIC LLM round-trip.** The keyword version (2026-07-13 a) was conceptually wrong for this task: Stage-3 queries are deliberately varied/implicit NL, and some keyword 'signals' were tool/DB names the query is told NOT to contain. New `genlib.factor_consistency` removed; `genlib.{FACTOR_CLASSIFIER_PROMPT, parse_factor_classification, compare_factors}` + `filter_candidates.llm_factor_recovery` classify the five factors from the query alone (checker model, prefer != Stage-3 teacher; temp 0/seed/concurrency-1) and FLAG mismatches (never drop; species stays the deterministic hard gate). Roundtrip framing per Alberti 2019; `basic-consequence` recovered by absence of a richer goal.
- **2026-07-13** — **Closed a real gap: Stage-4 now checks the generated QUERY expresses ALL five factors, not just species.** The pipeline's one generative step (Stage 3 writes the NL query) was only verified for species — origin/size/region/goal could be silently absent from the query while its config was built for them (an under-specified gold pair; also why ICE was ambiguous — a low score couldn't tell "bad config" from "bad query"). New `genlib.factor_consistency` (deterministic word-boundary signal scan; `basic-consequence` recovered by *absence* of a richer goal, matching the resolver's default) wired into `filter_candidates.deterministic_gates`: a **contradiction on a hard factor (species/size) fails the row**; an **unrecoverable factor only flags** (respects the implicit-premise query axis — implicit ≠ unrecoverable). **Finding on the existing N=30:** 0 hard-fails (no query contradicts species/size) but **13/30 flag an under-expressed factor**, dominated by multi-value intents (`analysis_goal`/`region_focus` *partial* — multi-label rows voice only one of their values) and `variant_size_class` *ambiguous* — a concrete, quantified query↔config faithfulness issue for review. Deterministic first cut (leaky keywords, tuned to remove the obvious gaps); the robust upgrade is an LLM factor-classifier. `per_factor` recovery stored per row for the review queue.
- **2026-07-12** — **Full-text citation-verification pass over all design choices + experiments (read the papers, no memory).** 8 parallel readers verified 27 cited papers against the *specific* claim each backs, with verbatim quotes + locations → `work/research/CITATION_VERIFICATION.md`. **No fabricated/non-existent citations, no invented numbers; the large majority SUPPORT.** Surfaced **one real misattribution + two overreaches + ~10 omitted caveats, all now fixed inline:** (1) **MISATTRIBUTION** — the "~50–70 examples per class" many-shot saturation figure is **not** in Agarwal 2024 (its per-class saturation is 512–2048/class; total-shot saturation is task-dependent) → relabelled our-own-estimate in `EXPERIMENTS.md` Exp 2 + here (§6.8, changelog); the Exp 2 conclusion *strengthens*. (2) **DPR overreach** — DPR uses dot-product (found cosine *worse*, §5.2) and its k=10 is near-optimal, so it does NOT establish "top-10 hurts" (that's our Exp 1/10); corrected in `systems_reading/README.md`. (3) **NeMo Guardrails** — cite for "programmable rails wrapping an LLM," NOT determinism (its own rails are LLM-mediated; §7.1 disclaims stand-alone use); reframed in the README + generation proposal. **Read-status gap CLOSED:** the three generation "spine" papers previously flagged cited-but-unread (SynthIE, Quality-Matters/ICE, Self-Instruct) are now read + quote-verified and SUPPORT (proposal §1a upgraded). **Added verified grounding:** ContextCite (Cohen-Wang 2024 — the principled Lasso-surrogate version our Exp 5/6 hand-rolls; LOO = its k=1 case) into Exp 5/6, and ALCE (Gao 2023 — NLI citation precision/recall) into the citation-rate deprecation. Minor: Xu title fix ("NOT" not "Not Always"); Gemma Scope is Gemma-2-only (retraining target for a Gemma-4 deploy). Every claim now traces to a verbatim quote in the report.
- **2026-07-08 (e)** — **Closed Exp 12 (teacher), ran Exp 13 (persona) pilot, added a deterministic test suite, launched the N=30 review set.** (1) **Teacher = `gemma4:26b` self-generation, CLOSED:** verified Gemma-4 has no MoE larger than 26b (Ollama page: E2B/E4B/12B/31B all dense, 26B sole MoE) so no fair size comparison can include the deployed model; surveyed SOTA open MoE (DeepSeek-V3 671B, Kimi-K2 1T, Qwen3-235B, Llama-4-Maverick) — all too big for 128 GB / cloud-only (breaks privacy) / cross-family; low EVOI for a short-query-writing task. (2) **Exp 13 persona pilot (N=12, seed 42, directional):** persona adds NO diversity (distinct-2 0.771 on vs 0.811 off; pairwise cosine 0.814 vs 0.810) — consistent with DataMorgana; ICE 54% vs 74% but n=5 single-seed = noise. Clean one-variable driver `work/generation/persona_ablation.py`. Keep persona for audience-realism only; revisit at ≥3 seeds. (3) Added `work/generation/verify_pipeline.py` — **17 deterministic invariant checks, no GPU** (zero-mutation, species/size/somatic gates, conflict flag, schema) — all pass. (4) Ran the fresh **N=30** drives-based mentor review set → `work/generation/candidates/review/review_queue.csv`: balanced coverage (**≥15 per factor value**, incl. the non-human/somatic/structural/regulatory gaps her draft misses), **28/30 pass deterministic gates** (2 = dedup catches), **ICE mean 82%**, enabled/row mean **16.1** (human 21 vs non-human 11 — ~half the old use-case seed's over-recommendation), **0 arbitrary-conflict flags**; judge flagged 11 solvability (over-conservative — scope-question evidence).
- **2026-07-08 (d)** — **Surfaced arbitrary conflict-tiebreaks in generated gold rows (flag, don't silently commit) — David flagged the alphabetical rung as non-rigorous.** The reused checker resolves an option conflict by priority, then on a tie by restrictiveness, then **alphabetical** (a determinism hack, not a principled choice). Baking that coin-flip into a gold example is wrong for a provenance-traced tool. New `flag_arbitrary_conflicts` (`work/generation/resolve_config.py`) detects conflicts the checker resolved between two **equal-factor-priority** options → records them in `_resolver.arbitrary_conflicts`; `filter_candidates.py` surfaces them as a `conflict_arbitrary:...` **review flag** (not a gate failure — the config is still checker-clean; a human confirms the drop). Verified: fires on a real `pick`/`per_gene` tie via the checker, silent on unequal priorities, 0 on the drives configs (they don't enable conflicting options). **Deliberately NOT letting the LLM resolve ties** (that reintroduces the fuzziness the checker exists to remove) — flag for the mentor. **Principled follow-up (proposed, not built):** resolve the output-mode conflict (`most_severe`/`summary`/`pick`/`per_gene`) by `analysis_goal` (basic→top-line, clinical→full per-transcript detail) so the factor scheme decides intentionally, flagging only when intent genuinely can't disambiguate.
- **2026-07-08 (c)** — **Rigor corrections + two planned generation-pipeline ablations (EXPERIMENTS.md Exp 12–13).** (1) **Teacher model:** reframed from "use a larger model" to *ablate it* — Xu et al. (**NAACL 2025, arXiv 2411.07133**, read in full) find larger same-family teachers are NOT reliably better, so the Stage-3 teacher is chosen by ICE, not assumed (Exp 12). (2) **DataMorgana read in full** (Filice et al. 2025, arXiv:2501.12789), **correcting** my earlier framing that all four query axes drive diversity: the paper's ablation shows the **persona/user axis is marginal** (NDG 2.536→2.484) while phrasing/premise/linguistic-variation carry it. Persona is **kept** in `query_axes.json` for audience-realism (this tool serves clinician/bioinformatician/student, unlike generic QA) and turned into a planned on/off experiment (Exp 13). (3) Reaffirmed the combination-plausibility gap (§10) and the `filter_common`→`frequency` fix (2026-07-08 (b)). Verified-from-full-text now: DataMorgana + Xu; SynthIE / Quality-Matters-ICE remain design-patterns-not-read.
- **2026-07-08 (b)** — **Re-seeded the generation pipeline's factor priorities factor-natively (drives-based).** Replaced Stage 0's use-case launder: `work/generation/seed_priorities.py` now authors `priority_by_factor.json` directly from `work/research/taxonomy_proposal.md` §3's web-form "drives" clusters (mapped via the catalogue's `category`/`species_restriction` fields) + two deterministic gates (species from `_is_human_only`; size = SNV-only predictors/splice/SNV-frequencies → not_applicable for structural-CNV) + a baseline identifier floor. **Why:** the use-case seed inherited the abandoned taxonomy's warts (e.g. `clinvar.basic-consequence=critical`) and left the coding/regulatory "default" sides unsignalled → over-recommendation. **Also fixed a real bug:** the `origin=somatic` hard rule targeted `filter_common`, which is not a catalogue id — the frequency pre-filter is `frequency` (`--check_frequency`); corrected in `factors.json` + the priority table. **Verified (deterministic, N=24, PYTHONHASHSEED=0):** zero-mutation invariant still holds on all rows; human mean enabled **33.0→21.4** (max 46→34), non-human 15.9→11.2 — ~35% less over-recommendation; somatic no longer enables `frequency` (0), small-variant never enables `gnomad_sv` (0), non-human never enables human-only options (0); 27 species-gated, 17 size-gated, 15 output-control options intentionally unpriced. Still PROVISIONAL (my reading of the proposal) — a one-file swap for the mentor's real table, but now a factor-native first-pass she edits rather than a laundered one. `_status`/`_authoring` in the generated file self-document the derivation.
- **2026-07-08** — **Built the gold-example generation pipeline (`work/generation/`, Stages 0–6).** Implements the reverse/asymmetric design of `work/research/generation_pipeline_proposal.md` as runnable, harness-consistent Python that **reuses** the demo pipeline (checker, species logic, parser, BGE embedder, tiering) rather than reimplementing it. **Key design: decoupled from the mentor's pending taxonomy** — the factor scheme + priorities live only in `generation_config/*.json`, so sign-off is a JSON swap, not a code change. Stages: `seed_priorities.py` (0: mechanically seeds a **PROVISIONAL** `priority_by_factor.json` from the existing `priority_by_use_case` — documented adapter, not validated), `sample_factors.py` (1: greedy inverse-frequency stratified sampler, seeded), `resolve_config.py` (2: factor tuple → checker-clean config; emits the checker's own output so re-checking is a **zero-mutation** no-op — the `validate_examples.py` bar, verified on all rows), `generate_queries.py` (3: local same-family teacher writes **only** the NL query, DataMorgana-style axes), `filter_candidates.py` (4: deterministic gates — valid-ids/checker-clean/species-match/dedup — + LLM-judge **flags**), `ice_screen.py` (5: leave-one-out ICE critical-recall usefulness screen), `export_for_review.py` (6: review queue CSV/JSON + append-only `provenance.jsonl`). Stage 7 (Web-VEP execution) out of scope. **Teacher decision grounded in verified literature:** default `gemma4:26b` self-generation, larger sibling **not** assumed better — Xu et al., *Stronger Models are Not Always Stronger Teachers*, **NAACL 2025 (arXiv 2411.07133)**, read from full text: same-family helps, larger-same-family does not reliably help ("Larger Models' Paradox"), compatibility predicts teacher quality, open-source > GPT-4; ICE is the empirical selector. **Citation fix:** the proposal cited this as *ICLR 2025* — it is *NAACL 2025*. **Live smoke (N=4, gemma4:26b, seed 42):** all 4 pass deterministic gates; sampler covers the mentor-draft gaps (non-human/somatic/structural each 2/2); non-human/SV rows correctly gate 25–37 human-only/SNV-only options; ICE recall 100%/92%/100% on 3 rows and flags the 4th (a degenerate empty generation, now distinguished from genuine misalignment). **Honesty:** all config is PROVISIONAL, `candidates/` are directional stand-ins (git-ignored), **not** approved gold — pending mentor validation of factors + priorities. Scientific-rigor note: the generation-specific papers (SynthIE, DataMorgana, Quality-Matters/ICE) are cited by the proposal by URL only and were **not** read from full text here — used as design patterns, flagged for verification.
- **2026-06-24 (b)** — **Built the deterministic ✓/✗ → JSON converter (structured-output deliverable; HANDOFF §12 thread 1).** Exp 8 showed the local model can't reliably emit JSON but reliably emits `✓/✗ [source: id]`, so OUR code now assembles schema-valid JSON — valid by construction, the LLM never emits JSON. **Task 1 (pure refactor):** added `extract_recommendations_detailed` (ordered per-option records: `option_id, action, confidence, priority, reason, value`) and rewrote `extract_recommendations` as a thin wrapper deriving its `(enabled, disabled)` sets from it — **verified byte-identical on all 400 logged responses** (re-parsed vs the sets logged at run time; 0 mismatches). **Task 2:** `build_recommendation_json` maps records + the SAME deterministic checker's corrected set + KB factual fields (web_form_section/cli_flag/web_form_subsection/priority + the SCHEMA_DESIGN web_form_field rules — plugins→`plugin_<Key>`, restrict-results→`summary`, species-scoped→`<id>_<Species>`, clinvar→`check_existing`) into the `output_schema/` contract. **Verification (offline, no GPU):** new `work/harness/build/build_output_json.py` builds + validates against `vep_recommendation.schema.json` (jsonschema) over the Exp 11 raw log → **398/398 non-empty responses schema-valid (100%)**; the only 2 non-valid are degenerate empty model generations (`'---'`, minItems:1 — a model no-op, correctly rejected, not a converter bug). Checker integration confirmed (bare mouse: `cadd`/`mutfunc` stripped, `constraint_check.passed=False`, violations recorded, nothing human-only left enabled). `validate_examples.py` all-pass, lints clean. Retires the fragility that blocked the proposal's structured-JSON/click-to-apply goal. Files: `vep_ai_demo/vep_assistant.py` (+`extract_recommendations_detailed`, `build_recommendation_json`, `_web_form_target`), `work/harness/build/build_output_json.py`. Not yet pushed to the public repo.
- **2026-06-24** — **Ran Experiment 11 — catalogue-only ablation (how much do the golden examples add over the option catalogue alone?).** Answers a direct mentor question. **Scope note (no overclaim):** the model is never shown the VEP documentation PDF in any condition — it sees **our derived 58-option catalogue** (`vep_options_expanded.json`, each option compressed to id+flag+~120-char description+metadata, distilled from release/115), which is our operationalization of the docs. Added a new `noex` condition (full catalogue + output contract + rules, **zero in-context examples** — `build_system_prompt(opts, [], q, retrieval_mode="all")`), reusing the exact pipeline (no logic fork; one-variable change vs `all` = examples 19→0). Held the test set fixed vs Exp 10 by excluding the 3 new clinical-report rows added 2026-06-23 (ran the **identical 20** queries; filtered files in `work/results_noex/`). 5 seeds (42–46), `gemma4:26b`, temp 0.7, concurrency 4, 400 calls (~1h56m, `caffeinate`). **Result — decomposed contribution on the simulated 20-set: bare 35% → +our catalogue (noex) 62% → +golden examples (all) 85% Enable F1**; the examples roughly **double critical-recall (49% → 96%)** and lift cat-cover (75% → 95%). So the catalogue alone is worth ~27 F1 over the raw model, and the gold examples add a *further* ~23 F1 — about as much again — and are the dominant driver of **must-have-option recall**. Consistency check PASSED (all=85%/96%/95%, bare=35% reproduce Exp 10 within noise). Caveat: bare's crit-recall (65%) > noex's (49%) is a metric artifact — bare over-recommends (raw harm **58** vs noex **1**) and scatter-hits criticals with terrible precision; read crit-recall alongside harm/cat-cover. A **raw-docs-PDF condition was considered and deferred** (scoring keyed to catalogue ids; PDF overflows the prompt budget; catalogue already operationalizes the docs). New rung `noex` added to `run_parallel_eval.py` (`COND_KEY`) + `score_metrics.py` (`ORDER`). Simulated gold → directional, not a benchmark. `EXPERIMENTS.md` Exp 11; raw `work/results_noex/raw/gemma4_26b.jsonl`.
- **2026-06-22** — **Ran Experiment 10 — 5-seed re-run of the model comparison (E1), all three Gemma, corrected parser.** One variable changed vs the original Exp 1: seed count **3 → 5** (seeds 42–46); same 58-option catalogue, 20-example simulated gold set, 4 conditions, `temperature=0.7`, harness (`run_parallel_eval.py`, concurrency 4). Also a *live* run (not an offline re-score), so it independently confirms the corrected-parser headline on fresh inference. **Result — 26b + all-examples = 84% ± 2% Enable F1 / 87% wt / 92% crit-recall / 95% cat-cover / 81% Disable-F1**, raw harm → 0 post-checker; cross-model Enable F1 e4b 65% → 12b 78% → 26b 84% (all corrected, directly comparable — clears the prior pre-parser-fix caveat on the cross-model table). **vs prior 3-seed re-analysis** (Exp 4/7): all-examples F1 **84% vs 87%**, crit-recall **92% vs 95%**, cat-cover **95% vs 96%**, Disable-F1 **81% vs 86%** — all within the ±2–4% decoding-noise band (now SD-bounded over 5 seeds, ≤2% on all-examples), conclusions unchanged. **Retracted one claim:** the old "semantic drops below bare / worsens with capability" does **not** survive the corrected parser — semantic is flat ~37–39% across model sizes and *above* bare; the recall-failure story (semantic ≪ keyword/all, no gain with model size) stands. Op note: 26b run detached under `caffeinate`+`nohup` to survive idle-sleep (three session-bound attempts had been killed by the machine sleeping). New: `compute_run_sd.py` parametrized to take `[log_path] [label]`. Pushed README + EXPERIMENTS.md (Exp 10) + the three 5-seed reports to the `askVEPai` repo. `EXPERIMENTS.md` Exp 10; reports `work/results/evaluation_results_gemma4_{e4b,12b,26b}.md`.
- **2026-06-21** — **Ran Experiment 9 — example-ORDER sensitivity (Agarwal et al. §4.7 replication).** New variable = in-context example order only; same harness/metric (priority-weighted LOO Enable F1), same 20-example simulated set + 58-option catalogue, same `gemma4:26b`, **greedy** (temp 0, to isolate order from decoding noise), LLM seed fixed; 10 random shuffles of a fixed set + the natural order. **Result: `all-examples` is order-robust** (weighted F1 **87.7% ± 1.6%**, default ≈ shuffle mean — and reproduces the established ~87%), **`semantic` top-8 is highly order-sensitive** (**60.0% ± 6.9%**, ~20-pt range; the similarity-sorted order at 54.4% is *below* the shuffle mean — 7/10 random orders beat it). So order is a non-issue for the recommended all-examples path (fixed file order fine; existing multi-run SD bounds it) and a second fragility for semantic (alongside the known option-filter harm). Caveat: all (19) vs semantic (8) differ in count + option-filter, so the SD *gap* conflates order with those; within-condition SD is clean. Simulated set → directional. New code: `examples_override=` hook in `build_system_prompt`, driver `work/harness/done/run_order_sensitivity.py`, wrapper `work/harness/done/run_order_experiment.sh`. Op note: 4-way concurrency saturates the single Metal GPU on the ~10K-token all-examples prompts → ran at concurrency 1 (~3 h, 440 calls). `EXPERIMENTS.md` Exp 9; report `work/results/order_sensitivity_gemma4_26b.md`.
- **2026-06-15 (d)** — **Verified `work/HANDOFF.md` is the current single cross-agent transfer file.** Confirmed it is complete + current through today: TL;DR, project/goals, status table, repo map, architecture, the parser fix (Exp 4), the hardening + offline re-score (Exp 7 — F1 87% / Disable-F1 86% / crit-recall 95% / harm→0), the full experiment ledger (Exp 1–8 incl. the attribution study 79% KB-grounded and the structured-output NEGATIVE result), provenance/honesty caveats, the taxonomy blocker + proposal (§10), open threads (incl. the proposed deterministic ✓/✗→JSON converter, §11), run/env reference, and glossary. `CLAUDE.md` points to it as the first read.
- **2026-06-15 (c)** — **Free-compute verification: demo smoke + structured-output feasibility.** The demo-path smoke validated the fixed checker end-to-end (mouse → strip + corrected-config block; unspecified-species → flag "assuming human", keep; human → clean) and **caught an active bug**: `_is_human_only` mis-flagged `'human + mouse only'` (e.g. `ccds`) as human-only, stripping it for mouse — fixed to key on species names (assembly strings like `GRCh37+GRCh38` no longer mislead it), unit-verified on all 16 restriction strings; offline-re-score harm corrected (all-examples raw harm 1→0, F1 unchanged). **Structured-output feasibility (Exp 8) = NEGATIVE:** `json_object` gave only **~40% valid JSON over 40 queries** (15/40 truncated, 7 malformed) with poor schema conformance; `json_schema` went degenerate earlier. So structured output is **not viable on the local 26b** for the full task — **this reverses the "structured output fixes the fragile parsers" plan**; the hardened free-text + exact-`[source:]` parser (Phase 0 parsed 179/180) is the more reliable path. Salvage paths noted. `EXPERIMENTS.md` Exp 8.
- **2026-06-15 (b)** — **Taxonomy research — the 7 use-cases have no canonical backing.** Two parallel research passes (Ensembl-official + field-standard/peer-tools) + our `ensembl_source`: (1) **Ensembl has NO official use-case taxonomy** — it segments only by interface/data-scale and the **6 web-form *function* sections** (`VEPConstants.CONFIG_SECTIONS`); the VEP paper / training / "examples & use cases" page never define scenario categories or per-workflow option priorities (only isolated heuristics: ACMG 5% AF, MANE-Select default). (2) The **field has no named workflow taxonomy** either but converges on **orthogonal composable axes** (separate ACMG/AMP-2015 germline vs AMP/ASCO/CAP-2017 somatic standards; separate ClinGen CNV standard + SV-specific tooling; species/origin/variant-class as independent flags in VEP/Funcotator/OpenCRAVAT/AnnotSV; Sequence Ontology multi-attribute) — **no peer tool uses a single-label scenario menu.** Both converge: **factor-based / multi-label, not 7 mutually-exclusive buckets.** Wrote a mentor-facing proposal (`work/research/taxonomy_proposal.md`): the 7 framed as a project assumption (with the mouse-somatic-SV overlap), the factor-based alternative (species × origin × variant-size-class × annotation-focus × low-weight scale), and **ordered asks — validate taxonomy → priorities → example schema — to settle BEFORE the gold set** so expert effort isn't wasted. `priority_by_use_case` confirmed as project judgment (no canonical source) needing the mentor.
- **2026-06-15** — **Code-review hardening + offline re-score (Exp 7).** A multi-pass review of `vep_assistant.py` / `evaluate.py` (+ drivers) fixed: phantom-id alias leak (Fix 4 — alias map filtered to real catalogue ids), 0-not-None scoring + errored-call exclusion (Fix 2/3 — undefined metrics → None, skipped in means), species **fail-closed, evidence-tuned** (Fix 1 — strip on confirmed non-human, *flag-not-strip* on `unknown`, since 8/20 human queries classify unknown), Phase-0 bullet-tolerant parse, conflict-loop skip-disabled guard, and the demo checker now **repairs** the output (`format_corrected_config`) not just warns — plus ~20 audited caveats. Found & fixed **3 species desyncs** (`check_and_fix_violations`, `evaluate.check_species_violations`, `score_metrics.species_harm`). **Re-scored the 240 logged 26b responses with the fixed code** (offline, no GPU, isolates the fix as one variable): all-examples enable-F1 **87% (stable)**, **disable-F1 81%→86%** (0-not-None correction; arithmetic confirms), crit-recall 95% / cat-cover 96% unchanged; phantom leak (`gnomad_af`×24, `gene_phenotype`×10) → **0**. Fallback audit: P1/P2 fire only for bare (100%) + 1 keyword, P0 carries all KB (179/180); species unknown=8/20 (flagged, not stripped); 0 errored. `EXPERIMENTS.md` Exp 7; harness `work/harness/done/rescore_offline.py`; report `..._RESCORED.md`.
- **2026-06-10 (b)** — **Ran Experiment 6 (clean, deterministic) — attribution decomposition + real-query generalization.** First diagnosed that **temp=0 is non-deterministic on this Metal/MoE stack** (concurrent runs drift 5–12 options per query from batch-composition float noise) → locked to **concurrency=1 + seed=42** (verified); the Exp 5 pilot (84%) is superseded by the clean combined-20 = **79%**. **6a decomposition:** grounding is **examples-dominant** — examples-only ablation flips **56%** vs descriptions **26%**, combined **79%** (21% parametric); the model mainly imitates the worked examples, descriptions cover the long tail (two largely-complementary channels). **6b generalization:** faithfulness **holds on 20 real forum queries** (77% all, **79% verbatim-only** = synthetic 79%) — not a synthetic artifact; the cueing confound didn't materialize. Per-use-case tracks specific (somatic 91%) → ubiquitous (pop-gen 53%). Pre-registered with anti-bias controls; rigor audit confirmed 19/20 baselines identical across modes. `EXPERIMENTS.md` Exp 6; raw in `results_fixedparser/attribution/`.
- **2026-06-10** — **Ran Experiment 5 — attribution testing** (7-query combined pilot, 26B, 77 recs). **faithfulness_rate = 84%** — 84% of recommendations are KB-grounded (disappear when their KB signal is ablated); only 16% parametric. Strong support for the provenance-traced thesis (the RAG drives the output, not training memory). Parametric ones are the *obvious* options (symbol/sift/check_existing/regulatory) the model knows anyway — *parametric ≠ wrong*; KB is load-bearing for the *specific* options (af_gnomade/g, clinvar, hgvs, protein → 100% faithful). `EXPERIMENTS.md` Exp 5; raw in `results_fixedparser/attribution/`.
- **2026-06-08 (b)** — **Designed Experiment 5 — attribution testing** (per-recommendation KB-faithfulness): ablate each recommended option's KB signal (guidance fields + example demonstrations), re-run greedy, measure whether it persists (parametric) or disappears (KB-faithful). Protocol written to `EXPERIMENTS.md` Exp 5; harness `work/harness/done/run_attribution.py` implemented + dry-run-validated (ablation strips guidance, keeps the option listable).
- **2026-06-08** — **🔑 PARSER BUG FIX — the headline correction.** `extract_recommendations` did fuzzy name-matching and ignored the model's clean `✓/✗ … [source: option_id]` output — dropping ~half the correct enables + all disables. Fixed to parse markers + exact `[source:]` ids (+ real-id-wins alias fix + raw-response logging). **Corrected 26B (all-examples): Enable-F1 55%→87%, recall 68%→94%, Disable-F1 0%→81%, critical-recall 70%→95%, category-coverage 75%→96%, over-rec 1.5×→1.18×.** Bare unchanged (sanity check ✓). **This corrects Exp 1–3:** prior F1s were ~30 pts low; "over-recommends / enable-heavy / all≈keyword" were parser artifacts (model is disciplined; all-ex 87% ≫ keyword 71%). Semantic-filtering harm survives (starker). Found via the user's "cleaner extraction" suggestion. Exp 1/2 to be re-run with the fix. See `work/EXPERIMENTS.md` Exp 4; corrected results in `work/results_fixedparser/`.
- **2026-06-07 (e)** — **Corrected the "model-size sweep" framing.** The 5-model set confounds size with **family** (Qwen2.5/Gemma4) and **architecture** (`gemma4:26b` is MoE ~3.8B-active; rest dense) — so it's a *model comparison*, not a clean size ladder. Reframed Exp 1 conclusions as **universal** ("all-examples wins for every model tested"), not size trends. A clean size effect needs one dense single-family ladder (likely confirmatory). (§6.8 + `EXPERIMENTS.md` Exp 1.)
- **2026-06-07 (d)** — **Clinically-meaningful re-scoring (Experiment 3).** Added raw-output logging (`run_parallel_eval.py` → `results/raw/*.jsonl`) + offline scorer (`score_metrics.py`); re-ran the 3 Gemma sizes (consistency check PASSED — exact-F1 reproduced Exp 1). **Answer to "55% is poor": no — best config (26B all-ex) has critical-recall 70% / category-coverage 75%**; the exact-F1 gap is over-recommendation (~1.5×) vs conservative synthetic gold. Real headroom = precision/discipline + the ~30% missed must-haves. Harm 0 post-checker. (12b pending.) See `work/EXPERIMENTS.md` Exp 3.
- **2026-06-07 (c)** — **Example-count sweep done (`gemma4:e4b`, N=2→19).** Result: **no corpus-size crossover** — all-examples ≈ keyword at every N (all−kw oscillates −2%↔+2%, noise); the robust gaps stay KB≫bare and keyword≫semantic. Consistency-checked vs Experiment 1 at N=19 (+2% vs +4%, within ±SD). Closes the preliminary experimental phase: on both reachable axes (model size, corpus size) all-examples never loses; the only in-range lever is option-retrieval recall. Recorded in `work/EXPERIMENTS.md`. Added an "Experiment discipline" section to `CLAUDE.md`.
- **2026-06-07 (b)** — Wrote `work/EXPERIMENTS.md` (full experimental report + literature grounding). Established that the example-count crossover (many-shot ICL) needs many more examples/class than a 15–20 gold set (our conservative estimate ~50–70/class; Agarwal's actual per-class saturation is 512–2048/class, verified 2026-07-12) — so the example-count sweep was scoped down to `gemma4:e4b` (curve shape only); the in-range finding is the option-filtering recall failure. Confirmed `gemma4:12b` (dense) is ~2.1× slower than `26b` (MoE).
- **2026-06-07** — **Completed the 5-model sweep** (qwen2.5 3b/7b + gemma4 e4b/12b/26b) on the M5 Max GPU. Result (§6.8): **no model-size crossover** — all-examples robustly beats selective retrieval (+2–4%) at every size incl 26B (corrected the earlier "shrinking trend"); **semantic option-filtering is harmful and worsens with capability** (26B semantic 25% < bare 31%); Gemma 4 validated (e4b≈qwen-7b; 26b best, 55% F1). Next: example-count sweep (the real corpus-size test).
- **2026-06-06 (c)** — **Ran the experiment locally on the M5 Max GPU.** Fixed the inference path (native arm64 Ollama → Metal, ~180 tok/s vs 10 on the Intel/Rosetta brew build). Built a **20-example simulated gold set** (full coverage, checker-validated) + a **parallel eval driver**.
- **2026-06-06** — Wired the eval to the **real system** (expanded 58-option catalogue + 7 bootstrap examples, leave-one-out) via env-vars (`VEP_OPTIONS_FILE/EXAMPLES_FILE/TESTSET_FILE/RESULTS_DIR`); dry-run validated. Added turnkey `work/harness/done/run_experiment.sh` (Gemma 4 e4b/12b/26b × 4 conditions × N runs). Verified expanded-catalogue priorities are consistent + reasonable. **Could not execute here:** CPU-only sandbox (no Metal) + upgraded local Ollama 0.17.6→0.30.6 for Gemma 4, but the Intel brew bottle lacks its inference runner. Experiment is ready to fire on a GPU box.
- **2026-06-05 (e)** — Audited the demo's *inference-affecting* hand-made fields (map: only `cli_flag/description/when_to_use/when_not_to_use/species_restriction/priority_by_use_case/conflicts_with/depends_on/name` + example `user_query/use_case_category/recommended_options/justification` reach inference; `web_form_section/category/use_case_tags` do not). All priorities internally consistent (human-only → non_human=not_applicable for all 11); all 8 examples checker-clean. **Conservative trim** of two enable-heavy demos in `training_examples.json`: `quick_lookup` 14→5 enabled, `rare_disease_exome` 16→13 (dropped redundant AlphaMissense/REVEL + off-topic SpliceAI) — reduces the enable-heavy bias that likely drives the demo's near-zero Disable-F1.
- **2026-06-05 (d)** — Added 7 verified **bootstrap training examples** (`work/preliminary_examples/`) to start preliminary experiments while the mentor's gold-standard data is pending: high-confidence only, expanded-catalogue ids, all passing the constraint checker (zero violations). structural_variants and redundant-predictor choices deliberately excluded. (§6.7)
- **2026-06-05 (c)** — Reorganised the directory: `vep_ai_demo/` is now the clean runnable demo only; all deliverables/summaries/research/reference moved to a sibling `work/` (with `work/README.md` index). Updated all path references here accordingly.
- **2026-06-05 (b)** — Added §3 "Proposed system — target architecture, scope & roadmap" (target defense-in-depth diagram, core/extended scope, phase roadmap, demo-vs-target table with a "Now" column). Renumbered later sections; §4 is now the current-state walkthrough.
- **2026-06-05 (a)** — Documented how `priority_by_use_case` ("criticality") was assigned and its provenance (§6.1).
- **2026-06-04 (c)** — Added the "Architecture & component walkthrough" (blocks B1–B11) with a query-flow diagram.
- **2026-06-04 (b)** — Added full provenance throughout + per-point model citations + corrections table; re-verified Gemma 4 and corrected the 12B-context error (128K, not 256K).
- **2026-06-04 (a)** — Initial progress doc. Completed Phase-1 foundation; reached the gold-standard-data blockage.
