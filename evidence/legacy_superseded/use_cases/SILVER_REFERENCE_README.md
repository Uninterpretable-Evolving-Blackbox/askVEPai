# Silver reference set — for mentor validation → gold

**File:** `silver_reference_set.json` (30 examples). **Status: SILVER, not gold.** These are
model-authored (Opus) reference examples, grounded in the VEP documentation and structurally validated, but
**not yet expert-validated**. They become gold only once the mentor signs off each row. Please treat every
config below as a *proposal to check*, not an answer.

## Why this exists

Two jobs at once:
1. **Validate the per-option priorities** — the mentor blocker. The configs come from a hand-built,
   doc-grounded priority rule set (`author_reference_set.py` → `doc_priority`) that is deliberately
   **independent** of the generation pipeline's `priority_by_factor.json`. Where they disagree is exactly
   where the pipeline's priority table needs a decision — so validating these 30 *is* validating the
   priorities.
2. **A reference to test the generation pipeline** — once validated, the pipeline's own `(query → config)`
   outputs are compared against these; if the pipeline matches the expert-validated set on this slice, we
   trust it to scale beyond what anyone will hand-author. (That is the pipeline's only real justification —
   we are not asking you to hand-author dozens; we are asking you to validate ~30 once.)

## How they were built

- **Coverage:** the 5-factor scheme, balanced — **every factor value appears ≥15 times** (well above the
  ≥3 minimum), including the rare cases (non-human, somatic, structural-CNV, regulatory, and genuine
  multi-label rows). Tuples sampled by the pipeline's stratified sampler (seed 42).
- **Config:** authored by a **doc-grounded rule set** written directly from the catalogue's
  `when_to_use`/`when_not_to_use` guidance (distilled + adversarially-verified from Ensembl release/115),
  then passed through the deterministic constraint checker. Every config is **checker-clean (0 mutations)** —
  no species/conflict/dependency violations, all valid option ids.
- **Query:** hand-written natural-language question per row (varied phrasing/persona/terminology), each
  verified by the semantic **query↔factor round-trip** to actually express its five factors.
- **Honest limitation:** these configs come from a *rule set*, not per-example hand-curation — so it is a
  doc-grounded priority *proposal* rendered as 30 examples. You are validating the priority logic through
  the examples, which is the efficient way to unblock the priority table.

## What each row carries (for review)

- `recommended_options` — the config (enabled + explicit disables with notes).
- `_review.criticality` — my **critical/recommended** call per option. **This is the priority proposal to
  validate.**
- `_review.uncertain` — the honest caveats to adjudicate (below).
- `_review.query_factor_recovery` — the semantic check that the query expresses each factor.
- `justification` — the doc-grounded rationale.

## Caveats to adjudicate (these are the real questions)

1. **Predictor redundancy.** Clinical coding rows enable SIFT + PolyPhen + CADD + AlphaMissense. **No VEP
   page ranks these** — this is editorial. ACMG PP3/BP4 warns against double-counting correlated predictors;
   a defensible minimal set is *one meta-predictor (REVEL or AlphaMissense) + CADD* for non-coding reach.
   **Which set do you want as the standard?**
2. **Structural-variant catalogue gap.** VEP's essential SV output is `--overlaps` (length/proportion of each
   gene/feature an SV spans). **It is not in the 58-option KB**, so SV rows cannot express it. Add to the
   catalogue?
3. **Non-human + population-frequency is largely unsatisfiable.** gnomAD/1000G are human-only, so a
   non-human population-frequency row has *no* frequency option available (see `silver_02`). The sampler
   produced this combo for coverage; is it in scope, or should such combos be excluded?
4. **Per-species resource availability.** "non-human" is treated uniformly, but SIFT (species-limited) and
   the Regulatory Build (human + a few model organisms) exist only for *some* species. Rows enable
   `regulatory`/`sift` where the factor allows, but the checker cannot verify per-species — Web-VEP or you
   would. Worth a per-species capability table later?
5. **Frequency threshold/direction.** ACMG BA1 stand-alone-benign = **AF > 5%** (ClinGen SVI 2018, ≥2000
   alleles). The frequency filter is set to flag common variants — confirm filter-out vs annotate-only.
6. **Essential vs optional tags are editorial.** The VEP docs are a *reference*; they do not publish a
   per-scenario recommended config or rank options. Every critical/recommended tag is well-reasoned from each
   option's documented scope + ACMG guidance, but is *my* synthesis, not a verbatim VEP recommendation.

## How to review

Per row: **approve** / **edit_config** / **edit_query** / **reject** + a comment. The highest-value edits are
on `_review.criticality` (which options are truly critical vs recommended vs should be off) and the
`uncertain` items above. Once approved, the rows become the gold set the harness and the pipeline are
evaluated against.

## Documentation grounding

Config rules written from the VEP options/plugins reference
(`ensembl.org/info/docs/tools/vep/script/vep_options.html`, `…/vep_plugins.html`, `…/vep_example.html`) and
the catalogue's release/115-derived guidance fields. Frequency threshold from ACMG/AMP 2015 (Richards et al.)
BA1 and the ClinGen SVI 2018 refinement (AF > 5%). The essential/optional judgements are editorial synthesis
grounded in each option's documented scope — the VEP docs do not themselves prescribe per-scenario configs.
