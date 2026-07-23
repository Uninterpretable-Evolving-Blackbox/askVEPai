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
ollama pull gemma4:26b          # the model this system is built and benchmarked on

# 3. Point it at the full 58-option catalogue and its example corpus
cd vep_ai_demo
export VEP_OPTIONS_FILE=$PWD/../work/vep_options_expanded.json
export VEP_EXAMPLES_FILE=$PWD/../work/preliminary_examples/simulated_gold_examples.json

# 4. Ask it something
python vep_assistant.py "germline exome variants, rare disease, human GRCh38"
python vep_assistant.py --minimal "germline exome variants, rare disease, human GRCh38"  # essentials only
python vep_assistant.py --full    "germline exome variants, rare disease, human GRCh38"  # + every add-on
python vep_assistant.py --explain --semantic "mouse CRISPR variants in GRCm39"   # + decision trace
python vep_assistant.py explain-result "why is my variant splice_donor_variant?" # output explainer
```

The two exports matter. A catalogue and a priority table are generated together, and the folder the
demo sits in still holds the original 26-option knowledge base from before the catalogue was rebuilt.
Run against that one and the importance tiers switch themselves off — five of its options, including
the transcript-database choice, do not exist in the current priority table, so the tiers would be
quietly wrong rather than obviously absent. The tool says so when it happens.

Classifying a question into factor values is a second, much smaller model call, and by default it
reuses the model above so that one download is enough. `VEP_FACTOR_MODEL=gemma4:e4b` makes it
noticeably faster if you have a small model pulled as well.

See [`vep_ai_demo/README.md`](vep_ai_demo/README.md) for all modes and flags.

> **Use a capable model.** The whole pipeline rests on the model emitting one strict line format —
> `✓ option [source: option_id] confidence: …` — which a deterministic parser then reads. Small models
> cannot hold that contract: they emit no `[source:]` citations at all, which drops the parser into a prose
> fallback built for the no-knowledge-base experiment, and that fallback guesses from wording (it will read
> "✗ polyphen: ON" as *enable*). `gemma4:26b` scores 84% enable-F1 and cites correctly essentially always;
> `qwen2.5:3b` scores 31% and routinely breaks the format. If the model cites an option that does not
> exist, or ignores the format entirely, the tool now says so rather than quietly guessing — but the fix
> for a small model is a bigger model.

### Or: describe the analysis as factor values (no model needed)

The assistant's real job is turning prose into a set of **factor values** ([below](#the-factor-scheme)); the
configuration itself is then resolved by deterministic code. So you can skip the language model entirely and
supply the factors directly — useful for seeing exactly what the system recommends for a given scenario, and
for reviewing the per-option priorities themselves. It needs no Ollama, no GPU, and gives the same answer
every time.

```bash
cd work/generation
export VEP_OPTIONS_FILE=$PWD/../vep_options_expanded.json

python recommend_by_factors.py --list-factors        # every legal factor value

# a human rare-disease coding question
python recommend_by_factors.py --species human --origin germline --size small \
    --region coding --goal clinical-interpretation

# region_focus and analysis_goal are multi-select — repeat the flag
python recommend_by_factors.py --species non-human --origin somatic --size structural-CNV \
    --region coding --region regulatory-noncoding \
    --goal clinical-interpretation --goal population-frequency

# --explain shows WHICH factor value drove each option to its priority
python recommend_by_factors.py --species human --origin germline --size small \
    --region regulatory-noncoding --goal clinical-interpretation --explain
```

The output separates **core** (what to switch on, split into `critical` / `recommended`) from **add-ons**
(`optional` — defensible extras, not on by default), lists what the factors **gated out** and why, and flags
anything a human still needs to settle:

```
CORE — switch these on (14)
  [critical   ] clinvar                --check_existing (derived)
  [critical   ] core_type              --refseq | --merged | --gencode_basic ...
  [critical   ] hgvs                   --hgvs
  [critical   ] regulatory             --regulatory
  [recommended] cadd                   --plugin CADD
  ...
ADD-ONS — defensible extras, not on by default (9)
  [optional   ] enformer               --plugin Enformer
  ...
GATED OUT by the factors (12) — not applicable to this scenario
  alphamissense, clinpred, dbnsfp, eve, mane, mutfunc, nmd, paralogues, polyphen, protein, revel, sift
