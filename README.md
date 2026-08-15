# Ask VEPai

**A locally-hosted RAG assistant that turns a plain-English variant-analysis scenario into a recommended
[Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) web-form configuration — with
justifications, source citations, and a deterministic safety net.**

*Google Summer of Code 2026 · EMBL-EBI (Ensembl)*

---

## What it does

Configuring the Variant Effect Predictor (VEP) means choosing from dozens of options (predictors,
frequency datasets, identifiers, filters…), and the right choice depends on your scenario. Ask VEPai takes a natural-language description of your analysis and recommends **which VEP
options to enable**, **why**, and **which knowledge-base entry each recommendation rests on**.

You ask:

> *"Germline exome variants from a rare-disease trio, human GRCh38."*

It answers with a per-option configuration (enable HGVS, MANE, ClinVar, gnomAD exome AF, pathogenicity
predictors…; disable what doesn't apply), each line carrying a `[source: option_id]` citation, plus the
detected use case and a decision trace.

## Design: "generate-and-verify" (RAG proposes, a checker disposes)

The core idea is that a local LLM is powerful but not trustworthy on its own, so a deterministic layer
guards its output:

```
 user scenario
      │
      ▼
 [1] Retrieval ........ pull relevant option docs + worked examples from the knowledge base
      │                 (all examples, keyword word-overlap, or --semantic BGE embeddings)
      ▼
 [2] Prompt assembly .. assemble the option KB + examples + a strict output contract
      │
      ▼
 [3] Local LLM ........ propose a config as `✓/✗ option [source: id]` lines  (via Ollama)
      │
      ▼
 [4] Parsing .......... extract the enable/disable decisions + citations
      │
      ▼
 [5] Constraint checker  DISPOSES of what the LLM gets structurally wrong, deterministically:
      │                  • block human-only options for a positively non-human species
      │                    (species unstated → keep them, flag "assuming human")
      │                  • block build-mismatched options when a build is named
      │                    (drop MANE/EVE on GRCh37, Geno2MP on GRCh38)
      │                  • resolve conflicts by priority, then restrictiveness, then name
      │                  • auto-enable missing dependencies (transitively); drop the
      │                    dependent option if its dependency is species-blocked
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

# 3. Ask it something — the 65-option catalogue is the default, no setup needed
cd vep_ai_demo
python vep_assistant.py "germline exome variants, rare disease, human GRCh38"
python vep_assistant.py --minimal "germline exome variants, rare disease, human GRCh38"  # essentials only
python vep_assistant.py --full    "germline exome variants, rare disease, human GRCh38"  # + every add-on
python vep_assistant.py --explain --semantic "mouse CRISPR variants in GRCm39"   # + decision trace
python vep_assistant.py --think   "germline exome variants, rare disease, human GRCh38"  # let it reason first
python vep_assistant.py explain-result "why is my variant splice_donor_variant?" # output explainer
```

Classifying a question into factor values is a second, much smaller model call, and by default it
reuses the model above so that one download is enough. `VEP_FACTOR_MODEL=gemma4:e4b` makes it
noticeably faster if you have a small model pulled as well.

> **The model does not reason before answering, on purpose.** `gemma4:26b` is a reasoning
> model, and letting it think costs about half the wall clock for no measurable gain: **34.9s vs
> 18.1s** per query, with enable-F1 unchanged and critical-recall slightly *better* without it.
> `--think` turns it back on. See [Speed](#speed-the-reasoning-phase-is-half-the-wait-and-buys-nothing).

See [`vep_ai_demo/README.md`](vep_ai_demo/README.md) for all modes and flags.

> **Use a capable model.** `gemma4:26b` is what this is built and benchmarked on. Smaller
> models are less reliable two ways: they more often break the strict `✓ … [source: id]`
> line the parser reads (the tool flags a bad or missing citation), and they more often
> misread the scenario when classifying it into factor values. The detected factor values
> are printed at the top of every answer so you can see that reading and correct it.

### Alternative: simply describe analysis scenarios (no model needed)

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

# variant_size_class, region_focus and analysis_goal are multi-select — repeat the flag.
# A whole-genome callset holding both SNVs and CNVs is the ordinary case, not an edge case.
python recommend_by_factors.py --species human --origin somatic \
    --size small --size structural-CNV \
    --region coding --region regulatory-noncoding \
    --goal clinical-interpretation --goal population-frequency

# --explain shows WHICH factor value drove each option to its priority
python recommend_by_factors.py --species human --origin germline --size small \
    --region regulatory-noncoding --goal clinical-interpretation --explain
```

This is the provenance view, so it prints the **internal** `critical` / `recommended` / `optional`
priorities rather than the two buckets a user is shown — its job is reporting what the table did. It
separates what to switch on from the add-ons (defensible extras, not on by default), lists what the
factors **gated out** and why, and flags anything a human still needs to settle:

```
CORE — switch these on (14)
  [critical   ] clinvar                --check_existing (derived; no
  [critical   ] core_type              --refseq | --merged | --gencod
  [critical   ] hgvs                   --hgvs
  [critical   ] regulatory             --regulatory
  [recommended] biotype                --biotype
  [recommended] cadd                   --plugin CADD
  [recommended] cell_type              --cell_type
  ...
ADD-ONS — defensible extras, not on by default (11)
  [optional   ] dbscsnv                --plugin dbscSNV
  [optional   ] dosage_sensitivity     --plugin DosageSensitivity
  ...
GATED OUT by the factors (12) — not applicable to this scenario
  alphamissense, clinpred, dbnsfp, eve, mane, mutfunc, nmd, paralogues, polyphen, protein, revel, sift
```

## Repository layout

```
askVEPai/
├── vep_ai_demo/      Runnable prototype: vep_assistant.py (recommend / explain / explain-result),
│                     evaluate.py (offline benchmark), and the data JSONs it loads.
│                     Ships the 65-option catalogue + 23-example corpus as its defaults.
└── work/             GSoC deliverables built on top of the demo:
    ├── vep_options_expanded.json     65-option VEP catalogue (source-grounded from Ensembl)
    ├── research/                     taxonomy_proposal.md (the factor scheme) +
    │                                 generation_pipeline_proposal.md (the example-generation design)
    ├── generation/                   the deterministic factor recommender:
    │                                 recommend_by_factors.py (factor values -> config, no model),
    │                                 seed_priorities.py -> generation_config/priority_by_factor.json
    │                                 (the per-option priority table the recommender reads)
    ├── preliminary_examples/         simulated gold set + ablations + tracker queries + validator
    ├── output_schema/                structured JSON output design (schema + mapping rules)
    ├── EXPERIMENTS.md                full experiment report (rationale · method · results · caveats)
    ├── harness/                      the evaluation harness + experiment drivers
    └── results*/                     saved evaluation + attribution reports
```

The **65-option** catalogue is the default. The experiment harness overrides the catalogue, examples,
test set and results directory via environment variables (`VEP_OPTIONS_FILE`, `VEP_EXAMPLES_FILE`,
`VEP_TESTSET_FILE`, `VEP_RESULTS_DIR`); the wrapper `work/harness/run_experiment.sh` sets them for you.

## The factor scheme

A scenario is not one category — it is a set of values across five largely-orthogonal factors. Three are facts about the data (the variant set decides them, not the user); two are intent (what the user wants out of the annotation). Each factor earns its place only if its values actually gate or shift a concrete cluster of options in the web form.

| Factor | Values | Kind | Role |
|---|---|---|---|
| **species** | human / non-human | data fact | **hard gate** + priority — gates the entire human-only block (PolyPhen, CADD/REVEL/AlphaMissense, gnomAD, ClinVar, MANE…) |
| **origin** | germline / somatic | data fact | priority, plus one hard rule (`somatic ⇒ no common-variant frequency filter`) |
| **variant_size_class** *(multi-select)* | small (SNV/indel) / structural-CNV | data fact | **hard gate** + priority — SVs drop the missense/splice predictors and swap gnomAD → gnomAD-SV |
| **region_focus** *(multi-select)* | coding / regulatory-noncoding | intent (*where*) | **hard gate** + priority — coding drives HGVS/protein/exon numbers/domains; regulatory drives the regulatory build, cell types, UTRAnnotator, Enformer |
| **analysis_goal** *(multi-select)* | basic-consequence / clinical-interpretation / population-frequency | intent (*why*) | priority — identifiers only vs ClinVar + predictors + phenotypes vs 1000G/gnomAD frequencies |

Splitting *where* from *why* is deliberate: a single axis mixing them mislabels the common case. The
pathogenicity predictors are driven by `analysis_goal` (why you are annotating), while `region_focus`
decides whether they apply at all — so a coding+regulatory variant set keeps them and a purely regulatory
one does not. The full rationale is in
[`work/research/taxonomy_proposal.md`](work/research/taxonomy_proposal.md).

Three of the five are **multi-select**, because they describe a *variant set* rather than one variant. A
whole-genome callset routinely contains both small and structural variants, so forcing a choice there
made the tool ask a question it could not accept the honest answer to. Multi-select gating is
all-values: an option is removed only when *every* active value rules it out, so a mixed set keeps the
tools for both halves. `variant_size_class` became multi-select on measurement — see the section below.

### What a question leaves unsaid: assume, say so, and ask only when it matters

A factor the question never mentions contributes nothing, so every option it would have supplied
silently disappears and the user gets a shorter configuration with no sign anything is missing. Ask
VEPai resolves each gap one of three ways, and asking is the last of them:

| | when | friction |
|---|---|---|
| **take it from the text** | the question settles it | none |
| **guess, and say which** | one answer is clearly safer than the others — *the normal case* | none |
| **ask** | no safe guess, and something essential is at stake | real |

Every guess is stated back: *"Assumed origin = somatic; say germline if these are inherited."* Nothing is
blocked and the lines can be ignored. **Whether to ask is arithmetic over the priority table, not a model
judgement** — resolve the configuration under every candidate answer, and stay quiet unless a must-have
option actually moves. It costs about 1 ms against a ~1000 ms classifier call and is auditable per query.

The defaults were chosen by measurement, not preference, and the measurements disagree with each other in
useful ways — `region_focus` from a deterministic sweep, `origin` from a danger audit (which *wrong* guess
switches on something destructive), `variant_size_class` from 78 controlled ablations. **Assembly is never
guessed**: it is the one gap where silence produces a *wrong* answer rather than a thin one, since MANE
exists only for GRCh38 while VEP's own form pre-ticks it for everyone, and guessing GRCh38 would be wrong
for exactly the GRCh37 clinical users the problem already affects.

```bash
# meet it as a user does; --why for the audit view, --factors to skip the model
python work/harness/try_reprompting.py --why "human tumour WGS, which variants are damaging?"

# how often it interrupts, per candidate policy, on 78 controlled ablations — no model, seconds
python work/harness/ask_rate.py
```

Design and every number: [`work/research/reprompting_proposal.md`](work/research/reprompting_proposal.md).

### Per-option priorities: critical / recommended / optional

Every option carries a priority **per factor value**, not one global label — `priority_by_factor.json`, keyed
`option → factor → value → priority`. Priorities compose by taking the **strongest** label across all active
factor values, while a hard gate can remove an option outright. That per-value keying is what lets one table
say that ClinVar is **critical** for clinical interpretation, merely **optional** in a population scan, and
**absent** from a basic consequence lookup — a single label per option cannot express that.

| Tier (internal) | Meaning | In the output |
|---|---|---|
| `critical` | omitting it makes the analysis unanswerable | **RECOMMENDED**, on |
| `recommended` | standard practice for this scenario | **RECOMMENDED**, on |
| `optional` | defensible and useful, but redundant or niche | **ADD-ONS**, offered, not on by default |
| `not_applicable` | a hard gate removes it | gated out, with the reason shown |

**The user sees two buckets, not three.** `critical` and `recommended` were always switched on together,
so the split was only ever a label on the way out; merging them changed no configuration and was verified
as a pure regrouping over all 72 factor tuples. The three internal priorities survive because real
mechanisms are defined on them (`--minimal`, repair of an under-recommending draft, critical-recall).
"Default" was rejected as a name because it reads as *applies automatically*, which is wrong for a bucket
the user still has to switch on — that distinction is carried by an *already on* marker instead, and it
earns its place: **54%** of a typical recommendation is switched on by the form before anything is
suggested.

> **Grounded vs. judgement.** The factual fields (CLI flag, form section, species restriction,
> conflicts, dependencies, defaults) are source-grounded from Ensembl `public-plugins` (release/115).
> The **priorities are not** — VEP does not rank its own options, so the core-vs-add-on tiering is our
> editorial judgement (ACMG PP3/BP4 / ClinGen SVI, Pejaver et al. 2022) and is **provisional** pending
> mentor sign-off. Full reasoning in [`taxonomy_proposal.md`](work/research/taxonomy_proposal.md).

### Generating examples on the factor scheme

**Generating gold examples.** Real, expert-validated examples are the blocker for turning the
directional numbers below into a benchmark, and hand-authoring dozens isn't practical. So the
pipeline uses *reverse generation*: deterministic code + the 65-option catalogue + the checker fix
the configuration first, then a local model writes only the natural-language query. It never selects
options and never sees an option id — so it cannot invent one.

Each candidate is sampled for balanced factor coverage, gated (valid ids · clean checker pass · dedup
· a query↔factor round-trip cross-checked by a *different* model), and screened for in-context
usefulness. Every row is checker-clean by construction, and a deterministic invariant suite guards
the pipeline's safety properties. Rationale: [`generation_pipeline_proposal.md`](work/research/generation_pipeline_proposal.md).

The deterministic half — factor values → configuration — is runnable as
[`recommend_by_factors.py`](work/generation/recommend_by_factors.py): it reads the provisional
priority table (`generation_config/priority_by_factor.json`) and applies the same hard gates and
constraint checker as the full pipeline.

## Evaluation

Evaluation runs in two parts, and both are **directional, not a benchmark** — the gold is simulated
and the priorities are provisional (see *Status & honesty*). All runs use **leave-one-out** (the scored
example is removed from the retrieval corpus) and report **mean ± SD** across runs.

### Factor scheme (current) — does the recommender reproduce the deterministic table?

The factor path fixes the configuration deterministically from the priority table. This asks whether
the RAG recommender, shown only the query, reaches the same configuration — i.e. whether the LLM's
proposal and the deterministic resolver agree. Factor-keyed, LOO over the 31-row generated set
(`gemma4:26b`, 3 seeds; harness `work/harness/eval_factor_set.py`).

| Metric | Result |
|---|---|
| Enable-F1 (tier-aware) | **89.5% ± 0.6%** |
| Critical-recall (excl. always-on `core_type`) | **95.1% ± 0.3%** |

**Self-consistency, not a benchmark** — the gold config is itself built by the provisional table, so
this measures *reproduction of that table*, not correctness against expert gold; it is **not comparable
to the 84% below**. Critical-recall is reported net of `core_type` (critical in every row, so trivially
recovered). Signing off the priorities turns this into a real enable-F1.

**Pass `--factors inferred`.** The harness defaults to `none`, which skips the classifier entirely and
withholds the scenario-resolved priorities from the prompt — worth about ten points of enable-F1, and
easy to quote by mistake. The figures above are the shipped path: the five factors read from the query,
then the options priced from that reading.

### Speed: the reasoning phase is half the wait, and buys nothing

`gemma4:26b` is a reasoning model — it emits a chain of thought before the answer. Measured over the
31-row set, **single-threaded so each figure is one user's actual wait** (`--think` on/off, harness
`work/harness/eval_factor_set.py`):

| Reasoning | Seconds / query | Enable-F1 | Critical-recall |
|---|---|---|---|
| on | 34.9 s | 78% | 92% |
| **off (default)** | **18.1 s** | **79%** | **95%** |

Nothing is traded: it is 1.93x faster with equal enable-F1 and *better* critical-recall, and far more
stable run to run. So reasoning is off by default and `--think` restores it.

Two related findings from the same run:

- **Reasoning helps the large model and hurts the small one.** `gemma4:e4b` gains 13 points of enable-F1
  and 12 of critical-recall with thinking *off*, while also being faster. Reasoning amplifies existing
  capability rather than substituting for it, so a smaller model with more thinking is not a route to speed.
- **Sending each option's full description does not help.** Every catalogue entry is truncated to 120
  characters in the prompt; sending the complete text costs **+16 s/query** and changes accuracy by less
  than the run-to-run noise. What the catalogue contributes is *which options exist and how they relate*,
  not prose about them — consistent with the +35-point catalogue-only result below.

### Model & retrieval selection (earlier — E1–E5)

These five experiments **predate the factor scheme** — run on the 20-example simulated set under the
earlier 7-use-case priorities. They settled what the factor scheme doesn't touch: which model, how to
feed the KB, whether recommendations are KB-grounded, whether the model can emit JSON, whether example
order matters. Re-keying to factor priorities would shift the absolute F1 but not which model or
retrieval wins. Full protocol + per-experiment detail: [`work/EXPERIMENTS.md`](work/EXPERIMENTS.md).

| ID | Asks | Result |
|---|---|---|
| E1 | Which model, and how to give it the KB? | all-examples wins for every model; `gemma4:26b` best |
| E2 | Does "all examples" ever lose to "retrieve a few" as the corpus grows? | No — lead *grows* (+13 by N=15) |
| E3 | Do recommendations come from the KB or model memory? | ~79% from the KB; holds on real forum queries |
| E4 | Can the model emit valid JSON instead of parsed text? | No (~40% valid) — keep the parser |
| E5 | Does reordering the in-prompt examples change the score? | all-examples robust; semantic fragile |

**Headline — `gemma4:26b`, corrected parser, 5 seeds (42–46), LOO over 20 simulated queries.
Raw harm → 0 after the checker.**

| Condition | Enable F1 | Disable F1 | Critical-recall | Category-cover | Over-rec |
|---|---|---|---|---|---|
| bare (no KB) | 20% ± 5% | 11% ± 13% | — | — | — |
| keyword | 74% ± 2% | 74% ± 4% | 67% ± 5% | 86% ± 2% | 1.21 |
| **all-examples** | **84% ± 2%** | **81% ± 6%** | **92% ± 5%** | **95% ± 2%** | 1.23 |
| semantic | 39% ± 2% | 24% ± 7% | 38% ± 3% | 45% ± 1% | 0.69 |

*Conditions: keyword = all 58 options + top-2 examples · all-examples = all 58 + all (≤19) examples ·
semantic = top-10 options + top-2 examples, by embedding. Enable/Disable F1 = precision·recall of the
options turned on / off vs gold; critical-recall = must-haves found; category-coverage credits
interchangeable predictors (e.g. CADD/REVEL). Definitions: [`work/EXPERIMENTS.md`](work/EXPERIMENTS.md).*

**Corpus-size sweep (E2)** — the gap grows, no crossover. Keyword is capped at its top-2 however large
the corpus gets; all-examples shows everything, so each added example widens the lead:

| N | keyword | all-examples | all − kw |
|---|---|---|---|
| 5 | 69% | 74% | +5 |
| 10 | 72% | 83% | +11 |
| 15 | 74% | 86% | **+13** |
| 19 | 73% | 86% | **+13** |

**KB attribution (E3)** — delete an option's KB evidence, re-ask; if the recommendation vanishes it was
KB-driven. ~**79%** are KB-grounded (56% from worked examples, 26% from descriptions), and it holds off
the synthetic distribution: 79% on verbatim real forum queries (n=56), 77% across all real (n=128).

**Findings.** `gemma4:26b` + all-examples (84% Enable-F1, 92% critical-recall). Include all examples;
don't hard-filter options — semantic is the weakest KB condition, flat at ~37–39% across model sizes.
The deterministic checker is necessary: raw-model species/conflict violations persist at every model
size and only the checker removes them. Reproducibility mattered — a parser bug capped early scores
~30 points and an alias built from the word "plugin" inflated the no-KB baseline ~10 points; both were
caught and re-derived offline from logged responses (no re-runs), because every raw response is logged.

## Acknowledgements

Built for **Google Summer of Code 2026** with **EMBL-EBI / Ensembl**. Uses [Ollama](https://ollama.com/)
for local inference and `BAAI/bge-small-en-v1.5` for semantic retrieval. VEP is developed by Ensembl. Being honest: Claude is used to assist with coding. It's pretty clever.
