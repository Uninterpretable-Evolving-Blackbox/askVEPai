# Gold-example generation pipeline — literature-grounded proposal

Status: **implemented.** The pipeline described below is built and runnable end to end (Stages 0–6; the
optional Web-VEP execution check, Stage 7, is out of scope for now). A first run of 30 examples produces
candidate `(query → config)` rows **balanced across the taxonomy** — at least 15 per factor value, including
the non-human, somatic, structural-variant and regulatory cases that are otherwise under-represented — with
28/30 passing all deterministic safety checks and a mean in-context critical-recall of ~82%; a separate
17-check verification suite passes.

> **No approved gold yet.** Everything this pipeline has produced so far is **candidate rows for review, not
> validated gold**. They run on a *first-pass, provisional* priority table (author's judgement, not
> validated) and depend on mentor sign-off of the factor taxonomy and per-option priorities in
> `taxonomy_proposal.md` before any of them become gold. `gold_examples.json` is currently empty.

This document is the design rationale for a **reproducible in-repo pipeline** that generates **candidate**
`(user_query → VEP web-form config)` examples for mentor review — the direction Likhitha outlined (lock
labels → generate queries and configs → optional Web-VEP runs → human review → size experiments). It reuses
code that already exists in the project (`validate_examples.py`, `vep_assistant.check_and_fix_violations`,
the 58-option catalogue).

---

## 1. Why not “ask a frontier model for the whole row”?