```

## Repository layout

```
askVEPai/
├── vep_ai_demo/      Runnable prototype: vep_assistant.py (recommend / explain / explain-result),
│                     evaluate.py (offline benchmark), and the data JSONs it loads.
│                     Demo knowledge base = 26 options / 8 examples.
└── work/             GSoC deliverables built on top of the demo:
    ├── vep_options_expanded.json     58-option VEP catalogue (source-grounded from Ensembl)
    ├── research/                     taxonomy_proposal.md (the factor scheme) +
    │                                 generation_pipeline_proposal.md (the example-generation design)
    ├── generation/                   the deterministic factor recommender:
    │                                 recommend_by_factors.py (factor values -> config, no model),
    │                                 seed_priorities.py -> generation_config/priority_by_factor.json
    │                                 (the per-option priority table the recommender reads)
    ├── preliminary_examples/         20-example simulated gold set + test queries + validator
    ├── output_schema/                structured JSON output design (schema + mapping rules)
    ├── EXPERIMENTS.md                full experiment report (rationale · method · results · caveats)
    ├── harness/                      the evaluation harness + experiment drivers
    └── results*/                     saved evaluation + attribution reports
```

The demo and the expanded system share the same code; the expanded **58-option** system is selected at
runtime via environment variables (`VEP_OPTIONS_FILE`, `VEP_EXAMPLES_FILE`, `VEP_TESTSET_FILE`,
`VEP_RESULTS_DIR`). The wrapper `work/harness/run_experiment.sh` sets them for you.

## The factor scheme

A scenario is not one category — it is a set of values across **five orthogonal factors**. Two are facts
about the data (the variant set decides them, not the user); three are intent (what the user wants out of
the annotation). Each factor earns its place only if its values actually gate or shift a concrete cluster of
options in the web form.

| Factor | Values | Kind | Role |
|---|---|---|---|
| **species** | human / non-human | data fact | **hard gate** + priority — gates the entire human-only block (SIFT/PolyPhen, CADD/REVEL/AlphaMissense, gnomAD, ClinVar, MANE…) |
| **origin** | germline / somatic | data fact | priority, plus one hard rule (`somatic ⇒ no common-variant frequency filter`) |
| **variant_size_class** | small (SNV/indel) / structural-CNV | data fact | **hard gate** + priority — SVs drop the missense/splice predictors and swap gnomAD → gnomAD-SV |
| **region_focus** *(multi-select)* | coding / regulatory-noncoding | intent (*where*) | **hard gate** + priority — coding drives HGVS/protein/exon numbers/domains; regulatory drives the regulatory build, cell types, UTRAnnotator, Enformer |
| **analysis_goal** *(multi-select)* | basic-consequence / clinical-interpretation / population-frequency | intent (*why*) | priority — identifiers only vs ClinVar + predictors + phenotypes vs 1000G/gnomAD frequencies |

Splitting *where* from *why* is deliberate: a single axis mixing them mislabels the common case. The
pathogenicity predictors are driven by `analysis_goal` (why you are annotating), while `region_focus`
decides whether they apply at all — so a coding+regulatory variant set keeps them and a purely regulatory
one does not. The full rationale is in
[`work/research/taxonomy_proposal.md`](work/research/taxonomy_proposal.md).

### Per-option priorities: critical / recommended / optional

Every option carries a priority **per factor value**, not one global label — `priority_by_factor.json`, keyed
`option → factor → value → priority`. Priorities compose by taking the **strongest** label across all active
factor values, while a hard gate can remove an option outright. That per-value keying is what lets one table
say that ClinVar is **critical** for clinical interpretation, merely **optional** in a population scan, and
**absent** from a basic consequence lookup — a single label per option cannot express that.

| Tier | Meaning | In the output |
|---|---|---|
| `critical` | omitting it makes the analysis unanswerable | **core**, on |
| `recommended` | standard practice for this scenario | **core**, on |
| `optional` | defensible and useful, but redundant or niche | **add-on**, offered, not on by default |
| `not_applicable` | a hard gate removes it | gated out, with the reason shown |

> **What is grounded, and what is judgement.** The *factual* fields — CLI flag, web-form section, species
> restriction, native-vs-plugin, conflicts, dependencies, defaults — are source-grounded from the Ensembl
> `public-plugins` web configuration (release/115). The *priorities* are not: **VEP does not rank its own
> options.** The plugin configuration is a flat availability map and the documentation lists "missense
> pathogenicity" as one undifferentiated family. So the core-vs-add-on split — notably treating REVEL,
> ClinPred and dbNSFP as add-ons because they *consume* other predictors' scores, while SIFT, PolyPhen, CADD,
> AlphaMissense and EVE each derive an independent call — is **our editorial judgement**, grounded in ACMG
> PP3/BP4 as refined by ClinGen SVI (Pejaver et al. 2022), which treats correlated in-silico predictors as a
> single line of evidence. That standard is external to VEP, and this table is exactly what the priorities
> need sign-off on. It is **provisional** until then.

### Generating examples on the factor scheme

Real, expert-validated gold examples are the blocker for turning the directional numbers below into a
benchmark, and hand-authoring dozens is not practical. So the project generates candidate `(query → config)`
examples by **reverse** generation: deterministic code plus the 58-option catalogue plus the checker fix the
**config** first, then a local model writes **only the natural-language query** — it never selects options,
and never sees an option id, so it cannot invent one. The pipeline samples the factor space for balanced
coverage, gates every candidate (valid ids, a clean checker pass, dedup, and a query↔factor round-trip
cross-checked by a *different* model from the one that wrote the query), and screens each for in-context
usefulness. Every row is checker-clean by construction, and a deterministic invariant suite holds the
pipeline's safety properties. Design rationale:
[`work/research/generation_pipeline_proposal.md`](work/research/generation_pipeline_proposal.md).

The deterministic half of that pipeline — factor values → recommended configuration — is runnable here as
`work/generation/recommend_by_factors.py` (see the [factor-values quickstart](#or-describe-the-analysis-as-factor-values-no-model-needed)
above). It reads the per-option priority table (`generation_config/priority_by_factor.json`, **provisional**,
authored from the taxonomy) and applies the same hard gates and constraint checker the full pipeline uses.

## Evaluation

> **Which scheme these experiments ran on.** The results below **predate the factor scheme** — they were run
> on the earlier 7 single-label use cases and their per-use-case priorities, scored against the 20-example
> simulated set. They are reported as-run, and they are *not* re-runs on factor priorities.
>
> They still stand, because of **what they were for**. Every one of them varies something the factor scheme
> does not touch: which local model to deploy (E1), how to put the knowledge base in the prompt (E1, E2),
> whether the recommendations are KB-grounded at all (E3), whether the model can emit JSON (E4), and whether
> example order matters (E5). Those are model- and retrieval-architecture questions, and the answers —
> `gemma4:26b`, all-examples, don't hard-filter, keep the text parser — are what the current system is built
> on. Re-keying the priorities would change the absolute F1 numbers but not which model or which retrieval
> strategy wins, since every condition is scored against the same gold under the same scheme.
>
> What they are **not**: a benchmark. The gold is simulated and the priorities are provisional, so treat
> every number as directional. The benchmark on the factor scheme comes after the priorities are validated.

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
| **E2** | Corpus-size sweep | As we add more examples to the knowledge base, does "put all examples in the prompt" ever lose its edge over "retrieve a relevant few"? | No — its lead *grows* with corpus size (+13 points by N=15) |
| **E3** | KB attribution | Do the recommendations actually come from the curated knowledge base, or from the model's frozen training memory? | ~79% come from the KB; holds on real forum queries too |
| **E4** | Structured-output feasibility | Could we drop the text parser by having the model emit machine-readable JSON directly? | **No** — the local model can't reliably produce valid JSON; keep the parser |
| **E5** | Example-order sensitivity | Does simply *reordering* the in-prompt examples change the score? | all-examples is robust to order; semantic retrieval is fragile |

### Headline results — `gemma4:26b` (corrected parser), mean ± SD across 5 runs

Leave-one-out over the 20 simulated gold queries; seeds 42–46; SD is across the 5 runs. **Raw harm → 0
for all conditions after the deterministic checker.**

| Condition | Enable F1 | Enable F1 (wt) | Disable F1 | Critical-recall | Category-cover | Over-rec |
|---|---|---|---|---|---|---|
| bare | 20% ± 5% | — | 11% ± 13% | — | — | — |
| keyword | 74% ± 2% | 76% ± 2% | 74% ± 4% | 67% ± 5% | 86% ± 2% | 1.21 ± 0.05 |
| **all-examples** | **84% ± 2%** | **87% ± 2%** | **81% ± 6%** | **92% ± 5%** | **95% ± 2%** | 1.23 ± 0.08 |
| semantic | 39% ± 2% | 42% ± 2% | 24% ± 7% | 38% ± 3% | 45% ± 1% | 0.69 ± 0.03 |

> **The `bare` row is corrected (was 30% ± 4%).** Options are matched to the model's text through an alias
> table built partly from each option's CLI flag. That table used to index *every* token in the flag
> string, which harvested the bare word `plugin` — the keyword that begins all 19 plugin flags — and left
> it pointing at one arbitrary plugin. The `bare` condition has no knowledge base, so the model writes
> prose with no `[source:]` citations and the parser falls back to scanning the prose for option names;
> 38 of 60 bare responses contain the ordinary English word "plugin", each of which then switched on a
> plugin the model never asked for. The alias table now takes only real flags and drops any alias that two
> options both claim, and the bare baseline drops accordingly. **The KB conditions are unaffected**
> (identical to the digit): they cite exact `[source: id]` tags and never reach that fallback. Nothing here
> changes a conclusion — the bare baseline was flattered, so every measurement of what the knowledge base
> *adds* was understated.

> **all-examples (84%) ≫ keyword (74%) ≫ semantic (39%)**, with tight run-to-run SD (≤2% for all-examples).
> Hard-filtering options (semantic) is the worst KB condition — barely above no-KB (bare 30%) and far below
> keyword/all — a retrieval-recall failure. The model is disciplined (1.23× over-recommendation) and disables
> well (81%) once parsed correctly. *(Computed by re-scoring all 400 logged responses — 20 queries × 4
> conditions × 5 runs — with the corrected parser; `work/compute_run_sd.py`.)*

### E1 · Model comparison — Enable F1, mean ± SD across 5 runs

Corrected parser, 5 seeds (42–46), all four conditions, leave-one-out over the 20 simulated gold queries.
(All three models were re-scored from their saved 5-seed logs, so these are directly comparable to the
Headline table above; `qwen2.5:3b/7b` were also tested and showed the same pattern.)

| Model | bare | keyword | all-ex | semantic | KB gain (all − bare) |
|---|---|---|---|---|---|
| gemma4:e4b | 15% ± 2% | 56% ± 3% | 62% ± 7% | 37% ± 4% | +47 |
| gemma4:12b | 17% ± 4% | 68% ± 4% | 78% ± 3% | 38% ± 2% | +61 |
| **gemma4:26b** | 20% ± 5% | 74% ± 2% | **84% ± 2%** | 39% ± 2% | **+64** |

Across every model, **all-examples ≥ keyword ≫ semantic**, and the all-examples lead grows with model size
(+6 over keyword at e4b → +10 at 26B). **semantic stays flat (~37–39%) regardless of model size** while
keyword/all-examples climb — so hard-filtering the option list to a top-k forfeits the capability gains and
leaves semantic barely above no-KB. (Mixes family/architecture, so it supports "all-examples wins for every
model", not a clean size *trend*.)

*(Corrected for the alias fix described above — previously bare 27/29/30%, and e4b keyword/all 59/65%. The
model ranking and every conclusion are unchanged; the knowledge base's contribution is simply larger than
first reported. **e4b is the one model whose KB scores moved** (−3), because it is weak enough to sometimes
omit the `[source:]` citations and fall into the prose fallback — 12b and 26b never do, so their numbers are
identical to the digit.)*

### E2 · Corpus-size sweep — does adding more examples ever stop helping?

A standard in-context-learning result is that, beyond some number of examples, putting *all* of them in the
prompt stops helping — and selectively retrieving a relevant few can start to win. **This experiment asks
whether that turning point is anywhere near our scale.** It grows the example corpus through
N = 2, 5, 10, 15, 19 (stratified, leave-one-out) and tracks the gap between *all-examples* and *keyword*
(top-2). If selective retrieval were going to win, the **all − keyword** gap would turn negative as N grows.

| N (corpus) | bare | keyword | all-ex | semantic | all − kw |
|---|---|---|---|---|---|
| 2 | 38% | 68% | 67% | 36% | −2% |
| 5 | 38% | 69% | 74% | 37% | +5% |
| 10 | 38% | 72% | 83% | 40% | +11% |
| 15 | 38% | 74% | 86% | 38% | **+13%** |
| 19 | 38% | 73% | 86% | 38% | **+13%** |

**No crossover — and the opposite of one.** All-examples' lead over keyword *grows* with corpus size, from
roughly nothing at N=2 to **+13 points by N=15–19**. The mechanism is simple: keyword retrieval is capped at
the top-2 examples no matter how large the corpus gets, while all-examples shows the model everything, so
each example added widens the gap. Semantic stays flat at ~36–40%.

> **This corrects an earlier version of this result.** The first run of this sweep used `gemma4:e4b` and the
> pre-fix parser, and reported "no difference between all-examples and keyword at any N". That was a parser
> artifact: the old parser discarded roughly half of every condition's recommendations, compressing the
> conditions together and hiding the gap. Re-run on `gemma4:26b` with the corrected parser, the gap is large
> and grows monotonically. The earlier version also attributed a "~50–70 examples per class" saturation
> threshold to Agarwal et al. (2024); that figure is not in the paper — it was our own estimate. Agarwal's
> saturation is task-dependent, and the paper's one per-class experiment saturates at 512–2048 per class,
> which places a curated gold set even further inside the "more examples still help" regime.

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
- **Include all examples; don't hard-filter options.** Selective example retrieval falls *further* behind as
  the corpus grows (−13 points by N=15, because it only ever shows the top 2), and semantic option-filtering
  is the weakest KB condition — flat at ~37–39% across model sizes while keyword/all-examples improve, so it
  forfeits the larger model's gains.
- **The RAG is doing its job:** ~79% of recommendations are KB-grounded and this holds on real queries.
- **The deterministic checker is necessary:** raw-model species/conflict violations persist at every model
  size and are only removed by the checker.
- **Reproducibility discipline matters:** a parser bug capped early scores by ~30 points; temperature=0 is
  non-deterministic under concurrency; and an alias built from the word `plugin` silently inflated the no-KB
  baseline by ~10 points. All three were caught only because every raw response is logged, so the fix could
  be re-applied to the old runs offline instead of re-running them — and every headline in this README was
  re-derived from those logs after each fix.

## Status & honesty

This is a **work in progress**, and the numbers above are **directional, not a benchmark**:

- **No approved gold examples exist yet.** The 20-example set the experiments run on is **simulated**
  (synthetic, constraint-checker-validated), and the generation pipeline produces *candidate* rows for
  review — not gold.
- **The priorities are provisional.** VEP does not rank its own options, so the per-option
  `critical`/`recommended`/`optional` tiers are authored judgement pending sign-off. They are the single
  thing gating a real benchmark: validate them, and the candidate rows become gold and the factor-keyed
  evaluation becomes meaningful.
- **The factor scheme itself is a project-internal construct** with no canonical Ensembl backing — it was
  grounded by checking each factor against the web form, not by adopting a published taxonomy. One part of
  it is a **proposed amendment**, not settled: `taxonomy_proposal.md` calls `region_focus` "purely soft",
  but the catalogue rates 9 of the 10 missense predictors *not applicable* to regulatory variants (CADD, which
  scores non-coding variants too, is the exception), and the constraint notes prescribe applying them "only
  to missense/coding variants". `region_focus` is therefore implemented as a hard gate, which needs a
  decision either way.
- **The experiments predate the factor scheme** (see the note under Evaluation) — they settled the model and
  retrieval choices, and were not re-run on factor priorities.
- Factual fields (`cli_flag`, web-form section, species restriction, native-vs-plugin, conflicts,
  dependencies, defaults) *are* **source-grounded** from the Ensembl `public-plugins` web configuration
  (release/115), not model memory.

## Acknowledgements

Built for **Google Summer of Code 2026** with **EMBL-EBI / Ensembl**. Uses [Ollama](https://ollama.com/)
for local inference and `BAAI/bge-small-en-v1.5` for semantic retrieval. VEP is developed by Ensembl.
