# Ask VEPai

**A local assistant that turns a plain-English description of a variant-analysis scenario into
an [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) web-form
configuration, with the reasoning that put each option there.**

Built as a GSoC project with EMBL-EBI. Runs against a local model via
[Ollama](https://ollama.com/); no query leaves the machine.

## What it does

Given a scenario like *"I have somatic variants from a tumour-normal pair, mostly SNVs, and I
want clinical interpretation on the coding hits"*, it:

1. Reads the scenario into a **factor tuple**: five factors (species, origin, variant size,
   region focus, analysis goal), plus the organism when the scenario names one.
2. Resolves the tuple to a set of VEP options through a priority table
   (`priority_by_factor.json`).
3. Runs a **constraint checker**: species and assembly restrictions, per-species data, option
   conflicts, missing dependencies, and the Restrict-results gate.
4. States every assumption it made about a fact the query left unsaid, or asks when the answer
   would change what is recommended.
5. Prints the configuration in the web form's own language (or a VEP command line, with `--cli`).
6. If the scenario asks for only some genes or a class of consequences, which the input form
   cannot restrict, it says how to filter the results page after the run.

Two secondary modes: **explain a VEP output annotation**, and a **decision trace** (`--explain`)
that shows why each option is where it is.

## Quick start

Python 3.9+, [Ollama](https://ollama.com/) running locally, and one pulled model.

```bash
ollama serve
ollama pull gemma4:26b
pip install -r requirements.txt

python3 vep_ai_demo/vep_assistant.py "somatic tumour-normal, clinical interpretation on the coding hits"
```

Only `openai` is required. Behind a proxy you need `NO_PROXY=localhost,127.0.0.1`, or every
Ollama call returns 502.

**The full flag and environment reference is in [`vep_ai_demo/README.md`](vep_ai_demo/README.md)**,
and `python3 vep_ai_demo/vep_assistant.py --help` prints it.

## Usage

### Recommend a configuration

```bash
python3 vep_ai_demo/vep_assistant.py "somatic tumour-normal, want clinical interpretation on the coding hits"
```

Runs interactively if you omit the scenario.

**What comes back.** Any assumptions (`Assumed region_focus = …`), a *Detected scenario* block
with the five factor values, the organism for a non-human run and the assembly for a human one (each
with where it came from), any *NOT AVAILABLE FOR THIS SPECIES* lines, then the configuration
in the web form's language: **RECOMMENDED**, **OPTIONAL** add-ons, and **ALREADY ON** (options
the form ships ticked, named once so you know they are in effect). ALREADY ON is species-aware:
the form's human-only defaults (APPRIS, TSL, MANE, ClinVar, PubMed, 1000 Genomes AF) are not
listed on a non-human run.

A callset with both small variants and SVs gets **two configurations, one per size**, because
the web form cannot express both at once.

A scenario that asks for named genes (checked against HGNC's approved symbols) or for
loss-of-function consequences ends with a note on the results page's filters, because the
input form annotates every variant.

### Depth

| Flag | Meaning |
|---|---|
| *(none)* | RECOMMENDED plus the OPTIONAL add-ons the scenario justifies |
| `--minimal` | only the options you must tick; add-ons hidden |
| `--full` | switch on every add-on the scenario justifies |

### Decision trace

```bash
python3 vep_ai_demo/vep_assistant.py --explain "germline exome from a rare-disease patient"
```

Before the configuration it prints the factor tuple and, for every option, which factor value
raised it, what else voted, and which gate removed it. In the configuration each option carries
a "because …" line and Ensembl's own description of it. After the configuration, *HOW THIS WAS
CORRECTED* lists what the checker changed.

### When the question does not say

| Flag | Meaning |
|---|---|
| *(none)* | ask when the answer would change the RECOMMENDED set; otherwise assume it and say so. Needs a terminal; in a pipe it assumes and says so |
| `--no-ask` | never ask; state every assumption |
| `--quiet` | never ask and print no assumption lines |

### State a fact instead of inferring it

```bash
python3 vep_ai_demo/vep_assistant.py --origin somatic --assembly GRCh37 "tumour-normal SNVs, coding, clinical interpretation"
```

| Flag | Values |
|---|---|
| `--species` | `human` \| `non-human` (the organism itself goes in the query text) |
| `--origin` | `germline` \| `somatic` |
| `--size` | `small` \| `structural-CNV` \| `both` \| `small+structural-CNV` |
| `--assembly` | `GRCh37` \| `GRCh38` (`hg19` / `hg38` accepted; human only) |

A stated fact beats the classifier and skips the question. GRCh38 is assumed for human when no
assembly is stated, or when the text names both builds ("lifted over from hg19 to GRCh38"); the
output says so. A value outside this list is rejected with the list.

### Explain a VEP output annotation

```bash
python3 vep_ai_demo/vep_assistant.py explain-result "why is my variant annotated splice_donor_variant?"
```

Uses the 41 consequence terms in `vep_consequences.json`.

### Other flags

`--cli` appends the equivalent VEP command line. `--no-factor-think` makes the classifier answer
without reasoning first: about 0.9 s a query instead of about 4 s, and weaker on misleading
wording. `--two-pass` runs the retired draft call (see *Legacy* below).

## How it works

**One model call.** The classifier reads the scenario into the five factor values and the
organism: about 4 s with reasoning on (the default) on `gemma4:26b`, M5 Max. The organism name
is checked against Ensembl's 356-species list (`species_index.json`), matching whole words, so the
model cannot invent one and "guinea-pig" is not read as pig. Genomes of one Ensembl taxon count as
one species (a dog breed is dog; a dingo is not). If the model call fails, the tool says so and
exits 1; it never prints a configuration it did not read. Everything after that is deterministic: the priority table resolves the tuple, and the
checker builds the configuration. There is no model-written draft to repair.

The checker enforces:

- **Species.** Human-only options are not applicable to a non-human run. Plugins follow
  Ensembl's own per-plugin species lists (VEP_plugins release/116 `plugin_config.txt`), checked
  against the organism named. SIFT data exists for 13 species; each list is checked against the organism and the option
  named when missing. The release-116 form shows no per-species frequency file for any species.
  The CADD annotation file offered depends on the organism: three of CADD's four files are human
  only. Variant synonyms is offered to pig, the one other species Ensembl has it for.
- **Assembly.** Options whose data exists for one build only are dropped when the other build
  is stated: MANE, TSL, APPRIS, EVE, MaveDB, gnomAD SV, All of Us, GENCODE promoters, ClinVar SV
  and six further plugins are GRCh38 only. No option is GRCh37 only.
- **Restrict results.** `pick`, `pick_allele`, `per_gene`, `most_severe` and `summary` are never
  offered.
- **Dependencies.** A missing prerequisite is switched on and recorded.
- **Conflicts.** Conflict edges come from the "Incompatible with" column of Ensembl's options
  page and from the one Restrict-results drop-down; one side is dropped and the output says which.
- **Add-ons.** An add-on is offered only if the organism and the stated build can use it.

## Choice of model

The model's only job is to read the question into the factor values and the organism, returned
as a small JSON object. `gemma4:26b` is the default and the model every figure below was
measured with. `gemma4:e4b` fits on a machine with less than about 20 GB of free memory; set
`VEP_MODEL` to use it.

## Project structure

```
vep_ai_demo/             THE TOOL: reads only this folder, so it runs on its own
  vep_assistant.py         the engine: classifier -> resolver -> checker -> output
  vep_options.json         the 70-option catalogue; each fact's source in its `provenance`
  factors.json             the factor scheme (values, hard gates, exclusions)
  priority_by_factor.json  the priority table the resolver reads
  species_index.json       Ensembl's species names, and which genomes are one species (by taxon)
  hgnc_symbols.json        HGNC approved gene symbols, for the results-filter note
  vep_consequences.json    41 VEP consequence terms, for explain-result
  ensembl_docs/            Ensembl's options and plugins pages, parsed, for --explain
  legacy/                  NOT USED BY THE DEFAULT PATH: the retired two-pass code and its
                           23 Claude-written examples. See vep_ai_demo/legacy/README.md

evidence/                THE EVIDENCE
  current_evidence/        today's measurements of the tool: start with its README
  legacy_decisions/        why the tool is built this way; each decision and what backed it
  legacy_superseded/       what was replaced, and the former names of files
reference/               Ensembl's own pages and source files the catalogue is built from
```

`vep_ai_demo/` holds the only copy of every data file the engine reads. Some documents cite the
project's mentor correspondence and review sheets; those are kept in the private working repository.

## Knowledge base

**70 VEP options**, as the release-116 web form offers them. Names and descriptions are
Ensembl's own words for 68 of them (the other two, `clinvar` and `species_frequency`, are our
groupings of controls the form offers indirectly). Every option's `provenance` records the file
and line each fact came from: the form code (`InputForm.pm`, `Object_VEP.pm`), the plugin
config, and the options, plugins and form pages. The on/off defaults were checked against the
form code for every option.

**What the default path uses.** The five factor values and the organism from the classifier,
and nothing else. They index the priority table; the checker then applies gates, conflicts and
dependencies, ranking a conflict by the priority the factor resolution gives each option. The 23
examples in `vep_ai_demo/legacy/training_examples.json` play no part; only `--two-pass` reads them.

**Evaluation scenarios.** The **31 review scenarios** in `evidence/current_evidence/cases/iced.json` were generated and
screened by our generation code (private working repository) and reviewed by the Ensembl mentors.

The five factors:

| Factor | Values | Kind |
|---|---|---|
| `species` | human · non-human | hard gate |
| `origin` | germline · somatic | hard gate (`somatic` switches off the frequency pre-filter) |
| `variant_size_class` | small · structural-CNV (multi-select) | hard gate |
| `region_focus` | coding · regulatory-noncoding (multi-select) | hard gate |
| `analysis_goal` | basic-consequence · clinical-interpretation · population-frequency (multi-select) | priorities only |

The earlier single-label use-case scheme (rare-disease-germline / somatic-cancer / …) was
retired in September 2026: a mouse somatic SV is somatic **and** structural **and** non-human
at once, and one bucket picks the wrong priorities. The design is `taxonomy_proposal.md` (private working repository).
It survives only as labels in `vep_ai_demo/legacy/` and decides nothing.

## Evaluation

**[`evidence/current_evidence/README.md`](evidence/current_evidence/README.md)** has every figure,
the question behind it, how it is scored, where it fails, and the file it comes from. In short
(`gemma4:26b`, temperature 0, reasoning on unless marked):

| experiment | reasoning on | reasoning off |
|---|---|---|
| 150 tricky cases: all four versions of a case read right | 145/150 (repeats: 143, 146) | 137/150 (137, 137) |
| …of which the misreads leave the RECOMMENDED options unchanged | 149/150 | |
| 31 review scenarios: same RECOMMENDED options as from the true factors | 30/31 | 29/31 |
| 754 organism names in Ensembl's index, named right (plain / with a decoy) | 746 / 749 | 746 / 745 |
| 78 scenarios with one fact removed: assumed and disclosed | 73/78 (repeats: 72 each) | 72/78 (72 each) |

**Against commercial closed-source models** ([experiment 6](evidence/current_evidence/README.md#6--chat-models-20-cases)):
Ask VEPai, running a local open model, does better than bare commercial chat models given the same job, the
current state-of-the-art Claude Opus 5.5 included. On 20 cases, with the same short instruction and no
rules, the best of them reaches about half of what the priority table recommends, and every one recommends
options that cannot work for the case or filters that silently delete results; Ask VEPai recommends none.

| arm | table options recommended (of 92, 16 cases) | options that cannot work for the case (20 cases) | row-deleting filters (20 cases) |
|---|---|---|---|
| **Ask VEPai** (gemma4:26b, local) | **92** | **0** | **0** |
| Claude Opus 5.5, with Ensembl's VEP documentation | 48 | 8 | 2 |
| Claude Opus 5.5 | 32 | 12 | 11 |
| ChatGPT (website, Thinking on) | 14 | 14 | 3 |

The first column scores against our own priority table, so it shows the chat models do not follow our
rules; the other two rest on Ensembl's species lists and on what VEP can compute for a structural variant,
and hold whatever the table says.

At temperature 0 the seed does not change the answer; the repeats measure run-to-run variation from
parallel requests. The 31-scenario figures score against the tool's own priority table, so they
measure how much a misread moves the output, not whether the table is right.

`vep_ai_demo/legacy/evaluate.py` is the retired two-pass benchmark. It never exercises the
default path and is kept only as a record; see `vep_ai_demo/legacy/README.md`.

## Known limitations

**Priorities are provisional.** The priority table is not mentor-signed yet, so every figure is
directional until it is. `priority_by_factor.json` is the single authored source; nothing
derives it.

**An unstated goal is sometimes filled in.** With reasoning on, the classifier occasionally
answers `basic-consequence` for a query that states no goal ("Show me variants affecting BRCA1,
BRCA2"), so the tool neither asks nor prints that it assumed one. The configuration is the same as
the fallback it would otherwise use.

**Three species settings were corrected against the rendered release-116 form** (28 September): the
per-species frequency option is no longer recommended, because the form shows no non-human frequency
file for any species; CADD is offered to the Red Jungle fowl genome only, not the broiler chicken; and
pig is offered Variant synonyms. The missing frequency files look like an issue on Ensembl's side
(`InputForm.pm` release 116, lines 1205–1209). What the form showed is in
`reference/ensembl_docs_116/form_species_check_2026-09-28.json`.

**Gene lists and consequence classes cannot be set on the input form.** The tool does not
restrict the configuration by gene or by consequence; it prints how to filter the results
page instead.

**Enable-F1 is undefined on the default path.** It scored a model-written draft that the
default path no longer produces.

AI Usage Statement:

Claude Opus 4.7, 5.0 and 5.5 were used to assist with coding research and write ups. Everythign were oversaw manually to make sure it's all as accurate as possible and for reading nicely.

---

## Legacy: the two-pass path (`--two-pass`)

Before September 2026 the default path made **two calls**: the classifier, then a second model
call that drafted the configuration. The checker rebuilt the RECOMMENDED set from the factor
tuple whatever the draft said, so on the 31 scenarios single-pass and two-pass produce the same
set. The draft call took about 18 s a query, and the default path now skips it. The code lives
in `vep_ai_demo/legacy/two_pass.py` and runs with `--two-pass`.

On the 2026-09-23 four-arm ablation, single-pass scores plain F1 0.940 against 0.932, 0.918 and
0.916 for three two-pass variants (each with a different in-context example corpus). On
class-weighted F1 it scores 0.962; the best two-pass variant scores 0.965 and the other two 0.912
and 0.906. Single-pass is kept because it makes one call instead of two for that result.
