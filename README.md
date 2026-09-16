# Ask VEPai

**A local assistant that turns a plain-English description of a variant-analysis scenario into
an [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) web-form
configuration, with the reasoning that put each option there.**

Built as a GSoC project with EMBL-EBI. Runs against a local model via
[Ollama](https://ollama.com/); no query leaves the machine.

## What it does

Given a scenario like *"I have somatic variants from a tumour-normal pair, mostly SNVs, and I
want clinical interpretation on the coding hits"*, it:

1. Reads the scenario into a **factor tuple** — five factors (species, origin, variant size,
   region focus, analysis goal) whose values are the ones the priority table is keyed on.
2. Resolves the tuple to a set of VEP options through a priority table
   (`priority_by_factor.json`) built from documented Ensembl behaviour.
3. Runs a **post-hoc constraint checker**: species restrictions, option conflicts, missing
   dependencies auto-enabled, species-data files that don't exist for this species, the
   Restrict-results family gated so nothing silently deletes rows from the output.
4. States every assumption it made about a fact the query left unsaid — or, off `--no-ask`,
   prompts for it.
5. Emits the configuration in the language the web form uses (or a VEP command line, with
   `--cli`).

There are also two secondary modes: **explain a VEP output annotation**, and a **decision
trace** that opens the classifier's factor tuple, the per-factor derivation for each priced
option, and everything the checker changed on the way to the output.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) running locally
- A pulled model (default: `gemma4:26b` — see *Choice of model* below)

## Setup

```bash
brew install ollama              # macOS; see ollama.com for other platforms
ollama serve
ollama pull gemma4:26b

pip install -r requirements.txt
```

Only `openai` is required for the CLI. `flask` is needed for the web UI in `work/webapp/`,
and `sentence-transformers` for the legacy `evaluate.py --semantic` arm.

## Usage

### Recommend a configuration

```bash
python vep_assistant.py "somatic tumour-normal, want clinical interpretation on the coding hits"
```

Runs interactively if you omit the scenario.

**What comes back.** A short *Detected scenario* block (the five factor values, with `?` where
the query left one open and the assumed value), any *NOT AVAILABLE FOR THIS SPECIES* line,
then the configuration in the web form's own language, split into **RECOMMENDED** and
**OPTIONAL**, plus **ALREADY ON** (the options the form ships ticked, named once so you know
they are in effect). Species-aware: the *ALREADY ON* list on a mouse run does not claim SIFT
is enabled by default when it is human-only.

Two variant sizes in one callset (a WGS run with both small variants and SVs) emit **two
configurations, one per size**, because the web form cannot express both at once.

### Depth

| Flag | Meaning |
|---|---|
| *(none)* | standard: RECOMMENDED plus the OPTIONAL add-ons the scenario justifies |
| `--minimal` | the smallest runnable set (dependencies kept) |
| `--full` | switch on every add-on the scenario justifies |

### Decision trace

```bash
python vep_assistant.py --explain "germline exome from a rare-disease patient"
```

Prints, before the configuration:
- the factor tuple the classifier read from the scenario;
- Layer 2 — the per-factor derivation for every priced option: which factor value raised it,
  who else voted, and which gate (if any) would have removed it;
- what the checker did to the resolved set: species-restriction and species-data drops,
  conflict-edge resolutions, Restrict-results values vetoed, dependencies auto-enabled, and
  every RECOMMENDED option the resolver placed (this is the whole configuration).

### What to do when the question does not say

Every run either states an assumption or asks. The default is *ask*, off `stdin`-tty; it falls
through to the stated assumption in a pipe, so scripts never hang.

| Flag | Meaning |
|---|---|
| *(none)* | ask if the answer changes the RECOMMENDED set; state it otherwise |
| `--no-ask` | never prompt; state every assumption |
| `--quiet` | apply the assumptions with no disclosure line (scripts / batch runs) |

### State a fact instead of inferring it

```bash
python vep_assistant.py --origin somatic --assembly GRCh37 "tumour-normal SNVs, coding, clinical interpretation"
```

Available flags and their allowed values:

| Flag | Values |
|---|---|
| `--species` | `human` \| `non-human` (the binary factor; the actual organism goes in the query text) |
| `--origin` | `germline` \| `somatic` |
| `--size` | `small` \| `structural-CNV` \| `both` \| `small+structural-CNV` |
| `--assembly` | `GRCh37` \| `GRCh38` (aliases `hg19` / `hg38` also accepted; human only) |

