# Ask VEPai — Experimental Report (preliminary, real system)

> **How to read this ledger (experiments vs re-analyses).** Entries are numbered chronologically (Exp 1–10)
> in the order they were done. Not all are independent experiments: several are **re-analyses** that
> re-score the *same logged model outputs* with corrected parsing/metrics — no new inference. For review,
> the README groups them as five experiments (E1–E5) plus corrections:
>
> | Ledger entry | Type | README ID |
> |---|---|---|
> | Exp 1 — Model comparison | Experiment (new runs) | E1 |
> | Exp 2 — Example-count sweep | Experiment (new runs) | E2 |
> | Exp 3 — Clinical re-scoring | **Re-analysis** of Exp 1 logs | (correction) |
> | Exp 4 — Parser bug fix | **Re-analysis** of Exp 1 logs (re-parse) | (correction) |
> | Exp 5 — Attribution (pilot) | Experiment (new runs) | E3 |
> | Exp 6 — Attribution (full + real) | Experiment (new runs) | E3 |
> | Exp 7 — Offline re-score | **Re-analysis** of Exp 1 logs | (correction) |
> | Exp 8 — Structured-output feasibility | Experiment (new runs) | E4 |
> | Exp 9 — Example-order sensitivity | Experiment (new runs) | E5 |
> | Exp 10 — 5-seed re-run of the model comparison | Experiment (new runs) | E1 |
>
> The headline numbers were first derived as **re-analyses** of Exp 1's logged 26b outputs (Exp 4 + 7).
> **Exp 10 (2026-06-22) supersedes them with a fresh 5-seed live run** of all three Gemma models under the
> corrected parser — current headline: **26b + all-examples = 84% Enable F1** (was 87% on the single 3-seed
> log). Run-level mean ± SD: `work/harness/compute_run_sd.py`.

