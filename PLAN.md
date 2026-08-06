# Ask VEPai — plan and status

GSoC 2026 · EMBL-EBI / Ensembl. A locally-hosted assistant that turns a plain-English
variant-analysis scenario into a recommended [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/)
web-form configuration, with justifications and provenance for every option it suggests.

This page is the current state of the work and what is planned next. It is deliberately blunt about
what is measured, what is provisional, and what is still wrong.

---

## The problem

VEP's web form exposes about sixty options. Choosing well needs you to know which ones exist, which
apply to your species and variant type, which conflict, and which matter for the question you are
actually asking. Most people do not, so they either accept the defaults or copy a configuration from
a colleague. Neither is a good answer, and neither leaves any record of why.

## The approach

**The model proposes, deterministic code disposes.** A language model is good at reading a scenario
and bad at guaranteeing a correct configuration, so it is never given the last word:

```
scenario  ->  read into 5 factor values  ->  price every option for THAT scenario
          ->  model proposes ✓/✗ with a [source: id] for each
          ->  drop anything invented   ->  restore missing must-haves
          ->  constraint checker       ->  final configuration + command
```

Four deterministic layers sit after the model: a hallucination gate that drops option ids not in the
catalogue, a step that restores must-haves a short answer left out, a constraint checker that removes
species / assembly / conflict violations and auto-enables dependencies, and a coverage guard that
refuses to show importance tiers it cannot vouch for.

**The five factors.** Two are facts about the sample and act as hard gates (species, variant size);
one is a fact with a single hard rule (germline vs somatic); two are intent (which regions, and what
for). A scenario is a set of values, not one category — a mouse somatic structural variant is all
three at once, which is why single-label schemes were abandoned.

## Status

| | |
|---|---|
| Option catalogue | **65 options**, grounded in Ensembl `public-plugins` release/115 |
| Recommender + checker + gates | working, published, runnable |
| Deterministic invariant suite | **32 checks**, seconds, no GPU |
| Per-query latency | **~11 s** end to end on the reference machine |
| Agreement with the priority table | **enable-F1 89.5% ± 0.6**, must-have recall **95.1% ± 0.3** (3 seeds) |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

## What is done

- **A catalogue grounded in source, not recall.** Flags, form sections, species restrictions,
  conflicts, dependencies and defaults all trace to release/115 files, with per-entry provenance.
- **A reproducible way to build examples.** Deterministic code fixes the configuration from a factor
  tuple; a local model writes only the natural-language scenario and never sees an option id, so it
  cannot invent one. Every candidate is gated before a human sees it.
- **Speed.** Both model calls stopped reasoning before answering, which cost time and bought nothing
  measurable: the recommender went 34.9 s → 18.1 s, the scenario classifier 8.2 s → 1.4 s, with the
  factor readings byte-identical on 29 of 31 rows and no end-to-end change.
- **One place to edit.** Option priorities are derived from the catalogue at load rather than kept in
  a generated file, so adding or changing an option is a single edit. A typo in a priority block is
  reported rather than silently ignored.
- **Stated facts beat inferred ones.** Species, origin, variant size and assembly can be set directly,
  in the web app or on the command line, and override whatever the model read. Assembly matters
  particularly: MANE transcripts exist only for GRCh38 and VEP's own form offers the checkbox
  regardless, so a GRCh37 user can enable an option with no data behind it.

## What is next

1. **Apply the mentor review.** Ten rows approved, twenty edited, one rejected. The unopposed edits are
   in; the rest are below.
2. **Two tiers instead of three.** Merging must-have and recommended into a single default bucket,
   with an *already on / turn on* marker — roughly half of a typical recommendation is switched on by
   the form before anything is suggested, and that distinction is more useful than the one it replaces.
3. **Run the recommended configuration against Web VEP** and check the output. The largest remaining
   independent piece.
4. **Ask when it matters, assume when it does not.** Measured over twenty real forum questions, 18 of
   20 leave something open that changes the answer. Safe assumptions plus stated facts take the
   questions needed from 1.5 per query to 0.65; a single taxonomy change would take it to zero.

## Open questions

These need a domain decision, not more code:

- **Is a variant set one size or two?** The scheme forces a choice between small and structural, but
  real questions say "SNVs and CNVs". Allowing both removes every remaining clarifying question.
- **Which predictors are the core set,** and on what axis? VEP itself ranks none of them; the current
  split follows a clinical-genetics standard external to VEP.
- **Should a purely regulatory query keep the missense predictors?** They produce empty columns, but
  the review asked for them back.
- **Should the assistant say what it cannot do?** VEP has no non-human frequency source, so
  "population frequencies for my mouse variants" currently returns a configuration with no frequency
  data and no explanation.

## Running it

```bash
# recommend a configuration
cd vep_ai_demo && python vep_assistant.py "germline exome variants, rare disease, human GRCh38"

# state the facts rather than having them read from the text
python vep_assistant.py --species human --assembly GRCh38 --size small "likely pathogenic coding variants"

# the deterministic checks — no GPU, a few seconds
VEP_OPTIONS_FILE=$PWD/work/vep_options_expanded.json PYTHONHASHSEED=0 \
  python work/generation/verify_pipeline.py
```

Needs a local [Ollama](https://ollama.com) with `gemma4:26b` pulled. No API keys, no data leaves the
machine.

## Repository

| | |
|---|---|
| `vep_ai_demo/` | the assistant: recommender, factor scheme, constraint checker, catalogue |
| `work/generation/` | the example-generation pipeline and its configuration |
| `work/harness/` | evaluation and test suites |
| `work/research/` | design proposals, source dossiers, literature notes |
| `work/generation/candidates/review/` | the candidate set under review and the decisions it asks for |

## Honesty note

The example configurations are generated from a priority table that is our own editorial judgement.
VEP does not rank its own options, so somebody had to, and that somebody was us. Until the Ensembl
mentors sign that table off, every metric on this page measures agreement with a proposal rather than
correctness — and the design decisions it rests on are written down in
`work/generation/candidates/review/DECISIONS.md` precisely so they can be argued with.
