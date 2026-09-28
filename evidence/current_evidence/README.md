# Current evidence — the system as it runs today

Ask VEPai turns a plain-English variant-analysis scenario into a recommended Ensembl VEP web-form
configuration, with a reason for every option, running on a local model.

The tool makes **one model call**: `gemma4:26b`, reasoning on, reads the scenario into five factor values
(species, origin, variant size, region, analysis goal) plus the organism's name. Deterministic code turns
those into the configuration. Why it is built this way is in [`../legacy_decisions/`](../legacy_decisions/).

Five experiments measure it. Each reports the tool's setting (reasoning on) beside reasoning off.

| experiment | question | reasoning on | reasoning off |
|---|---|---|---|
| [1 · 150 tricky cases](#1--150-tricky-cases) | Does the model read the five factors when the wording misleads? | **143/150** | 135/150 |
| [2 · 31 review scenarios](#2--31-review-scenarios) | Does the user get the right configuration for plainly worded scenarios? | **29/31** | 30/31 |
| [3 · 754 organism names](#3--754-organism-names) | Does the model name the organism? | **746/754** | 746/754 |
| [4 · the mentors' four queries](#4--the-mentors-four-queries) | What does the model make of the mentors' own example queries? | stable on 3 of 4 | not run |
| [5 · 78 missing facts](#5--78-missing-facts) | When a fact is missing, does the tool ask, or assume a safe value and say so? | **73/78** | 72/78 |

Every run: `gemma4:26b` on an Apple M5 Max, temperature 0, seed 42. At temperature 0 the seed does not
change the answer (seeds 42 and 43 give the same text on the same query), so the seeds 42, 43 and 44 of
experiments 2 and 4 are three calls of the same question. The run itself can move an answer: parallel
requests and the server's prompt cache change the arithmetic slightly, and a near-tie can then go the
other way. Experiments 1, 2, 4 and 5 were run again on 2026-09-27 with the same prompt and model; those
files end in `_repeat1` to `_repeat3`, and each section gives their figures. Each script writes to
[`results/`](results/) under its own name, with `reasoning_on` or `reasoning_off`. Experiments 2 and 5 read
their cases from [`cases/`](cases/); the others carry their cases in the script.

---

## 1 · 150 tricky cases

`factors_150_tricky_cases.py`, with `factors_150_species_through_tool.py` and `factors_150_settings_effect.py`

**Question.** Does the model read each factor correctly when the wording is built to mislead it?

**Cases.** 5 factors × 5 kinds of trick × 6 cases = 150. The tricks: the cue word is negated ("not a mouse
study"), used in another sense, the name of a tool, about something other than this data, or overruled by
biology. Each case is asked four ways, with the other four factors stated plainly:

| version | what it tests |
|---|---|
| plain | the fact stated plainly |
| trap | a misleading cue word; the answer must not move |
| twin | the same sentence without the trick; the answer must flip |
| absent | the fact removed; the answer must be "unstated" |

The cases are in `results/factors_150_tricky_cases_list.csv`.

**Why this design.** The tricks are the ways a cue word points the wrong way. A keyword scan reads the
first cue it finds: it took "going down this rabbit hole" as rabbit, "used as a guinea pig" as pig and "not
a mouse study" as mouse, and the same happens with "tumour", "deletion" or "clinical" in the other factors
(the 24 hand-written traps in [`../legacy_superseded/keyword_traps/`](../legacy_superseded/keyword_traps/)).
The four versions follow two published test designs:

- **trap** is an invariance test from CheckList (Ribeiro et al., "Beyond Accuracy: Behavioral Testing of
  NLP Models with CheckList", ACL 2020): a change that must not move the answer.
- **twin** is a contrast set (Gardner et al., "Evaluating Models' Local Decision Boundaries via Contrast
  Sets", Findings of EMNLP 2020): a small edit that must flip the answer. Trap and twin are scored as a
  pair, right on both.
- **absent** tests what the tool needs to ask or to state an assumption: that a missing fact is read as
  "unstated" ([`../legacy_decisions/missing_facts/`](../legacy_decisions/missing_facts/)).

Every factor × trick cell holds 6 cases with its true values balanced (3/3, or 2/2/2 for the goal), so no
cell is left empty and each factor has 30: a clean sweep bounds its error rate below 10% (rule of three).

**Scored.** A case counts only if all four versions are right. Species is scored the way the tool reads
it: the tool sets species to non-human whenever the model names an animal, so
`factors_150_species_through_tool.py` re-reads the 30 species cases through that path.
`factors_150_settings_effect.py` asks, for every miss, whether it changes what the user is told to tick:
it runs the tool on the true factors and on the model's reading (no model call) and compares the
RECOMMENDED options.

**Results.**

| | reasoning on | reasoning off |
|---|---|---|
| plain | 150/150 | 150/150 |
| trap | 146/150 | 140/150 |
| twin | 150/150 | 149/150 |
| absent | 147/150 | 146/150 |
| **all four right** | **143/150** | **135/150** |
| RECOMMENDED options unchanged by the misreads (`factors_150_settings_effect.py` on `factors_150_tricky_cases_reasoning_on.json`, written to `factors_150_settings_effect_reasoning_on.json`) | 148/150 | not scored: it reads species before the tool's correction |
| by factor, all four right of 30: species · origin · size · region · goal | 29 · 29 · 30 · 30 · 25 | 26 · 26 · 28 · 29 · 26 |
| time per query, one user (40 queries) | 5.0 s | 1.0 s |
| files | `factors_150_tricky_cases_reasoning_on.json`, `factors_150_species_through_tool_reasoning_on.json` | `factors_150_tricky_cases_reasoning_off.json`, `factors_150_species_through_tool_reasoning_off.json` |

Baselines on the same 150: keyword rules 27/150; always answering the commonest value 0/150.

**Where it fails.** With reasoning on, five of the seven misses are the analysis goal: two fill in
`basic-consequence` when no goal was stated, so the tool does not ask; two are traps that mix up clinical
and population-frequency goals; one reads "clinical precision" as a clinical goal. Two of the seven change
the RECOMMENDED options, both by adding options (anal-word-1 and anal-doma-5). Of the other five, three only
lose the "Assumed …" line the tool would have printed. Reasoning off gets 10 cases wrong that reasoning on gets
right (three species, three origin, two variant-size, one region, one goal) and 2 right that reasoning on
gets wrong. Its raw species answer, before the tool's correction, scores 125/150.

**Repeats.** Three more runs (`factors_150_tricky_cases_reasoning_{on,off}_repeat{1,2,3}.json`,
`factors_150_species_through_tool_reasoning_off_repeat{1,2,3}.json`):

| | run above | repeat 1 | repeat 2 | repeat 3 |
|---|---|---|---|---|
| reasoning on, all four right | 143 | 141 | 142 | 142 |
| reasoning on, RECOMMENDED unchanged | 148 | 147 | 148 | 146 |
| reasoning off, all four right, species through the tool | 135 | 135 | 135 | 135 |

With reasoning on, six misses recur in all four runs (spec-doma-2 trap, orig-word-3 absent, anal-word-1
trap, anal-tool-4 absent, anal-doma-4 trap, anal-doma-5 trap); anal-nega-3, anal-word-2, vari-doma-6,
orig-doma-6 and vari-atta-3 miss in some runs only.

**Limits.** The cases were written by us; the `label_ok` column of the case list is not yet filled in.

---

## 2 · 31 review scenarios

`factors_31_review_scenarios.py`

**Question.** For plainly worded scenarios, does the user get the configuration the true factors give?

**Cases.** The 31 scenarios the mentors reviewed ([`cases/iced.json`](cases/iced.json)), each with its five factor labels.

**Scored.** Per factor, whether the model's answer matches the label, and whether it changes the
RECOMMENDED options at all: a label mismatch that leaves the configuration unchanged costs the user
nothing. End-to-end F1 compares the configuration from the model's factors with the one from the true
factors. The three calls per scenario (seeds 42, 43 and 44) gave identical answers, and so did a repeat
run (`factors_31_review_scenarios_reasoning_on_repeat1.json`).

**Results.**

| | reasoning on | reasoning off |
|---|---|---|
| **same RECOMMENDED options as from the true factors** | **29/31** | **30/31** |
| end-to-end F1 | 0.960 | 0.967 |
| all five labels exactly right | 21/31 | 22/31 |
| labels right: species · origin · size · region · goal | 31 · 28 · 30 · 31 · 24 | 31 · 28 · 30 · 31 · 25 |
| files | `factors_31_review_scenarios_reasoning_on.json` | `factors_31_review_scenarios_reasoning_off.json` |

**Where it fails.** Of the 11 label misses with reasoning on (in 10 scenarios), 9 change nothing the user
sees: origin moves only one option, and a goal answered as [basic, clinical] where the label says
[clinical] gives the same options. The two that change the configuration are one variant-size and one goal
reading.

**Limits.** The scenarios and their labels were written by us and reviewed by the mentors. Plainly worded,
so easier than experiment 1.

---

## 3 · 754 organism names

`organism_754_names.py`

**Question.** Does the model name the organism the data comes from?

**Cases.** Every non-human name in Ensembl's species list (`vep_ai_demo/species_index.json`): 754 names for
270 species, scientific and common names, breeds and strains. Each name is asked twice, with the other
four factors stated plainly:

- **plain**: the organism is the only one named.
  "The samples are from a pig. We called acquired somatic CNVs in regulatory regions. I want to know which
  are pathogenic."
- **with a decoy**: a second organism, picked at random from the same list, is named as something the data
  is not from; the answer must still be the sample's organism.
  "Not a pelodiscus sinensis study: the samples are from a pig. We called acquired somatic CNVs …"
  The four decoy sentences are "My supervisor works on X, but the samples are Y", "The variants were first
  reported in X; ours are from Y", "We followed a protocol written for X, and the samples are Y" and
  "Not an X study: the samples are Y".

The cases are in `results/organism_754_names_list.csv`.

**Scored.** The organism the tool looks up from the model's answer, at species level as the engine groups
Ensembl's genomes: by taxon, so a breed or strain of one taxon counts as that species, and a strain Ensembl
files under its own taxon (the mouse CAST/EiJ is *Mus musculus castaneus*) counts as a species of its own,
because the per-species data lists treat it so. Also whether the model's human/non-human answer
contradicts the organism it named.

**Results.**

| kind of name | example | n | on, plain | on, decoy | off, plain | off, decoy |
|---|---|---|---|---|---|---|
| scientific | Nothobranchius furzeri | 239 | 238 | 238 | 238 | 236 |
| common | nine-banded armadillo | 208 | 208 | 207 | 208 | 206 |
| also an ordinary word | turkey, cattle | 55 | 55 | 55 | 55 | 55 |
| breed or strain | Rambouillet sheep | 134 | 130 | 132 | 131 | 132 |
| flagged as a common false hit | drill, guinea pig | 8 | 7 | 8 | 7 | 8 |
| with an assembly or hybrid tag | muscovy duck (domestic type) | 110 | 108 | 109 | 107 | 107 |
| **all** | | **754** | **746** | **749** | **746** | **744** |

| | reasoning on | reasoning off |
|---|---|---|
| organism name and human/non-human answer contradict | 0/1508 | 266/1508 |
| files | `organism_754_names_reasoning_on.json` | `organism_754_names_reasoning_off.json` |

**Where it fails.** With reasoning on, 13 of the 1,508 answers. Four are the model: "drill" and "eastern
happy" answered unstated, and "hippocampus comes" answered unstated plain and as hyrax beside a decoy. Nine
drop a strain or hybrid tag Ensembl files under a separate taxon: "mouse" for the mouse strains CAST/EiJ,
JF1/MsJ and PWK/PhJ (4), "bos taurus" or "cattle" for the Bos taurus hybrid (3), and "common carp" for the
German mirror and Hebao red carp (2). The tool then offers the data of the species named. With reasoning
off the name is about as good, but the human/non-human answer contradicts the named animal 266 times; the tool
corrects that from the name.

**Limits.** The test cases are Ensembl's own names. To look a name up, the species list also holds 24
names derived from them, each marked `derived`: the plain scientific name of each species Ensembl hosts
only by strain or sex ("heterocephalus glaber" for `heterocephalus_glaber_female` and `_male`), and
"muscovy duck" for Ensembl's "muscovy duck (domestic type)". One run at temperature 0.

---

## 4 · The mentors' four queries

`mentor_queries.py`

**Question.** What does the model read from the example queries the mentors gave?

**Cases.** The four queries of the 2026-09-16 meeting agenda, as given.

**Scored.** Not against labels: the factors are shown with unstated left visible, three calls per query,
to see what the model supplies and whether it is stable.

**Results** (reasoning on; `mentor_queries_reasoning_on.json`):

| query | origin | analysis goal | same in all three calls |
|---|---|---|---|
| Find variants in genes associated with colorectal cancer. | somatic | clinical | yes |
| Which variants in my sample affect genes associated with breast cancer? | unstated (first call), somatic (second and third) | clinical | no |
| Show me variants affecting BRCA1, BRCA2 | unstated | basic-consequence, filled in by the model | yes |
| Which variants produce loss-of-function consequences in my hereditary cancer gene panel? | germline | clinical | yes |

Species is unstated in all four (human is assumed, and the tool says so); size and region are empty.

**Where it fails.** A gene list or a loss-of-function filter is outside the five factors. The tool says the
form cannot restrict by gene or consequence and points to the filter on Ensembl's results page.

**Repeat.** A second run (`mentor_queries_reasoning_on_repeat1.json`) read origin as unstated in all three
calls for both cancer queries; the other two queries read as above. Origin for these two queries is not
stable between runs.

**Limits.** Four queries. Reasoning off not run.

---

## 5 · 78 missing facts

`missing_facts_78_rewrites.py`

**Question.** When the scenario leaves a fact out, does the tool notice, and then either ask or assume a
safe value and say so?

**Cases.** 78 rewrites of the 31 review scenarios, each with one fact's wording removed
([`cases/ablated_queries.json`](cases/ablated_queries.json)): origin 20, variant size 23, region 23, analysis goal 12. A model
rewrote each scenario; a rewrite was kept only if a re-read found the removed fact unstated and the other
four unchanged.

**Scored.** Each rewrite goes through the tool as a user runs it. The missing fact must come back as a
stated assumption ("Assumed origin = somatic"), which means the model read it as unstated and the tool
applied its rule for that fact:

| missing fact | what the tool does |
|---|---|
| species | assumes human and says so |
| origin | assumes somatic and says so: that keeps the common-variant filter off, which would discard real tumour variants |
| variant size | assumes both sizes and says so |
| region | assumes both regions and says so |
| analysis goal | asks, because every answer changes the RECOMMENDED options; without a terminal to ask on it assumes a basic consequence call and says so |

A rewrite fails when the model supplies the missing fact itself: the tool then neither asks nor says it
assumed anything.

**Results.**

| | reasoning on | reasoning off |
|---|---|---|
| **reached the rule and said so** | **73/78** | **72/78** |
| origin · size · region · goal | 18/20 · 23/23 · 22/23 · 10/12 | 18/20 · 23/23 · 23/23 · 8/12 |
| files | `missing_facts_78_rewrites_reasoning_on.json` | `missing_facts_78_rewrites_reasoning_off.json` |

How often the tool asks is fixed by that table, with no model involved: 12 of the 78, all analysis goal.

**Where it fails.** With reasoning on, the model supplied origin twice, region once and a
`basic-consequence` goal twice, so the tool did not ask those two users. The goal fill is the same
failure as in experiment 1.

**Repeats.** Three more runs with reasoning on (`missing_facts_78_rewrites_reasoning_on_repeat{1,2,3}.json`):
72/78 each (origin 17/20, size 23/23, region 21/23, goal 11/12).

**Limits.** The rewrites come from our own scenarios; species has no rewrites among the 78.

---

## Re-run

```bash
export NO_PROXY=localhost,127.0.0.1 OLLAMA_BASE_URL=http://localhost:11434/v1
# 1 · 150 tricky cases
python3 evidence/current_evidence/factors_150_tricky_cases.py --reader reasoning_on --workers 8 --latency-sample 40    # ~30 min
python3 evidence/current_evidence/factors_150_tricky_cases.py --reader reasoning_off --workers 8 --latency-sample 40   # ~8 min
python3 evidence/current_evidence/factors_150_species_through_tool.py results/factors_150_tricky_cases_reasoning_on.json results/factors_150_species_through_tool_reasoning_on.json
VEP_FACTOR_THINK=0 python3 evidence/current_evidence/factors_150_species_through_tool.py results/factors_150_tricky_cases_reasoning_off.json results/factors_150_species_through_tool_reasoning_off.json
python3 evidence/current_evidence/factors_150_settings_effect.py evidence/current_evidence/results/factors_150_tricky_cases_reasoning_on.json   # no model
# 2 · 31 review scenarios
python3 evidence/current_evidence/factors_31_review_scenarios.py --seeds 42,43,44 --json evidence/current_evidence/results/factors_31_review_scenarios_reasoning_on.json
VEP_FACTOR_THINK=0 python3 evidence/current_evidence/factors_31_review_scenarios.py --seeds 42,43,44 --json evidence/current_evidence/results/factors_31_review_scenarios_reasoning_off.json
# 3 · 754 organism names
python3 evidence/current_evidence/organism_754_names.py --reader reasoning_on --workers 8     # ~1 h
python3 evidence/current_evidence/organism_754_names.py --reader reasoning_off --workers 8    # ~15 min
python3 evidence/current_evidence/organism_754_names.py --rescore evidence/current_evidence/results/organism_754_names_reasoning_{on,off}.json   # after a species-list change, no model
# 4 · the mentors' four queries
python3 evidence/current_evidence/mentor_queries.py --seeds 42,43,44 --json evidence/current_evidence/results/mentor_queries_reasoning_on.json
# 5 · 78 missing facts
python3 evidence/current_evidence/missing_facts_78_rewrites.py --reader reasoning_on     # ~10 min
python3 evidence/current_evidence/missing_facts_78_rewrites.py --reader reasoning_off    # ~2 min
```

Experiments 1 and 3 rewrite their case lists on every run; copy a reviewed CSV aside first.
