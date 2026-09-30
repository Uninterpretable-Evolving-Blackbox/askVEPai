# Ask VEPai: trained chatbot interface for Ensembl VEP web

**Google Summer of Code 2026 · final report**

| Contributor | David (Wei) ([Uninterpretable-Evolving-Blackbox](https://github.com/Uninterpretable-Evolving-Blackbox)) |
|---|---|
| Organisation | Genome Assembly and Annotation (EMBL-EBI, Ensembl) |
| Mentors | Likhitha (mentor), Aine (co-mentor) |
| Project size | 175 hours (medium) |
| Proposal | *Ask VEPai: Provenance-Traced AI Configuration Assistant for Ensembl VEP Web* |
| Code | this repository, at tag `gsoc-2026-final` |

Ask VEPai reads a plain-English description of a variant-analysis job and returns a recommended configuration for the [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) web form, with the reason for every option, the facts it assumed, and what the form cannot do. It runs on a local open model through [Ollama](https://ollama.com/), so no query leaves the machine.

How to install and run it: [`README.md`](README.md). Every measurement: [`evidence/current_evidence/README.md`](evidence/current_evidence/README.md).

Lesson learnt: "Simplicity is prerequisite for reliability." (Edsger W. Dijkstra, 1975)

The design began with retrieval-augmented generation, embedding-based semantic retrieval and two model calls. LLMs attract a lot of hype, but as the project went on, the role of the LLM was reconsidered, and the simpler, more deterministic design was often better and more reliable.

## 1. What Ask VEPai does

A user describes the analysis in their own words:

> Germline exome from a child with a suspected rare disease, mostly SNVs and small indels in coding regions. Which variants could be pathogenic?

Ask VEPai answers in a few seconds (output shortened where marked `…`):

```
  Assumed species = human
  Assumed assembly = GRCh38
Detected scenario:
- species: human
- origin: germline
- variant_size_class: small
- region_focus: coding
- analysis_goal: clinical-interpretation
- assembly: GRCh38 (assumed)

============================================================
  YOUR VEP CONFIGURATION
============================================================
RECOMMENDED — set these on the VEP web form  [11]
  Identify canonical transcripts   (Additional annotations › Transcript annotation)
  Protein matches   (Additional annotations › Protein annotation)
  HGVS   (Identifiers section)
  MaveDB   (Additional annotations › Functional effect)
  Exon and intron numbers   (Additional annotations › Transcript annotation)
  Phenotypes   (Additional annotations › Phenotype data and citations)
  Protein   (Identifiers section)
  Pathogenicity predictions: AlphaMissense, CADD, EVE   (Predictions section)
      CADD drop-down: CADD SNVs and InDels annotation file
  Splicing predictions: SpliceAI   (Predictions section)

OPTIONAL  [15]
  BLOSUM62   (Predictions › Conservation)
  …
ALREADY ON when the form loads — leave ticked  [11]
  APPRIS, Transcript biotype, Find co-located short variants, ClinVar clinical significance, …
```

Each option is named as the form names it, with the section to find it in.

Facts the scenario leaves out are assumed and stated (here the species and the genome build), or asked for when the answer would change one of the RECOMMENDED options.

`--explain` adds the reason for every option: the factor value that raised it, from the project's priority table, and Ensembl's own description of the option from the release-116 [options](https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html) and [plugins](https://www.ensembl.org/info/docs/tools/vep/script/vep_plugins.html) pages.

`--cli` prints the same configuration as a VEP command, using the flags from Ensembl's options page and plugin configuration.

`explain-result` explains a term in VEP's output, using the 41 consequence terms from Ensembl's [Calculated variant consequences](https://jun2026.archive.ensembl.org/info/genome/variation/prediction/predicted_data.html) page.

## 2. How it works

```
scenario (prose) ──► one model call ──► 5 factor values ──► priority table + checker ──► RECOMMENDED / OPTIONAL
                     (gemma4:26b,         + organism          (deterministic code)        + why each option
                      local, Ollama)
```

- **Five factors.** Every scenario is described by five facts: species (human or not), origin (germline or somatic), variant size (small, structural, or both), region (coding, regulatory, or both) and analysis goal (basic consequences, clinical interpretation and population frequency). The model's only job is to read these, plus the organism's name for species-specific options, from the text.
- **The priority table** ([`priority_by_factor.json`](vep_ai_demo/priority_by_factor.json)) gives, for each option and each factor value, `recommended`, `optional` or `not_applicable`. It was written for this project. The mentors corrected it through their edits to 31 example answers and their comments on our questions; the rows they have not reviewed await their decision.
- The checker removes what the organism or the genome build cannot use, going by Ensembl's own lists; recommends missing prerequisites; resolves conflicts between options; and never recommends an option that deletes rows from the results. An extra annotation only adds a column the user can ignore, but a filter that drops rows can hide the variant the user is looking for.

The configuration is built deterministically, so the same five factors always give the same configuration, and every option traces to the factor value that raised it. The full description is in [`README.md`](README.md).

## 3. From the proposal: what was delivered

The problem from the proposal: the VEP web interface "exposes an extensive configuration surface that overwhelms new users." The project brief asked for three things: label the web form's options, assemble training data, and build a prototype model. Two requirements were agreed with the mentors before the start: the model is open source and runs locally, and the first data are constructed gold examples.

The proposal described a two-pass design: retrieval picks worked examples, the model drafts a configuration, and a checker corrects it. I built this design and ran it until 14 September. It was then replaced by the design in §2. The table gives, for each deliverable in the proposal, what the two-pass design delivered and what the current tool delivers. Experiment numbers refer to the project's experiment ledger.

| deliverable in the proposal | two-pass design (to 14 September) | current tool |
|---|---|---|
| Knowledge base of ~55 options, each mapped to its web-form section | 58 options by June, taken from the web-form code and Ensembl's pages (my pre-GSoC demo had 26) | 70 options, all taken from Ensembl's web-form code and documentation. Each option records the Ensembl file and line every fact came from ([`reference/`](reference/README.md)) |
| 15–20 gold-standard examples with an 80/20 train/test split | Initial 23 worked examples written with Claude to test retrieval methods. Used both in the prompt and, one held out at a time, as the test set. From July, 31 scenarios generated by `gemma4:26b` systematically from the factor space, reviewed by the mentors | The same 31 scenarios, after two rounds of mentor review, plus three test sets: 150 tricky cases, 754 organism names, 78 scenarios with one fact removed. Nothing is trained, so there is no split |
| RAG pipeline returning structured JSON | Built: worked examples in the prompt, the model drafts a configuration, the checker corrects it. Enable-F1 88.0 once the five factors were added (Exp 17) | One model call reads the five factors; the priority table and checker build the configuration. The checker had been rebuilding the draft's RECOMMENDED options on every scenario; one call scores F1 0.898, in 1.2 s against two-pass’ 17.9 s ([D3](evidence/legacy_decisions/README.md)) |
| Semantic retrieval vs keyword retrieval vs all examples | Benchmarked. Showing every example beat both retrieval methods: 86% enable-F1, against 73% for keyword and 38% for semantic retrieval (Exp 2). | No retrieval. It survives only on the legacy `--two-pass` path |
| Constraint checker with 100% species-violation detection | Built. The model wrote a list of options, then the checker corrected it. It knew only human or non-human, so it deleted human-only options (for example ClinVar) from any non-human request. It also dropped one of any two options that cannot be used together, and added any option another one depends on | The checker now builds the list itself from the priority table. It then checks each option against the organism the user named, using Ensembl's per-species lists (for example, SIFT exists for 13 species). Tested on all 358 non-human species in Ensembl's index, each with every kind of scenario: no option was ever shown to a species Ensembl doesn't list it for. |
| Evaluation report, N = 3–5 runs, mean ± SD | Measuring the system: the configuration the model wrote was scored against the gold examples (enable-F1), each run 3–5 times and reported as mean ± SD, across 20 experiments in the project's ledger. Choosing the model: five models compared (Exp 1), then three Gemma 4 sizes (Exp 10, five runs; Exp 19, three runs); `gemma4:26b` chosen (D1) | Measuring the system: five experiments on the model's one job, reading the scenario, each with reasoning on and off and each repeated (evidence/current_evidence/README.md). At temperature 0 the seed changes nothing, so repeats measure run-to-run drift and are reported as a range. Choosing the model: three Gemma 4 sizes re-checked on the one-call design, on the 31 review scenarios, with the same prompt. Same RECOMMENDED options as from the true factors: `gemma4:26b` 30/31, `gemma4:e4b` 27/31, `gemma4:e2b` 25/31; all five factors read right: 24/31, 20/31, 18/31. `gemma4:26b` kept. |
| Web-form JSON schema for "click to apply" | Built. The schema was designed with each option's form section, field and action. The model could not write it reliably (valid JSON on 16 of 40 queries, Exp 8), so code assembled it instead: the model's text was parsed, checked, and turned into JSON that always matches the schema | Not carried over. How the tool connects to Ensembl's new web platform is the web team's decision. |
| End-to-end demo | Command line | Command line as instructed by mentors [`vep_ai_demo/vep_assistant.py`](vep_ai_demo/vep_assistant.py). The web interface is Ensembl's to build |
| README, setup guide, knowledge-base contribution guide | A progress log and reading order for the mentors | [`README.md`](README.md), [`vep_ai_demo/README.md`](vep_ai_demo/README.md) (every flag and environment variable), [`reference/README.md`](reference/README.md) (sources), and [§8](#8-how-to-extend) |
| *Extended:* QLoRA fine-tuning | Decided not needed | Decided not needed: the model's only job is reading five factors, which it does without training |
| *Extended:* FastAPI endpoint | Not built | Ensembl is building its new web platform, and will decide how the tool connects to it. The command-line tool is the integration point until then |
| *Extended:* VEP output explainer | `explain-result`, from my pre-GSoC demo | The same, its 41 consequence terms checked against Ensembl's release-116 page |
| *Extended:* attribution testing | Done (Exp 5–6): removing one part of the knowledge base and re-running. Removing the worked examples removed 71% of the recommendations; the option descriptions, 2%; the priority labels, 0% | The model never names an option, so every recommendation traces to a row of the priority table. `--explain` prints the factor value that raised each option and the rule that removed one |

## 4. Results

All figures: `gemma4:26b` through Ollama on an Apple M5 Max, temperature 0. The question behind each, how it is scored, where it fails and the file it comes from are in [`evidence/current_evidence/README.md`](evidence/current_evidence/README.md).

| experiment | reasoning on (the default) | reasoning off |
|---|---|---|
| 150 tricky cases: all four versions of a case read right | 145/150 (repeats 142, 147) | 137/150 (repeats 137, 137) |
| …of which the misreads leave the RECOMMENDED options unchanged | 149/150 (repeats 148, 149) | — |
| 31 review scenarios: same RECOMMENDED options as from the true factors | 30/31 (repeat 30) | 29/31 (repeat 29) |
| Organism named right, over 754 names from Ensembl's species list (scientific, common, breeds) | 746/754 (repeats 747, 746) | 746/754 (repeats 746, 746) |
| …when the text also mentions a second organism the data is not from | 749/754 (repeats 750, 749) | 745/754 (repeats 744, 743) |
| Scenarios with one fact left out: the tool uses its default for it and tells the user (78 rewrites of the review scenarios) | 73/78 (repeats 72, 72, 72) | 72/78 (repeats 72, 72, 72) |

The 31-scenario figures score the tool against its own priority table: they measure how far a misread moves the output, not whether the table is right. The external check is agreement with the mentor's own edits to round 1 of the review: F1 0.763, measured on the scenarios as she reviewed them.

### Compared with general chat models

Could a general chat model do this job instead? Each model got the same short instruction ("recommend which
options to tick on the VEP web form") and 20 scenarios, one question per scenario, with no memory between
them. Some also got Ensembl's 27-page VEP web documentation.

| model | options it recommended, of the 92 the table recommends | options that cannot work for the case | filters that delete results |
|---|---|---|---|
| **Ask VEPai** (`gemma4:26b`, local) | **92** | **0** | **0** |
| Claude Opus 5.5 (state of the art), with the documentation | 48 | 8 | 2 |
| Claude Opus 4.7, with the documentation | 35 | 20 | 9 |
| Claude Opus 5.5 | 32 | 12 | 11 |
| Claude Sonnet 5, with the documentation | 18 | 18 | 6 |
| ChatGPT (website, Thinking on) | 14 | 14 | 3 |
| Claude Sonnet 5 (claude.ai website) | 8 | 6 | 2 |

How to read the columns:

- **Options recommended.** The standard is this project's priority table, applied to each scenario's known
  facts: 92 options over 16 scenarios. Ask VEPai scores 92 because it *is* that table, so this column shows
  how far the chat models are from our choices, not that they are wrong.
- **Cannot work for the case.** Options Ensembl does not offer for that species (CADD for sheep), or
  short-variant tools recommended for structural variants (SIFT, SpliceAI). These are errors by Ensembl's
  own lists, whatever table one prefers.
- **Filters that delete results.** Settings such as "one consequence per gene" or "coding regions only",
  which remove rows from the output and can hide the variant the user is looking for.

Bigger models and the documentation help, but even the best arm, Opus 5.5 with the documentation, recommends
about half of the table's options and still suggests options that cannot work. The full method, every
answer and the per-case scores are in experiment 6 of
[`evidence/current_evidence/README.md`](evidence/current_evidence/README.md).

## 5. Upstream

*To confirm with the mentors on 1 October.*

## 6. Limitations

- **The priority table is provisional.** Mentors coming back with priority table reviews.
- Some organism names are deliberately not resolved. Common and scientific names, Ensembl's aliases ("swine"), abbreviated scientific names ("S. scrofa"), and yeast, worm and fly all resolve. Names that could mean two species ("C. lupus": dog or dingo) are left unresolved on purpose, and organisms outside the VEP web form (Arabidopsis, which is in Ensembl Plants) are not recognised.
- An unstated goal is sometimes filled in. With reasoning on, the model occasionally answers basic-consequence for a query that states no goal ("Show me variants affecting BRCA1, BRCA2"), so the tool neither asks nor prints that it assumed one. The configuration is the same as the fallback it would otherwise use; the user only loses the notice
- **Repeated runs can differ.** At temperature 0 the 150 tricky cases scored 145, 142 and 147 on three runs with reasoning on; with reasoning off, 137 on all three. The mentors' two cancer queries read origin differently on different runs with reasoning on.
- **Genes and consequence classes cannot be set on the input form.** The tool prints how to filter the results page instead.
- **Command line only.** No JSON output, no API.
- **Hardware.** `gemma4:26b` needs more than about 20 GB of free memory (`gemma4:e4b` fits in less, and reads the factors less well). A configuration takes about 5 s with reasoning on (median 5.1 s over 40 timed questions) and about 1 s with it off.
## 7. What is left

1. **Mentor decisions on the priority table:** the structural-variant exclusions; canonical transcripts on every query; three rows marked as ours; the seven rows where our table differs from the mentor's edits.
2. **Catalogue sources:** re-source the older options from the release-116 form files; they still cite the release-115 files. The three options added from the release-116 form, and every corrected one, already cite release 116.
3. **Tricky cases:** draw the organisms from Ensembl's index.
4. **Real questions:** turn the eight configuration questions from Ensembl's issue trackers into a test set, with answers confirmed by the mentors.
5. **Web integration:** a JSON output mode or an API, if the web team wants one.
## 8. How to extend

Everything the tool knows is in four JSON files in [`vep_ai_demo/`](vep_ai_demo/); the code reads them at start-up. An environment variable points the tool at another copy of any of them (listed in [`vep_ai_demo/README.md`](vep_ai_demo/README.md)).

| file | holds |
|---|---|
| `vep_options.json` | the options: what each is, where it sits on the form, who can use it |
| `priority_by_factor.json` | for each option and each factor value: `recommended`, `optional` or `not_applicable` |
| `factors.json` | the five factors and their values |
| `species_index.json` | Ensembl's species names, and which genomes count as one species |

### Add or correct an option

Add an entry to `vep_options.json`:

| field | value |
|---|---|
| `id`, `name` | our identifier; the label the form shows |
| `cli_flag` | the VEP command-line equivalent |
| `web_form_section`, `web_form_subsection` | where it sits: `input`, `identifiers`, `variants_frequency_data`, `additional_annotations`, `predictions`, `filters` or `advanced` |
| `web_default_on`, `web_default_value` | whether the form ships it ticked, and with what value |
| `species` | Ensembl production names (`sus_scrofa`), or `"all"` if every species has it |
| `assemblies` | the builds that have its data, or `null` for both |
| `depends_on`, `conflicts_with` | other option ids |
| `description` | Ensembl's own words, from the options or form page |
| `provenance` | for each field, the file and line in `reference/` it came from |

Then give it a row in `priority_by_factor.json` in the same change. An option with no row is never shown.

### Change a recommendation

A row in `priority_by_factor.json` lists, for each factor value that concerns the option, one of three labels:

```json
"af_gnomade": {
  "analysis_goal":      { "population-frequency": "recommended" },
  "variant_size_class": { "structural-CNV": "not_applicable" }
}
```

The engine applies two rules:

1. **Removal.** Species, origin, variant size and region can remove an option. A factor removes it only when every value the scenario has for that factor says `not_applicable`, so a coding-and-regulatory scenario keeps its missense predictors.
2. **Ranking.** Otherwise the strongest label across all the scenario's values wins. `recommended` puts the option in RECOMMENDED; `optional` makes it an add-on; no label leaves it out.

Run any scenario with `--explain` to see which value raised each option and which rule removed one.

### Add a factor value

Add it to `factors.json`. The classifier's instructions list the allowed values from that file, so the model can answer with the new value straight away. Then add the new value to the rows of `priority_by_factor.json` it should affect.

### Swap the model

Set `VEP_MODEL` to any model Ollama serves, and `VEP_FACTOR_MODEL` if the classifier should use a different one. Measure it before relying on it:

```bash
python3 evidence/current_evidence/factors_150_tricky_cases.py --model <model>
python3 evidence/current_evidence/organism_754_names.py --model <model>
```

### Measure a change

Re-run the experiments in [`evidence/current_evidence/`](evidence/current_evidence/README.md) with `--json <file>` and compare the new file with the published one in `results/`. `--limit N` runs the first N cases only, for a quick check (the 150-case, organism and missing-fact scripts).

### Follow a new Ensembl release

The sources, with their URLs and dates, are listed in [`reference/ensembl_source/README_sources.md`](reference/ensembl_source/README_sources.md) and [`reference/ensembl_docs_116/README.md`](reference/ensembl_docs_116/README.md). Fetch the new release's copies, diff them against these, and update the options whose facts moved, with their `provenance`.

## 9. Challenges/What I learned

My experience before with Bioinformatics and Machine Learning was research-based, statistically analyzing datasets, training and evaluating models.

This main aim of askVEPai however, is to be helpful for real users.

- Much consideration had gone into how easy it is to use. Removing friction, increasing speed cleanliness of output etc.

- A lot of effort also gone into considering non-technical aspect, such as building priority table, and designing default fallbacks that minimizes information lost at output, that are arguably even more important than the system design.

- Initially we had 2 LLM call design with long system prompt and RAG. Resulted in slower responses and performs less accurately than current one pass. Role of LLM for this project should be to infer scenario user types in natural language, which often is messy, this is what LLM are best at, and we stop at that. Resolving the rest deterministically with checkers and gates improves accuracy and speed. No need for further training or fancy ML techniques! Muilti LLM call with RAG and fine tuning would sound fancier on CV but would not improve the tool and harder to maintain. I would never.

## 10. Acknowledgements

Thanks to the EBI team, particularly

Likhitha who gave me this opportunity to work on a useful project with people at arguably the most prestigious Bioinformatics research body. For overseeing and guiding this project from beginning to End.

oversaw beginning to end of this project
