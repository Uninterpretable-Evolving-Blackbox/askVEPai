# askVEPai — the engine

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

Python 3.9+. Only `openai` is required.

## Flags

| Flag | Meaning |
|---|---|
| `--explain` | why each option is there — our rule, and Ensembl's own words for it |
| `--minimal` | only what you must tick; hides the add-ons |
| `--cli` | print the VEP command instead of the web-form lists (add-ons as a comment) |
| `--species` `--origin` `--size` `--assembly` | state a fact instead of letting the model infer it |
| `--region` `--goal` | state the region (`coding`, `regulatory`, `both`) and the goal (`basic`, `clinical`, `frequency`, several joined with `+`) |
| `--organism` | name the organism, e.g. `--organism pig`; looked up in Ensembl's species list, and sets the species |
| `--no-ask` | never prompt; state the assumed values instead |
| `--quiet` | apply the safe defaults with no disclosure lines |
| `--reasoning-off` | the model reads the scenario without reasoning first: ~0.6 s instead of ~3 s, weaker on misleading wording |
| `--two-pass` | also run the retired draft call (loads `legacy/two_pass.py`), for comparison work |

`--think`, `--semantic` and `--no-check` were removed on 2026-09-16, and `--full`, `--factor-think` and `--ask`
on 2026-10-04 (`--no-factor-think` is now `--reasoning-off`); passing one prints why and exits 2.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `VEP_MODEL` | `gemma4:26b` | the model that reads the scenario |
| `VEP_FACTOR_MODEL` | `VEP_MODEL` | a separate classifier model, if wanted |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | the Ollama endpoint |
| `VEP_FACTOR_THINK` | on | `0` turns classifier reasoning off |
| `VEP_CLASSIFIER_PROMPT` | `v2` | `v1` restores the pre-2026-09-16 prompt |
| `VEP_OPTIONS_FILE` `VEP_FACTORS_FILE` `VEP_PRIORITY_FACTOR_FILE` | this directory | use another data file |
| `VEP_EXAMPLES_FILE` | `legacy/training_examples.json` | the `--two-pass` corpus; absent means empty. The default path never reads it |
| `VEP_KEEP_ALIVE` | `-1` | how long Ollama keeps the model loaded |
| `VEP_RESULTS_DIR` | `results/` | where saved recommendations go |

## Files

```
vep_assistant.py         the engine
vep_options.json         the 70-option catalogue, each fact sourced in its `provenance`
factors.json             the factor scheme: values, hard gates, exclusions
priority_by_factor.json  the priority table the resolver reads
species_index.json       Ensembl's species names, to check the organism the model names
ensembl_docs/            Ensembl's options and plugins pages, parsed, for `--explain`
legacy/                  NOT USED BY THE TOOL — the stage-B benchmark and its 23
                         Claude-written examples. See legacy/README.md.
```

The engine reads only this directory, so it runs on its own. An environment variable overrides any
data file. These files are the only copy; builders kept in the private working repository write them
from Ensembl's sources.

## Where everything else lives

| | |
|---|---|
| what the project is, how it was evaluated | [`../README.md`](../README.md) |
| the experiments and their results | `../evidence/current_evidence/` |
| why the tool is built this way | `../evidence/legacy_decisions/` |
| the test cases | `../evidence/current_evidence/cases/` |
