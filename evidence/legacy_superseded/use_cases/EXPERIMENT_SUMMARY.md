---
title: "Ask VEPai — Experiment Report"
subtitle: "Rationale, method, and results (GSoC 2026, EMBL-EBI)"
date: "2026-06-21"
---

> # ⚠️ SUPERSEDED — read `EXPERIMENTS.md` instead
>
> **This document is frozen at 2026-06-21 and covers only Experiments 1–9.** `EXPERIMENTS.md` is the live
> ledger (Exp 1–13 + the corrections). Maintaining two ledgers is what let the errors below survive for three
> weeks after they were corrected in the other one, so this file is no longer updated.
>
> **Three claims in the text below are wrong.** They are annotated in place, but in summary:
> 1. **"No crossover at N≤19"** (Exp 2) — **OVERTURNED.** A parser artifact. On 26b with the fixed parser,
>    all-examples' lead over keyword *grows* to **+13 points by N=15**.
> 2. **"semantic is harmful and worsens with capability — at 26B semantic (25%) drops below bare (31%)"**
>    (Exp 1) — **RETRACTED.** Does not survive the corrected parser: semantic is flat ~37–39% and sits
>    *above* bare. What stands is that semantic is the weakest KB condition and does not improve with size.
> 3. **"~50–70 examples per class"** — **MISATTRIBUTED to Agarwal et al. 2024.** That figure is not in the
>    paper; it was our own estimate. Agarwal's saturation is task-dependent, and the paper's one per-class
>    experiment saturates at 512–2048 per class.
>
> **The headline here (87% / 95% / 96% / 86%) is also superseded** by Exp 10's 5-seed live run:
> **84% ± 2 / 92% ± 5 / 95% ± 2 / 81% ± 6** — the drops are seed noise, not regression. And every `bare`
> figure below predates the 2026-07-15 alias fix, which corrected the no-KB baseline down by ~8–12 points.

# Overview

**Ask VEPai** is a locally-hosted RAG assistant that turns a natural-language variant-analysis scenario
into a recommended Ensembl VEP web-form configuration, with justifications and provenance. The architecture
is *defense-in-depth*: a retrieval + local-LLM stage **proposes** a configuration; a deterministic Python
constraint checker **disposes** of what the LLM gets structurally wrong (species / conflict / dependency).

This report summarises the experiments run to date — why each was done, how, and what it found.

## System under test

- **Knowledge base:** expanded **58-option** VEP catalogue (`vep_options_expanded.json`).
- **Examples:** **20-example simulated gold set** (7 use-case categories, constraint-checker-validated).
- **Models:** Gemma 4 (`e4b` / `12b` / `26b`) and Qwen 2.5 (`3b` / `7b`), via local Ollama on Apple Metal.
- **Protocol:** leave-one-out (LOO) over the 20 queries; 4 retrieval conditions — **bare** (no KB),
  **keyword** (all 58 options + top-2 examples by word overlap), **all-examples** (all options + all
  examples), **semantic** (top-10 options + top-2 examples by embedding similarity).
- **Headline metric:** priority-weighted Enable F1 (leave-one-out), plus clinical metrics
  (critical-recall, category-coverage); multi-run **mean ± SD**.

## Honesty caveats (read before citing any number)

1. **The 20-example gold set is *simulated*** (synthetic, checker-validated stand-ins at the target scale),
   pending the mentor's real gold data. **All numbers are directional, not a benchmark.**
2. **The 7 use-case categories have no canonical Ensembl/field backing** — they are a project-internal
   construct pending mentor validation; metrics keyed to a single-label use case are provisional.
3. **A parser bug (fixed 2026-06-08) capped every earlier score by ~30 points.** Experiments 1–3 below are
   reported as run, but their absolute numbers are **superseded** by the corrected results (Exp 4 / Exp 7).

# Experiments at a glance

