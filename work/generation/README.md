# Gold-example generation pipeline (`work/generation/`)

A reproducible, in-repo pipeline that produces candidate `(user_query → VEP web-form config)` rows for the
Ask VEPai example set. It implements the **reverse / asymmetric** generation design (see
`../research/generation_pipeline_proposal.md`): deterministic code + the option catalogue + the constraint
checker fix the **configuration (Y)** first; a local LLM then writes only the **natural-language query (X)**;
automated gates + an in-context usefulness screen + a review export decide what survives.

> ⚠️ **PROVISIONAL.** The factor scheme (`generation_config/factors.json`) and the per-option priorities
> (`generation_config/priority_by_factor.json`, authored factor-natively from
> `../research/taxonomy_proposal.md` §3's "drives" clusters — see `seed_priorities.py`) are **authored
> judgement, not yet expert-validated.** The pipeline is built so these live only in config: to adopt a
> validated table you replace the two config files, not the code. Everything the pipeline writes under
> `candidates/` is a directional stand-in — never treat it as approved gold; it is git-ignored.

## Why this shape

Asking one model to write the whole row (query **and** configuration) reproduces well-known failure modes:
option-id drift, skew toward common scenarios, and no explicit disables. Instead the catalogue + checker own
the configuration and the LLM writes only natural language — the project's "LLM proposes, deterministic
Python disposes" architecture. Two consequences fall out for free:

- **The model cannot hallucinate an option**, because it never sees or names one (`generate_queries.py`
  forbids naming options, flags, or column names). Every option in every generated config comes from
  deterministic code.
- **The distribution of configurations is controllable**, because code samples the factor space directly
  rather than hoping the model covers the rare corners (non-human, somatic, structural, regulatory).

Design framing and citations (SynthIE reverse generation; DataMorgana query axes; Quality-Matters / ICE) are
in `../research/generation_pipeline_proposal.md`.

## Teacher model

Stage 3's teacher (which writes the query only) defaults to **`gemma4:26b` — self-generation**; a larger
sibling is **not** assumed to be a better teacher. Grounding: Xu et al., *Stronger Models are Not Always
Stronger Teachers*, NAACL 2025 (arXiv:2411.07133) — same-family teachers help, but larger-same-family does
not reliably help ("Larger Models' Paradox"), and compatibility with the student predicts teacher quality.
Stage 5 (ICE) is the empirical selector: run it with different `--student`/teacher pairings and compare
rather than guessing. `teacher_sweep.py` and `persona_ablation.py` are the two ablation drivers.

## Stages

| Stage | Script | LLM? | Reuses |
|-------|--------|------|--------|
| 0 config | `seed_priorities.py` + `generation_config/*.json` | no | taxonomy §3 "drives" clusters + catalogue `category`/`species_restriction` |
| 1 sample | `sample_factors.py` | no | greedy inverse-frequency, seeded (balanced factor coverage) |
| 2 resolve | `resolve_config.py` | no | `check_and_fix_violations`, `infer_species`, `_is_human_only` |
| 3 query gen | `generate_queries.py` | yes | `evaluate.call_llm` (Ollama) |
| 4 gates | `filter_candidates.py` | judge only | `check_and_fix_violations`, BGE embedder, `rouge_l` |
| 5 ICE | `ice_screen.py` | yes | `build_system_prompt`, `extract_recommendations` |
| 6 export | `export_for_review.py` | no | the per-option priority tiers |

A Web-VEP execution check (running the emitted config and checking the output) is intentionally out of scope
for this build.

**Invariants.** Stage 2 emits the checker's OWN output, so Stage 4 re-running the checker makes **zero**
changes (the self-consistency bar). The emitted configs are order-independent (identical across hash seeds);
`run_generation.sh` pins `PYTHONHASHSEED=0` so diagnostics are bit-reproducible too. Stage 5 never breaks
leave-one-out (candidates are not in the corpus). `verify_pipeline.py` (below) checks all of this with no
GPU.

## Run

```bash
# fast deterministic verification — NO GPU; proves the pipeline's safety invariants
VEP_OPTIONS_FILE=$PWD/../vep_options_expanded.json PYTHONHASHSEED=0 python verify_pipeline.py

# whole pipeline (needs a local Ollama server running with the model pulled)
bash run_generation.sh 31 gemma4:26b 42        # 31 balanced rows, teacher gemma4:26b, seed 42

# or stage-by-stage (env vars select the catalogue + example corpus)
export VEP_OPTIONS_FILE=$PWD/../vep_options_expanded.json
python seed_priorities.py
python sample_factors.py --n 31 --out candidates/tuples.json
python resolve_config.py --tuples candidates/tuples.json --out candidates/resolved.json
python generate_queries.py --in candidates/resolved.json --out candidates/queried.json --seed 42 --concurrency 1
python filter_candidates.py --in candidates/queried.json --out candidates/filtered.json   # add --no-judge to skip the LLM judge
python ice_screen.py --in candidates/filtered.json --out candidates/iced.json --student gemma4:26b --seed 42
python export_for_review.py --in candidates/iced.json --outdir candidates/review
```

Output: `candidates/review/review_queue.csv` (+ `.json`, `review_view.txt`) and an append-only
`provenance.jsonl`. The seed is for **reproducibility, not statistics** — this produces a deliverable (a
review set), so one seeded run is the whole job. `resolve_config.py --enable critical` gives a tighter,
higher-precision config than the default `critical+recommended`.

To get just the deterministic factor → config recommendation without running the whole pipeline, use
[`recommend_by_factors.py`](recommend_by_factors.py) — see the factor-values quickstart in the top-level
README.

## Design notes & open items

- **The per-option priorities are authored, not validated.** Replace `factors.json` +
  `priority_by_factor.json` with a validated table and re-run; no code changes needed. VEP itself does not
  rank its options, so the critical / recommended / optional split is editorial judgement (the predictor
  tiering follows ACMG PP3/BP4 as refined by ClinGen SVI, Pejaver et al. 2022 — a standard external to VEP).
- **Combination plausibility is a distribution choice, not a safety one.** Stage 1 balances the factor
  *values* treating the factors as independent, so it can draw implausible corners. The hard gates make even
  those resolve to a sensible (often minimal) config, so this affects *which rows are worth building*, not
  configuration safety. Two combinations the catalogue genuinely cannot satisfy (non-human +
  population-frequency, non-human + structural) are excluded via `factors.json` `exclusions`; the resolver
  additionally flags any scenario whose requested annotation has no available source (`unsatisfiable_factors`).
- **Conflict tiebreaks can be arbitrary (flagged, not yet principled).** The reused checker breaks an
  equal-priority option conflict by restrictiveness then alphabetical — a determinism device, not a
  principled choice. `resolve_config.flag_arbitrary_conflicts` surfaces these as a `conflict_arbitrary`
  review flag rather than silently committing a coin-flip. A principled fix (resolve output-mode conflicts by
  `analysis_goal`) is planned.
- **Dedup thresholds are unvalidated.** Cosine ≥ 0.92 (hand-picked) AND ROUGE-L ≥ 0.70 (the Self-Instruct
  convention). The `AND` is deliberately conservative (it misses paraphrase duplicates) and should be
  ablated against a hand-labelled pair set.
