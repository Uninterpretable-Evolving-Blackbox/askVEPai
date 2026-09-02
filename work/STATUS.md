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
| Deterministic invariant suite | **65 checks**, seconds, no GPU |
| Per-query latency | **~18 s** at concurrency 1, reasoning off (`EXPERIMENTS.md` Exp 14: 18.1 s vs 34.9 s with `--think`; **1 seed**, unlike the 3-seed figures below) |
| Agreement with the priority table | **enable-F1 89.5% ± 0.6** (3 seeds). Must-have recall is withdrawn — see below |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Output tiers | **two** — RECOMMENDED and ADD-ONS (merged 2026-08-07, third tier deleted 2026-08-19) |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

**Must-have recall is withdrawn, and 95.1% should not be quoted.** It scored against the internal
`critical` tier. That tier was the one part of the table an expert reviewed, and twelve of her twenty
edits moved options across it — corrections never applied, because merging the display had made them
invisible. Three mechanisms went on reading the uncorrected boundary: `--minimal` filtered on it,
`restore_missing_critical` restored it, and this metric scored against it. So 95.1% measured agreement
with a judgement its only reviewer had rejected, scored against itself.

The tier was deleted on 2026-08-19 rather than hidden. `--minimal` now means "no add-ons",
`restore_missing_recommended` restores the RECOMMENDED bucket, and with one enabled set there is one
recall to report, which enable-F1 already covers. `enable-F1 89.5%` stands and is unaffected: it was
always scored on the enabled set, which the merge and the deletion both leave unchanged.

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
factor tuples; export totals unchanged at 391 recommended and 121 add-ons. Those two numbers are the
2026-08-07 state and are quoted only as the before/after of the merge. The mentor corrections landed
afterwards, so the sheet as generated today reads **328 recommended and 183 add-ons**.

## What is next

1. **Two separate passes for short and structural variants — BUILT 2026-08-31, one piece outstanding.**
   A scenario carrying both sizes now emits one configuration per size instead of one union of them,
   because the web form cannot express both at once: CADD's control is a four-way annotation-file
   drop-down and the files are mutually exclusive. The four labels are in the catalogue as
   `web_form_values`, read off the live form and **absent from our release/115 snapshot**, so they need
   re-checking against the form.

   `variant_size_class` stays `select: multi` and the evidence for that is untouched — assuming both
   still loses options on 0 of 29 ablations where single-select loses on 15. The split happens at render
   time, where the form imposes it. **The two passes together enable exactly what the single
   configuration did**, checked over all 36 both-size factor tuples (`verify_pipeline.py` §8b), so this
   re-assigns options to the run that can use them rather than changing any recommendation.

   CADD-SV is GRCh38-only, so a stated GRCh37 drops CADD from the structural pass with a reason rather
   than leaving it on with no file behind it. An unstated build keeps it, as the assembly gate does
   everywhere else.

   Outstanding: **the browser rendering is unverified.** The payload and the command are correct per
   pass and were tested directly; the page itself could not be exercised here because Ollama is not
   installed on this machine. Her question about whether coding/non-coding should split the same way is
   still unanswered; the exchange is recorded verbatim in the project log.
2. **Apply the mentor review.** Ten rows approved, twenty edited, one rejected. The unopposed edits are
   in. About twelve of the edits were must-have↔recommended moves and are **no-ops** under two tiers.
   Newly confirmed and not yet applied: `check_existing` → add-on wherever the condition holds (21 rows,
   not the 6 originally flagged), and the 8 missing web-exposed plugins.
3. **Run the recommended configuration against Web VEP** and check the output. The largest remaining
   independent piece.
4. **Ask when it matters, assume when it does not.** Built, tested and live. On 78 controlled ablations,
   one fact removed from our own queries so the right answer is known, the tool interrupts on **40 of
   78**, raising 46 questions: **34** about assembly and **12** about `analysis_goal`. Reproduce with
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