| # | Experiment | Question it answers | Headline result |
|---|---|---|---|
| 1 | Model comparison | Which model / condition is best? | all-examples wins for **every** model; `gemma4:26b` best |
| 2 | Example-count sweep | Does all-examples' lead collapse as the corpus grows? | **[OVERTURNED — see banner]** its lead *grows*: +13 pts by N=15 |
| 3 | Clinical re-scoring | Is "~55% F1" really poor? | No — exact-F1 understates quality (crit-recall ≫ F1) |
| 4 | **Parser bug fix** | Were the scores capped by a parser bug? | **Yes — true best = 87% F1 / 95% crit-recall** |
| 5 | Attribution (pilot) | Are recommendations KB-driven or parametric? | ~84% KB-faithful (later refined) |
| 6 | Attribution (full + real) | Where does grounding live; does it hold on real queries? | 79% KB-grounded; holds on real forum queries |
| 7 | Offline re-score | Re-measure after code-review fixes | Headline robust; Disable-F1 81%→86% |
| 8 | Structured JSON output | Can the local model emit schema-valid JSON? | **No** (negative result) — keep free-text parser |
| 9 | **Example-order sensitivity** | Does example order change the score? | all-examples robust; semantic order-fragile |

---

# Experiment 1 — Model comparison

**Rationale.** Establish which model and which retrieval condition perform best, and whether the
all-examples vs selective-retrieval choice matters across models.

**Method.** 5 models × 4 conditions, N=20 examples, 3 runs, leave-one-out, priority-weighted Enable F1.
(Caveat: this set mixes model *family* and *architecture* — `gemma4:26b` is MoE, others dense — so it
supports *universal* statements, not clean size *trends*.)

**Result (Enable F1, mean over 20 queries × 3 runs — later shown to be parser-capped):**

| model | bare | keyword | all-ex | semantic |
|---|---|---|---|---|
| qwen2.5:3b | 31% | 35% | 39% | 33% |
| gemma4:e4b | 26% | 45% | 49% | 32% |
| qwen2.5:7b | 33% | 45% | 47% | 36% |
| gemma4:12b | 26% | 46% | 50% | 29% |
| gemma4:26b | 31% | 52% | **55%** | 25% |

**Findings.** (1) **All-examples beats keyword for every model tested.** (2) ~~**Semantic option-filtering is
harmful and worsens with capability** — at 26B, semantic (25%) drops *below* bare (31%)~~ — **RETRACTED
(Exp 10):** this does not survive the corrected parser. Semantic is **flat at ~37–39% across all three model
sizes and sits *above* bare**, not below it. What stands: semantic is by far the weakest KB condition (39%
vs 84%) and, unlike keyword/all-examples, does **not** improve as the model scales — so hard-filtering 58
options to 10 forfeits the larger model's gains (a retrieval-recall failure). Only the "below bare / worsens
with capability" framing is withdrawn. (3) KB value grows with model size. (4) **Best config: `gemma4:26b`
+ all-examples.** (5) Raw species/conflict violations persist at all sizes — all removed by the
deterministic checker.

---

# Experiment 2 — Example-count sweep (corpus-size axis)

**Rationale.** Test whether all-examples' lead over selective retrieval **collapses as the corpus grows**
(isolating corpus size from model size). ~~Literature on many-shot ICL (Agarwal et al. 2024) predicts the
crossover only appears at ~50–70 examples *per class*~~ — **MISATTRIBUTION (corrected 2026-07-12):** that
figure is **not in Agarwal et al.** It was our own conservative estimate. A full-text check found Agarwal's
saturation is task-dependent (≈10→125 *total* shots; XSum declines past ~50 total), and the paper's only
per-class experiment saturates at **512–2048 per class**. Agarwal also runs no retrieval baseline, so it
grounds "more distinct examples keep helping", not the all-vs-selection crossover. The real per-class
saturation being an order of magnitude higher only puts a curated gold set *further* inside the
"more examples help" regime — so the conclusion strengthens.

**Method.** `gemma4:e4b`, stratified LOO subsample, N ∈ {2,5,10,15,19}, 2 runs.

**Result.** ~~all−keyword delta oscillates in the noise band (−2% to +2%) with no trend. **No corpus-size
crossover.**~~ — **OVERTURNED (re-run 2026-07-14).** The flat delta was a **parser artifact**: the old parser
discarded roughly half of every condition's recommendations, compressing the conditions together. Re-run on
`gemma4:26b` with the fixed parser, all-examples' lead over keyword **grows monotonically with corpus
size** — ~0 at N=2 → **+13 points by N=15–19** — because keyword is capped at the top-2 examples however
large the corpus gets. The direction of the original conclusion (no crossover) survives; its *substance*
("all ≈ keyword at every N") does not.

---

# Experiment 3 — Clinically-meaningful re-scoring

**Rationale.** Exact-match Enable F1 over-penalises a recommender on an *ambiguous* task (interchangeable
predictors like CADD/REVEL score as both false-positive and false-negative). Re-measure with metrics that
target what matters — **critical-recall** (fraction of must-have options recommended) and
**category-coverage** (fraction of needed annotation *types* covered) — computed offline from raw logs.

