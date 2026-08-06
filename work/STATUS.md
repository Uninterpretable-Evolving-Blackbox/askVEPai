# Ask VEPai — where the project stands

The single "where are we" page: what is done, what is next, and what needs a decision. The README
covers what the tool is, how it is built and how to run it. Design rationale lives in `research/` —
`taxonomy_proposal.md` for the factor scheme, `generation_pipeline_proposal.md` for how examples are
built, `underspecification_proposal.md` for what to do when a question does not say. Evidence for every
number below is in `EXPERIMENTS.md`.

## Status

| | |
|---|---|
| Option catalogue | **65 options**, grounded in Ensembl `public-plugins` release/115 |
| Recommender + checker + gates | working, published, runnable |
| Deterministic invariant suite | **32 checks**, seconds, no GPU |
| Per-query latency | **~11 s** end to end on the reference machine |
| Agreement with the priority table | **enable-F1 89.5% ± 0.6**, must-have recall **95.1% ± 0.3** (3 seeds) |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

## What is next

1. **Apply the mentor review.** Ten rows approved, twenty edited, one rejected. The unopposed edits are
   in; the rest are below.
2. **Two tiers instead of three.** Merging must-have and recommended into a single default bucket,
   with an *already on / turn on* marker — roughly half of a typical recommendation is switched on by
   the form before anything is suggested, and that distinction is more useful than the one it replaces.
3. **Run the recommended configuration against Web VEP** and check the output. The largest remaining
   independent piece.
4. **Ask when it matters, assume when it does not.** Measured over twenty real forum questions, 18 of
   20 leave something open that changes the answer. Safe assumptions plus stated facts take the
   questions needed from 1.5 per query to 0.65; a single taxonomy change would take it to zero.

## Open questions

These need a domain decision, not more code:

- **Is a variant set one size or two?** The scheme forces a choice between small and structural, but
  real questions say "SNVs and CNVs". Allowing both removes every remaining clarifying question.
- **Which predictors are the core set,** and on what axis? VEP itself ranks none of them; the current
  split follows a clinical-genetics standard external to VEP.
- **Should a purely regulatory query keep the missense predictors?** They produce empty columns, but
  the review asked for them back.
- **Should the assistant say what it cannot do?** VEP has no non-human frequency source, so
  "population frequencies for my mouse variants" currently returns a configuration with no frequency
  data and no explanation.

## Honesty note

The example configurations are generated from a priority table that is our own editorial judgement.
VEP does not rank its own options, so somebody had to, and that somebody was us. Until the Ensembl
mentors sign that table off, the agreement figures above measure fidelity to a proposal rather than
correctness — and the decisions it rests on are written down in
`generation/candidates/review/DECISIONS.md` precisely so they can be argued with.
