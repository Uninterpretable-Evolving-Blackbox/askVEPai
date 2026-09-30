# Current evidence — the system as it runs today

Ask VEPai turns a plain-English variant-analysis scenario into a recommended Ensembl VEP web-form
configuration, with a reason for every option, running on a local model.

The tool makes **one model call**: `gemma4:26b`, reasoning on, reads the scenario into five factor values
(species, origin, variant size, region, analysis goal) plus the organism's name. Deterministic code turns
those into the configuration. Why it is built this way is in [`../legacy_decisions/`](../legacy_decisions/).

Six experiments measure it. The first five report the tool's setting (reasoning on) beside reasoning off; the
sixth sets the tool beside general chat models.

| experiment | question | reasoning on | reasoning off |
|---|---|---|---|
| [1 · 150 tricky cases](#1--150-tricky-cases) | Does the model read the five factors when the wording misleads? | **145/150** (repeats 143, 146) | 137/150 (137, 137) |
| [2 · 31 review scenarios](#2--31-review-scenarios) | Does the user get the right configuration for plainly worded scenarios? | **30/31** | 29/31 |
| [3 · 754 organism names](#3--754-organism-names) | Does the model name the organism? | **746/754** (repeats 747, 746) | 746/754 (746, 746) |
| [4 · the mentors' four queries](#4--the-mentors-four-queries) | What does the model make of the mentors' own example queries? | stable within a run on 3 of 4 | stable on 4 of 4, and between runs |
| [5 · 78 missing facts](#5--78-missing-facts) | When a fact is missing, does the tool ask, or assume a safe value and say so? | **73/78** (repeats 72, 72, 72) | 72/78 (72, 72, 72) |
| [6 · chat models, 20 cases](#6--chat-models-20-cases) | Does a general chat model, given the same job, recommend what the reviewer asked for? | **52/76** of her options; best chat model 33/76 | not run |

Every run: `gemma4:26b` on an Apple M5 Max, temperature 0, seed 42. At temperature 0 the seed does not
change the answer (seeds 42 and 43 give the same text on the same query), so the seeds 42, 43 and 44 of
experiments 2 and 4 are three calls of the same question. The run itself can move an answer: parallel
requests and the server's prompt cache change the arithmetic slightly, and a near-tie can then go the
other way. Experiments 1 to 5 were run more than once with the same prompt and model; the extra runs end in
`_repeat1` to `_repeat3`, and each section gives their figures. Each script writes to
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

21 cases carry a hand fix where the generated wording clashed with its background, referred to something
never mentioned, or had a debatable label. Each fix applies to its own case only (`CASE_FIXES` in the
script, with the reason; the case list's last column says what it changes), so the other cases keep their
generated wording: one case is hand-written (a pig-kidney transplant), 14 have one background fact or one
sentence rewritten, and on seven versions a second reading is also scored right: "not just the consequence
types" also counts basic, and a frequency question that names a disease also counts clinical.

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
| trap | 148/150 | 142/150 |
| twin | 150/150 | 149/150 |
| absent | 147/150 | 146/150 |
| **all four right** | **145/150** | **137/150** |
| RECOMMENDED options unchanged by the misreads (`factors_150_settings_effect.py`, written to `factors_150_settings_effect_reasoning_on.json`) | 149/150 | not scored: it reads species before the tool's correction |
| by factor, all four right of 30: species · origin · size · region · goal | 29 · 29 · 30 · 30 · 27 | 25 · 26 · 29 · 29 · 28 |
| time per query, one user (40 queries) | 5.1 s | 1.0 s |
| files | `factors_150_tricky_cases_reasoning_on.json`, `factors_150_species_through_tool_reasoning_on.json` | `factors_150_tricky_cases_reasoning_off.json`, `factors_150_species_through_tool_reasoning_off.json` |

Baselines on the same 150: keyword rules 27/150; always answering the commonest value 0/150.

**Where it fails.** With reasoning on, five misses. Two fill in `basic-consequence` when no goal was stated
(anal-word-2, anal-tool-4) and one fills in germline when no origin was stated (orig-word-3), so the tool
neither asks nor prints its "Assumed …" line. One answers "unstated" for iPSCs from volunteers grown on mouse
feeder cells (spec-doma-2); the tool then assumes human, the right answer. One reads "clinical precision" as a
clinical goal (anal-word-1), the only miss that changes the RECOMMENDED options: it adds HGVS and Phenotypes.
Reasoning off gets 9 cases wrong that reasoning on gets right (four species, three origin, one variant-size,
one region) and 1 right that reasoning on gets wrong. Its raw species answer, before the tool's correction,
scores 127/150.

**Repeats.** Two more runs of each (the same file names ending `_repeat1` and `_repeat2`):

| | run above | repeat 1 | repeat 2 |
|---|---|---|---|
| reasoning on, all four right | 145 | 143 | 146 |
| reasoning on, RECOMMENDED unchanged | 149 | 148 | 149 |
| reasoning off, all four right, species through the tool | 137 | 137 | 137 |

With reasoning on, three misses recur in all three runs (orig-word-3 absent, anal-word-1 trap, anal-tool-4
absent); spec-doma-2 and anal-word-2 miss in two, orig-word-6, orig-doma-6 and vari-doma-6 in one.

**Limits.** The cases were written and read through by us; no mentor has checked the labels yet
(the `label_ok` column of the case list is empty).

---

## 2 · 31 review scenarios

`factors_31_review_scenarios.py`

**Question.** For plainly worded scenarios, does the user get the configuration the true factors give?

**Cases.** The 31 scenarios the mentors reviewed ([`cases/iced.json`](cases/iced.json)), each with its five factor labels.
Six rows carry a label correction, recorded in the row under `_relabelled_2026-09-30` with the old value and
the reason: rows 1 and 25 describe short variants as well as structural ones; row 1 also asks for
population frequencies, and row 19 is about "a patient", which the definitions count as clinical; rows 8,
28 and 30 never say germline or somatic, so origin is unstated.

**Scored.** Per factor, whether the model's answer matches the label, and whether it changes the
RECOMMENDED options at all: a label mismatch that leaves the configuration unchanged costs the user
nothing. End-to-end F1 compares the configuration from the model's factors with the one from the true
factors. The three calls per scenario (seeds 42, 43 and 44) gave identical answers, and so did a repeat
run of each setting (`factors_31_review_scenarios_reasoning_{on,off}_repeat1.json`).

**Results.**

| | reasoning on | reasoning off |
|---|---|---|
| **same RECOMMENDED options as from the true factors** | **30/31** | **29/31** |
| end-to-end F1 | 0.966 | 0.962 |
| all five labels exactly right | 24/31 | 25/31 |
| labels right: species · origin · size · region · goal | 31 · 31 · 30 · 31 · 25 | 31 · 31 · 30 · 31 · 26 |
| files | `factors_31_review_scenarios_reasoning_on.json` | `factors_31_review_scenarios_reasoning_off.json` |

**Where it fails.** With reasoning on, 7 label misses in 7 scenarios. Six are the analysis goal, where the
model leaves out basic-consequence ([clinical] where the label says [basic, clinical]); a basic goal adds
nothing to a clinical one, so the user sees the same options. The one that changes the configuration is row
25: the model reads structural variants only, where the scenario also covers short variants. With reasoning
off, row 19 also changes the configuration: it reads the goal as population frequency only.

**Smaller models.** The same 31 scenarios, the same prompt and labels, reasoning on, three
calls each (identical): gemma4:e4b 27/31 same RECOMMENDED options, F1 0.962, 20/31 all five labels right;
gemma4:e2b 25/31, F1 0.945, 18/31 (`factors_31_review_scenarios_reasoning_on_{e4b,e2b}.json`). gemma4:26b,
above, 30/31, F1 0.966, 24/31.

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
| scientific | Nothobranchius furzeri | 239 | 238 | 238 | 238 | 237 |
| common | nine-banded armadillo | 208 | 208 | 207 | 208 | 206 |
| also an ordinary word | turkey, cattle | 55 | 55 | 55 | 55 | 55 |
| breed or strain | Rambouillet sheep | 134 | 130 | 132 | 131 | 132 |
| flagged as a common false hit | drill, guinea pig | 8 | 7 | 8 | 7 | 8 |
| with an assembly or hybrid tag | muscovy duck (domestic type) | 110 | 108 | 109 | 107 | 107 |
| **all** | | **754** | **746** | **749** | **746** | **745** |

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

**Limits.** The test cases are Ensembl's own names. To look a name up, the species list also holds 540
names derived from them, each marked `derived` and none of them a test case: the plain scientific name of
each species Ensembl hosts only by strain or sex ("heterocephalus glaber" for `heterocephalus_glaber_female`
and `_male`), "muscovy duck" for Ensembl's "muscovy duck (domestic type)", Ensembl's REST aliases ("swine",
"bovine"), abbreviated scientific names ("s scrofa" for "S. scrofa"), six adjectives of ours ("porcine"),
and yeast, C. elegans and fruit fly, which the form lists and REST /info/species does not. Every result
file is scored against this list.

**Repeats.** Two more runs of each setting, on the species list with the derived names
(`organism_754_names_reasoning_{on,off}_repeat{1,2}.json`):

| | run above | repeat 1 | repeat 2 |
|---|---|---|---|
| reasoning on: plain / decoy | 746 / 749 | 747 / 750 | 746 / 749 |
| reasoning off: plain / decoy | 746 / 745 | 746 / 744 | 746 / 743 |
| reasoning off: human/non-human answer contradicts the named animal | 266 | 263 | 259 |

With reasoning on the contradiction count is 0 in all three.

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

**Reasoning off** (`mentor_queries_reasoning_off.json`, `_repeat1.json`), the same in all three calls and in
both runs: colorectal cancer, origin germline, goal clinical; breast cancer, origin unstated, goal clinical;
BRCA1, BRCA2, species human, no goal (so the tool asks, where reasoning on fills in basic-consequence);
the hereditary panel, origin germline, goal basic-consequence and clinical.

**Limits.** Four queries.

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

**Repeats.** Three more runs of each setting (`missing_facts_78_rewrites_reasoning_{on,off}_repeat{1,2,3}.json`):
reasoning on 72/78 each (origin 17/20, size 23/23, region 21/23, goal 11/12); reasoning off 72/78 each, the
same as its first run (18/20, 23/23, 23/23, 8/12).

**Limits.** The rewrites come from our own scenarios; species has no rewrites among the 78.


---

## 6 · Chat models, 20 cases

`chat_models_20_cases.py`

**Question.** Could a general chat model do this job instead? Given the same instruction, does it recommend
the options the reviewer asked for, and avoid the ones that delete results or do not apply?

**Cases.** 20 (`cases/chat_models_20_cases.json`, each with its source and why it was picked):

| cases | source | why |
|---|---|---|
| 1–12 | scenarios the reviewer marked on the round-1 sheet (rows 3, 25, 31, 17, 29, 27, 21, 20, 24, 26, 6, 9) | the only cases with an agreed answer; she approved 8 as shown and edited 4 |
| 13–16 | the mentors' four example queries | gene lists and loss-of-function filters, which the form cannot set |
| 17–18 | trap versions from experiment 1 | misleading wording ("not a mouse study") |
| 19–20 | pig (clinical) and sheep (population frequency) | species with their own data lists |

Every arm gets the same instruction (`cases/chat_models_system_prompt.txt`): recommend which options to tick on
the VEP web form, and answer as RECOMMENDED, OPTIONAL, NOT ON THE FORM and ASSUMED. One question per case.

| arm | where | settings |
|---|---|---|
| Ask VEPai | this repository, run locally | `vep_assistant.py --no-ask`, gemma4:26b, reasoning on |
| ChatGPT | the chatgpt.com website| the default free model with the Thinking button on; memory off; a new chat per case, the instruction pasted above the question. Web search was also on (its answers cite ensembl.org) |
| Claude Sonnet 5 medium | the claude.ai website | Sonnet 5, medium effort (default); memory off; a new chat per case, the instruction pasted above the question |
| Claude Sonnet 5, with the VEP documentation | the Anthropic API | `claude-sonnet-5`, effort medium; the instruction as the system prompt; Ensembl's 27-page VEP web documentation PDF before each case |
| Claude Opus 5.5 (SOTA)| the Anthropic API | `claude-opus-5-5`, effort medium (default); the instruction as the system prompt |
| Claude Opus 5.5 (SOTA), with the VEP documentation | the Anthropic API | the same, with the same PDF |

An API call carries no memory and no earlier conversation: each case is a single call.

**Scored.** On cases 1–12, against the reviewer's round-1 sheet with her edits
(`cases/chat_models_reference.json`): 76 options she wants recommended, leaving out the ones the form
already ticks. Each answer is read entry by entry and mapped to catalogue options by the patterns in the
script; an entry that says not to tick something ("leave … unticked", "Filter by frequency: No filtering")
recommends nothing. Four counts:

- **her options in RECOMMENDED**: of her 76, how many the arm tells the user to tick
- **named anywhere**: how many it mentions at all, in any part of the answer
- **row-deleting filters**: recommended entries that switch on a filter that removes result rows (pick, one
  consequence per gene, most severe, coding regions only, the frequency filter) where she did not ask for it
- **short-variant tools on SV-only cases**: options the priority table marks not applicable to structural
  variants (SIFT, PolyPhen, the gnomAD and 1000 Genomes short-variant frequencies, SpliceAI …), recommended
  on cases 2–6, whose variants are structural only

Cases 13–20 have no agreed answer; they were read by hand.

**Results.**

| arm | her options in RECOMMENDED | named anywhere | row-deleting filters | short-variant tools on SV-only cases |
|---|---|---|---|---|
| **Ask VEPai** | **52/76** | **67/76** | **0** | **0** |
| Claude Opus 5.5 (API), with the VEP documentation | 33/76 | 56/76 | 2 | 7 |
| Claude Opus 5.5 (API) | 22/76 | 38/76 | 6 | 11 |
| ChatGPT (website) | 11/76 | 30/76 | 3 | 13 |
| Claude Sonnet 5 (API), with the VEP documentation | 9/76 | 39/76 | 3 | 17 |
| Claude Sonnet (claude.ai website) | 7/76 | 25/76 | 1 | 6 |

Files: `results/chat_models_20_cases_answers_{ask_vepai,opus55_pdf,opus55,chatgpt,sonnet5_pdf,claude_chat}.json`,
scores with every miss per case in `results/chat_models_20_cases_scores.json`. API cost for the 20 cases:
Opus 5.5 $0.50 (16 s a case), with the PDF $1.17 (23 s); Sonnet 5 with the PDF $0.54 (11 s).

**Where they differ.**

- **The chat models name the right kinds of tools but put them on the wrong cases.** Every chat arm
  recommends short-variant tools for structural variants; Ask VEPai never does, because the priority table
  withholds them.
- **Filters that delete rows.** The chat arms recommend "coding regions only" for coding questions and "one
  consequence per variant" for summaries; both remove results the user cannot get back. Ask VEPai never
  recommends them.
- **The documentation helps the larger model most.** With the PDF, Opus 5.5 goes from 22 to 33 of her 76 and
  from 6 to 2 row-deleting filters; Sonnet 5 with it scores 9, against 7 for Sonnet in the chat app. It still misses the options that depend on the
  kind of variant or question: cell type and miRNA structure (6 cases each), gnomAD SV and Phenotypes (5 each).
- **Species (cases 19, 20).** Only Ask VEPai offers CADD for pig; both Opus arms say CADD is human-only,
  which Ensembl's plugin configuration contradicts. For sheep every arm says the form has no breed
  frequencies, which is right; Opus 5.5 with the PDF recommends Variant synonyms, which Ensembl has for human
  and pig only.
- **Regulatory only (case 17).** Sonnet 5 with the PDF recommends "coding regions only" for a question about
  regulatory regions only.
- **Where the chat models do better.** They explain what the form cannot do (restricting to a gene list, a
  loss-of-function filter) at more length, and suggest external resources.

**Limits.** The reference favours Ask VEPai: it is our tool's round-1 output with the reviewer's edits, and she
approved 8 of the 12 as shown. One answer per case per arm; the two websites run with their own hidden
instructions and settings, and ChatGPT searched the web; the API arms have neither. The mapping from free text to options is by
pattern; the per-case misses in the scores file show every decision it made.

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
# 6 · chat models, 20 cases (the chat-app answers were pasted by hand; the key is read from ~/.anthropic_key)
python3 evidence/current_evidence/chat_models_20_cases.py --ours                                  # ~3 min
python3 evidence/current_evidence/chat_models_20_cases.py --ask claude-opus-5-5 --effort medium   # ~$0.50
python3 evidence/current_evidence/chat_models_20_cases.py --ask claude-opus-5-5 --effort medium --pdf   # ~$1.20
python3 evidence/current_evidence/chat_models_20_cases.py --detail                                # score only, no model
```

Experiments 1 and 3 rewrite their case lists on every run; copy a reviewed CSV aside first.