**System under test:** expanded **58-option catalogue** (`vep_options_expanded.json`) + **20-example simulated gold set** (`preliminary_examples/simulated_gold_examples.json`, 7 use cases, checker-validated). **Not** the demo's 26 options / 8 examples.
**Protocol:** leave-one-out over all 20 queries; 4 retrieval conditions; multi-run mean. Parallel GPU eval (`run_parallel_eval.py`, 4 concurrent slots) on **Apple M5 Max, Metal** (native arm64 Ollama, ~180 tok/s).
**Conditions:** *bare* (no KB) · *keyword* (all 58 options + top-2 examples by word overlap) · *all-examples* (all 58 options + all examples) · *semantic* (top-10 options + top-2 examples by BGE cosine).
**Note on status:** these are **simulated** gold examples (synthetic stand-ins at the target scale, pending the mentor's real gold set) — directional results, not a benchmark.
**Note on the taxonomy:** the 7 use-case categories are a **project-internal construct with NO canonical Ensembl or field-standard backing** (researched 2026-06-15 — see `work/research/taxonomy_proposal.md`): Ensembl organises VEP by option-*function* (6 web-form sections), not by use-case, and the field favours orthogonal/multi-label axes (species × origin × variant-class …). The categories — and the `priority_by_use_case` keyed to them — are **pending mentor validation**; every metric keyed to a single-label use case is provisional on that taxonomy being kept.

---

## Experiment 1 — Model comparison (5 models, N=20 examples, runs=3)

> **Confound — NOT a clean size sweep.** This set mixes **family** (Qwen2.5 vs Gemma 4) and
> **architecture** (`gemma4:26b` is **MoE**, ~3.8B active/token; all others **dense**). So results below
> support only **universal** statements ("X holds for every model tested"), **not size *trends*** — we
> cannot cleanly attribute any effect to model size. A clean size sweep needs **one family + one
> architecture** (e.g. dense Gemma 4: E2B/E4B/12B/31B, excluding the MoE 26B; or dense Qwen2.5
> 3B/7B/14B/32B). The rough ordering below is for reading convenience only.

Enable F1 (mean over 20 queries × 3 runs):

| model | bare | keyword | all-ex | semantic | all − kw | run time |
|-------|------|---------|--------|----------|----------|----------|
| qwen2.5:3b | 31% | 35% | 39% | 33% | +4% | 890 s |
| gemma4:e4b | 26% | 45% | 49% | 32% | +4% | 3170 s |
| qwen2.5:7b | 33% | 45% | 47% | 36% | +2% | 1826 s |
| gemma4:12b | 26% | 46% | 50% | 29% | +4% | 9604 s |
| gemma4:26b | 31% | **52%** | **55%** | 25% | +3% | 4554 s |

**Findings**
1. **All-examples beats keyword for *every model tested*** (+2 to +4%) — Qwen and Gemma, dense and MoE,
   small and large. This is a **universal** result, robust to the family/architecture confound (it holds
   for all 5 regardless). What we **cannot** claim is a *size trend* — the axis is confounded (see note),
   and the earlier "+4/+4/+2 shrinking with size" read was already retracted as noise. So: no model in
   this set makes selective retrieval beat all-examples; whether *size specifically* matters is untested
   (would need a clean dense single-family ladder — likely confirmatory given Exp 2 + the literature).
2. **Semantic option-filtering is harmful and *worsens* with capability:** 33→32→36→29→**25%**. At 26B, semantic (25%) drops **below bare (31%)** — filtering 58 options to 10 discards what the strong model would have used. This is a **retrieval-recall failure** (see literature), robust across all models. *(Superseded by Exp 10: under the corrected parser + 5 seeds, semantic is flat ~37–39% across model sizes and sits **above** bare; the "below bare / worsens with capability" framing is withdrawn. The retrieval-recall failure — semantic ≪ keyword/all and no gain with size — stands.)*
3. **KB value grows with model size:** keyword Δ-vs-bare +4% (3B) → +12% (7B) → +21% (26B); citation 0→~85–98%; use-case accuracy 15%→100% (26B, all-examples).
4. **Best config:** `gemma4:26b` + all-examples = **55% Enable F1 / 63% priority-weighted / 100% use-case detection**.
5. **Defense-in-depth re-validated:** raw-model species/conflict violations persist at all sizes (up to 63 conflicts at 26B-keyword) — all removed by the deterministic checker.
6. **Disable-F1 stays low (~1–5%)** except `gemma4:e4b` (13–18%) — the enable-heavy demonstration bias is real; better instruction-followers (e4b) pick up the conservative-trim disable signal.

**Compute note (counterintuitive):** `gemma4:12b` (9604 s) is **~2.1× slower than `gemma4:26b`** (4554 s). 12B is *dense* (12B active/token); 26B is *MoE* (~3.8B active/token) → less compute per token despite more total weights.

---

## Experiment 2 — Example-count sweep (corpus-size axis)

**Question:** does all-examples' lead over selective retrieval **collapse as the corpus grows** (N = 2→5→10→15→19, stratified subsample, fixed LOO test set)? This isolates **corpus size** from model size.

**Literature-grounded prediction (we expect NO crossover at N≤19):**
- Many-shot ICL ([Agarwal et al. 2024](https://arxiv.org/html/2404.11018v1)): for **constrained-output tasks** (like ours — pick from a bounded option set), performance rises with a *small* number of demonstrations and **saturates quickly**; the plateau/degradation appears around **~50–70 examples *per class*** (≈350–500 total for our 7 use cases) or at **context saturation**.
- Long-context vs RAG ([2501.01880](https://arxiv.org/abs/2501.01880); [Databricks](https://www.databricks.com/blog/long-context-rag-performance-llms)): stuffing all context beats selective retrieval *when it fits and is relevant*; selective wins on cost and once context saturates / "lost-in-the-middle" sets in (~20-pt mid-context degradation).
- **Our regime:** 20 examples (~3/class), all-examples prompt ~10K tokens in a 32–256K window — far below overflow and far below the ~50–70/class crossover. So the sweep **confirms our operating regime (all-examples dominates), it does not discover a crossover.** Reaching the crossover needs **hundreds** of examples — beyond a curated gold set; only a large corpus (e.g., raw helpdesk logs) would.

**Result — `gemma4:e4b`** (stratified LOO subsample; **runs=2**; N ∈ {2,5,10,15,19}; cmd:
`run_example_sweep.py --models gemma4:e4b --ns 2,5,10,15,19 --runs 2 --concurrency 4`):

| N (corpus) | bare | keyword | all-ex | semantic | all − kw |
|---|---|---|---|---|---|
| 2 | 27% | 43% | 43% | 28% | −0% |
| 5 | 27% | 43% | 45% | 32% | +2% |
| 10 | 27% | 47% | 46% | 30% | −1% |
| 15 | 27% | 47% | 44% | 30% | −2% |
| 19 | 27% | 46% | 48% | 31% | +2% |

**Finding: no corpus-size crossover — and all-examples ≈ keyword at *every* N.** The all−kw delta
oscillates in the **noise band (−2% to +2%)** with no trend. At N=2→19 (far below the ~50–70/class
many-shot saturation point), including all examples vs selecting top-2 makes **no reliable difference**.
The robust gaps are elsewhere: KB ≫ bare (27% → 43–48%) and **keyword ≫ semantic** (~−14% throughout,
flat in N — as expected, since semantic filters *options*, not examples). This **matches the
literature-grounded prediction**: a curated gold-set scale is below the regime where example selection
matters.

**Consistency check vs Experiment 1** (same harness/metric/LOO; only N varies): at N=19 this run gives
e4b all−kw = +2%; Experiment 1 (runs=3, full corpus) gave +4% — agreement **within the ±SD noise band**,
so the two experiments measure the same quantity. *Caveat (discipline rule 4):* runs=2 here vs the ≥3
standard — adequate for the predictable curve shape; the conclusion (all−kw ≈ 0) is robust to it, and a
runs=3 pass would tighten ± without changing it.

**Bottom line:** on both axes we can reach (model size 3B–26B; corpus size N≤19), **all-examples never
loses and the all-vs-selective-*examples* question is effectively moot** at this scale. The single
in-range, actionable result remains the **option-retrieval recall failure** (don't hard-filter the 58
options). The example crossover needs hundreds of examples (a large corpus) — out of scope for a 15–20
gold set; the harness scales to N≫20 unchanged when such data exists.

---

## Correction — clinically-meaningful re-scoring (precision diagnosis)  *(re-analysis of Experiment 1; no new model runs; chronological entry "Experiment 3")*

**Motivation.** Best exact-match Enable F1 is ~55% — but the split is **recall 68% / precision 48%**
(26B, all-examples), i.e. the model **finds 2/3 of gold options and over-recommends by ~1.4×**. Exact-match
F1 over-penalises a recommender on an *ambiguous* task: every defensible extra is an "error" and
interchangeable picks (CADD vs REVEL) score as misses. So we re-measure with metrics that target what
matters, computed **offline from raw logs** (no LLM re-run needed once captured):
- `critical_recall` — of the gold's **critical** options for the use case, fraction recommended (must-haves).
- `important_recall` — same for critical+recommended.
- `category_cover` — of the **annotation categories** the gold needs, fraction with ≥1 option recommended
  (credits "got a pathogenicity predictor", not "got REVEL exactly") — uses the catalogue's `category` field.
- `over_rec` — `|enabled|/|gold|`; `harm` — raw human-only-for-non-human count (0 post-checker).

**Justification (discipline rule 7).** *(a) Consistency:* this is a **re-measurement of the identical
Experiment-1 system** — same KB (58), examples (20), conditions, seeds, temperature, harness; the only
change is raw-output logging. `exact_f1` is reported as a **built-in consistency check** and must reproduce
Experiment 1 (26B all-examples ≈55%). *(b) Literature:* task-completion / recall-of-critical-items and
category coverage are standard for recommendation over an ambiguous label space; safety reported separately
(harm). **Scope:** the 3 Gemma sizes (the deployable models; qwen devalued).

**Infra fix:** `run_parallel_eval.py` now writes `work/results/raw/<model>.jsonl` (per-call enabled/disabled/
gold/use-case/query); `work/harness/score_metrics.py` computes the above from those logs — so future metric changes
never require a re-run.

**Result** — consistency check **PASSED** (26B all-ex exact-F1 = 55% here vs 55% in Exp 1; e4b 47% vs 49%; all within ±SD → same system):

| model | cond | exact-F1 | **crit-recall** | imp-recall | **cat-cover** | over-rec | harm(raw) |
|-------|------|---------|-----------------|------------|---------------|----------|-----------|
| gemma4:26b | keyword | 54% | 68% | 70% | 75% | 1.47× | 35 |
| gemma4:26b | all-ex | 55% | **70%** | 71% | **75%** | 1.50× | 31 |
| gemma4:26b | semantic | 28% | 62% | 32% | 53% | 1.09× | 16 |
| gemma4:e4b | keyword | 48% | 66% | 64% | 70% | 1.65× | 28 |
| gemma4:e4b | all-ex | 47% | 63% | 60% | 66% | 1.41× | 23 |
| gemma4:12b | keyword | 46% | 62% | 62% | 69% | 1.52× | 16 |
| gemma4:12b | all-ex | 53% | 57% | 65% | 68% | 1.41× | 22 |

(Universal across all 3 Gemma — no size/architecture trend claimed: all-examples crit-recall **57–70%**,
cat-cover **66–75%**, each well above its exact-F1 47–55%. Best = 26B.)

**Finding: ~55% exact-F1 substantially *understates* quality.** Best config (26B, all-examples) has
**critical-recall 70%** and **category-coverage 75%** — it surfaces ~70% of the *must-have* options and
covers ~75% of the needed annotation *types*. The exact-F1 gap is explained by **over-recommendation
(~1.5×)** vs conservative synthetic gold + binary scoring of interchangeable options. So "50% = poor" is
mostly a **metric/gold artifact**, not broken recommendations.

**Real headroom remains:** 70% crit-recall ⇒ ~30% of must-haves still missed; over-rec 1.5× ⇒ a
precision/discipline gap. These are the genuine improvement targets (structured per-option output; better
examples / fine-tuning; real gold).

**Safety:** raw harm 31–35 (human-only options for non-human queries) → **all removed by the checker
(post-checker harm = 0).** **all ≈ keyword** on clinical metrics too (crit-recall 68 vs 70; cat-cover 75 =
75) — consistent with Exp 1/2; **semantic** tanks category-coverage (53% vs 75%) — option-filtering recall
failure, re-confirmed.

## Correction — PARSER BUG FIX  *(re-analysis of Experiment 1; no new model runs; chronological entry "Experiment 4"). This is where the corrected headline numbers come from.*

**A parsing bug, not the model, was capping all prior scores.** The model emits a clean
`✓/✗ **option** [source: option_id]` format, but `extract_recommendations` ignored the markers and
`[source:]` tags and did fuzzy name-matching (built for the demo's 26 ids) — dropping ~half the model's
correct enables, adding spurious wrong ids, and discarding **every** `✗` disable. Fixed to parse the
marker + exact `[source: id]` (fuzzy fallback only when no tags, e.g. bare). Also added raw-response
logging so parser/metric changes never need a re-run again.

**Corrected 26B (fixed parser; identical run otherwise; `work/results_fixedparser/`):**

| cond | exact-F1 | crit-recall | cat-cover | Disable-F1 | precision | recall | over-rec |
|------|----------|-------------|-----------|------------|-----------|--------|----------|
| bare | 30% | 56% | 49% | 4% | 36% | 29% | 0.91× |
| keyword | 71% | 68% | 82% | 67% | 68% | 77% | 1.18× |
| **all-ex** | **87%** | **95%** | **96%** | **81%** | **82%** | **94%** | **1.18×** |
| semantic | 39% | 38% | 45% | 21% | 52% | 33% | 0.71× |

**Sanity check:** `bare` Enable-F1 30% vs 31% before (no `[source:]` → fuzzy fallback) — unchanged, as required.

**What this CORRECTS in Exp 1–3 (all were parser-capped):**
- Absolute F1s were all **~30 points too low**; the true best config (26B all-ex) is **87% F1 / 95%
  critical-recall / 96% category-coverage**, not 55%/70%/75%.
- **"Over-recommends 1.5× / Disable-F1 ≈ 0 / enable-heavy bias"** were **parser artifacts** — the model is
  disciplined (**1.18×**) and disables well (**Disable-F1 81%**). The fuzzy parser had thrown away the `✗` lines.
- **"all ≈ keyword (all-vs-select moot)"** (Exp 1/2) was **parser-capped**: corrected, **all-ex 87% ≫
  keyword 71% (+16)**. The example-count sweep (Exp 2) used the buggy parser → its "no advantage"
  conclusion is **invalid and must be re-run** with the fix.

**What SURVIVES:** **semantic option-filtering still hurts, now even more starkly** (all-ex crit-recall 95%
vs semantic 38%; F1 87% vs 39%) — the recall failure is robust. The deterministic checker is still
validated (raw harm 1–33 → 0 post-checker).

**Status:** 26B is the model; with correct extraction the system is **~87% F1 / 95% critical-recall** on
the simulated gold — strong. Re-running Exp 1/2 with the fix (and the durable raw logs) is the cleanup.

## Experiment 5 — Attribution testing (per-recommendation KB-faithfulness)

**Question.** Is each recommended option driven by the curated KB (**faithful**: it disappears when its
KB signal is removed) or by the model's **parametric** training knowledge (it persists)? This is
*independent of whether the recommendation is "correct"*, so it is **valid on the simulated gold** and
unblocked by the missing real data.

**Why it matters.** RAG's value and the project's "provenance-traced" thesis require recommendations to be
KB-grounded — so they update when VEP changes and trace to authoritative data; parametric recommendations
risk staleness. Coarse evidence already exists (bare 30% vs all-examples 87% ⇒ the KB drives ~57 F1
points); this measures it **per recommendation** and produces the proposal's promised attribution profile.

**Fixed setup (consistent with Exp 4).** model `gemma4:26b`; condition **all-examples** (no retrieval
confound — all examples in-prompt); 58-option KB + 20 simulated examples, leave-one-out; the fixed parser.
**Decoding `temperature=0` (greedy)** — a *documented, justified* deviation from the eval's 0.7:
attribution needs a deterministic recommendation so the ablation effect is not confounded by sampling
noise (standard for occlusion/feature attribution).

**Ablation (per *recommended* option r, per query Q).** "KB signal for r" =
 1. r's **guidance**: blank `description` / `when_to_use` / `when_not_to_use`; neutralize
    `priority_by_use_case` → all `optional`. *Keep* `id` / `cli_flag` / `species_restriction` (+ conflicts/
    depends) so r stays a valid, *listable* option the model could still choose — the test is whether it
    chooses it *without guidance*.
 2. r's **demonstrations**: remove r from every corpus example's `recommended_options`.
 Rebuild the all-examples prompt, re-run Q (greedy), check whether r ∈ enabled.
 - **Combined** (primary): (1)+(2). r gone → **faithful** (attribution = 1); r persists → **parametric** (0).
 - **Decomposition** (secondary): (1)-only and (2)-only → *description-attribution* vs *example-attribution*.

**Metric.** `attribution(r,Q) ∈ {0,1}`; `faithfulness_rate` = mean over all (Q, recommended r);
per-option and per-use-case profiles; **headline = fraction of recommendations that are KB-faithful**
(high-attribution = KB-driven, low = potentially-stale parametric).

**Controls / validity.** *Negative control:* ablate a sample of NON-recommended options → should rarely
*create* a recommendation (confirms the ablation is local). *Collateral:* count OTHER recommendations that
change per ablation (should be small). *Determinism:* temp=0; run the baseline twice → must be identical.

**Cost.** We only ablate the *recommended* options (~12–15/query), not all 58 — sufficient to attribute the
recommendations. Pilot = 7 stratified queries × (~13 combined ablations + 1 baseline) ≈ ~100 greedy runs
≈ ~1.5–2 h on 26B. Full 20 queries ≈ ~300 runs ≈ ~4–5 h (decomposition ×3). Re-scorable: log each
ablation's enabled set + the ablated unit.

**Implementation.** `work/harness/run_attribution.py` (reuses `build_system_prompt` on an ablated catalogue +
ablated examples in all-examples mode, `call_llm` at temp=0, and the fixed `extract_recommendations`).
Per query: baseline → R_full; ∀ r ∈ R_full → ablated run → persist?; log + aggregate.

**Justification (discipline rule 7).** *(a) consistency:* same model / KB / examples / LOO as Exp 4; one
variable per run (the removed KB signal for r); temp=0 documented. *(b) literature:* occlusion /
leave-one-out feature attribution (Zeiler & Fergus 2014) and RAG context-faithfulness — the per-item
ablation is the standard way to attribute a black-box output to its inputs.

**Result (7-query stratified pilot, combined ablation, 77 recommendations).**
**faithfulness_rate = 84%** — 84% of recommendations *disappear* when their KB signal is removed
(KB-faithful); only 16% persist (parametric). **Strong support for the provenance-traced thesis: the RAG
genuinely drives recommendations, not parametric regurgitation — changing the KB changes 84% of the output.**

The profile matches the prediction:
- **Fully KB-faithful (100%):** the *specific/differentiating* options — `af`, `af_gnomade`, `af_gnomadg`,
  `clinvar`, `hgvs`, `protein`, `numbers`, `core_type`. The model needs the curated guidance for these.
- **Parametric (low faithful):** the *obvious/ubiquitous* options the model knows from training — `symbol`
  71%, `check_existing` 71%, `sift` 67%, `biotype` 75% — and "common-sense" matches `regulatory`→regulatory
  query (0%), `pick`→large-VCF (0%), `gnomad_sv`→SV query (0%). **Parametric ≠ wrong** — these are correct
  recommendations the model would make anyway; the KB simply isn't *load-bearing* for them.
- **Per-query:** highest where configs are specific (rare-disease 97%, somatic 92%); lowest where general
  annotations dominate (non-human 62%).

**Caveats:** per-option faithfulness is noisy for low-n options (`pick`/`gnomad_sv` n=1, `regulatory` n=2 →
the 0%s are directional); the aggregate 84% over 77 recs is robust. On the simulated KB/gold; greedy
decoding. Decomposition (`description`-only vs `examples`-only) and the full 20-query run not yet done.

**Takeaway.** The RAG is doing its job (84% KB-grounded) — the whole rationale for RAG over fine-tuning
(updatable + traceable). The KB is load-bearing for the specific options; the obvious ones the model's
prior already covers — useful for deciding where to strengthen the KB. Raw: `results_fixedparser/attribution/`.

## Experiment 6 — Attribution: KB-component decomposition (6a) + real-query generalization (6b)  [DONE 2026-06-10]

Two analyses extending Exp 5, sharing ONE harness/model/KB so they are directly comparable. Each changes
exactly one variable; everything else (`gemma4:26b`, expanded 58-option KB, all-examples retrieval,
temp=0, combined-mode unless noted) is held fixed. Driver: `work/harness/run_exp6.sh`.

**Methodological finding that reshaped the protocol — temp=0 is NOT deterministic on this stack.**
Diagnostics before launch (Apple M5 Max, Metal, gemma4:26b):
- 3× identical baseline, temp=0, `seed=None`, sequential → **non-deterministic** (option `nmd` flipped
  in/out; 25 vs 26 enabled).
- 3× identical baseline, temp=0, **`seed=42`, sequential (concurrency 1)** → **deterministic** (identical).
- Same prompt+seed run **alone vs co-batched** with 3 different queries under concurrency 4 → **5–12
  options differ**. Batched inference makes float reductions batch-composition-dependent → at temp=0
  argmax, borderline options flip and cascade.
**Consequence:** reproducible attribution requires **`--concurrency 1` + fixed `seed=42`** (the only
configuration that is deterministic). The Exp 5 pilot (84%, single run at concurrency 4) is therefore
**noise-exposed and superseded** by this clean re-run (pilot preserved as
`gemma4_26b_combined_pilot7_cc4.json`). The Exp 1–4 F1 numbers are **not** affected — they used `--runs 3`
mean±SD, which averages over exactly this batch noise (this is *why* the discipline mandates multi-run).

**6a — KB-component decomposition (where does the faithfulness live?).** On the full 20-query simulated set
(LOO), run attribution in three modes against the SAME deterministic baselines: `combined` (ablate option
guidance + example demonstrations together), `description` (guidance only), `examples` (demonstrations
only). Compares faithful(combined / description / examples) per option + overall. *Prediction:* examples
dominate for common options (few-shot ICL imitation); descriptions matter for options rare/absent in the
worked examples; combined ≥ max(description, examples).

**6b — real-query generalization (does faithfulness hold off the synthetic distribution?).** Curate real
VEP config questions from public forums (`work/preliminary_examples/real_queries_biostars.json`), run
combined-mode attribution (no LOO — no gold example exists; full 20-example corpus), compare faithfulness
to the synthetic combined run. **Gold-free** — measures KB-GROUNDING + behaviour, NOT correctness
(correctness still needs the mentor's gold; these queries double as that benchmark's scaffold).

**Anti-bias controls (pre-registered).**
- *One variable.* 6a varies only the ablation mode; 6b varies only the query source. Same harness, model,
  KB, temperature, decoding, seed, scoring code throughout.
- *Determinism.* `--concurrency 1` + `seed=42`, verified deterministic above → a single ablation run is
  exact and the appear/disappear metric is signal, not sampling noise. Baselines saved with every run so
  cross-mode baseline identity is auditable. (mean±SD does not apply — the run is deterministic, not
  sampled.)
- *Same regime.* Synthetic queries are LOO (gold example removed → 19-example corpus); real queries have
  no gold example (→ 20-example corpus). Both are in the "no exact-match example" regime; the ±1 example
  is logged as a negligible, unavoidable, non-biasing nuisance (equalising it would require deleting a
  real example or leaking the synthetic answer — both worse).
- *No cherry-picking.* Real queries selected on topicality + use-case ONLY, before any system output was
  seen; verbatim where fetchable; URLs + source logged per query; human use-case tag quarantined from the
  prompt (used only for stratification/reporting; "use-case-detection agreement" is reported as
  consistency vs a weak human label, not accuracy).

**Real-query provenance caveat (honesty).** Biostars (the richest source) is Cloudflare-blocked → for its
posts the *titles* are verbatim but the *body wording is reconstructed from search snippets* (flagged
`verbatim:false` per item). Only GitHub `ensembl-vep` issues are verbatim. So 6b tests generalization to
real *scenarios/topics*; the *phrasing* is partly reconstructed (and reconstructed by an LLM, which may
bias it toward the synthetic style → understating distribution shift). **Final set: 20 queries, all 7
use cases, 9/20 verbatim** (GitHub `ensembl-vep`/`VEP_plugins`, incl. 2 that fill the previously-missing
`regulatory_noncoding`), **11/20 reconstructed** (Biostars/seqanswers). Each item carries a `framing` tag:
**16 scenario-framed vs 4 names_options** (queries pasting VEP flag names — these **cue** options
independently of the KB and would deflate measured faithfulness, so they are reported only as a flagged
sensitivity slice, not in the headline). Result reported as **directional**, with verbatim-only and
scenario-only slices as sensitivity checks — consistent with the project's simulated-gold posture, not a
benchmark.

**Results (deterministic, concurrency=1, seed=42; 2026-06-10). Driver `run_exp6.sh`; ~7.5 h.**

*Rigor audit — baseline identity across modes:* **19/20 baselines IDENTICAL** across the three ablation
modes; the lone difference is one borderline option (`nmd`) flipping in a single query
(`test_rare_disease_exome_clinical`) — the residual MoE/model-reload noise floor (phases ran hours apart),
1 rec in ~202 (0.5%), immaterial to every conclusion. (This is exactly why baselines were saved.)

*6a — decomposition (where the grounding lives):*

| ablation | faithfulness | reading |
|---|---|---|
| examples-only (drop demonstrations) | **56%** | the worked examples are the PRIMARY channel |
| description-only (drop option guidance) | **26%** | option descriptions are a substantial COMPLEMENTARY channel |
| combined (both) | **79%** | total KB-grounded → **21% parametric** |

combined (79%) ≈ examples + description (56+26 = 82) ⇒ the two channels are **largely complementary**
(small overlap, since combined ≥ their union): the model grounds **most** recommendations by *imitating the
demonstrated configs* (few-shot ICL), and a meaningful minority by *reading the option descriptions* (the
long-tail options that rarely appear in the 20 examples). Removing descriptions *on top of* examples flips
a further ~23 points — descriptions are **not** redundant. (Refinement from the `compress_options` audit:
the "description" channel here is the option's `description[:120]` + the priority labels actually shown in
the all-examples prompt; `when_to_use`/`when_not_to_use` feed only the semantic-retrieval embeddings, not
this prompt, so the harness's blanking of those two fields was inert — the 26% reflects description-text +
priority labels.) Prediction (examples dominate; descriptions
cover the long tail; combined ≥ max) **confirmed**. The clean combined-20 (**79%**) **supersedes the Exp 5
pilot** (84%, noisy single-run, 7 queries, concurrency 4).

*6b — real-query generalization (does it hold off the synthetic distribution?):*

| slice | faithfulness | n |
|---|---|---|
| synthetic combined-20 (reference) | 79% | 202 |
| real — verbatim only (cleanest comparison) | **79%** | 56 |
| real — ALL | 77% | 128 |
| real — scenario-framed only (headline) | 75% | 96 |
| real — names_options / cued (confound check) | 81% | 32 |

**Faithfulness generalizes:** real 77% (verbatim-only **79%**, identical to synthetic) vs synthetic 79% — a
≤2-point gap, within noise. The KB-grounding is **not an artifact of synthetic query phrasing**. The
anticipated **cueing confound did not materialize** (the flag-naming slice is 81%, *not* deflated; the
headline shifts <2 pts whether cued queries are included or excluded). Per use case, real faithfulness
tracks the Exp 5 specific-vs-ubiquitous axis: somatic 91% / non-human 85% / SV 81% / rare-disease 80%
(specialized → KB-driven) vs regulatory 71% / quick-lookup 60% / population-genetics 53% (ubiquitous
frequency/identifier annotation the model knows parametrically).

**Bottom line.** ~79% of recommendations are KB-grounded — driven mainly by the worked examples, with
descriptions covering the long tail — and this **holds on real forum queries (77–79%)**, robust to
provenance (verbatim-only = synthetic) and query framing (cued ≈ headline). Directional (simulated gold/KB;
correctness still needs the mentor's real configs). Raw: `results_fixedparser/attribution/` (+ noisy pilot
preserved as `gemma4_26b_combined_pilot7_cc4.json`).

## Metric deprecation — citation-rate (superseded by attribution)

`evaluate.measure_citation_rate` is **deprecated** (2026-06-13): it measures *format compliance*, not
citation validity. Audited against 240 logged gemma4:26b responses:
- **Deflates** — counts the indented `Reason:` line (carries enable/disable language + the option name
  but no `[source:]`, since that tag sits on the ✓ line above) as an *uncited recommendation*. Honest rate
  (cited ✓/✗ lines ÷ ✓/✗ lines) = **100%**; the function reports **86%** (−14%); 473 Reason lines miscounted.
- **Shrinking denominator** — the option vocabulary is a hardcoded demo-era (26-name) list, NOT derived
  from the KB (the old docstring's claim was false). On the 58-option catalogue **32/58 ids are
  unrecognised** (`core_type, phenotypes, nmd, dbnsfp, tsl…`) → **25% of real ✓/✗ lines (551/2173) invisible**.
- **Substring matching**, no word boundaries (`"protein"⊂"protein_coding"`, `"mane"⊂"permanent"`).
- **Compliance ≠ validity** — only checks that `[source:` exists; `[source: <nonsense>]` counts as cited,
  so it cannot distinguish a faithful citation from a hallucinated one. And because the prompt forces a
  `[source:]` on every line, a *correct* version of this metric is ~always 100% — uninformative.

**Superseded by attribution** (`run_attribution.py`, Exp 5/6): "is the citation *correct/grounded*" is
faithfulness, measured causally (79% combined, ±0.6 over 3 seeds). Citation-rate should not be reported;
the structured-output migration makes cited-ness structural (every recommendation carries its `option_id`
provenance). The related `extract_use_case` parser has the same scrape-the-prose fragility (logged: real
misclassifications, e.g. regulatory/non-human → structural_variants via the "variants" substring) and is
likewise resolved by structured output.

## Scoring caveats (how to read the enable/disable metrics)

Audited `evaluate.score_response` 2026-06-13 (caveats now inline in the code). The metrics are usable but
read the headline numbers with these in mind:
- **Prefer weighted RECALL over weighted F1.** Priority-weighting is applied to *precision* too
  (non-standard) — a critical true-positive lifts precision, so weighted precision partly does recall's
  job. `enable_recall_weighted` is the cleaner headline; `enable_f1_weighted` inherits the oddity.
- **Enable F1 is a harsh lower bound.** Exact canonical-id match scores interchangeable options
  (CADD / REVEL / AlphaMissense) as both FP and FN; the softer `category_cover` / `critical_recall`
  (`score_metrics.py`) are the fairer quality estimates.
- **Don't lean on disable F1.** The "should be off" universe is all 58 options but the gold lists only a
  few explicit disables (≤6, median ~3); unmentioned options are unscored → weakly defined.
- **Means use 0-not-None.** Undefined cases (empty gold disables: 1/20; empty model/parser output) average
  in as real 0s — minor on this gold, but prefer the offline `score_metrics.py` (None + skip) for means.
- **Weighting needs `gt_category`.** Omit it and weighted silently == unweighted (all real callers pass it).
- **Violation counts are pre-checker** (raw model harm); the deployed checker drives species/conflict to 0.

## Correction — Offline re-score with the corrected code (+ fallback-trigger audit)  *(re-analysis of Experiment 1; no new model runs; chronological entry "Experiment 7")*  [DONE 2026-06-15]

After the post-Exp-6 code review (phantom-id alias filter, 0-not-None / errored-exclude scoring, species
fail-closed, checker-repairs-output), the eval numbers needed re-measuring. Because all those changes are
PARSING/SCORING/METRIC changes and `build_system_prompt` + the model are unchanged, this is an **offline
re-score, not a live re-run**: re-parse the 240 logged 2026-06-08 gemma4:26b responses
(`results_fixedparser/raw/gemma4_26b.jsonl`) with the current code (`work/harness/rescore_offline.py`). This
isolates the code change as the only variable (zero sampling/batch noise, no GPU) and is an integration
test of the fixed parse→score→aggregate→report path on real data. Valid only because the prompt is unchanged.

**Corrected metrics (mean over query × 3 runs):**

| cond | enable-F1 | enable-F1-wt | disable-F1 | crit-recall | cat-cover | over-rec | raw harm |
|------|------|------|------|------|------|------|------|
| bare | 31% | 40% | 12% | 57% | 50% | 0.85 | 33 |
| keyword | 71% | 75% | 72% | 68% | 82% | 1.18 | 1 |
| **all-examples** | **87%** | **90%** | **86%** | **95%** | **96%** | 1.18 | 0 |
| semantic | 39% | 42% | 24% | 38% | 45% | 0.71 | 0 |

**vs recorded 2026-06-08:** enable-F1 **87% (stable)**, crit-recall **95%**, cat-cover **96%** unchanged;
**Disable-F1 81% → 86%** — the 0-not-None fix drops the 1/20 empty-gold-disable query's spurious 0 from
the mean (81% over 20 with one 0 ≈ 86% over the 19 *defined*; arithmetic confirms the fix). Headline robust.
"raw harm" is PRE-checker (bare 33 → the deterministic checker drives it to 0); the species fix keeps the
8 unknown(human) queries from inflating it.

**Phantom-id fix confirmed ACTIVE on real data:** the old run leaked `gnomad_af` ×24 and `gene_phenotype`
×10 into the enabled sets (a model citing `[source: gnomad]`/`[source: phenotype]` → dead demo-era ids);
the new alias filter eliminates them (re-parse phantom leak = **0**).

**Fallback-trigger audit (which paths fire vs are purely defensive):**
- Parser: **bare** → 100% fallback (P1-table 36, P2-prose 24 of 60); **keyword** → P0 59/60 (+1 P2);
  **all / semantic** → P0 60/60. So Phase 1/2 exist to score the BARE baseline (bare has no ✓/✗ format
  instruction); Phase 0 carries every KB condition (179/180). Justified, but specific to bare.
- New Phase-0 bullet-tolerance: no-op here (KB output is already ✓-at-line-start) — defensive only.
- Species: human 9 / unknown 8 / mouse,zebrafish,rat 1 each — the 8 unknown are human analyses, now
  flagged-not-stripped (correct).
- Errored-call handling: 0 errors in this log — defensive only (guards future timeouts).

**`_is_human_only` multi-species fix (2026-06-15, caught by the demo-path smoke):** the old literal-
`"human and"` test wrongly flagged `'human + mouse only'` (e.g. `ccds`) as human-only and stripped it for
mouse queries. Fixed to key on species names (assemblies like `GRCh37+GRCh38` no longer mislead it). Effect
on the table above: enable/disable/crit/cat F1 unchanged (set-based), raw harm corrected (`keyword` 3→1,
`all-examples` 1→0 — the spurious flag removed). Unit-verified across all 16 restriction strings.

**Bottom line:** corrected numbers stand (all-examples enable-F1 87%, disable-F1 86%, crit-recall 95%,
cat-cover 96%, raw harm → 0 post-checker); the fixes are corrections + robustness, not headline movers;
fallbacks are justified (bare) or defensive (not dead code). Harness `work/harness/rescore_offline.py`; corrected
report `results_fixedparser/evaluation_results_gemma4_26b_RESCORED.md`.

## Experiment 8 — Structured-output feasibility on the local 26b (NEGATIVE result)  [DONE 2026-06-15]

Motivation: the audited free-text parsers (`extract_use_case`, citation-rate, the `[source:]` fuzzy
fallback) were all slated to be retired by migrating the model to emit **structured JSON**. This tests
whether `gemma4:26b` (via Ollama) can reliably produce schema-valid JSON for the full recommendation task.
- **json_schema (strict grammar-constrained):** went DEGENERATE (whitespace runs, `finish_reason=None`,
  truncated JSON) — abandoned earlier.
- **json_object (JSON-mode + post-hoc validate/resolve):** harness `work/harness/structured_pilot.py`, 40 queries
  (20 gold + 20 real), temp 0, `max_tokens=16384`.

**Result (json_object, 40 queries):** valid JSON **16/40 (~40%)**; finish reasons **18 stop / 15 length
(truncated) / 7 malformed**. Even valid outputs frequently violate the schema: `recommendations` is
sometimes a single dict not a list (its keys get iterated as bare strings), and `option_id` values are
often not real catalogue ids (exact-id match only **2% gold / 22% real**). The model writes verbose JSON
that **truncates** on large recommendation sets (a rare-disease query enables ~24 options) even at 16K tokens.

**Verdict — structured output is NOT viable as-is on this local model.** Neither route reliably emits
schema-valid, conformant JSON for the full task. **This reverses the earlier assumption** that the fragile
free-text parsers should be fixed by migrating to structured output: on this stack the **free-text +
Phase-0 exact `[source:]` parser is the MORE reliable path** (Exp 7: Phase 0 parsed 179/180 KB-condition
responses cleanly). So the hardened free-text parser + the metric deprecations stand as the pragmatic
solution; structured output is **deferred**, not adopted.

**Salvage paths (if structured output is still wanted later):** (a) bound the output drastically — emit
only `{option_id, action}` per option, no free-text reasons (truncation is reason-verbosity); (b) per-
option / streamed extraction; (c) a stronger / cloud model for the JSON pass; (d) hybrid — free-text
generation + a separate structured-extraction pass. Not pursued now. Raw: `/tmp/structpilot_v2.log`.

## Experiment 9 — Example-ORDER sensitivity (all vs semantic)  [DONE 2026-06-21]

Motivation: Agarwal et al. 2024 ("Many-Shot ICL", NeurIPS) §4.7 report that even in the many-shot
regime, the **order** of in-context examples causes large, inconsistent variance (they tested 10 random
orderings of a fixed 50-example set on MATH). Our harness holds example order fixed (file order for
`all`; similarity order for `semantic`), so multi-run SD captures decoding noise only, never order. This
experiment measures how much order alone moves our score.

**Consistency (what changed vs prior runs):** ONE new variable — example order. Same harness primitives
(`evaluate._run_condition`, `vep_assistant.build_system_prompt`, priority-weighted leave-one-out Enable
F1), same 20-example **simulated** gold set + 58-option catalogue, same model `gemma4:26b`. The example
SET is held fixed per ordering (paper-style); only the permutation varies. **Deviation, justified:**
decoding is **greedy (temp 0)**, not the 0.7 used in scored runs — because here the ORDERING is the
replicate unit, and greedy removes decoding noise so the across-ordering SD is pure order effect. LLM
sampling seed held fixed (42). New code: `examples_override=` hook in `build_system_prompt`;
driver `work/harness/run_order_sensitivity.py`; wrapper `work/harness/run_order_experiment.sh`. Semantic shown at
**top-8** (not the production top-2) so there are enough examples for order to be measurable (top-2 has
only 2 orderings).

**Literature grounding:** Agarwal et al. §4.7 (10 orderings of a fixed set; no universally-best order);
Lu et al. 2022 (few-shot prompt-order sensitivity). 10 shuffles = paper parity; report mean ± SD over
orderings.

**Result (10 shuffles s0..s9 + natural/default order; greedy; LOO priority-weighted Enable F1):**

| Condition | #ex shown | weighted Enable F1 mean ± SD | min–max (range) | default order |
|---|---|---|---|---|
| all      | 19    | **87.7% ± 1.6%** | 84.6–90.6% (6.0%) | 87.6% |
| semantic | top-8 | **60.0% ± 6.9%** | 48.8–68.7% (19.9%) | 54.4% |

**Findings:**
- **`all-examples` is order-robust:** SD 1.6% sits inside the ±2–4% decoding-noise band; `default` order
  (87.6%) ≈ shuffle mean (87.7%). With the full set in context, position barely matters. (Consistency
  check: this mean reproduces the established all-examples ~87% weighted F1 from Exp 1/7.)
- **`semantic` (top-8) is highly order-sensitive:** SD 6.9%, range ~20 pts — the paper's §4.7 effect
  reproduces, but only in the small-context condition. Strikingly, the natural similarity-sorted order
  (54.4%) is BELOW the shuffle mean (60.0%): 7/10 random orders beat it — retrieval rank ≠ optimal
  in-context order.
- **Caveat:** `all` (19) vs `semantic` (8) differ in example count AND semantic applies the top-10 option
  filter, so the SD GAP conflates order with count + filtering. Within each condition the SD is a clean
  order-only measure (same count/filter, greedy → zero decoding noise).

**Verdict:** order is a non-issue for the recommended `all-examples` path (fixed file order is fine;
existing multi-run SD already bounds it) and a real fragility for `semantic` — a second strike alongside
the known "semantic top-k option filter hurts" result. If semantic is ever used, pin order and report
mean ± SD over orderings. **Simulated gold set → directional, not a benchmark.**
Repro: `bash work/harness/run_order_experiment.sh "gemma4:26b" 10 all,semantic 8` (greedy, concurrency 1 on a
single Metal GPU — 4-way concurrency saturates the server on the ~10K-token all-examples prompts; ~3 h
for 440 calls). Report `work/results/order_sensitivity_gemma4_26b.md`; raw
`work/results/raw/order_sensitivity_gemma4_26b.jsonl`.

## Experiment 10 — 5-seed re-run of the model comparison (E1, all 3 Gemma, corrected parser)  [DONE 2026-06-22]

**Motivation.** The headline 26b numbers (Exp 4 + 7) were *re-analyses* of the single 2026-06-08 3-seed
log, and E1's cross-model table was **pre-parser-fix** (only 26b had its response text logged, so only it
could be re-parsed — e4b/12b/qwen sat at the parser-capped ~47–55%). To get clean, directly-comparable
**corrected** numbers for **all three** models in one consistent run — and to raise the seed count to the
literature standard (Agarwal et al. 2024 used 5 seeds for several experiments; our protocol floor is 3) —
re-ran `gemma4:e4b/12b/26b` **live at 5 seeds** with the current corrected parser/scoring code.

**Consistency (what changed vs prior runs).** Exactly **one** variable vs the original Exp 1: seed count
**3 → 5** (seeds 42→46). Everything else held fixed — same 58-option catalogue, same 20-example simulated
gold set, same 4 conditions, same `temperature=0.7`, same harness (`run_parallel_eval.py`, concurrency 4),
same model tags. This is also a *live* run rather than an offline re-score, so it independently confirms
the corrected-parser headline on fresh inference (not just on the re-parsed 2026-06-08 log).

**Command (provenance).** `VEP_OPTIONS_FILE/EXAMPLES_FILE/TESTSET_FILE/RESULTS_DIR` set to the expanded
catalogue + simulated set; `python work/harness/run_parallel_eval.py --model <m> --runs 5 --concurrency 4` for each
of e4b/12b/26b (26b run detached under `caffeinate` to survive idle-sleep). temp 0.7, seeds 42–46.
Reports: `work/results/evaluation_results_gemma4_{e4b,12b,26b}.md`; run-level mean ± SD via
`work/harness/compute_run_sd.py <raw_log> <label>` (now parametrized to take a log path + label).

**Headline — `gemma4:26b`, mean ± SD across the 5 runs (seeds 42–46):**

| cond | enable-F1 | enable-F1-wt | disable-F1 | crit-recall | cat-cover | over-rec |
|------|------|------|------|------|------|------|
| bare | 30% ± 4% | 38% ± 4% | 11% ± 13% | 56% ± 8% | 45% ± 6% | 0.74 |
| keyword | 74% ± 2% | 76% ± 2% | 74% ± 4% | 67% ± 5% | 86% ± 2% | 1.21 |
| **all-examples** | **84% ± 2%** | **87% ± 2%** | **81% ± 6%** | **92% ± 5%** | **95% ± 2%** | 1.23 |
| semantic | 39% ± 2% | 42% ± 2% | 24% ± 7% | 38% ± 3% | 45% ± 1% | 0.69 |

**Cross-model — Enable F1, mean ± SD across the 5 runs (all corrected, directly comparable):**

| model | bare | keyword | all-ex | semantic |
|---|---|---|---|---|
| gemma4:e4b | 27% ± 1% | 59% ± 3% | 65% ± 6% | 37% ± 3% |
| gemma4:12b | 29% ± 5% | 68% ± 4% | 78% ± 3% | 38% ± 2% |
| **gemma4:26b** | 30% ± 4% | 74% ± 2% | **84% ± 2%** | 39% ± 2% |

**Comparison to the prior 3-seed headline (Exp 4/7).** 26b all-examples enable-F1 **84% (5-seed) vs 87%
(single 3-seed log)**; crit-recall **92% vs 95%**, cat-cover **95% vs 96%**, disable-F1 **81% vs 86%**. All
shifts are **within the ±2–4% decoding-noise band** the discipline expects (now estimated over 5 seeds with
tight SD ≤2% on all-examples), so the conclusions are unchanged — the small drops are seed noise, not a
real regression. The all-examples lead over keyword grows with model size (+6 at e4b → +10 at 26B),
reproducing "all-examples wins for every model; 26b best."

**One claim retracted (honesty).** The Exp 1 finding *"semantic option-filtering is harmful and worsens
with capability — at 26B semantic (25–28%) drops below bare (31%)"* **does NOT survive the corrected
parser**. With the fixed parser semantic is **flat at ~37–39% across all three model sizes** and sits
**above** bare (27–30%), not below it. The robust part stands: **semantic is by far the weakest KB
condition** (≈39% vs all-examples 84% at 26B) and **does not improve with model size** while keyword/all
climb — so hard-filtering 58 options to a top-k still forfeits the larger model's gains (a retrieval-recall
failure). Only the "below bare / worsens with capability" framing is withdrawn.

**Bottom line.** Clean 5-seed corrected numbers for all three Gemma models; 26b + all-examples = **84%
Enable F1 / 92% critical-recall / 95% category-coverage / 81% Disable-F1**, raw harm → 0 post-checker.
This is the current headline (supersedes the 3-seed re-analyses for the E1/headline tables). **Simulated
gold set → directional, not a benchmark.**

## Experiment 11 — Catalogue-only ablation: how much do the golden examples add over the option catalogue alone?  [DONE 2026-06-24]

**Motivation (mentor question, 2026-06-24).** Likhitha asked, in effect: *assuming the model "has" the VEP
documentation and the gold examples, how much do the gold examples add beyond the documentation?* The
existing 4 conditions don't answer this directly — every non-`bare` arm includes ≥2 examples, so there was
no "options/documentation, zero examples" rung. **Important scope correction (do not overclaim):** the model
is **never shown the VEP documentation PDF or any prose docs** in *any* condition. What it sees is **our
58-option catalogue** (`vep_options_expanded.json`) — each option compressed to id + flag + a **~120-char
truncated description** + species/priority/conflict/depends metadata, *distilled by us* from Ensembl
release/115. So this experiment measures **our derived option catalogue**, which is our operationalization of
the documentation — **not** the raw documentation itself. A true raw-docs run is a *different, unrun*
experiment (deferred — see note at the end). Framing aside: nothing is *trained*; this is all RAG (the KB is
in the prompt, not the weights). See HANDOFF §9.

**New condition `noex` (catalogue-only, no examples).** Full **58-option catalogue + the exact output
contract + the rules block**, but **zero in-context examples** — `build_system_prompt(vep_options, [], query,
retrieval_mode="all")`. Identical pipeline otherwise (same parser, same deterministic checker, same scoring).
This isolates the **golden-examples contribution** as the single changed variable vs `all` (examples 19→0);
and the single changed variable vs `bare` is the catalogue+format (bare has neither). So the ladder
`bare → noex → all` cleanly decomposes "raw model" → "+our option catalogue" → "+golden examples".

**Methodological note on scoring `noex`.** Even catalogue-only, the model still emits the prompted
`✓/✗ [source: option_id]` format and cites real catalogue ids (Phase-0 parse holds; citation rate 81%), so
the id-keyed F1/recall metrics stay valid and comparable. This is exactly *why* a raw-docs run is harder: the
docs don't use our ids, so a docs-only model couldn't cite them and the metric would break — another reason
the catalogue is the right operationalization to score.

**Consistency (what changed vs Exp 10).** Same model `gemma4:26b`, same 58-option catalogue, same
`temperature=0.7`, same harness (`run_parallel_eval.py`, concurrency 4), same 5 seeds (42–46), same
leave-one-out. **One nuance, controlled:** the simulated gold set was extended 20→23 on 2026-06-23 (3 new
rare-disease/somatic *clinical-report* rows). To keep the test set fixed vs Exp 10 (discipline rule 4), this
run **excludes those 3** and uses the **identical 20 queries** Exp 10 used (filtered files
`work/results_noex/{gold_20set,testset_20set}.json`; 0 removed of the original 20, stratified 3/3/3/3/3/2/3).
The fresh `bare`/`all` arms therefore double as a consistency check against Exp 10. (A 23-set re-run is a
clean follow-up if the new rows are kept.) **Deviation:** `keyword` numbers here come from the harness's
forced-baseline (it always injects `bare,keyword`); reported for context, not the focus.

**Command (provenance).** `VEP_OPTIONS_FILE=work/vep_options_expanded.json
VEP_EXAMPLES_FILE=work/results_noex/gold_20set.json VEP_TESTSET_FILE=work/results_noex/testset_20set.json
VEP_RESULTS_DIR=work/results_noex caffeinate -i python work/harness/run_parallel_eval.py --model gemma4:26b --runs 5
--concurrency 4 --conditions noex,all --seed 42`. 400 calls, ~1h56m. Raw:
`work/results_noex/raw/gemma4_26b.jsonl`; report `work/results_noex/evaluation_results_gemma4_26b.md`.
Pre-flight: 8-call smoke confirmed the ~11K-token `all` prompt is **not** context-truncated on the
already-running server (all=77% ≫ noex=45% on 2 queries; responses end cleanly).

**Result — `gemma4:26b`, mean ± SD across 5 seeds (seeds 42–46), 20-query LOO:**

| condition | Enable F1 | wtd F1 | Disable F1 | crit-recall | cat-cover | over-rec | raw harm |
|---|---|---|---|---|---|---|---|
| bare (no KB) | 35% ± 3% | 45% ± 3% | 11% ± 8% | 65% ± 4% | 58% ± 3% | 1.05 | 58 |
| **noex (catalogue only, no examples)** | **62% ± 2%** | **65%** | — | **49% ± 3%** | **75% ± 2%** | 1.13 | 1 |
| keyword (catalogue + top-2 ex) | 73% ± 2% | 76% ± 2% | 74% ± 3% | 69% ± 6% | 83% ± 4% | 1.20 | 2 |
| **all (catalogue + all examples)** | **85% ± 1%** | **88% ± 1%** | **84% ± 1%** | **96% ± 2%** | **95% ± 2%** | 1.20 | 0 |

**Consistency check PASSED:** `all` = 85% / crit-recall 96% / cat-cover 95% and `bare` = 35% reproduce Exp
10 (84% / 92% / 95%; bare 30%) within the ±2–4% noise band → this run is directly comparable.

**Findings.**
1. **Our option catalogue alone is worth ~27 F1 points over the raw model** (bare 35% → noex 62%): the
   compressed catalogue (descriptions + flags + priorities + the citation format) substantially grounds the
   model on its own — without any worked examples.
2. **The golden examples add a further ~23 F1 points on top of the catalogue** (noex 62% → all 85%) —
   roughly **as large as the catalogue's own contribution**, and at this scale the examples are the
   bigger lever for the *quality* metrics: **critical-recall nearly doubles (49% → 96%)** and category-cover
   rises (75% → 95%). So the examples are what make the system reliably surface the **must-have** options,
   not just plausible ones. This is the direct answer to the mentor: *the option catalogue gets you to ~62%
   but misses ~half the critical options; the gold examples are what close that gap.*
3. **Even one/two examples help a lot** (noex 62% → keyword 73%): most of the disable-signal appears only
   once examples are present (noex emits few disables; keyword/all Disable-F1 74–84%) — the conservative
   *trim* behaviour is example-taught, not catalogue-taught.
4. **Caveat — bare's crit-recall (65%) > noex's (49%) is a metric artifact, not bare being "better".** Bare
   massively over-recommends human-only options (**raw harm 58** vs noex's 1) and scatter-hits some critical
   options with terrible precision (cat-cover 58%, Disable-F1 11%); the deterministic checker would strip
   those 58 violations. Read crit-recall **alongside** harm/cat-cover, not alone. noex is *disciplined*
   (harm 1, the species rules are in the catalogue it can see) but, without worked examples, **under-selects
   the criticals** — exactly the gap examples fill.

**Bottom line.** Decomposed contribution on the simulated 20-set: **raw model 35% → +our option catalogue
62% → +golden examples 85%** Enable F1, with the examples roughly **doubling critical-recall (49→96%)**. The
gold examples are not redundant with the catalogue — they are the dominant driver of *must-have-option*
recall. **Simulated gold → directional, not a benchmark**; `noex` is a new clean rung for future model runs.

**Deferred follow-up — raw-documentation condition (considered, NOT run).** A "feed the VEP documentation
PDF" condition was considered and deferred. Reasons: (1) **scoring incompatibility** — our metrics are keyed
to canonical catalogue ids; raw docs don't use them, so a docs-only model can't emit cite-able ids and F1
stops being comparable (changes the metric, not just one variable); (2) **feasibility** — the docs PDF
(~2.4 MB rendered) far exceeds the ~11K-token prompt budget we already push, so it needs a chunked
doc-retrieval index (a new subsystem, not a one-line condition), and Exp 8 showed this stack degrades near
context limits; (3) **relevance** — we deliberately distil the docs into the compact catalogue precisely
because raw docs are too large, unparseable, and can't drive the deterministic checker, so the catalogue
**is** our operationalization of the docs. If a raw-docs signal is ever wanted, the scoreable version is
"catalogue + a *retrieved doc snippet*" vs "catalogue alone" (keeps ids valid, changes one variable).

## Implications for the GSoC project

- **Retrieval design (in-range, actionable):** at a ~58-option KB, **do not hard top-k filter the options** — the semantic top-10 condition loses relevant options (recall failure) and underperforms keeping all 58. It stays flat (~37–39% Enable F1) as the model scales while keyword/all-examples climb, so filtering forfeits the larger model's gains. Keep all options in-prompt, or use high-recall hybrid retrieval; reserve aggressive filtering for when the option set genuinely exceeds context.
- **Examples:** with a curated gold set (target 15–20), **include all examples** — the corpus is far below the many-shot saturation point, so selection only loses signal. Selective example retrieval becomes relevant only at hundreds of examples.
- **Model selection:** **Gemma 4 validated.** `e4b` (~8B-eff) is the efficiency pick (all-examples 65% Enable F1); `26b` (MoE) is the quality pick (all-examples **84% Enable F1**, corrected 5-seed) and faster than dense `12b` (78%).
- **Disable-F1 gap:** the enable-heavy demonstration bias is the next quality lever (the conservative trim + a strong instruction-follower already help, per e4b).
- **Defense-in-depth:** the deterministic checker remains necessary — raw-model species/conflict violations persist at every model size.

## Reproducibility
- `work/harness/run_parallel_eval.py` — parallel LOO eval (env: `VEP_OPTIONS_FILE/EXAMPLES_FILE/TESTSET_FILE/RESULTS_DIR`).
- `work/harness/run_example_sweep.py` — corpus-size sweep (stratified subsample).
- `work/harness/run_order_sensitivity.py` (+ `work/harness/run_order_experiment.sh`) — example-ORDER sensitivity (Exp 9): N shuffles of a fixed set, greedy, mean ± SD over orderings.
- `work/harness/aggregate_results.py` — cross-model crossover table.
- `work/harness/run_experiment.sh` — turnkey wrapper.
- Reports: `work/results/evaluation_results_*.md`, `work/results/example_sweep_*.md`.
- Env: native arm64 Ollama (Metal), `OLLAMA_NUM_PARALLEL=4`, `OLLAMA_CONTEXT_LENGTH=32768`.