Anything you state here beats the classifier and skips the corresponding question. `GRCh38`
is assumed for human when no assembly is stated. A typo is rejected with the list above
rather than silently ignored.

### Explain a VEP output annotation

```bash
python vep_assistant.py explain-result "why is my variant annotated splice_donor_variant?"
```

Uses the 41 consequence terms in `vep_consequences.json` (SO definitions).

### Other flags

| Flag | Meaning |
|---|---|
| `--cli` | append the equivalent VEP command line (web-form output is the default) |
| `--factor-think` | turn on Gemma's reasoning-first mode for the classifier (slower; not tested whether output improves) |
| `--no-check` | skip the constraint checker (not advised) |

## How it works

**One model call.** 
1. A factor classifier reads the scenario into the five factor values at
~1.2 s on the 26b local model on M5 Max.  
2. Everything after that is deterministic and uses negligible time: the priority table
resolves the tuple to a set of options, and the checker enforces species restrictions,
species-data files, dependencies, conflicts and the Restrict-results gate. The checker is
the primary constructor here — it is not repairing model output, because there is none.

The constraint checker enforces:

- **Species restrictions** — human-only options are removed for non-human species by the
  priority table.
- **Species data** — SIFT and frequency files are checked per species and named when missing.
  CCDS and variant synonyms are removed for all non-human species, even where Ensembl has
  them.
- **Restrict results** — four of the five options are never offered; `most_severe` remains an
  add-on for basic questions.
- **Dependencies** — a missing prerequisite is auto-enabled and recorded.
- **Conflicts** — declared conflict edges drop one side and say which.

## Choice of model

The model's only job is to read the question into five factor values, returned as a small
JSON object with reasoning off. `gemma4:26b` is the default: on the 31 review scenarios it
scores 0.898 end-to-end F1 against 4b's 0.874. The
smaller model is not practically faster since 26b is very fast anyway, and its errors fall mostly on variant size, which decides
whether whole groups of options are switched off. `e4b` is a workable fallback on a machine
with less than about 20 GB of free memory; set `VEP_MODEL` to use it.


## Project structure

```
vep_assistant.py         # engine — default path: classifier → resolver → checker
factors.json             # the factor scheme (values, hard gates, exclusions, joint rules)
priority_by_factor.json  # override for the priority table (derived by default from DRIVES in
                         #   vep_assistant.py + per-option blocks in the catalogue; the file
                         #   wins when present, e.g. a mentor-signed table dropped in)
vep_options.json         # the 68-option catalogue
vep_consequences.json    # 41 VEP consequence terms (SO definitions)
training_examples.json   # 23 legacy examples: --two-pass in-context corpus, and the checker's
                         #   use-case tie-break when two options conflict
requirements.txt         # openai + flask (web UI) + sentence-transformers (legacy --semantic)
results/                 # recommendations and evaluation reports
```

Design rationale, deterministic invariant harnesses (79 checks, no GPU), the full option
dossier and the generation pipeline live one level up in `work/`; see `../work/README.md`.

## Knowledge base

**68 VEP options**, from the release/115 `public-plugins` source reconciled against the
release-116 documentation pages, with `species_restriction`, dependencies, conflicts and the
factor-keyed priorities the resolver reads.

**What the shipped path uses.** The five factor values from the classifier plus the priority
table. The 23 legacy examples in `training_examples.json` are also read on this path — the
checker uses them for one thing only, breaking ties when two options conflict, by detecting a
use case from the query against the old seven-category labels.

**OUTDATED, measuring. Evaluation scenarios.** The pipeline is scored on the **31 candidate scenarios** in
`../work/generation/candidates/iced.json`, generated and ICE-screened by the pipeline in
`../work/generation/` and reviewed by the Ensembl mentors. Every current number under
*Known limitations* comes from that set.

The five factors are:

| Factor | Values | Kind |
|---|---|---|
| `species` | human · non-human | data fact, hard gate |
| `origin` | germline · somatic | data fact (one rule: `somatic` switches off the frequency pre-filter) |
| `variant_size_class` | small · structural-CNV (multi-select) | data fact, hard gate |
| `region_focus` | coding · regulatory-noncoding (multi-select) | intent, hard gate |
| `analysis_goal` | basic-consequence · clinical-interpretation · population-frequency (multi-select) | intent |

The old single-label use-case scheme (rare-disease-germline / somatic-cancer / …) was
retired from the priority table in September 2026: a mouse somatic SV is somatic **and**
structural **and** non-human at once, and forcing it into one bucket picks the wrong
priorities. See `../work/research/taxonomy_proposal.md`. The scheme still lives in two
places: as the labels on `training_examples.json`, and inside the checker's conflict
tie-break.

