# Ask VEPai — where the project stands

The single "where are we" page: what is done, what is next, and what needs a decision. The README
covers what the tool is, how it is built and how to run it. Design rationale lives in `research/` —
`taxonomy_proposal.md` for the factor scheme, `generation_pipeline_proposal.md` for how examples are
built, `underspecification_proposal.md` for the measurements on what a question leaves unsaid, and
`reprompting_proposal.md` for the design that answers it. Evidence for every number below is in
`EXPERIMENTS.md`.

## Status

| | |
|---|---|
| Option catalogue | **65 options**, grounded in Ensembl `public-plugins` release/115 |
| Recommender + checker + gates | working, published, runnable |
| Deterministic invariant suite | **36 checks**, seconds, no GPU |
| Per-query latency | **~18 s** end to end, reasoning off (`EXPERIMENTS.md` Exp 14: 18.1 s vs 34.9 s with `--think`) |
| Agreement with the priority table | **enable-F1 89.5% ± 0.6**, must-have recall **95.1% ± 0.3** (3 seeds) |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Output tiers | **two** — RECOMMENDED and ADD-ONS (merged 2026-08-07) |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

**The must-have recall figure measures something the user never sees.** The three internal priorities
exist for real mechanisms — `restore_missing_critical`, `--minimal` and this metric are all defined on
the must-have tier — but the output shows two buckets, so 95.1% is not recall on a tier anyone reviewed.
It is an internal signal until a replacement is agreed.

## Recent work

**Two tiers instead of three.** RECOMMENDED (the former must-have and recommended, merged) and ADD-ONS.
Naming per Nakib: *"default" carries a different meaning — something that applies automatically instead
of some expert suggestion*, which is wrong for a bucket the user still has to switch on.

That distinction is meant to be carried by an *already on* marker, on the grounds that **54%** of a
typical recommendation (6.2 of 11.5 options per row) is switched on by the VEP form before anything is
suggested. **The marker is not implemented yet** — the rationale for the naming stands, the surface does
not exist, and this line should not be read as describing shipped behaviour.

The merge changed **no configuration**: the engine had always enabled must-have ∪ recommended as one
set, so the split was only ever a label on the way out. Verified as a pure regrouping over all 72
factor tuples; export totals unchanged at 391 recommended and 121 add-ons.

## What is next

1. **Apply the mentor review.** Ten rows approved, twenty edited, one rejected. The unopposed edits are
   in. About twelve of the edits were must-have↔recommended moves and are **no-ops** under two tiers.
   Newly confirmed and not yet applied: `check_existing` → add-on wherever the condition holds (21 rows,
   not the 6 originally flagged), and the 8 missing web-exposed plugins.
2. **Run the recommended configuration against Web VEP** and check the output. The largest remaining
   independent piece.
3. **Ask when it matters, assume when it does not.** Built, tested and live. On 78 controlled ablations,
   one fact removed from our own queries so the right answer is known, the tool interrupts on **38 of
   78**, raising 44 questions: **32** about assembly and **12** about `analysis_goal`. Reproduce with
   `harness/ask_rate.py`, which prices every candidate policy on the same cases with no model.

   That is a lot of interruption for a design whose first principle is that asking is the exception, and
   it is flagged as such in `reprompting_proposal.md` §9. The assembly share is the part the ablations
   can only overstate: their queries never name a build, while **4 of the 8** real tracker questions do,
   and the question is suppressed whenever the text says.

   How often real users omit things is **not established**: of 43 issues pulled verbatim from the
   trackers, only 8 are configuration questions. That number decides how aggressive to be, and needs the
   `real_data` Likhitha has offered.

## Open questions

These need a domain decision, not more code:

- **Which predictors are the core set,** and on what axis? VEP itself ranks none of them; the current
  split follows a clinical-genetics standard external to VEP.
- **Should a purely regulatory query keep the missense predictors?** They produce empty columns, but
  the review asked for them back.
- **Should the assistant say what it cannot do?** VEP has no non-human frequency source, so
  "population frequencies for my mouse variants" currently returns a configuration with no frequency
  data and no explanation.

**Settled:** Ask VEPai stays **web-form-only** — CLI-only options (`--overlaps`, `--max_af`,
`--variant_class`, `--check_svs`, `--clin_sig_allele`, `--clinvar_somatic_classification`) are out of
scope. Two tiers, named RECOMMENDED and ADD-ONS. `check_existing` may move to add-on.

**Decided from measurement** (`reprompting_proposal.md` §9, each reversible by one line, each with the
alternative priced in `harness/ask_rate.py`):

- **A variant set can be both small and structural.** `variant_size_class` is `select: multi`, guessed
  *both*. This amends the signed-off taxonomy, so §5 carries the full argument. No configuration moves:
  the 31 review rows are single-valued and the export totals 391 recommended / 121 add-ons.
- **`analysis_goal` is asked, not guessed.** It meets neither of our conditions for guessing. On the 8
  real tracker questions it is genuinely absent once, so asking costs less than the ablations imply.
  Skipping is free and the fallback announces itself.
- **Assembly is asked, never guessed** — the one gap where silence gives a *wrong* answer, and where
  both guesses delete something real. Read from the text where it is there (4 of 8 real questions), and
  scored on what the user stated rather than on what we assumed for them.
- **The interrupt bar is the RECOMMENDED bucket the user sees**, named as `ASK_BAR_PRIORITIES`. Not the
  internal `critical` tier: twelve of the twenty mentor edits moved options across that boundary, so an
  interruption should not depend on it. Both bars raise identical questions on the current guesses.

## Honesty note

The example configurations are generated from a priority table that is our own editorial judgement.
VEP does not rank its own options, so somebody had to, and that somebody was us. Until the Ensembl
mentors sign that table off, the agreement figures above measure fidelity to a proposal rather than
correctness — and the decisions it rests on are written down in
`generation/candidates/review/DECISIONS.md` precisely so they can be argued with.
