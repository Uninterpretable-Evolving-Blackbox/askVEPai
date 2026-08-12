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

> **Citations note (all read + verified from full text, 2026-07-12).** Earlier drafts over-claimed uniform
> verification while the notes flagged SynthIE / Quality-Matters / Self-Instruct as cited-but-unread. A
> full-text verification pass (2026-07-12, logged in `CITATION_VERIFICATION.md`) has now **read every source
> here from the full paper and matched each claim to a verbatim quote**. Result: all citations **SUPPORT**
> their claims — no fabrications, no misattributions among the generation citations — with a handful of
> omitted caveats now folded in (e.g. SynthIE's inverse-frequency is over KG entities by *running*
> frequency; the ICE 0.54 result used *combined* filters; DataMorgana's "persona marginal" is empirical to
> the authors' category sets, not a law). One earlier citation (Shakeri et al. 2020) was **removed** as a
> misattribution, and three unverifiable references ("NeurIPS 2024 constraint", "Crab", "LONGFAITH") were
> dropped. **Bibliographic fixes:** Xu et al.'s title is "Stronger Models Are **NOT** Stronger Teachers"
> (not "Not *Always*"). The design-choice provenance table (§1a) marks what rests on verified literature vs.
> my own judgment.

This document is the design rationale for a **reproducible in-repo pipeline** that generates **candidate**
`(user_query → VEP web-form config)` examples for mentor review — the direction Likhitha outlined (lock
labels → generate queries and configs → optional Web-VEP runs → human review → size experiments). It reuses
code that already exists in the project (`validate_examples.py`, `vep_assistant.check_and_fix_violations`,
the 65-option catalogue).

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

### 1a. Design-choice provenance — literature vs. author judgment

Every row of the table above is a *literature-motivated* pattern, but the **binding design decisions** below
mix literature with my own engineering, and the literature they rest on is at **different read-tiers** (see
the Citations note). Tags: **[L✓]** literature read from full text; **[L⚠]** flagged as cited-but-unread in
earlier drafts — **all [L⚠] rows were read + verified on 2026-07-12** (`CITATION_VERIFICATION.md`) and
SUPPORT their claims; the tag is kept to mark which were late-verified; **[Src]** Ensembl VEP source / our
checker / KB; **[Judg]** my own choice, no external source claims it.

| Binding design decision (as implemented) | Grounding | Source (read-status) |
|---|---|---|
| Code+KB+checker fix the config Y; the LLM writes only the query X | **[L✓]**+**[Src]**+**[Judg]** | NeMo Guardrails (Rebedea 2023, **read**) as prior art; our checker **[Src]**; the label-first asymmetry from SynthIE **[L⚠]** |
| Reverse / asymmetric generation (fix label, generate text) | **[L⚠]** | **SynthIE** (Josifoski 2023) — cited, **not full-text-read** |
| Stratified inverse-frequency sampler (Stage 1) | **[L⚠]** | SynthIE §3.2 + Sechidis 2011 — both cited, read not confirmed |
| Query-diversity **axis grid** (Stage 3) | **[L✓]** | DataMorgana (Filice 2025, **read in full**) |
| — keeping the **persona** sub-axis despite marginal diversity | **[Judg]** | DataMorgana's *own* ablation finds persona marginal; keeping it for audience-realism is **my call**, not the paper's (and Exp 13 tests it) |
| ICE usefulness screen (Stage 5) | **[L⚠]** | **Quality-Matters / ICE** (Iskander 2024) — cited, **not full-text-read** |
| Roundtrip-consistency framing of ICE | **[L⚠]** | Alberti 2019 — cited, read-status unconfirmed |
| Teacher chosen **empirically** (not by size) | **[L✓]** | Xu et al. (NAACL 2025, **read in full**) |
| Dedup: ROUGE-L < 0.70 **AND** cosine < 0.92 | **[L⚠]**+**[Judg]** | 0.70 = Self-Instruct (Wang 2023, **not re-verified**); the 0.92 threshold + the AND rule are **[Judg]**, unvalidated |
| Human calibration set (grow toward 150+) | **[L⚠]** | ARES (Saad-Falcon 2024) — cited, read-status unconfirmed |
| NOT evolving configs (Evol-Instruct on queries only, if at all) | **[L⚠]**+**[Judg]** | WizardLM (Xu 2024) cited; the "don't evolve a structured config" call is **[Judg]** |

**Bottom line (updated 2026-07-12):** the pipeline's *spine* — reverse generation (SynthIE), stratified
coverage (SynthIE §3.2 + Sechidis), and the ICE screen (Quality-Matters + Alberti) — has now been **read from
full text and verified to SUPPORT** its claims (`CITATION_VERIFICATION.md`); the earlier "still-unread"
caveat is **resolved**, and all [L⚠] rows above are verified (with the per-row caveats folded in). What
remains genuinely **my own judgment** (not a literature fact) are the binding knobs: the **persona axis**
(DataMorgana finds persona marginal — keeping it is my audience-realism call), the **dedup thresholds** (0.92
hand-picked, the AND rule mine), and **"don't evolve configs"** — all flagged for ablation. Note also that
NeMo Guardrails grounds the *programmable-rails* concept, **not** determinism (its own rails are LLM-mediated;
our Python checker is the deterministic part) — see fix #4 in `CITATION_VERIFICATION.md`.

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

## 5. Stage 2 — Deterministic config resolver (reverse / asymmetric step)

**Goal:** produce `recommended_options` from the factor tuple **without** an LLM.

**Algorithm** (implemented in `resolve_config.py`; implements `taxonomy_proposal.md` §5):

```
for each option in catalogue:
  if a HARD factor (species / variant_size_class), or the origin=somatic->frequency rule,
     marks it not_applicable  -> drop
  else priority = strongest over active factor values (critical > recommended > optional)
       enable if priority in {critical, recommended}
then apply depends_on / conflicts_with and run check_and_fix_violations to a FIXED POINT
     (the emitted config is the checker's repaired output).
```

Because the resolver emits the checker's own repaired output, re-running the checker is a no-op — so the
Stage-4 gate can **fail a row only if the checker would change anything** (the zero-mutation bar, same as
`validate_examples.py`). *(Grounding: SynthIE — control P(Y) by sampling structured labels before text.)*

**`optional`-option policy (open, needs mentor rule):** default enable `critical` + `recommended`; log a
small `optional` subset per row for Disable-F1 signal.

**Explicit disables:** a small set of meaningful "off" options carry `"enabled": false` + a `note`
(closed-world signal the mentor draft omitted).

**Reuse:** `work/preliminary_examples/validate_examples.py` — gold rows must pass with **zero checker
mutations**.

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
marginal** for diversity while the *question* axes carry it. We reproduced this on our data at **N=30 over 5
seeds** (persona on vs off: distinct-2 **0.640 ± 0.011 vs 0.651 ± 0.015**; mean pairwise cosine
**0.8028 ± 0.0036 vs 0.8039 ± 0.0077**) — both flat within SD, i.e. persona buys **no measurable
diversity**. Persona is retained only as a possible *audience-realism* lever; if it doesn't earn its place it
will be removed. Same discipline applies to the dedup thresholds and model choices.

*(Numbers corrected 2026-07-15: this previously cited "distinct-2 0.771 vs 0.811, cosine 0.814 vs 0.810",
which matches no stored artifact — neither the 5-seed N=30 run nor the N=12 pilot. The conclusion is
unchanged, and the cosine direction in the old figures was inverted. The ICE arm of this ablation is **not**
quoted here: the persona and teacher-sweep scripts count degenerate generations differently, so their ICE
values are not comparable until recomputed.)*

**Teacher model (chosen empirically, not assumed):** the model that writes the query is chosen by measuring
which teacher's queries the student best learns from (the ICE screen, §8), not by size or an a-priori
"bigger/self is best" assumption. Grounding: Xu et al. (NAACL 2025) — a bigger same-family teacher is not
reliably a better teacher ("Larger Models' Paradox"), and open-source teachers can beat GPT-4. A **5-seed
sweep** across `gemma4:{e4b, 12b, 26b, 31b}` (student fixed at `26b`, N=30) found **all four teachers within
noise of each other** (~80–88% ICE, overlapping error bars), so there is no reliable difference between them.
(An earlier 3-seed pilot suggested self-generation underperformed and `e4b` was best; that was small-sample
noise and did not survive the larger run.) So the deployed model is **kept as its own teacher** (`26b` writes
for the `26b` student) — the simplest choice, with no evidence a teacher/student split would help. Queries are
generated at a fixed seed + concurrency 1 (Metal/MoE determinism rule).

**Procedure:** sample one category per axis (weighted by `probability`); prompt the model with the factor
tuple + a plain-language scenario + the axis descriptions + 1–2 seed queries; generate `k` candidates and
keep one passing the §7 gates. Reproducible via fixed seed + concurrency 1 (Metal/MoE determinism rule).

### 6b. Justification draft (optional)

The model may draft `justification` prose; **factual fields** (`cli_flag`, `web_form_section`, priorities)
always come from the catalogue at export time, never the model.

### 6c. What we deliberately do *not* do

- **Evol-Instruct on configs** (WizardLM, Xu et al., ICLR 2024 — Evol-Instruct *"rewrite… step by step into
  more complex instructions"*): evolving a structured 65-option set would create conflict violations. Evolve
  *queries* only, if at all.
- **Forward (query → config) generation as gold** — only as a roundtrip diagnostic (§8).

---

## 7. Stage 4 — Automated gates

### 7.1 Deterministic (must pass)

| Gate | Implementation | Literature analogue |
|------|----------------|---------------------|
| Valid option ids | ⊆ `vep_options_expanded.json` | parameter-alignment errors (Iskander et al., 2024) |
| Checker clean | `check_and_fix_violations` on the real query → 0 mutations | constraint-first synthesis |
| Factor consistency | the query must **express all five factors** its config encodes. **Species is the only deterministic hard gate** (`infer_species`): a query whose species contradicts its config fails the row. The other four are checked by a semantic LLM round-trip (a *different* model reads only the query and re-classifies all five factors) and **only ever flag — they never drop a row**, because the queries are deliberately implicit and a classifier disagreement is not proof of a bad query. Plus somatic rows must not enable **`frequency`** (the `--check_frequency` pre-filter) | hard rules in taxonomy §3; query↔config faithfulness |
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

**Review sheet:** factor tuple, query, enabled (RECOMMENDED / ADD-ONS), disabled, checker log, ICE score, judge
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

**Read-status — ALL read + verified from full text on 2026-07-12** (`CITATION_VERIFICATION.md`); every
citation below **SUPPORTS** its claim, no misattributions. Earlier drafts flagged 1/3/6 (SynthIE,
Quality-Matters, Self-Instruct) as cited-but-unread and 2/7/8/9 (Alberti, ARES, Sechidis, WizardLM) as
read-status-unconfirmed — now closed. Per-row caveats are in `CITATION_VERIFICATION.md` §2.

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
5. Xu, Z., Jiang, F., Niu, L., Lin, B. Y., & Poovendran, R. (2025). Stronger Models Are Not Stronger
   Teachers for Instruction Tuning. ***NAACL 2025.*** https://aclanthology.org/2025.naacl-long.224/ ·
   arXiv 2411.07133 (the paper's real thesis: teacher–student *compatibility* — their CAR metric,
   Spearman ρ≈0.889 vs 0.566 for reward alone — governs teacher quality, supporting empirical teacher choice)
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
