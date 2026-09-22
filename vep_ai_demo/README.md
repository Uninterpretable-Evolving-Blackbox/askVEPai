# Ask VEPai

A local assistant that turns a plain-English description of a variant-analysis scenario into
an [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) **web-form
configuration**. Add `--explain` for the per-factor derivation of every option.

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

- Python 3.9+
- [Ollama](https://ollama.com/) running locally
- A pulled model (default: `gemma4:26b` — see *Choice of model* below)

## Setup

```bash
brew install ollama              # macOS; see ollama.com for other platforms
ollama serve
ollama pull gemma4:26b

pip install -r requirements.txt
```

Only `openai` is required for the CLI. `flask` is needed for the web UI in `work/webapp/`.

## Usage

### Recommend a configuration

```bash
python vep_assistant.py "somatic tumour-normal, want clinical interpretation on the coding hits"
```

Runs interactively if you omit the scenario.

**What comes back.** A short *Detected scenario* block showing the five factor values (any
gap the query left open is filled in and disclosed on an `Assumed <factor> = <value>` line),
any *NOT AVAILABLE FOR THIS SPECIES* line, then the configuration in the web form's own
language, split into **RECOMMENDED** and **OPTIONAL**, plus **ALREADY ON** (the options the
form ships ticked, named once so you know they are in effect). Species-aware: the *ALREADY
ON* list on a mouse run does not claim MANE is enabled by default when it is human-only.

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

Adds two extras to the run:

**Before the configuration:**
- the factor tuple the classifier read from the scenario;
- Layer 2 — the per-factor derivation for every priced option: which factor value raised it,
  who else voted, and which gate (if any) would have removed it.

**After the configuration**, under *HOW THIS WAS CORRECTED*:
- what the checker did to the resolved set: species-restriction and species-data drops,
  conflict-edge resolutions, Restrict-results values vetoed, dependencies auto-enabled, and
  every RECOMMENDED option the resolver placed.

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
| `--factor-think` | turn on classifier reasoning. Measured: tuple identical on 29/31 rows, no end-to-end change, ~6× slower (Exp 15). Today's grid: reasoning-on fixes all 4 species misses at ~7 s/query; with the old prompt 2 of the first 44 cases hit the token cap with no answer. Full new-prompt result pending. |
| `--no-check` | skip the constraint checker (not advised) |

Note: `explain-result` still runs with reasoning **on** — its call goes through an endpoint
that ignores the off switch.

## How it works

**One model call.** A factor classifier reads the scenario into the five factor values at
~1.2 s on the 26b local model. Everything after that is deterministic: the priority table
resolves the tuple to a set of options, and the checker enforces species restrictions,
species-data files, dependencies, conflicts and the Restrict-results gate. The checker is
the primary constructor here — it is not repairing model output, because there is none.

The species value comes from the model's reading of the query; there is no keyword override
on top of it.

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
scores 0.898 end-to-end F1 against 0.874 for `gemma4:e4b`, at about 0.9 s a query. The
smaller model is no faster (1.2 s), and its errors fall mostly on variant size, which decides
whether whole groups of options are switched off. `e4b` is a workable fallback on a machine
with less than about 20 GB of free memory; set `VEP_MODEL` to use it.

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `VEP_MODEL` | `gemma4:26b` | the model that reads the question into the five factor values (also runs the draft under `--two-pass` and `explain-result`) |
| `VEP_FACTOR_MODEL` | falls back to `VEP_MODEL` | separate classifier model, if wanted |
| `VEP_CLASSIFIER_PROMPT` | `v2` | classifier prompt; `v1` restores the old one |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `VEP_OPTIONS_FILE` | (auto) | catalogue override; uses `work/vep_options_expanded.json` when that exists, else the demo file |
| `VEP_FACTORS_FILE` | (auto) | factor scheme override; uses `work/generation/generation_config/factors.json` when that exists, else `factors.json` |
| `VEP_PRIORITY_FACTOR_FILE` | (auto) | priority-table override; both default files exist in the repo (written 15 Sept), so the file wins — the derivation from DRIVES + the catalogue is the fallback path |
| `VEP_EXAMPLES_FILE` | `training_examples.json` | the 23 stage-B examples. Read only by `--two-pass` and by `legacy/`; the default path does not use them |
| `VEP_FACTOR_THINK` | off | classifier reasoning (see `--factor-think` above for the measured effect) |
| `VEP_SPECIES_HINT` | off | diagnostic: put the species-scan matches into the prompt as hints |
| `VEP_KEEP_ALIVE` | `-1` | how long Ollama keeps the model loaded; `-1` = forever, `0` = unload immediately, `5m` = five minutes |
| `VEP_RESULTS_DIR` | `results/` | where saved recommendations and reports go |

If a proxy is set, `NO_PROXY=localhost,127.0.0.1` is usually needed.

## Project structure

```
vep_assistant.py         # engine — default path: classifier → resolver → checker
factors.json             # the factor scheme (values, hard gates, exclusions, joint rules)
priority_by_factor.json  # the current DRIVES dump (written 15 Sept); read directly. The
                         #   derivation from DRIVES + the catalogue is the fallback when the
                         #   file is absent. NOT mentor-signed — nothing in the repo is.
vep_options.json         # the 68-option catalogue
vep_consequences.json    # 41 VEP consequence terms (SO definitions)
training_examples.json   # 23 stage-B examples: the --two-pass in-context corpus. The default
                         #   path does not read them.
requirements.txt         # openai (CLI) + flask (the web UI in ../work/webapp/)
legacy/                  # NOT USED BY THE TOOL — the stage-B benchmark, a reference PDF and
                         #   saved output from March 2026. See legacy/README.md.
```

Design rationale, deterministic invariant harnesses (79 checks, no GPU), the full option
dossier and the generation pipeline live one level up in `work/`; see `../work/README.md`.

## Knowledge base

**68 VEP options**, from the release/115 `public-plugins` source reconciled against the
release-116 documentation pages, with `species_restriction`, dependencies, conflicts and the
factor-keyed priorities the resolver reads.

**What the shipped path uses.** The five factor values from the classifier, and nothing else.
They index the priority table; the checker then applies conflicts, gates and dependencies,
ranking a conflict by the priority the FACTOR RESOLUTION gives each option. The 23 examples in
`training_examples.json` play no part — they are read only under `--two-pass`.

**Evaluation scenarios.** The pipeline is scored on the **31 candidate scenarios** in
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
priorities. See `../work/research/taxonomy_proposal.md`. It survives only as the labels on
`training_examples.json` and in `legacy/`; it decides nothing. The checker's conflict
tie-break stopped reading it on 2026-09-13 and now ranks on the factor resolution.

## Evaluation

The shipped path is exercised by the harnesses in `../work/harness/`:

- `factor_accuracy.py` — the classifier's five-factor output on the 31 review scenarios.
- `factor_grid.py` — the 600-query stress grid (species, origin, size, region, goal). The
  cases and labels were written by Claude and are not yet reviewed by a mentor.
- `verify_pipeline.py` — the 79 deterministic invariant checks (no GPU, seconds).

Results land in `../work/results/`, which is git-ignored; a fresh clone will not have them,
run the harnesses to regenerate. The latest saved set is
`../work/results/final_2026-09-15/`; those runs had `VEP_SPECIES_HINT=1` on and have not
been re-run since it was switched off by default.

`legacy/evaluate.py` is the **stage-B** benchmark: it scores the two-pass draft
recommender's text on 8 hardcoded test queries, weighted by the retired use-case snapshot
kept in `../work/harness/legacy/`. It never exercises the shipped one-call path. Kept only
for comparison work against older figures.

## Known limitations

**Priorities are provisional.** The five-factor priority table is not fully mentor-signed;
it is derived from 31 examples with mentor comments. Every reported number is directional
until sign-off. The priorities live in `DRIVES` inside `vep_assistant.py` plus the
per-option blocks in the catalogue. `priority_by_factor.json` on disk (present in both
default paths since 15 Sept) is the current dump of that derivation, and while a file exists
it is what the engine reads. A demotion in `DRIVES` does nothing until `seed_priorities.py`
is re-run to overwrite the JSON. When a signed-off table lands, drop it in at the same path.

**Class-weighted F1 is a directional headline, not a mentor-blessed number.** Last measured
at 0.900 (`../work/harness/exp/class_weighted_f1.py`), with `VEP_SPECIES_HINT=1` on and not yet
re-run since it was switched off by default. The weights are ours.

---

## Legacy: the two-pass path (`--two-pass`)

**What it was.**

- Before September 2026 the default was **two model calls**: the classifier, then a second
  call — the *recommender* — that drafted the configuration prose.
- The checker rebuilt the RECOMMENDED set from the factor tuple whatever the draft said, so
  single-pass and two-pass produce the same set at the option level on all 31 measured
  scenarios.
- The draft still contributed the per-option prose that `--explain` printed, plus a handful
  of extra options the checker had to tag and cap.

**Why it was retired.**

- Single-pass: ~1.2 s per query. Two-pass: ~18 s. (26b local.)
- Four-arm ablation in `../work/results/final_2026-09-15/`: single-pass beat every two-pass
  variant (three different in-context corpora) on plain and class-weighted F1.
- Last two-pass number: `enable-F1 = 88.0% ± 0.2` (2026-09-04, L4).

**What's still here.**

- `--two-pass` runs the draft-recommender call, for comparison work.
- `--think` and `--semantic` were removed on 2026-09-16; passing either now exits with a
  reason.

**Two caveats that apply here and to `evaluate.py`, not to the shipped classifier.**

- Value field is ignored in scoring: `gnomad_af: "gnomAD exome"` vs `gnomAD genome` counts
  as the same enable.
- Response parsing is line-level: a line mixing "enable X" and "disable Y" ranks the first
  matching context. Citations are counted only in `[source: ...]` form.