**factor-value inference eval**
Reasoning on results produced correct inference 148/150, and the non correct cases did not result in config change(one is clincial and basic whereas the correct config is basic, but basic is just a subset of that, second is clinical + pop frequency rather than the correct one being clinical only, one extra optional but nothing changes recommended)
Reasoning off 138/150 correct, fail to grasp species sometimes.
work/results/factor_grid_natural_shipped_v2prompt.json (new prompt, reasoning off)
work/results/factor_grid_natural_think_v2prompt.json (new prompt, reasoning on)


## Evaluation

The shipped path is exercised by the harnesses in `../work/harness/`:

- `factor_accuracy.py` — the classifier's five-factor output on the 31 review scenarios.
- `factor_grid.py` — the 600-query stress grid (species, origin, size, region, goal).
- `verify_pipeline.py` — the 79 deterministic invariant checks (no GPU, seconds).

Recent numbers from `../work/results/final_2026-09-15/`: factor accuracy across 3 seeds
(species 31/31 rule-based, exact tuple 21/31, e2e F1 0.970 ± 0.000), 78-row fallback
end-to-end (76/78 disclosed), class-weighted F1 that prices errors by their documented effect
on the VEP output. Note `work/results/` is git-ignored, so a fresh clone will not have those
files; run the harnesses to regenerate. Those runs also had `VEP_SPECIES_HINT=1` on and have
not been re-run since it was switched off by default.


`evaluate.py` in the demo is the **legacy** benchmark: it scores the two-pass draft
recommender's text on 8 hardcoded test queries, weighted by the retired use-case snapshot
kept in `../work/harness/legacy/`. It never exercises the shipped one-call path. Kept only
for comparison work against older figures.

## Known limitations

**Priorities are provisional.** The five-factor priority table is not mentor-signed yet;
every reported number is directional until it is. The priorities are authored in `DRIVES`
inside `vep_assistant.py` plus the per-option blocks in the catalogue, and derived at load
time. `priority_by_factor.json` on disk is a signed-off override that wins when present — the
route for a reviewed table is to drop it in; edit the JSON alone and the next
`seed_priorities.py` run overwrites it, and a demotion made in `DRIVES` does nothing until
the JSON is regenerated.

**Enable-F1 on the shipped path is undefined.** The classical enable-F1 metric scored a
model-written draft configuration that the current path no longer produces (see *Legacy*
below). The class-weighted F1 in `../work/harness/class_weighted_f1.py` is the current
figure — 0.900 as last measured, with `VEP_SPECIES_HINT=1` on and not yet re-run since it was
switched off by default. The weights are ours, not a mentor's.

---

## Legacy: the two-pass path (`--two-pass`)

Before September 2026 the default path was **two calls**: the factor classifier, then a
second model call — the **recommender** — that drafted the configuration prose. The checker
then rebuilt the RECOMMENDED set from the factor tuple whatever the draft said, so on the 31
measured scenarios single-pass and two-pass produce the same set at the option level. What
the draft still contributed was the per-option prose that `--explain` printed, and a handful
of extra options it proposed that the priority table prices for nothing (a class the checker
had to tag and cap). At ~18 s per query on the 26b local model (against ~1.2 s for
single-pass) it is now off by default.

The two-pass path is still runnable for comparison work:

| Flag | Meaning |
|---|---|
| `--two-pass` | run the draft-recommender call as well |
| `--think` | turn on Gemma's reasoning-first mode for the recommender under `--two-pass` (slower; not tested whether output improves) |

`enable-F1 = 88.0% ± 0.2` (2026-09-04, L4) stands as the last two-pass figure. The four-arm
ablation in `../work/results/final_2026-09-15/` compares single-pass against three two-pass
variants (each with a different in-context example corpus) and finds single-pass ahead of
every two-pass arm on plain and class-weighted F1 — which is why example retrieval was
dropped from the shipped pipeline.

Two caveats that apply to this path and to `evaluate.py`, not to the shipped classifier:

- **Value field is ignored in scoring.** Getting `gnomad_af: "gnomAD exome"` right vs
  `gnomAD genome` counts as the same enable.
- **Response parsing is line-level.** A line mixing "enable X" and "disable Y" ranks the
  first matching context. In practice the draft uses one line per option, so this rarely
  fires. Citations are counted only in `[source: ...]` form.
