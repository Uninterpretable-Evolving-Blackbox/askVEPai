# VEP AI Assistant

A prototype chatbot that recommends [Ensembl VEP](https://www.ensembl.org/info/docs/tools/vep/index.html) (Variant Effect Predictor) configuration based on your analysis scenario. Built as a GSoC demo.

The assistant uses a local LLM via [Ollama](https://ollama.com/) with a curated knowledge base of 26 VEP options and 8 scenario-to-recommendation training examples. It recommends which options to enable or disable, explains why, and generates a ready-to-use VEP command.

## Features

- **Scenario-based recommendations** -- describe your analysis (rare disease, cancer, GWAS, etc.) and get tailored VEP configuration
- **Decision trace** -- full transparency into retrieval scoring, option provenance, and confidence levels
- **VEP output explainer** -- explain consequence terms and annotations in plain language
- **Post-hoc constraint checker** -- automatically detects and corrects species restriction violations and option conflicts
- **Keyword-based retrieval** -- selects the most relevant training examples using word overlap (no embedding model needed)
- **Semantic retrieval** (`--semantic`) -- uses sentence-transformers embeddings for more accurate example and option retrieval

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) running locally
- A pulled model (default: `qwen2.5:3b`)

## Setup

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama and pull a model
ollama serve
ollama pull qwen2.5:3b

# Install Python dependency
pip install -r requirements.txt
```

## Usage

### 1. Interactive recommendation

```bash
python vep_assistant.py
```

Prompts you to describe your analysis scenario, then streams a recommendation with:
- Detected use case category
- Per-option enable/disable decisions with confidence and source citations
- A generated VEP command line

### 2. Recommendation with decision trace (`--explain`)

```bash
python vep_assistant.py --explain "I have germline exome variants from a rare disease patient"
```

Shows the full decision trace before the recommendation:
- **Layer 1: Retrieval transparency** -- all training examples ranked by relevance score with matched keywords
- **Layer 2: Option confidence map** -- priority and confidence for each option given the detected use case
- **Layer 3: Confidence scores** -- high/medium/low derived from `priority_by_use_case` metadata

### 3. VEP output explainer

```bash
python vep_assistant.py explain-result "Why is my variant annotated as splice_donor_variant?"
```

Explains VEP consequence terms and annotations using definitions from `vep_consequences.json`.

### 4. Semantic retrieval mode (`--semantic`)

```bash
python vep_assistant.py --semantic "I have germline exome variants from a rare disease patient"
python vep_assistant.py --semantic --explain "I have mouse variants from CRISPR editing in GRCm39"
```

Uses sentence-transformers (`BAAI/bge-small-en-v1.5`, ~130MB, CPU-only) to embed queries and match against training examples and VEP options by cosine similarity instead of keyword overlap. Requires `sentence-transformers`:

```bash
pip install sentence-transformers
```

When combined with `--explain`, the decision trace shows cosine similarity scores instead of word overlap counts.

### Additional flags

| Flag | Description |
|------|-------------|
| `--explain` | Show decision trace before recommendation |
| `--semantic` | Use embedding-based semantic retrieval instead of keyword overlap |
| `--no-check` | Skip post-hoc constraint checking |

### Inline query

```bash
python vep_assistant.py "I have somatic variants from a tumour-normal pair"
```

## Evaluation

Compare knowledge-base-enhanced recommendations against a bare model across 8 test scenarios:

```bash
# Keyword retrieval only (2 conditions: bare vs keyword KB)
python evaluate.py

# With semantic retrieval (3 conditions: bare vs keyword KB vs semantic KB)
python evaluate.py --semantic

# Specify a different model
python evaluate.py --model qwen2.5:7b
python evaluate.py --model qwen2.5:14b --semantic
```

| Flag | Description |
|------|-------------|
| `--model MODEL` | Ollama model name (default: `VEP_MODEL` env var or `qwen2.5:3b`) |
| `--semantic` | Add "with KB + semantic retrieval" condition |
| `--all-examples` | Add "with KB + all examples" condition (no retrieval filtering) |
| `--runs N` | Number of runs per configuration for variance estimates (default: 1) |
| `--seed SEED` | Base random seed for reproducibility (default: 42) |

Uses leave-one-out evaluation: the ground truth example is excluded from the retrieval corpus so the model is never shown the answer it's scored against. Results are saved to `results/evaluation_results_<model>.md`.

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `VEP_MODEL` | `qwen2.5:3b` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint |

## Project structure

```
vep_assistant.py        # Main assistant (3 modes: recommend, explain, explain-result)
evaluate.py             # Evaluation: knowledge-base vs bare model comparison
vep_options.json        # 26 VEP options with structured metadata
training_examples.json  # 8 curated scenario-to-recommendation pairs
vep_consequences.json   # 41 VEP consequence terms (Sequence Ontology definitions)
requirements.txt        # Python dependencies (openai, sentence-transformers)
results/                # Saved recommendations and evaluation reports
```

## How it works

1. **Knowledge base loading** -- VEP options (with priorities, conflicts, species restrictions) and training examples are loaded from JSON files
2. **Retrieval** -- the user query is matched against training examples by word overlap (default) or cosine similarity over sentence embeddings (`--semantic`); top 2 examples are included in the prompt. In semantic mode, the top 10 most relevant options (out of 26) are also selected
3. **Prompt compression** -- options are compressed into a compact text format to fit within small model context windows
4. **LLM generation** -- the local model generates a recommendation with per-option decisions, source citations, and a VEP command
5. **Constraint checking** -- the response is parsed and checked for species restriction violations and option conflicts, which are auto-corrected with warnings

## Knowledge base

The knowledge base covers 8 training examples across 7 use case categories:

| Category | Example scenario |
|----------|-----------------|
| Rare disease (germline) | Exome variants from a Mendelian disorder patient |
| Somatic cancer | Tumour-normal paired somatic variants |
| Regulatory / non-coding | GWAS hits in intergenic regions |
| Population genetics | Allele frequency comparison across populations |
| Structural variants | Large deletions/duplications from long-read WGS |
| Splice analysis | Variants near exon-intron boundaries |
| Quick lookup | Single rsID annotation |
| Non-human | Mouse CRISPR editing variants |

Each of the 26 VEP options has metadata including:
- Priority per use case (critical / recommended / optional / not_applicable)
- Species restrictions (human-only vs all species)
- Conflicts with other options
- Dependencies

## Known limitations

Documented for transparency. These are areas for future improvement, not blockers for the current prototype.

**Evaluation methodology:**
- **Small sample size** -- 8 test queries with single-run defaults (temperature=0.7). Use `--runs 3` for variance estimates, but N=8 is still too small for statistically robust conclusions. Intended as a directional signal, not a benchmark.
- **Leave-one-out partially addresses data leakage** -- the ground truth example is excluded from retrieval, but the remaining 7 training examples share vocabulary and structure that may still leak signal. A fully held-out test set (with independent ground truth) would be more rigorous.
- **All options weighted equally** -- getting `symbol` right (enabled in every scenario) counts the same as getting `regulatory` right (the differentiating factor for non-coding analysis). Priority-weighted scoring would better reflect clinical importance.
- **Value field ignored** -- ground truth specifies `gnomad_af: "gnomAD exome"` but scoring only checks enabled/disabled, not which gnomAD dataset. The model gets full credit for enabling gnomAD genome when exome was correct.

**Response parsing:**
- **Enable/disable context is line-level** -- if a single line contains both "enable X" and "disable Y", the first matching context wins for all options on that line. In practice, LLM output uses separate lines per option, so this rarely triggers.
- **Citation rate is format-sensitive** -- only detects `[source: ...]` tags. Other citation formats (parenthetical, prose, etc.) are counted as missing.

**Constraint checker:**
- **Dependencies not enforced** -- `clinvar` declares `depends_on: ["check_existing"]` but the constraint checker only resolves conflicts, not dependencies. If the LLM recommends ClinVar without `--check_existing`, no warning fires.
- **Use case detection always uses keyword matching** -- even in `--semantic` mode, the constraint checker's `_detect_use_case()` falls back to word overlap for determining which priority rules to apply.
