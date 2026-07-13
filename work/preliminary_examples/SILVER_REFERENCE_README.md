# Silver reference set — for your validation → gold

**File:** `silver_reference_set.json` (30 examples), with a flat `silver_reference_review.csv` you can mark
up. **These are not gold yet.** They're model-generated reference examples, grounded in the VEP
documentation and structurally validated, but not expert-validated — so please treat each config as a
*proposal to check*, not an answer. Once you sign off the rows, they become our first real gold set.

## Why I made these

Two jobs at once:
1. **To lock the per-option priorities** — the thing currently blocking real gold. I built the configs from
   an *independent*, documentation-grounded reading of which options matter for each scenario, deliberately
   separate from the generation pipeline's own priority table. Wherever the two disagree is exactly where I
   need your decision.
2. **To have a reference for testing the generation pipeline.** Once these are validated, I compare the
   pipeline's own `(query → config)` outputs against them; if the pipeline matches your validated set on this
   slice, we can trust it to scale. That's the whole point of the pipeline — you validate ~30 once, not
   dozens, and it scales from there with spot-checks.

## How they're built

- **Coverage:** the five-factor scheme, balanced — every factor value appears at least 15 times, including
  the rarer cases (non-human, somatic, structural variants, regulatory, and genuine multi-label rows).
- **Config:** written from a documentation-grounded rule set (using each option's documented scope from
  Ensembl release/115), then run through the constraint checker — every config is checker-clean (no
  species/conflict/dependency violations, all valid option ids).
- **Query:** a natural-language question per row, verified so that it actually expresses all five of its
  factors.
- **Honest limitation:** the configs come from a rule set, not per-example hand-curation — so this is really
  a documentation-grounded priority *proposal* rendered as 30 examples. Validating it through the examples is
  the efficient way to settle the priorities.

## What each row carries (for review)

- `recommended_options` — the config (enabled options + explicit disables with notes).
- `_review.criticality` — my critical/recommended call per option. **This is the priority proposal to
  validate.**
- `_review.uncertain` — the honest caveats I'd like you to adjudicate (below).
- `_review.query_factor_recovery` — the check that the query expresses each factor.
- `justification` — the rationale.

## The questions I'd most like your view on

1. **Predictor set.** Clinical coding rows enable SIFT + PolyPhen + CADD + AlphaMissense. VEP doesn't rank
   these, and ACMG PP3/BP4 warns against double-counting correlated predictors — a defensible minimal set is
   one meta-predictor (REVEL or AlphaMissense) + CADD for non-coding reach. Which set do you want as standard?
2. **A structural-variant catalogue gap.** VEP's core SV output is `--overlaps` (how much of each gene/feature
   an SV spans). It isn't in our 58-option list yet, so SV rows can't express it — should I add it?
3. **Non-human + population-frequency.** gnomAD/1000G are human-only, so a non-human population-frequency row
   has no frequency option available. The sampler produced this combination for coverage — is it in scope, or
   should we exclude such combinations?
4. **Per-species resources.** SIFT (species-limited) and the Regulatory Build (human + a few model organisms)
   exist only for some species; I enable them where the factors allow, but the checker can't verify per
   species. Worth a per-species capability table later?
5. **Frequency threshold.** ACMG BA1 stand-alone-benign is AF > 5% — confirm filter-out vs annotate-only.
6. **Essential vs optional is my reading.** The VEP docs are a reference; they don't publish a per-scenario
   recommended config. Every critical/recommended tag is my well-reasoned call from each option's documented
   scope plus ACMG guidance, not a VEP prescription.

## How to review

Per row: **approve** / **edit config** / **edit query** / **reject**, plus a comment (there are empty
`review_decision` and `mentor_comment` columns in the CSV). The most valuable edits are on the criticality
calls and the questions above. Once approved, the rows become the gold set the harness and the pipeline are
measured against.