**Method.** Re-measure the identical Exp-1 system; `exact_f1` reported as a consistency check (it reproduced
Exp 1, confirming same system).

**Result (later parser-capped).** Best config (26B all-examples) had crit-recall 70% and category-coverage
75% — well above its 55% exact-F1. **"50% F1 = poor" is largely a metric/gold artifact**, not broken
recommendations. Raw harm removed by the checker (post-checker harm = 0).

---

# Experiment 4 — Parser bug fix (the headline correction)

**Rationale / discovery.** The model emits a clean `✓/✗ option [source: option_id]` format, but the parser
ignored the markers and `[source:]` tags and did fuzzy name-matching — **dropping ~half the correct enables
and every disable.** A parsing bug, not the model, was capping all prior scores.

**Method.** Fix the parser to read the marker + exact `[source: id]`; add raw-response logging; re-run
identically otherwise.

**Corrected `gemma4:26b` results:**

| condition | exact-F1 | crit-recall | category-cover | Disable-F1 | over-rec |
|---|---|---|---|---|---|
| bare | 30% | 56% | 49% | 4% | 0.91× |
| keyword | 71% | 68% | 82% | 67% | 1.18× |
| **all-examples** | **87%** | **95%** | **96%** | **81%** | 1.18× |
| semantic | 39% | 38% | 45% | 21% | 0.71× |

**What this corrects.** Absolute F1s were ~30 points too low; the true best config is **87% F1 / 95%
critical-recall / 96% category-coverage**. The "over-recommends / enable-heavy / all ≈ keyword" reads were
parser artifacts — the model is disciplined (1.18×) and disables well. **all-examples (87%) ≫ keyword (71%).**

**What survives.** Semantic option-filtering still hurts (now more starkly); the deterministic checker is
still validated (raw harm → 0 post-checker).

---

# Experiment 5 — Attribution: per-recommendation KB-faithfulness (pilot)

**Rationale.** RAG's value (and the project's "provenance-traced" thesis) requires recommendations to be
**KB-driven** (they update when VEP changes) rather than **parametric** (model memory, risks staleness).
This is independent of correctness, so it is valid on the simulated gold.

**Method.** Occlusion/ablation: for each recommended option, remove its KB signal (guidance + example
demonstrations), re-run greedy, and check whether it disappears (faithful) or persists (parametric).

**Result (7-query pilot, 77 recommendations).** **faithfulness_rate = 84%** — most recommendations are
KB-driven. The *specific* options (allele-frequency, ClinVar, HGVS, protein) are 100% KB-faithful; the
*obvious/ubiquitous* ones (symbol, SIFT) are parametric (and parametric ≠ wrong). (Pilot later found to be
single-run/noise-exposed — superseded by Exp 6.)

---

# Experiment 6 — Attribution: decomposition (6a) + real-query generalization (6b)

**Rationale.** (6a) *Where* does the grounding live — in the worked examples or the option descriptions?
(6b) Does the faithfulness hold off the synthetic distribution, on real forum queries?

**Key methodological finding.** On this Metal/MoE stack, **temperature=0 is not deterministic** under
concurrency (batch-composition float noise flips borderline options). Reproducible attribution requires
**concurrency 1 + fixed seed**. (This does not affect the Exp 1–4 F1 numbers, which used `--runs 3` mean±SD
that averages over exactly this noise.)

**Result.**

*6a — decomposition:* examples-only ablation = **56%**, description-only = **26%**, combined = **79%**
(⇒ 21% parametric). The two channels are largely complementary: the model grounds most recommendations by
imitating the demonstrated configs (few-shot ICL), with descriptions covering the long-tail options.

*6b — real queries:* faithfulness on real forum queries = **77%** (verbatim-only **79%**, identical to
synthetic). KB-grounding is **not** a synthetic-phrasing artifact.

