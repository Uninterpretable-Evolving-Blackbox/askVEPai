# Ask VEPai — the engine

The tool itself. **For what the project is, how it was built and how it was evaluated, read the
[repository README](../README.md) one level up.** This file covers running the engine and nothing else.

## What it is

One Python module. It reads a plain-English scenario into five factor values, then resolves those
deterministically into an Ensembl VEP web-form configuration.

```
scenario (prose)
   → classifier (one model call)  → species · origin · variant size · region focus · analysis goal
   → priority table               → the options this scenario calls for
   → constraint checker           → conflicts, species gates, dependencies, assembly
   → RECOMMENDED / OPTIONAL / ALREADY ON, in the form's own words
```

**The model's only job is prose → five values.** Everything after that is ordinary code, which is
why most of the test suite needs no GPU.

## Run it

```bash
ollama serve
ollama pull gemma4:26b
pip install -r requirements.txt

python3 vep_assistant.py "somatic tumour-normal, clinical interpretation on the coding hits"
```

Run it with no scenario for an interactive prompt. Behind a proxy you need
`NO_PROXY=localhost,127.0.0.1`, or every Ollama call returns 502.

Python 3.9+. Only `openai` is required; `flask` is for the web UI in `../work/webapp/`.

## Flags

| Flag | Meaning |
|---|---|
| `--explain` | why each option is there — our rule, and Ensembl's own words for it |
| `--minimal` | only what you must tick; hides the add-ons |
| `--full` | every add-on as well |
| `--cli` | also print the equivalent VEP command line |
| `--species` `--origin` `--size` `--assembly` | state a fact instead of letting the model infer it |
| `--no-ask` | never prompt; state the assumed values instead |
| `--quiet` | apply the safe defaults with no disclosure lines |
| `--no-factor-think` | skip classifier reasoning: ~0.9 s a query instead of ~4 s, weaker on misleading wording |
| `--two-pass` | also run the retired draft call, for comparison work |

`--think`, `--semantic` and `--no-check` were removed on 2026-09-16; passing one prints why and exits 2.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `VEP_MODEL` | `gemma4:26b` | the model that reads the scenario |
| `VEP_FACTOR_MODEL` | `VEP_MODEL` | a separate classifier model, if wanted |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | the Ollama endpoint |
| `VEP_FACTOR_THINK` | on | `0` turns classifier reasoning off |
| `VEP_CLASSIFIER_PROMPT` | `v2` | `v1` restores the pre-2026-09-16 prompt |
| `VEP_OPTIONS_FILE` `VEP_FACTORS_FILE` `VEP_PRIORITY_FACTOR_FILE` | auto | override a data file — see *Two copies* below |
| `VEP_EXAMPLES_FILE` | `legacy/training_examples.json` | the `--two-pass` corpus; absent means empty. The default path never reads it |
| `VEP_KEEP_ALIVE` | `-1` | how long Ollama keeps the model loaded |
| `VEP_RESULTS_DIR` | `results/` | where saved recommendations go |

## Files

```
vep_assistant.py         the engine
vep_options.json         the 68-option catalogue
factors.json             the factor scheme: values, hard gates, exclusions
priority_by_factor.json  the priority table the resolver reads
vep_consequences.json    41 consequence terms, for `explain-result`
legacy/                  NOT USED BY THE TOOL — the stage-B benchmark and its 23
                         Claude-written examples. See legacy/README.md.
```

### Two copies of each data file

Each data file is looked up in this order: an environment variable, then the `work/` copy one level
up, then the copy in this directory.

So with `work/` beside it the engine reads `../work/vep_options_expanded.json`; cloned on its own it
reads `vep_options.json` here. The `work/` copy is the curated, provenance-tracked one, so it must
win when present — otherwise editing it would silently fail to reach the tool. **The two are kept
byte-identical by hand and nothing enforces it**; if you edit one, edit both.

## Where everything else lives

| | |
|---|---|
| what the project is, how it was evaluated | [`../README.md`](../README.md) |
| the test harnesses | `../work/harness/` — see its README for what each script is |
| design rationale, the option dossiers | `../work/research/` |
| the 31 review scenarios and the pipeline that made them | `../work/generation/` |
