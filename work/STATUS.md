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
| Per-query latency | **~11 s** end to end on the reference machine |
| Agreement with the priority table | **enable-F1 89.5% ± 0.6**, must-have recall **95.1% ± 0.3** (3 seeds) |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Output tiers | **two** — RECOMMENDED and ADD-ONS (merged 2026-08-07) |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

**And the must-have recall figure now measures something the user never sees.** The three internal
priorities survive the tier merge — `restore_missing_critical`, `--minimal` and this metric are all
defined on the must-have tier — but the output shows two buckets, so 95.1% can no longer be described
as recall on a tier anyone reviewed. It is an internal signal until a replacement is agreed.

## Done since the last update

**Two tiers instead of three.** RECOMMENDED (the former must-have and recommended, merged) and ADD-ONS.
Naming per Nakib: *"default" carries a different meaning — something that applies automatically instead
of some expert suggestion*, which is wrong for a bucket the user still has to switch on. That
distinction is carried by an *already on* marker instead, and it earns its place — **54%** of a typical
recommendation (6.2 of 11.5 options per row) is switched on by the form before anything is suggested.

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
3. **Ask when it matters, assume when it does not.** Built and tested; the asking half is held back
   pending a taxonomy decision (below). On 81 controlled ablations — one fact removed from our own
   queries, ground truth known — the tool needs a question on **16 of 81**, and all 16 are the same
   factor. Allowing a variant set to be both small and structural takes that to **zero**.

   *(An earlier version of this line cited "18 of 20 real forum questions". That set was hand-
   transcribed and turned out to be edited — five items had VEP command lines removed, which makes a
   question look more under-specified than the user's real one. **The set and every figure from it are
   withdrawn**, and the corrections are carried through `research/underspecification_proposal.md` §1,
   §7.3 and the new §7.4. How often real users omit things is therefore **still unmeasured** — of 43
   issues pulled verbatim from the trackers, only 8 are configuration questions at all.)*

## Open questions

These need a domain decision, not more code:

- **Is a variant set one size or two?** The scheme forces a choice between small and structural, but
  real questions say "SNVs and CNVs" — review row 1 is exactly that. Allowing both removes every
  remaining clarifying question. **This one is blocking:** the tool currently asks which of the two it
  is, and silently discards half of an honest answer of "both", so the asking behaviour is held back
  until it is settled.
- **Which predictors are the core set,** and on what axis? VEP itself ranks none of them; the current
  split follows a clinical-genetics standard external to VEP.
- **Should a purely regulatory query keep the missense predictors?** They produce empty columns, but
  the review asked for them back.
- **Should the assistant say what it cannot do?** VEP has no non-human frequency source, so
  "population frequencies for my mouse variants" currently returns a configuration with no frequency
  data and no explanation.
- **Assembly.** MANE exists only for GRCh38 and `InputForm.pm:694-702` gates its checkbox on species
  alone, so a GRCh37 user can tick an option with no data behind it. It cannot be inferred from a
  question that never names a build — assume GRCh38 and disclose, ask, or add a field.

**Settled since the last update:** Ask VEPai stays **web-form-only** — CLI-only options (`--overlaps`,
`--max_af`, `--variant_class`, `--check_svs`, `--clin_sig_allele`, `--clinvar_somatic_classification`)
are out of scope. Two tiers, named RECOMMENDED and ADD-ONS. `check_existing` may move to add-on.

## Honesty note

The example configurations are generated from a priority table that is our own editorial judgement.
VEP does not rank its own options, so somebody had to, and that somebody was us. Until the Ensembl
mentors sign that table off, the agreement figures above measure fidelity to a proposal rather than
correctness — and the decisions it rests on are written down in
`generation/candidates/review/DECISIONS.md` precisely so they can be argued with.