**Bottom line.** ~79% of recommendations are KB-grounded and this holds on real queries — the core RAG
thesis is supported. (Directional; correctness still needs the mentor's real configs.)

---

# Experiment 7 — Offline re-score with corrected code

**Rationale.** After a code review fixed several parsing/scoring issues (phantom-id alias leak, undefined-
metric handling, species fail-closed, checker now repairs output), the numbers needed re-measuring. Because
only parsing/scoring changed (not the prompt or model), this is an **offline re-score** of the logged
responses — isolating the code change as the only variable, no GPU needed.

**Result.** Headline robust: all-examples enable-F1 **87% (stable)**, crit-recall **95%**, category-cover
**96%**; **Disable-F1 81% → 86%** (correcting a spurious zero from one empty-gold query). Phantom-id leak
eliminated (→ 0). The deterministic checker drives raw harm to 0 post-checker.

---

# Experiment 8 — Structured JSON output feasibility (negative result)

**Rationale.** The fragile free-text parsers were slated to be replaced by having the model emit structured
JSON. This tests whether `gemma4:26b` can reliably produce schema-valid JSON for the full task.

**Result.** **Not viable on the local model.** Grammar-constrained JSON went degenerate; JSON-mode produced
only ~40% valid JSON over 40 queries (frequent truncation on large recommendation sets, poor schema
conformance). **This reverses the "structured output fixes the parsers" plan** — the hardened free-text +
exact `[source:]` parser is the more reliable path on this stack. Structured output is deferred (salvage
paths noted: bounded output, per-option extraction, or a stronger model for the JSON pass).

---

# Experiment 9 — Example-order sensitivity

**Rationale.** Agarwal et al. 2024 (§4.7) show that even in the many-shot regime, the **order** of
in-context examples causes large, inconsistent variance. Our harness holds example order fixed, so its
multi-run SD captures decoding noise only — never order. This measures how much order alone moves the score.

**Method.** One new variable — example order. Same harness/metric/model (`gemma4:26b`), same 20-example set,
**greedy decoding** (to isolate order from decoding noise), fixed LLM seed; 10 random shuffles of a fixed
set + the natural order. Conditions: `all` (19 examples shown) and `semantic` (top-8). Report mean ± SD
**across orderings**.

**Result (priority-weighted Enable F1, leave-one-out):**

| condition | examples shown | mean ± SD | min–max (range) | natural order |
|---|---|---|---|---|
| **all** | 19 | **87.7% ± 1.6%** | 84.6–90.6% (6.0%) | 87.6% |
| **semantic** | top-8 | **60.0% ± 6.9%** | 48.8–68.7% (19.9%) | 54.4% |

**Findings.** **`all-examples` is order-robust** — SD 1.6% sits inside the decoding-noise band, and the
natural file order ≈ the shuffle mean (and reproduces the established ~87%). **`semantic` (top-8) is highly
order-sensitive** — SD 6.9%, ~20-point range; notably the similarity-sorted order (54.4%) is *below* the
shuffle mean (60.0%), so the retrieval ranking is not an optimal in-context order.

**Caveat.** `all` (19) and `semantic` (8) differ in example count and the option filter, so the SD *gap*
conflates order with those factors; within each condition the SD is a clean order-only measure.

**Takeaway.** Order is a non-issue for the recommended all-examples path (the fixed file order is fine), and
a second fragility for semantic (alongside the known option-filter harm). If semantic is ever used, order
must be pinned and reported as mean ± SD over orderings.

---

# Overall conclusions

1. **Best configuration:** `gemma4:26b` + **all-examples** — **87% Enable F1, 95% critical-recall, 96%
   category-coverage, 86% Disable-F1** on the simulated gold; raw harm → 0 after the deterministic checker.
2. **Do not hard-filter the 58 options.** Semantic top-k option filtering is robustly harmful (a
   retrieval-recall failure) and worsens with model capability — confirmed across models, conditions, and
   the order experiment.
3. **Include all examples.** At a curated-gold-set scale (≤20), selective example retrieval only loses
   signal; the corpus is far below the many-shot crossover.
4. **The RAG is doing its job:** ~79% of recommendations are KB-grounded (driven mainly by the worked
   examples), and this holds on real forum queries — supporting RAG over fine-tuning (updatable + traceable).
5. **The deterministic checker is necessary** — raw-model species/conflict violations persist at every model
   size and are only removed by the checker.
6. **Free-text + exact-`[source:]` parsing is the reliable path** on this local stack; structured JSON
   output is not yet viable.
7. **Reproducibility discipline matters:** a parser bug capped early numbers by ~30 points, and temp=0 is
   non-deterministic under concurrency — both caught only because results are logged and multi-run.

**Standing limitation.** All results are on the *simulated* gold set and the provisional 7-use-case
taxonomy — directional evidence, to be re-confirmed against the mentor's real gold-standard data.