The current **simulated** 23-example set (`preliminary_examples/simulated_gold_examples.json`) is a
synthetic, checker-validated stand-in — balanced across the use cases, but not real expert configs (and not
hand-authored). A forward path — one strong LLM writes query + options + justification in a single pass —
repeats failures we already see in the mentor's first draft (rare-disease skew, inconsistent option ids, no
explicit disables). Tool-learning work shows the same pattern at scale: in *Quality Matters* (Iskander et
al., EMNLP 2024), the ToolBench training set has **parameter-alignment errors in 47.9% of instances**
(Table 5; the paper's cross-dataset summary is "over 33%").

The literature converges on a different shape for **structured outputs** (each row below is backed by a
verbatim quote from the cited source):

| Pattern | Source | Verified core idea |
|---------|--------|--------------------|
| **Asymmetric / reverse generation** | SynthIE (Josifoski et al., EMNLP 2023) | Fix the **label Y** first, generate text **X** second: *"prompt an LLM to perform the task in the reverse direction… Leveraging this asymmetry in task difficulty."* |
| **Roundtrip consistency** | Alberti et al. (ACL 2019) | Generate Q from (context, answer), re-answer, keep only if recovered: *"If A and A′ match we finally emit (C, Q, A)."* Basis of our ICE screen (§8). |
| **Constraint-first synthesis** | our deterministic checker; NeMo Guardrails (Rebedea et al., 2023) as prior art | Ground truth must pass **verifiable rules** before NL is written — "the LLM proposes, deterministic code disposes." |
| **Stratified coverage** | SynthIE §3.2; Sechidis et al. (ECML PKDD 2011) | Balance by **per-value coverage**: SynthIE reweights *"inversely proportional to its frequency"*; Sechidis's iterative stratification preserves each label's distribution better than random (caveat: it trades off exact per-example counts). |
| **Explicit diversity config** | DataMorgana (Filice et al., ACL 2025 Industry) | Query diversity comes from an explicit **category grid**, not from hoping the LLM varies phrasing — but see the persona caveat in §6a (their own ablation finds the *user/persona* axis marginal). |
| **Intrinsic quality gates + ICE** | *Quality Matters* (Iskander et al., EMNLP 2024) | **Six** intrinsic criteria for tool data; **In-Context Evaluation** measures whether an example *helps* a target model. On ToolBench, a filtered **10K subset scored 0.54 vs 0.45 for the full 73K** (ToolAlpaca: only on-par). |
| **Teacher ≠ student for ICL** | *Larger Models' Paradox* (Xu et al., **NAACL 2025**) | A *bigger* same-family teacher is **not** reliably better; open-source teachers beat GPT-4; compatibility with the student matters. → the query-writing teacher is chosen **empirically by ICE** (§6a, §8), not by size. |
| **Dedup filtering** | Self-Instruct (Wang et al., ACL 2023) | Keep a new item only if **ROUGE-L similarity < 0.7** vs any existing one (verbatim rule). |
| **Human calibration set** | ARES (Saad-Falcon et al., NAACL 2024) | A small (**150+**) human preference set calibrates automated judges; PPI gives confidence intervals. |

**Design principle for Ask VEPai:** deterministic code + KB + checker **dispose** of the labels; a local LLM
**proposes** only natural language (queries, optional justification). This matches the project's
defense-in-depth architecture and Exp 6 (examples-dominant grounding).

---

## 2. Pipeline overview

**Pipeline (Stage 0 = mentor sign-off, then 1–7):**

`0.` labels + per-option priorities (mentor)
→ `1.` stratified factor sampler (balance coverage across every factor value)
→ `2.` deterministic config resolver + checker (repaired to a fixed point)
→ `3.` query generator, category-conditioned for diversity [+ optional justification]
→ `4.` validation + dedup gates
→ `5.` ICE / roundtrip usefulness screen
→ `6.` mentor review queue
→ `7.` optional Web-VEP execution check
→ approved `gold_examples.json` + provenance JSONL.

Stages 1–2 use **no** LLM (labels are deterministic); only Stage 3 does (natural language only).

**Mentor step mapping:**

| Mentor step | Pipeline stage |
|-------------|----------------|
| 1. Lock category labels | Stage 0 — factor taxonomy + `priority_by_factor` |
| 2. Generate queries + options (≥3/category) | Stages 1–3 (options from resolver, queries from LLM) |
| 3. Run Web VEP | Stage 7 — execution validation only |
| 4. Human review | Stage 6 |
| 5. Dataset size experiments | Existing harness (`run_example_sweep.py`, `run_parallel_eval.py`) on approved gold |

---

## 3. Stage 0 — Lock labels (prerequisite)

**Input:** signed-off `research/taxonomy_proposal.md` (five factors, multi-label).

**Output (all implemented under `work/generation/generation_config/`):**

1. `factors.json` — allowed values per factor.
2. `priority_by_factor.json` — per-option per-factor priorities (currently a **provisional first pass**,
   authored from the taxonomy §3 "drives" clusters; replaces the legacy `priority_by_use_case`).
3. `query_axes.json` — DataMorgana-style query-diversity categorisations (independent of the biology
   factors); see §6a.

**Literature:** DataMorgana (Filice et al., 2025) shows question-side diversity must be configured
explicitly rather than hoped for — but their own ablation finds the *question* categorisations carry the
diversity while the *user/persona* categorisation is marginal (see §6a). We therefore treat each axis as a
hypothesis to test, not a feature to assume.

**Blocker:** generation is not scaled past a smoke test until the priorities are mentor-approved.

---

## 4. Stage 1 — Stratified factor sampling

**Goal:** choose *which* gold row to build next, balancing **per-factor-value coverage** (not single-label
categories).

**Method (implemented in `sample_factors.py`):**

1. Maintain a `(factor, value)` coverage table.
2. Each draw builds a **factor tuple**: `species`, `origin`, `variant_size_class` take one value each (data
   facts); `region_focus`, `analysis_goal` take one or more (intent, multi-select).
3. **Selection policy:** greedy inverse-frequency — prefer the currently rarest values, with a seeded
   tie-break so tuples don't collapse. Same spirit as SynthIE's coverage reweighting (Josifoski et al.,
   2023, §3.2: *"inversely proportional to its frequency"*).
4. **Multi-label stratification** for holdout splits: iterative stratification (Sechidis et al., 2011) —
   *planned* for when N ≥ 50 (not yet implemented; we are at N ≈ 30 and use leave-one-out).

**Target sizes** (from taxonomy proposal §6):

| Tier | ≥ per factor value | ~total rows | Use |
|------|-------------------|-------------|-----|
| Minimum viable | 3 | 24–30 | Leave-one-out; directional holdout |
| Stable | 5–6 | ~50 | 80/20 multi-label holdout |
| Benchmark | 10 | 100+ | Per-factor metrics with confidence |

---

## 5. Stage 2 — Deterministic config resolver

**Goal:** turn a factor tuple into the recommended VEP config — with **no LLM involved**.

**How it works** (`resolve_config.py`, following `taxonomy_proposal.md` §5). For each option in the catalogue:

1. **Drop it** if a hard factor rules it out — species or variant size marking it not-applicable (e.g. a
   human-only predictor for a mouse query), or the "somatic → no frequency filter" rule.
2. **Otherwise enable it** if it is *critical* or *recommended* for any of the query's active factor values.

Then apply the option dependencies and conflicts and run the constraint checker until nothing more changes;
the config we keep is that final, checker-clean result.

Because the config is already exactly what the checker would produce, running the checker on it again changes
nothing. That gives us a simple validity test later (Stage 4): **a row is only rejected if the checker would
have changed it** — the same bar `validate_examples.py` uses. *(This is the reverse-generation idea from
SynthIE: fix the structured answer first, deterministically, before any natural-language text is written.)*

**Open question for you — the merely *optional* options.** Right now we enable *critical* + *recommended*,
and log a few *optional* ones per row so the model also learns which options to leave off.

**Explicit "off" options:** a few configs mark some options as deliberately disabled (with a note), so the
example says "these are intentionally *not* used" rather than just "these weren't mentioned" — something the
first draft of the examples didn't capture.

**Reuse:** every config must pass `work/preliminary_examples/validate_examples.py`, i.e. the checker leaves it
unchanged.

---

## 6. Stage 3 — Natural-language generation (the only LLM-authored artifact)

**Goal:** given a **fixed** config + factor tuple, generate a `user_query` (and optionally a
`justification`) a human would plausibly ask. The model **never** picks option ids.

### 6a. Query generation — category-conditioned

**Config:** `generation_config/query_axes.json` — categorisations with `name`, `description`, `probability`
(DataMorgana form; Filice et al., 2025).

**Axes:**

| Categorisation | Categories | Status |
|----------------|-----------|--------|
| `phrasing` | concise / verbose / short-search-query | diversity-bearing (DataMorgana "question" axis) |
| `premise` | explicit / implicit | diversity-bearing |
| `terminology` | field-standard / lay | diversity-bearing (their "linguistic variation") |
| `persona` | clinician / bioinformatician / student | **under test — likely to be cut** |

**Persona caveat (verified + reproduced):** DataMorgana's own ablation shows the **user/persona axis is
marginal** for diversity while the *question* axes carry it. We reproduced this on our data (persona on vs
off: distinct-2 0.771 vs 0.811, mean pairwise cosine 0.814 vs 0.810 — no gain, slightly worse). Persona is
retained only as a possible *audience-realism* lever and is being ablated; if it doesn't earn its place it
will be removed. Same discipline applies to the dedup thresholds and model choices.

**Teacher model (chosen empirically, not assumed):** I pick the model that writes the query by measuring
which teacher's queries the student best learns from (the ICE screen, §8), rather than by size or a "bigger
model / self is best" assumption. Grounding: Xu et al. (NAACL 2025) — a bigger same-family teacher is not
reliably a better teacher ("Larger Models' Paradox"), and open-source teachers can beat GPT-4. I ran a
**5-seed sweep** across `gemma4:{e4b, 12b, 26b, 31b}` (student fixed at `26b`, N=30): **all four teachers
come out within noise of each other** (roughly 80–88% ICE, with overlapping error bars), so there is no
reliable difference between them. (An earlier 3-seed pilot had suggested self-generation underperformed and
`e4b` was best, but that was small-sample noise and did not survive the larger run.) I therefore **keep the
deployed model as its own teacher** — `26b` writes the queries for the `26b` student — as the simplest
choice, with no evidence that splitting teacher and student would help. Queries are generated at a fixed seed
and concurrency 1 for reproducibility (Metal/MoE determinism rule).

**Procedure:** sample one category per axis (weighted by `probability`); prompt the model with the factor
tuple + a plain-language scenario + the axis descriptions + 1–2 seed queries; generate `k` candidates and
keep one passing the §7 gates. Reproducible via fixed seed + concurrency 1 (Metal/MoE determinism rule).

### 6b. Justification draft (optional)

The model may draft `justification` prose; **factual fields** (`cli_flag`, `web_form_section`, priorities)
always come from the catalogue at export time, never the model.

### 6c. What we deliberately do *not* do

- **Evol-Instruct on configs** (WizardLM, Xu et al., ICLR 2024 — Evol-Instruct *"rewrite… step by step into
  more complex instructions"*): evolving a structured 58-option set would create conflict violations. Evolve
  *queries* only, if at all.
- **Forward (query → config) generation as gold** — only as a roundtrip diagnostic (§8).

---

## 7. Stage 4 — Automated gates

### 7.1 Deterministic (must pass)

| Gate | Implementation | Literature analogue |
|------|----------------|---------------------|
| Valid option ids | ⊆ `vep_options_expanded.json` | parameter-alignment errors (Iskander et al., 2024) |
| Checker clean | `check_and_fix_violations` on the real query → 0 mutations | constraint-first synthesis |
| Factor consistency | `infer_species(query)` matches the tuple; somatic rows must not enable **`frequency`** (the `--check_frequency` pre-filter) | hard rules in taxonomy §3 |
| Dedup | embedding cosine < 0.92 AND ROUGE-L < 0.7 within a factor cell | Self-Instruct (Wang et al., 2023): *"ROUGE-L similarity… less than 0.7"* |

*(Dedup thresholds 0.92 / 0.70 and the AND rule are not yet tuned — flagged for an ablation. 0.70 is
Self-Instruct's convention.)*

### 7.2 LLM-as-judge (flag, never auto-drop)

Adapts the intrinsic criteria of Iskander et al. (2024, §4.1 — "six intrinsic properties"):

- **Specificity** — species/assay/variant type stated enough to infer the config.
- **Coherence** — one coherent scenario.
- **Solvability** — a *configuration-recommendation* scenario, not a how-to/troubleshooting ticket
  (scope per `HANDOFF.md` §11).

Failures are **flagged for review, never silently dropped**. (On our data this judge over-flags
solvability — treated as advisory only.)

---

## 8. Stage 5 — ICE / roundtrip usefulness screen

**Motivation:** a correct `(query, config)` pair can still be **unhelpful as an ICL example**. *Quality
Matters* (Iskander et al., 2024, §5) defines **In-Context Evaluation** — *"evaluate the educational value of
each data instance by measuring the performance of in-context learning using the specific instance"* — and
shows it *"is inherently different from human-prescribed correctness."*

**Procedure (implemented in `ice_screen.py`):**

1. Hold out candidate row `e` (leave-one-out).
2. Run the student (`gemma4:26b`) over the other approved examples (all-examples condition).
3. Score **priority-weighted critical-recall** on `e`.
4. If critical-recall = 0 on a non-minimal query, **flag** (query too vague or config misaligned).

This is a **screen**, not an auto-reject. It is also the empirical **teacher selector** (run per teacher,
compare ICE). Roundtrip grounding: Alberti et al. (2019) — keep only if the answer is recovered.

---

## 9. Stage 6 — Human review

**Queue:** all minimum-viable-tier rows fully reviewed; later tiers review all flagged rows + a spot-check.

**Review sheet:** factor tuple, query, enabled (core/add-ons), disabled, checker log, ICE score, judge
flags. Mentor actions: `approve` / `edit_query` / `edit_config` / `reject` + comment.

**Calibration set:** the first mentor-reviewed rows become a human preference set for tuning judge prompts —
ARES (Saad-Falcon et al., NAACL 2024) uses **150+** such annotations with PPI for confidence intervals; we
start smaller and grow toward that.

**Provenance:** append-only `generation/provenance.jsonl` per row, e.g.:

```json
{
  "id": "gen_...",
  "factor_labels": { "...": "..." },
  "query_axes_cell": { "...": "..." },
  "teacher_model": "gemma4:26b",
  "teacher_seed": 142,
  "kb_hash": "sha256:…",
  "checker_clean": true,
  "ice_critical_recall": 0.85,
  "review_status": "pending"
}
```

---

## 10. Stage 7 — Optional Web-VEP execution check

**Scope:** validates that the config *runs* and output looks sane — **not** gold definition. Export the
approved config to Web-VEP/REST, run on a fixed panel of 1–3 variants per factor cell (species-appropriate),
store outputs, route failures to the mentor queue. Optional for minimum-viable gold; required before
claiming end-to-end benchmark quality. **(Out of scope in the current build.)**

---

## 11. Output schema (approved gold)

Same shape as `simulated_gold_examples.json`, extended with `factor_labels` and a `provenance_id`;
`use_case_category` is kept nullable for harness migration. Eval harness reads it via
`VEP_EXAMPLES_FILE=work/generation/gold_examples.json`.

---

## 12. Code layout (implemented under `work/generation/`)

```
work/generation/
  README.md
  genlib.py                     # shared reuse of the demo pipeline
  generation_config/{factors,query_axes,priority_by_factor}.json
  seed_priorities.py            # Stage 0 (authors priority_by_factor)
  sample_factors.py             # Stage 1
  resolve_config.py             # Stage 2
  generate_queries.py           # Stage 3
  filter_candidates.py          # Stage 4
  ice_screen.py                 # Stage 5
  export_for_review.py          # Stage 6
  verify_pipeline.py            # 17-check deterministic test suite (no GPU)
  run_generation.sh             # turnkey driver (Stages 0-6)
  candidates/                   # gitignored, never gold
  gold_examples.json            # mentor-approved only (currently EMPTY — nothing approved yet)
```

Stage 7 (`run_web_vep_check.py`) is not built. All scripts honour `VEP_OPTIONS_FILE` and log per the
`EXPERIMENTS.md` discipline.

---

## 13. Teacher vs student roles (explicit)

| Artifact | Who generates | Why |
|----------|---------------|-----|
| Factor tuple | Stratified sampler | Coverage control (SynthIE §3.2; Sechidis 2011) |
| `recommended_options` | Deterministic resolver + checker | Faithfulness; no LLM-hallucinated ids |
| `user_query` | Local model (NL only; teacher chosen by ICE — §6a) | Diversity via category grid (DataMorgana) |
| `justification` | Model draft; facts from KB | source-grounded prose |
| ICL usefulness | Measured on the student (`gemma4:26b`) | ICE (Iskander 2024); teacher choice per Xu 2025 |
| Gold truth | Mentor-approved | human calibration (ARES) |

The simulated 23-example set remains **directional** until this pipeline produces mentor-validated rows.

---

## 14. What success looks like (evaluation)

1. `validate_examples.py` — 100% pass on `gold_examples.json`.
2. `run_parallel_eval.py --runs 5` — compare to the simulated baseline; append to `EXPERIMENTS.md`
   (one variable: corpus).
3. Coverage report — every factor value ≥ tier threshold.
4. Attribution on `real_queries_biostars.json` — faithfulness should not collapse vs synthetic (Exp 6b).

---

## 15. Open decisions (for mentor)

1. **`optional` options in gold** — enable recommended-only, or add explicit plausible-but-wrong negatives?
2. **Query axes** — which personas/phrasings match Ensembl helpdesk traffic (and does persona help at all —
   we already find it marginal)?
3. **Web-VEP panel** — which variant fixtures per species?
4. **Combination plausibility** — which factor-value *combinations* are worth building (the sampler treats
   factors as independent; see `PROGRESS.md` §10)?

---

## References

All fetched and quote-verified against primary-source full text unless noted.

1. Josifoski, M., Šakota, M., Peyrard, M., & West, R. (2023). Exploiting Asymmetry for Synthetic Training
   Data Generation: SynthIE **and the Case of Information Extraction**. *EMNLP 2023.*
   https://aclanthology.org/2023.emnlp-main.96/ · arXiv 2303.04132
2. Alberti, C., Andor, D., Pitler, E., Devlin, J., & Collins, M. (2019). Synthetic QA Corpora Generation
   with Roundtrip Consistency. *ACL 2019.* https://aclanthology.org/P19-1620/
3. Iskander, S., Tolmach, S., Shapira, O., Cohen, N., & Karnin, Z. (2024). Quality Matters: Evaluating
   Synthetic Data for Tool-Using LLMs. *EMNLP 2024.* https://aclanthology.org/2024.emnlp-main.285/ ·
   arXiv 2409.16341
4. Filice, S., Horowitz, G., Carmel, D., Karnin, Z., Lewin-Eytan, L., & Maarek, Y. (2025). Generating
   Diverse Q&A Benchmarks for RAG Evaluation with DataMorgana. *ACL 2025 Industry.* arXiv 2501.12789
5. Xu, Z., Jiang, F., Niu, L., Lin, B. Y., & Poovendran, R. (2025). Stronger Models Are Not Always Stronger
   Teachers for Instruction Tuning. ***NAACL 2025.*** https://aclanthology.org/2025.naacl-long.224/ ·
   arXiv 2411.07133
6. Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A., Khashabi, D., & Hajishirzi, H. (2023).
   Self-Instruct: Aligning Language Models with Self-Generated Instructions. *ACL 2023.* arXiv 2212.10560
7. Saad-Falcon, J., Khattab, O., Potts, C., & Zaharia, M. (2024). ARES: An Automated Evaluation Framework
   for Retrieval-Augmented Generation Systems. *NAACL 2024.* https://aclanthology.org/2024.naacl-long.20/ ·
   arXiv 2311.09476
8. Sechidis, K., Tsoumakas, G., & Vlahavas, I. (2011). On the Stratification of Multi-Label Data.
   *ECML PKDD 2011,* LNCS 6913, pp. 145–158.
9. Xu, C., Sun, Q., Zheng, K., Geng, X., Zhao, P., Feng, J., Tao, C., & Jiang, D. (2024). WizardLM:
   Empowering Large **Pre-Trained** Language Models to Follow Complex Instructions. *ICLR 2024.*
   arXiv 2304.12244
10. Rebedea, T., Dinu, R., Sreedhar, M., Parisien, C., & Cohen, J. (2023). NeMo Guardrails: A Toolkit for
    Controllable and Safe LLM Applications with Programmable Rails. *EMNLP 2023 (System Demonstrations),*
    arXiv 2310.10501. — prior art for programmable "rules dispose" guardrails
    (*"programmable guardrails… controlling the output of an LLM to respect some human-imposed constraints"*).

**Removed in the citation audit:** Shakeri et al. (2020) — misattribution (their filter is LM-likelihood,
not roundtrip; roundtrip is credited there to Alberti et al.); an unnamed "NeurIPS 2024 constraint" paper,
"Crab (ACL 2025)", and "LONGFAITH" — unverifiable, no locatable source.

Internal: `research/taxonomy_proposal.md`, `preliminary_examples/README.md`, `HANDOFF.md` §10–12,
`EXPERIMENTS.md`.

---

## Progress update (latest)

This pipeline generates candidate `(query → config)` examples so we can build a gold set without
hand-authoring dozens by hand. Here is where it stands now, and the one thing I'd most like you to look at.

**I've tightened the pipeline in two places.** First, *query faithfulness*: the only part a model writes is
the natural-language query, so I added a check that the query actually expresses all five factors its config
was built for (species, origin, variant size, region, goal), not just species as before — a checker reads
only the query and recovers the factors, and anything it can't recover is flagged for review. This closes a
gap where a query could quietly omit, say, "somatic" or "structural" while still being paired with a config
built for them. Second, I re-ran the two open design ablations properly: on the teacher model the candidates
all come out within noise of each other, so I'm keeping the deployed model as its own teacher (the earlier
"a smaller teacher writes more learnable queries" reading was small-sample noise); and the persona
query-axis adds no measurable diversity, so I'm keeping it only for audience realism.

**Reference examples for you to validate — this is the main ask.** To move from candidate rows to real gold,
and to have something to measure the pipeline against, I've generated a **30-example reference set** for your
review: `preliminary_examples/silver_reference_set.json` (with a flat `silver_reference_review.csv` you can
mark up per row, and `SILVER_REFERENCE_README.md` explaining it). They're balanced across every factor value,
all pass the constraint checker cleanly, and each query is verified to express its factors. They're
**model-generated and grounded in the VEP documentation — a proposal for you to check, not validated gold.**
I built the configs from an independent, documentation-grounded reading of the option priorities *on purpose*,
so that wherever they disagree with the pipeline's own priority table is exactly where we need your decision.
Validating these does two jobs at once: it locks the per-option priorities (the thing currently blocking real
gold), and the validated set becomes the reference the generation pipeline is measured against. The plan from
there is that you validate ~30 once, they become gold, and the pipeline scales beyond that with spot-checks —
so we never have to hand-author dozens.

**A few specific decisions I'd value your view on** (detailed in the silver-set README):
1. Which pathogenicity predictors to treat as the standard set vs redundant — VEP itself doesn't rank them.
2. Two catalogue gaps the reference set exposed: VEP's structural-variant overlap output (`--overlaps`) isn't
   in our option list yet; and non-human + population-frequency has no available option at all, since
   gnomAD/1000G are human-only — so is that combination in scope?
3. The allele-frequency cutoff to filter on (ACMG BA1 stand-alone-benign uses AF > 5%).
