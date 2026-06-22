# Ask VEPai

**A locally-hosted RAG assistant that turns a plain-English variant-analysis scenario into a recommended
[Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) web-form configuration — with
justifications, source citations, and a deterministic safety net.**

*Google Summer of Code 2026 · EMBL-EBI (Ensembl)*

---

## What it does

Configuring the Variant Effect Predictor (VEP) means choosing from dozens of options (predictors,
frequency datasets, identifiers, filters…), and the right choice depends on your scenario — rare-disease
germline, somatic cancer, non-coding/regulatory, population genetics, structural variants, non-human, or a
quick lookup. Ask VEPai takes a natural-language description of your analysis and recommends **which VEP
options to enable/disable**, **why**, and **where each recommendation came from**.

You ask:

> *"Germline exome variants from a rare-disease trio, human GRCh38."*

It answers with a per-option configuration (enable HGVS, MANE, ClinVar, gnomAD exome AF, pathogenicity
predictors…; disable what doesn't apply), each line carrying a `[source: option_id]` citation, plus the
detected use case and a decision trace.

## Design: "defense-in-depth" (RAG proposes, a checker disposes)

The core idea is that a local LLM is powerful but not trustworthy on its own, so a deterministic layer
guards its output:

```
 user scenario
      │
      ▼
 [1] Retrieval ........ pull relevant option docs + worked examples from the knowledge base
      │                 (keyword word-overlap, or --semantic BGE embeddings)
      ▼
 [2] Prompt assembly .. compress the option KB + examples + a strict output contract
      │
      ▼
 [3] Local LLM ........ propose a config as `✓/✗ option [source: id]` lines  (via Ollama)
      │
      ▼
 [4] Parsing .......... extract the enable/disable decisions + citations
      │
      ▼
 [5] Constraint checker  DISPOSES of what the LLM gets structurally wrong, deterministically:
      │                  • block human-only options for a non-human species
      │                  • resolve conflicts by per-use-case priority
      │                  • auto-enable missing dependencies
      ▼
 recommended VEP web-form configuration  (+ decision trace, + provenance)
```

The LLM **proposes**; the Python checker **disposes**. Across every model size we tested, the raw model
emits species/conflict violations — and the checker removes them all (post-checker harm = 0).

## Quickstart

**Requirements:** Python 3.10+, [Ollama](https://ollama.com/) running locally, and a pulled model.

```bash
# 1. Install Python deps (openai client + sentence-transformers for semantic mode)
pip install -r requirements.txt

# 2. Start Ollama and pull a model
ollama serve
ollama pull qwen2.5:3b          # small/fast for a first run; gemma4:26b is the quality pick

# 3. Run the demo assistant (from the demo folder)
cd vep_ai_demo
python vep_assistant.py "germline exome variants, rare disease, human GRCh38"
python vep_assistant.py --explain --semantic "mouse CRISPR variants in GRCm39"   # + decision trace
python vep_assistant.py explain-result "why is my variant splice_donor_variant?" # output explainer
```

See [`vep_ai_demo/README.md`](vep_ai_demo/README.md) for all modes and flags.

## Repository layout

```
askVEPai/
├── vep_ai_demo/      Runnable prototype: vep_assistant.py (recommend / explain / explain-result),
│                     evaluate.py (offline benchmark), and the data JSONs it loads.
│                     Demo knowledge base = 26 options / 8 examples.
└── work/             GSoC deliverables built on top of the demo:
    ├── vep_options_expanded.json     58-option VEP catalogue (source-grounded from Ensembl)
    ├── preliminary_examples/         20-example simulated gold set + test queries + validator
    ├── output_schema/                structured JSON output design (schema + mapping rules)
    ├── EXPERIMENTS.md                full experiment report (rationale · method · results · caveats)
    ├── run_*.py / run_*.sh           the evaluation harness + experiment drivers
    └── results*/                     saved evaluation + attribution reports
```

The demo and the expanded system share the same code; the expanded **58-option / 20-example** system is
selected at runtime via environment variables (`VEP_OPTIONS_FILE`, `VEP_EXAMPLES_FILE`,
`VEP_TESTSET_FILE`, `VEP_RESULTS_DIR`). The wrapper `work/run_experiment.sh` sets them for you.

## Evaluation

The system is evaluated offline with **leave-one-out** (LOO) over the example set — the scored example is
removed from the retrieval corpus, so the model is never shown the answer it's graded against. Four
retrieval conditions are compared:

| Condition | Options in prompt | Examples in prompt |
|---|---|---|
| **bare** | none (no KB) | none |
| **keyword** | all 58 | top-2 by word overlap |
| **all-examples** | all 58 | all (≤19 under LOO) |
| **semantic** | top-10 by embedding | top-2 by embedding |

**What Enable F1 / Disable F1 mean.** The model's answer is two sets of options: the ones it says to
**enable** and the ones it says to **disable**. Each is scored against the gold answer with
precision/recall/F1:

- **Enable F1** — of the options the model enabled, how many were correct (precision), and of the gold's
  enabled options, how many it found (recall); F1 is their harmonic mean. *Priority-weighted* Enable F1
  weights critical options more than optional ones.
- **Disable F1** — the same, for the options the model explicitly turned **off**.

So Enable F1 measures "did it pick the right options to turn on", Disable F1 "did it correctly turn the
wrong ones off". **critical-recall** (fraction of must-have options recommended) and **category-coverage**
(fraction of needed annotation *types* covered — credits an interchangeable predictor like CADD/REVEL) are
softer, clinically-oriented views; **over-recommendation** = |enabled| / |gold|; **raw harm** = human-only
options proposed for a non-human query, *before* the checker. Full definitions, protocol, and caveats:
[`work/EXPERIMENTS.md`](work/EXPERIMENTS.md).

**Reported as mean ± SD across runs** wherever multiple runs exist — the SD is the run-to-run (decoding)
noise. E1 and the headline table use **5 seeds (42–46)**; the other experiments state their own run counts.
(In the order experiment below the SD is across example *orderings* instead, because that is the variable
under study.)

### The experiments

There are **five experiments** — each one a new set of model inference runs:

| ID | Experiment | What it asks | Result |
|---|---|---|---|
| **E1** | Model comparison | Which local model, and which way of giving it the knowledge base (nothing / keyword-retrieved / all examples / embedding-retrieved), produces the best recommendations? | all-examples wins for **every** model; `gemma4:26b` is best |
| **E2** | Corpus-size sweep | As we add more examples to the knowledge base, does "put all examples in the prompt" ever lose its edge over "retrieve a relevant few"? | No — no crossover up to 19 examples (as the ICL literature predicts) |
| **E3** | KB attribution | Do the recommendations actually come from the curated knowledge base, or from the model's frozen training memory? | ~79% come from the KB; holds on real forum queries too |
| **E4** | Structured-output feasibility | Could we drop the text parser by having the model emit machine-readable JSON directly? | **No** — the local model can't reliably produce valid JSON; keep the parser |
| **E5** | Example-order sensitivity | Does simply *reordering* the in-prompt examples change the score? | all-examples is robust to order; semantic retrieval is fragile |

### Headline results — `gemma4:26b` (corrected parser), mean ± SD across 5 runs

Leave-one-out over the 20 simulated gold queries; seeds 42–46; SD is across the 5 runs. **Raw harm → 0
for all conditions after the deterministic checker.**

| Condition | Enable F1 | Enable F1 (wt) | Disable F1 | Critical-recall | Category-cover | Over-rec |
|---|---|---|---|---|---|---|
| bare | 30% ± 4% | 38% ± 4% | 11% ± 13% | 56% ± 8% | 45% ± 6% | 0.74 ± 0.16 |
| keyword | 74% ± 2% | 76% ± 2% | 74% ± 4% | 67% ± 5% | 86% ± 2% | 1.21 ± 0.05 |
| **all-examples** | **84% ± 2%** | **87% ± 2%** | **81% ± 6%** | **92% ± 5%** | **95% ± 2%** | 1.23 ± 0.08 |
| semantic | 39% ± 2% | 42% ± 2% | 24% ± 7% | 38% ± 3% | 45% ± 1% | 0.69 ± 0.03 |

> **all-examples (84%) ≫ keyword (74%) ≫ semantic (39%)**, with tight run-to-run SD (≤2% for all-examples).
> Hard-filtering options (semantic) is the worst KB condition — barely above no-KB (bare 30%) and far below
> keyword/all — a retrieval-recall failure. The model is disciplined (1.23× over-recommendation) and disables
> well (81%) once parsed correctly. *(Computed by re-scoring all 400 logged responses — 20 queries × 4
> conditions × 5 runs — with the corrected parser; `work/compute_run_sd.py`.)*

### E1 · Model comparison — Enable F1, mean ± SD across 5 runs

Corrected parser, 5 seeds (42–46), all four conditions, leave-one-out over the 20 simulated gold queries.
(All three models were re-scored from their saved 5-seed logs, so these are directly comparable to the
Headline table above; `qwen2.5:3b/7b` were also tested and showed the same pattern.)

| Model | bare | keyword | all-ex | semantic |
|---|---|---|---|---|
| gemma4:e4b | 27% ± 1% | 59% ± 3% | 65% ± 6% | 37% ± 3% |
| gemma4:12b | 29% ± 5% | 68% ± 4% | 78% ± 3% | 38% ± 2% |
| **gemma4:26b** | 30% ± 4% | 74% ± 2% | **84% ± 2%** | 39% ± 2% |

Across every model, **all-examples ≥ keyword ≫ semantic**, and the all-examples lead grows with model size
(+6 over keyword at e4b → +10 at 26B). **semantic stays flat (~37–39%) regardless of model size** while
keyword/all-examples climb — so hard-filtering the option list to a top-k forfeits the capability gains and
leaves semantic barely above no-KB. (Mixes family/architecture, so it supports "all-examples wins for every
model", not a clean size *trend*.)

### E2 · Corpus-size sweep — does adding more examples ever stop helping?

A standard in-context-learning result is that, beyond some number of examples, putting *all* of them in the
prompt stops helping — and selectively retrieving a relevant few can start to win. **This experiment asks
whether that turning point is anywhere near our scale.** Using `gemma4:e4b`, it grows the example corpus
through N = 2, 5, 10, 15, 19 (stratified across the 7 use cases, leave-one-out) and tracks the gap between
*all-examples* and *keyword* (top-2). If selective retrieval were going to win, the **all − keyword** gap
would turn negative as N grows.

*(These absolute numbers predate the parser fix; the meaningful quantity here is the **all − keyword**
delta, not the level — and the bug affected all conditions, so the delta is the robust read.)*

| N (corpus) | bare | keyword | all-ex | semantic | all − kw |
|---|---|---|---|---|---|
| 2 | 27% | 43% | 43% | 28% | −0% |
| 5 | 27% | 43% | 45% | 32% | +2% |
| 10 | 27% | 47% | 46% | 30% | −1% |
| 15 | 27% | 47% | 44% | 30% | −2% |
| 19 | 27% | 46% | 48% | 31% | +2% |

**No corpus-size crossover** — matching the many-shot-ICL prediction that example selection only matters at
~50–70 examples/class, far above a curated gold set.

### E3 · Knowledge-base attribution — are the recommendations actually coming from the KB?

The whole reason to use RAG instead of fine-tuning is that recommendations should come from the **curated
knowledge base** — so they stay current as VEP changes and can be traced to a source — rather than from the
model's frozen training memory. This experiment tests that premise **causally**: for each option the model
recommended, we **delete that option's evidence from the knowledge base** (its description/guidance, and its
appearances in the worked examples) and re-ask. If the recommendation **disappears**, it was KB-driven
("faithful"); if it **persists**, the model produced it from memory ("parametric"). Run on `gemma4:26b`,
all-examples, greedy with a fixed seed, so the deleted evidence is the only thing that changes.

*Decomposition — where the grounding lives:*

| Ablation | Faithful | Reading |
|---|---|---|
| examples-only (drop demonstrations) | **56%** | worked examples are the primary channel |
| description-only (drop option guidance) | **26%** | descriptions are a substantial complementary channel |
| combined (both) | **79%** | total KB-grounded → 21% parametric |

*Generalization — does it hold off the synthetic distribution?*

| Query set | Faithful | n |
|---|---|---|
| synthetic combined-20 (reference) | 79% | 202 |
| real forum — verbatim only | **79%** | 56 |
| real forum — all | 77% | 128 |

**~79% of recommendations are KB-grounded, and this holds on real forum queries** (verbatim-only identical
to synthetic) — supporting RAG over fine-tuning for an evolving tool. *(Deterministic greedy runs;
combined faithfulness was stable to ±0.6% over 3 seeds.)*

### E4 · Structured-output feasibility — can we drop the text parser? (negative result)

Today the model writes free text (`✓/✗ option [source: id]`) that a parser reads. A tempting simplification
is to have the model emit **machine-readable JSON** directly, conforming to a fixed schema, so no parsing is
needed. This experiment tests whether `gemma4:26b` can reliably do that for the full task (40 queries, two
JSON modes). **Answer: no.** Grammar-constrained JSON went degenerate; JSON-mode produced only **~40% valid
JSON over 40 queries** (frequent truncation on long recommendation lists, poor schema conformance). **This
reversed the "structured output fixes the parser" plan** — on this local stack the hardened free-text +
exact `[source:]` parser is the more reliable path. Deferred, with salvage paths noted in the ledger.

### E5 · Example-order sensitivity — does reordering the examples change the answer?

Prior work (Agarwal et al. 2024, §4.7) shows an LLM's answer can shift purely from the **order** examples
appear in the prompt. Our normal harness always uses one fixed order, so it would never reveal this. This
experiment holds the *set* of examples fixed and **shuffles their order 10 times** (plus the natural order),
re-scoring each time, to measure how much the result swings from order alone. Greedy decoding with a fixed
model seed, so order is the only variable. Reported as priority-weighted Enable F1, mean ± SD **across the
orderings**.

| Condition | Examples shown | mean ± SD | min–max (range) | natural order |
|---|---|---|---|---|
| **all-examples** | 19 | **87.7% ± 1.6%** | 84.6–90.6% (6.0%) | 87.6% |
| **semantic** | top-8 | **60.0% ± 6.9%** | 48.8–68.7% (19.9%) | 54.4% |

**all-examples is order-robust** (SD within decoding noise); **semantic is order-fragile** (~20-point range)
— and its similarity-sorted order (54.4%) is *below* the shuffle mean, so retrieval rank ≠ optimal order.

### Key findings

- **Best config:** `gemma4:26b` + all-examples — **84% Enable F1, 92% critical-recall, 95% category-coverage,
  81% Disable-F1**; raw harm → 0 after the checker.
- **Include all examples; don't hard-filter options.** Selective example retrieval doesn't help at this
  scale, and semantic option-filtering is the weakest KB condition — flat at ~37–39% across model sizes
  while keyword/all-examples improve, so it forfeits the larger model's gains.
- **The RAG is doing its job:** ~79% of recommendations are KB-grounded and this holds on real queries.
- **The deterministic checker is necessary:** raw-model species/conflict violations persist at every model
  size and are only removed by the checker.
- **Reproducibility discipline matters:** a parser bug capped early scores by ~30 points, and temperature=0
  is non-deterministic under concurrency — both caught only because results are logged and multi-run.

## Status & honesty

This is a **work in progress**, and the numbers above are **directional, not a benchmark**:

- The 20-example gold set is **simulated** (synthetic, constraint-checker-validated) — a stand-in until a
  mentor-provided real gold set is available.
- The 7 use-case categories (and the per-use-case option priorities) are a **project-internal construct**
  with no canonical Ensembl/field backing yet — pending validation.
- Factual fields (`cli_flag`, web-form section, species restriction, native-vs-plugin) are
  **source-grounded** from the Ensembl `public-plugins` web configuration, not model memory.

## Acknowledgements

Built for **Google Summer of Code 2026** with **EMBL-EBI / Ensembl**. Uses [Ollama](https://ollama.com/)
for local inference and `BAAI/bge-small-en-v1.5` for semantic retrieval. VEP is developed by Ensembl.
