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
| [6 · chat models, 20 cases](#6--chat-models-20-cases) | Does a general chat model, given the same job, recommend what the priority table recommends? | **92/103**; best chat model 53/103 | not run |

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

**Why this design.** The tricks are the ways a cue word points the wrong way. They were chosen from the
failures of a keyword scan, which reads the first cue it finds: it took "going down this rabbit hole" as
rabbit, "used as a guinea pig" as pig and "not a mouse study" as mouse, and the same happens with "tumour",
"deletion" or "clinical" in the other factors (the 24 hand-written traps in
[`../legacy_superseded/keyword_traps/`](../legacy_superseded/keyword_traps/)). CheckList, below, asks for exactly
this: its list of capabilities is a starting point, to be extended with ones specific to the task or domain.
Each trick matches a known problem in reading biomedical text; the references describe that problem, not
these tricks:

| trick | known problem | reference |
|---|---|---|
| negation ("not a mouse study") | negation detection | Chapman et al., "A simple algorithm for identifying negated findings and diseases in discharge summaries" (NegEx), J Biomed Inform 34(5):301–310, 2001 |
| attachment ("controls recruited through a cancer registry") | whether a term describes this data or something else; ConText's *experiencer* asks the same of a condition: the patient's, or someone else's ("family history of pneumonia") | Harkema et al., "ConText: an algorithm for determining negation, experiencer, and temporal status from clinical reports", J Biomed Inform 42(5):839–851, 2009 |
| tool name ("we keep COSMIC open for lookups") | a name that also means something else; the reference measures it for gene names ("CAT" is a gene in eight species; fly genes "can" and "lie"), not for tool names | Chen, Liu & Friedman, "Gene name ambiguity of eukaryotic nomenclatures", Bioinformatics 21(2):248–256, 2005 |
| word sense ("run it with clinical precision") | word sense disambiguation: an ambiguous biomedical term ("cold": temperature or the virus) read by its context | Jimeno-Yepes, McInnes & Aronson, "Exploiting MeSH indexing in MEDLINE to generate a data set for word sense disambiguation" (MSH WSD), BMC Bioinformatics 12:223, 2011 |
| domain ("man's best friend", "grown on mouse feeder cells") | reading that needs domain knowledge | no single source; closest are CheckList's taxonomy and named-entity capabilities (below) |

Most tool-name cases name a resource that suggests another factor (COSMIC for somatic, Delly for structural,
ENCODE for regulatory); the six species cases have few real tools to draw on (Salmon, Beagle) and are the
least realistic.

The four versions follow published test designs:

- **plain** is a minimum functionality test, and **trap** an invariance test, from CheckList (Ribeiro et al.,
  "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList", ACL 2020): simple examples that must
  work, and a change that must not move the answer.
- **twin** is a contrast set (Gardner et al., "Evaluating Models' Local Decision Boundaries via Contrast
  Sets", Findings of EMNLP 2020, 1307–1323): a small edit that must flip the answer. A case counts only if
  all four versions are right, which is the paper's contrast consistency: right on every element of the set.
- **absent** is an unanswerable question in the sense of SQuAD 2.0 (Rajpurkar, Jia & Liang, "Know What You
  Don't Know: Unanswerable Questions for SQuAD", ACL 2018, 784–789): when the text does not say, the answer must be
  "unstated". It is what the tool needs to ask or to state an assumption
  ([`../legacy_decisions/missing_facts/`](../legacy_decisions/missing_facts/)).

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
(the `label_ok` column of the case list is empty). The contrast-set paper asks for two things this set does not
have: cases written by experts, without a model in the loop (ours were written with a language model), and a
reading of the results as negative evidence only: a miss shows a failure, a pass does not prove the model
reads such wording correctly.

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

Where each part comes from:

| part | source |
|---|---|
| the 754 names | Ensembl's own species list, REST `/info/species` (saved as `reference/ensembl_source/rest_info_species_2026-09-28.json`); names derived for lookup are not test cases |
| the decoys | drawn at random (fixed seed) from the same list, always another species |
| kind of name | scientific: the name is the genome's scientific name; also an ordinary word: the name is in the English dictionary (`/usr/share/dict/words`); breed or strain, and tags: the form of Ensembl's name; common false hits: a list of ours with the reason for each (hedgehog, the SHH gene family; platypus, the variant caller; guinea pig, the idiom) |
| the sentences | ours: the four decoy frames and the background stating the other four factors |

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
what the priority table recommends, and avoid options that cannot work for the case or delete results?

**Cases.** 20 (`cases/chat_models_20_cases.json`, each with its source and why it was picked):

| cases | source | why |
|---|---|---|
| 1–12 | review scenarios (rows 3, 25, 31, 17, 29, 27, 21, 20, 24, 26, 6, 9) | plainly worded, with known factors |
| 13–16 | the mentors' four example queries | gene lists and loss-of-function filters, which the form cannot set; facts left unstated |
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
| Claude Opus 4.7, with the VEP documentation | the Anthropic API | `claude-opus-4-7`, effort medium, adaptive thinking on; the same PDF |

An API call carries no memory and no earlier conversation: each case is a single call.

**The standard: the priority table.** The priority table (`vep_ai_demo/priority_by_factor.json`) is this
project's statement of which options each kind of analysis should get: every recommendation Ask VEPai makes
comes from it. This experiment treats it as the correct answer. For each case with known facts, the reference
configuration is what the table recommends for those facts: for cases 1–12, the review scenarios' current
labels in `cases/iced.json`; for 17–20, the facts in `cases/chat_models_20_cases.json`. That is 103 options
over the 16 cases, leaving out the ones the form already ticks. Cases
13–16 leave facts unstated, so they have no reference.

**Scored.** Each answer's RECOMMENDED part is read entry by entry and mapped to catalogue options by the
patterns in the script; an entry that says not to tick something ("leave … unticked", "Filter by frequency:
No filtering") recommends nothing. Four counts:

- **reference options recommended** (16 cases): of the table's 103, how many the arm tells the user to tick
- **not in the reference** (16 cases): options the arm tells the user to tick that the table does not
- **cannot work for the case** (20 cases): recommended options Ensembl does not offer for the case's species
  (CADD for sheep, MaxEntScan for mouse), or options the table marks not applicable to structural variants
  (the gnomAD and 1000 Genomes short-variant frequencies, missense predictors, HGVS, protein identifiers …)
  on a case whose variants are structural only (cases 3–6)
- **row-deleting filters** (20 cases): recommended entries that switch on a filter that removes result rows:
  one consequence per variant or per gene, most severe, coding regions only, the frequency filter

Row-deleting filters do not depend on the table. Cannot-work rests on Ensembl's species lists and, for
structural variants, on the table's list of options that do not apply to them.

**Results.**

| arm | reference options recommended | not in the reference | cannot work for the case | row-deleting filters |
|---|---|---|---|---|
| **Ask VEPai** | **92/103** | **0** | **0** | **0** |
| Claude Opus 5.5 (SOTA, API), with the VEP documentation | 53/103 | 11 | 2 | 2 |
| Claude Opus 4.7 (API), with the VEP documentation | 42/103 | 26 | 9 | 9 |
| Claude Opus 5.5 (SOTA, API) | 38/103 | 16 | 5 | 11 |
| Claude Sonnet 5 (API), with the VEP documentation | 22/103 | 19 | 14 | 6 |
| ChatGPT (website) | 17/103 | 15 | 11 | 3 |
| Claude Sonnet 5 medium (claude.ai website) | 9/103 | 9 | 4 | 2 |

Case by case: Ask VEPai recommends every reference option on 15 of the 16 cases; no chat arm does so on any.
Cases where the user gets nothing that cannot work and no row-deleting filter, of 20: Ask VEPai 20, Opus 5.5
with the documentation 16, ChatGPT 15, Sonnet 5 on claude.ai 15, Sonnet 5 with the documentation 12, Opus 5.5
11, Opus 4.7 with the documentation 8.

Files: `results/chat_models_20_cases_answers_{ask_vepai,opus55_pdf,opus55,opus47_pdf,sonnet5_pdf,chatgpt,claude_chat}.json`;
every case's missed, extra, cannot-work and row-deleting options in `results/chat_models_20_cases_scores.json`.
API cost for the 20 cases: Opus 5.5 $0.50 (16 s a case), with the PDF $1.17 (23 s); Opus 4.7 with the PDF
$1.29 (13 s); Sonnet 5 with the PDF $0.54 (11 s).

**What Ask VEPai's 92/103 means.** Ask VEPai is the table applied to the model's reading of the case, so
its score measures that reading. The model read 77 of the 80 factor values right on the 16 cases. One miss
costs options: case 2 (review row 25) also covers short variants, and the model reads structural variants
only, so the 11 short-variant options are missing; experiment 2 reports the same miss. The other two (cases 5
and 7) leave out basic-consequence beside a clinical goal, which changes no option. On the four queries with
unstated facts it stated each assumption, except the goal of case 15 ("Show me variants affecting BRCA1,
BRCA2"), which it filled in as basic-consequence without asking: the same miss as in experiments 1, 4 and 5.

**Where the chat models differ.**

- **They put short-variant tools on structural variants.** Every chat arm does on at least one of cases 3–6:
  on case 5, a structural-variant question, Opus 4.7 with the documentation recommends AlphaMissense, REVEL,
  dbNSFP, HGVS and the gnomAD short-variant frequencies. Opus 5.5 with the documentation does it once.
- **They miss options the table ties to the kind of question.** Opus 5.5 with the documentation misses
  UTRAnnotator on 9 cases, Phenotypes and Protein matches on 6 each, gnomAD SV on 5.
- **Filters that delete rows.** The chat arms recommend "one consequence per variant/gene" and "coding
  regions only"; Opus 5.5 does so 11 times without the documentation, 2 times with it.
- **The newer model does better with the same documentation.** Opus 4.7 with the PDF recommends 42 of the
  103, against 53 for Opus 5.5, and more than twice as many options outside the table (26 against 11), 9 that
  cannot work for the case (against 2) and 9 row-deleting filters (against 2). With thinking left to the model,
  Opus 4.7 used none on any case; Opus 5.5 with the PDF used 300–1,070 thinking tokens a case (685 on average).
- **The documentation helps the larger model most.** With the PDF, Opus 5.5 goes from 38 to 53 of 103
  and from 11 to 2 row-deleting filters; Sonnet 5 with it reaches 22, against 9 for Sonnet 5 on the claude.ai
  website.
- **Species (cases 19, 20).** Only Ask VEPai offers CADD for pig; both Opus arms say CADD is human-only,
  which Ensembl's plugin configuration contradicts. For sheep every arm says the form has no breed
  frequencies, which is right; Opus 5.5 with the PDF recommends Variant synonyms, which Ensembl has for human
  and pig only.
- **Where the chat models do better.** They explain what the form cannot do (restricting to a gene list, a
  loss-of-function filter) at more length, and suggest external resources.

**Limits.** The reference is our own priority table, so Ask VEPai is marked against the rules it follows:
its score shows the model reads the cases right, not that the rules are right. How right the table is rests
on its review: of its 70 rows, 22 follow a mentor's written decision and the other 48 are our decisions. The row-deleting column and the species part of cannot-work do not use the table, and hold either way. The facts of cases 19 and 20 were set by us. Two of them are readings rather than stated facts: case 18's "mostly in promoters and enhancers" is taken as regulatory only, and case 20 never states a region, so it takes the tool's default for an unstated region (both). One answer per case per arm; the two websites run
with their own hidden instructions and settings, and ChatGPT searched the web; the API arms have neither.
The mapping from free text to options is by pattern; the scores file lists every decision it made. The
scores file also scores cases 1–12 against their configuration as reviewed in round 1
(`cases/chat_models_reference_round1.json`, before later changes to the table): Ask VEPai 53/76, Opus 5.5
with the documentation 34/76.

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
