# Action plan — the 2026-08-11 mentor feedback

Likhitha's message plus the threaded reply, and the two Sheets comments from Jamie Allen (row 1) and
Aleena Mushtaq (row 13). Internal working document; `action_plan_*` is excluded from the public repo.

Each item below is either **verified** against the code or marked as needing a check. Verified means it
was reproduced, not just read.

---

## 0. Where each comment came from

The feedback arrives in three forms and they are not equally anchored. Getting this wrong means fixing
the wrong row, so it is set out before the work:

- **Likhitha's bullets** are *general statements* ("We don't recommend HGVS for SVs/CNVs"), not tied to a
  row. They read as generalisations from reviewing the 31-row sheet, so for each one the affected rows
  are computed below rather than assumed.
- **Her threaded "L24 notes"** is the only row reference she gives, and it is **ambiguous**. Our row 24
  sits on CSV line 31 (the header is on line 7), and `round2_comments.py` records that the Google Sheet
  has a different row offset from ours. If she means line 24 it is not our row 24. Our row 24 *is* a
  mouse row, which fits a mouse comment — but see the finding below before treating it as row-anchored.
- **Jamie Allen (row 1)** and **Aleena Mushtaq (row 13)** are anchored to specific rows by quoted query
  text, so those two are unambiguous.

### What is already correct, and one earlier claim corrected

**ClinVar, AlphaMissense and PolyPhen-2 are already gated off for mouse** — verified absent on **all 11**
mouse rows (2, 6, 8, 9, 12, 15, 18, 21, 24, 28, 30). Three of the four things her L24 note lists are
already handled and must not be "fixed" again.

**`paralogues` is the one live defect there**, offered as an ADD-ON on **5 of the 11** mouse rows (8, 12,
18, 21, 30). It is absent from the other six because they are `regulatory-noncoding`, where a separate
gate already removes it.

**Row 24 is not one of those five.** Its tuple is `non-human / germline / small / regulatory-noncoding /
basic-consequence`, so paralogues does not appear on it at all. What row 24 *does* exhibit is the
**`symbol` on a purely regulatory query** defect — a different bullet of hers. So either "L24" points at
a row other than our 24, or the mouse remark is a general observation rather than a reading of that row.
**Do not cite row 24 back to her as the paralogues example**; cite rows 8/12/18/21/30, and cite row 24
for `symbol` if a row-level example is wanted.

*(An earlier pass of this analysis reported all four options "correctly absent from row 24". That was
row 21, picked by a first-match on "musculus". The tuples differ and the conclusion above supersedes it.)*

---

## A. Priority-table corrections — mechanical, one sitting, no mentor input needed

Edits to `generation_config/priority_by_factor.json` and the `vep_ai_demo/` copy. Every symptom below was
reproduced against the 31 rows, and the row counts are what to quote back.

| # | mentor point | provenance | verified symptom | rows hit | edit |
|---|---|---|---|---|---|
| A1 | no HGVS for SVs/CNVs | general bullet | `hgvs` has no `variant_size_class` entry, so it survives SV queries — and it is `critical` for clinical goals, so it lands in RECOMMENDED, not add-ons | **13 / 31** | add `variant_size_class: {structural-CNV: not_applicable}` |
| A2 | no symbols for regulatory features | general bullet; row 24 is an instance | `symbol` has no `region_focus` entry | **9 / 31** purely-regulatory rows | add `region_focus: {regulatory-noncoding: not_applicable}` |
| A3 | MAVE for short-variant clinical | general bullet **and** Jamie Allen on row 1 | `mavedb` has only `species: {non-human: not_applicable}` — no positive priority anywhere | **31 / 31** (appears in none) | add `analysis_goal: {clinical-interpretation: recommended}`, `variant_size_class: {small: recommended, structural-CNV: not_applicable}` |
| A4 | LOEUF for SV/CNV | general bullet | `loeuf` is `clinical-interpretation: optional` only, no size entry | **15 / 31** — every SV row | add `variant_size_class: {structural-CNV: recommended}` |
| A5 | no paralog mapping for mouse | L24 note (ambiguous anchor) | `paralogues` has no `species` entry, offered as an add-on to non-human rows | **5 / 11** mouse rows; 6/31 non-human overall | add `species: {non-human: not_applicable}` |

A2 and A5 interact: both are already suppressed on regulatory rows by other gates, so the row counts do
not simply add. Re-export and diff rather than predicting the total.

**A6 — CCDS.** Superseded by MANE for human, unmaintained, "won't be supported in future". Currently
`region_focus: {coding: optional}`, so it already sits in ADD-ONS. Retiring it is a catalogue change, not
a priority change, and it needs C5 answered first.

**Where each edit actually goes — NOT all in `priority_by_factor.json`.** That file is a dump, not the
source: `load_priority_by_factor` uses it as an *override* only if present, and it is currently
byte-identical to what `build_priority_table` derives (verified: 0 of 65 options differ). Editing it
alone would create a divergence from the `DRIVES` spec that does not exist today, and would vanish the
moment anyone deletes the file. Each correction belongs at its own source:

| # | edit it here | why |
|---|---|---|
| A1 hgvs off for SV | **catalogue**: `hgvs.priority_by_use_case.structural_variants`, `"optional"` → `"not_applicable"` | `DRIVES` has no `not_applicable` list for size; the SV gate reads the catalogue (`SIZE_GATE_SOURCE`) |
| A2 symbol off for regulatory | **`REGION_GATE_NONCODING`** in `vep_assistant.py:155` — add `"symbol"` | that list *is* the regulatory gate |
| A3 MaveDB reachable | **`DRIVES`** `analysis_goal.clinical-interpretation.recommended` — add `"mavedb"`; **and** the catalogue, which has *no* `structural_variants` key for it at all | needs a positive priority (spec) and a size gate (catalogue) |
| A4 LOEUF on for SV | **`DRIVES`** `variant_size_class.structural-CNV.recommended` — add `"loeuf"` | the only positive size list in the spec |
| A5 paralogues off for non-human | **catalogue**: `paralogues.species_restriction` is the free text `"species with Ensembl paralogues"`, and `_is_human_only()` returns **False** on it, so the species gate never fires | third instance of A-root-3: the fact is written down and unreadable by any gate |

So A1 and A5 are catalogue-value fixes, A2 is a gate-list fix, A4 is a spec fix, and A3 is both. Only
after editing the source should `seed_priorities.py` regenerate the JSON dump, so the two stay identical.

**Steps.** Edit each source above → regenerate `priority_by_factor.json` and copy both it and
`factors.json` to `vep_ai_demo/` → add one check per correction to `verify_pipeline.py`, each asserting
the symptom is gone on the rows listed above → re-run `verify_pipeline.py`, `defaults_evidence.py`,
`test_user_context.py` → re-export the review sheet and diff against 391 recommended / 121 add-ons.

**Watch for:** A3 makes MaveDB reachable for the first time, so it will appear in the sheet where it
never has. That is the point — Jamie and Likhitha asked for it independently — but say so in the reply
rather than letting them find it.

---

## A-root. Why these five exist, and why fixing five is not enough

The five corrections are not five independent slips. They are samples from one structural weakness, and
the plan is worse than useless if it only patches the samples — the next review round will find a sixth.

**The pipeline is not at fault.** The resolver faithfully applies whatever the catalogue and `DRIVES`
say; `verify_pipeline.py` already asserts the SV gate holds ("structural-CNV rows never enable a
catalogue-SV-not_applicable option") and it passes. The gates work. **Their input is wrong**, in three
distinguishable ways, and nothing checks any of them:

**1. A gating value can simply be wrong.** `hgvs` carries
`priority_by_use_case.structural_variants: "optional"` in the catalogue — so the SV gate correctly does
not fire, and the invariant suite correctly stays green, while HGVS goes out on 13 SV rows. The
catalogue *asserts* HGVS is applicable to SVs. Likhitha says it is not. That is our domain judgement
being wrong, and no test can catch it, because the catalogue is the thing tests are written against.

**2. A gating key can be absent, silently.** Seven options carry **no `structural_variants` key at all**
— `ancestral_allele`, `blosum62`, `go`, `intact`, `mavedb`, `opentargets`, `riboseqorfs`. The SV gate
cannot see them. `mavedb` is one, which is part of why it never appears anywhere. Absence reads exactly
like "applicable", and 25 options *are* marked `not_applicable`, so the field looks well-populated.

**3. A fact can be recorded in prose and never reach a gate.** `paralogues.when_not_to_use` already says
*"Species lacking Ensembl paralogue data"* — which is Likhitha's L24 point, written in our own catalogue,
months ago. It is free text, so no gate reads it, and `paralogues` has no `species` entry. The catalogue
knew and could not act on it.

### What to do about it

- **A-root-1 — completeness check.** Assert every option carries every gating key it can be gated on.
  Seven fail today. Mechanical, belongs in `verify_pipeline.py`, and turns silent absence into a
  failure.
- **A-root-2 — reconcile prose against the structured fields.** Scan `when_not_to_use` / `when_to_use`
  for limitation language ("non-human", "species lacking", "not for structural", "GRCh38 only") and
  assert the corresponding structured field agrees. This would have caught `paralogues` without a
  mentor, and it is cheap because the prose is already written.
- **A-root-3 — stop spending their review on things a test could catch.** These are people with full
  jobs who went out of their way to read 31 generated configurations. Asking them to review 65 options
  against a set of gating keys instead would be *more* of their time, not less, and it is the wrong ask.

  The point of A-root-1 and -2 is that **`mavedb` having no `structural_variants` key, and `paralogues`
  contradicting its own `when_not_to_use` prose, are things we could have found ourselves.** They spent
  reviewer attention on those. What only they can supply is the judgement — that HGVS is not wanted for
  SVs, that MAVE belongs in short-variant clinical work — and that should be what the sheet asks them
  for. Keep the row-based review; make it carry only the questions that need a domain expert.

A-root-1 and -2 are ours to build and should ship with the A1–A5 corrections, so the reply can say the
class is closed rather than the instances. A-root-3 is a request to them and belongs with C1–C5.

---

## B. Things that need a source check before an edit — half a day

**B1. Non-human allele frequency.** Likhitha: *"We could recommend AF data for non-human analysis in many
cases."* Today `af`, `af_1kg`, `af_gnomade`, `af_gnomadg` all carry `species: {non-human: not_applicable}`,
**and** `factors.json` excludes the pair `{non-human × population-frequency}` outright, on the stated
grounds that such a scenario "resolves to a config with no frequency source at all". If she is right,
that exclusion is wrong and the 31 rows are missing a whole scenario class by construction.

Check: which non-human frequency sources does VEP release/115 actually expose — Ensembl variation
frequencies for mouse/rat/zebrafish, and what are they called in `InputForm.pm`? Grounded in
`ensembl_source/`, not from memory. Then either lift the exclusion and add the options, or reply
explaining what the catalogue can and cannot express.

**B2. Species granularity.** The factor is `human | non-human`, which cannot say "mouse has no ClinVar
but zebrafish has X". A5 patches one symptom; the general case needs per-species availability. The
catalogue already carries a free-text `species_restriction` per option, so the data is partly there —
what is missing is a factor value or a lookup keyed to actual species.

This is a **taxonomy change**, so it needs a ruling, and it is the same shape as the assembly problem:
availability is a function of `(species, assembly)`. Do not start it before C1 below is answered.

---

## C. Questions only they can answer — send these, do not guess

**C1. Species scope.** *"Most scenarios are human, mouse and zebrafish. Are these the only species the
project focuses on?"* She is exactly right, and it is worth quoting the count back: the 31 rows are
**16 human, 11 mouse (2, 6, 8, 9, 12, 15, 18, 21, 24, 28, 30) and 4 zebrafish (4, 14, 20, 26)** — three
species, nothing else. No cattle, pig, or plants, and no non-human row that leaves the organism unnamed.

The answer decides B2 and the generation sampler. If agricultural species are in scope, `species` cannot
stay binary and the option catalogue needs per-species availability rather than human/non-human.

**C2. The type-level output.** Her spec: *"[option type] should/could be used and the following options
are supported in Ensembl VEP for [species]([assembly]): [options]"*. Three things need confirming before
it can be built:

- Is the type layer the catalogue's existing `category` field? It has 17 values
  (`pathogenicity_prediction` 9, `functional_effect` 8, `identifiers` 6, `frequency_data` 5, …), which is
  close to what she describes but was authored by us, not by them.
- Does the type-level recommendation **replace** the per-option one, or wrap it? A user still has to tick
  boxes on a form, so something must eventually name options.
- Priorities are currently per option. Do they become per type?

**C3. Scenario plausibility.** *"Some scenarios wouldn't happen — SV analysis from exome data, sequencing
a population of wild mice in an expression study."* The sampler balances factor coverage and has no
notion of whether a combination occurs in practice. The cheapest fix is a blocklist of impossible or
implausible factor combinations, supplied by them — asking them to invent scenarios is expensive, asking
them to veto combinations is not.

**C4. Gene panels.** *"Queries often specify a particular set of genes related to disease/cancer
phenotypes."* This is the third independent sighting of "the tool should capture a value it currently
cannot" — with `cell_type` and Aleena's populations note. Is a gene list a factor, or a free-text field
that rides alongside like assembly does?

**C5. CCDS retirement (A6).** Remove it from the catalogue, or keep it and mark it deprecated? It is a
form field VEP still shows, so removing it makes our catalogue disagree with the form.

---

## D. Coverage gaps — after C1 and C3

New scenario classes to generate: **GWAS-hit interpretation**, **crops / induced mutations**,
**gene-panel queries**, and whatever C1 says about agricultural species. Each needs a factor tuple that
the current taxonomy may not express — a GWAS-hits query is arguably `population-frequency` +
`regulatory-noncoding`, but crops and gene panels are not obviously expressible at all.

Do not generate these before C1/C3/C4 are answered, or they will be regenerated afterwards.

---

## E. The structural one: type-level output

This changes the output contract, not the table, and it has one consequence worth stating plainly
before any work starts:

**It invalidates the headline metric.** Enable-F1 89.5% measures per-option agreement. If the deliverable
is a type plus an availability list, per-option F1 scores something we no longer ship. A replacement
metric has to be agreed at the same time, or the project loses its only number.

It also **dissolves an open question**: "which predictors are the core set, and on what axis?" has been
in `STATUS.md` for weeks. Under type-level output we do not choose — we name the type and list what is
available. That question should be struck rather than answered.

Sequence, once C2 is answered: agree the type vocabulary → decide what the metric becomes → change the
output schema (`output_schema/vep_recommendation.schema.json`) → change the renderer → re-run the LOO
under the new metric. This is the largest remaining piece of work in the project apart from Stage 7.

---

## Suggested order

1. **A1–A5 now.** Cheap, verified, independent of every open question. It also unblocks the round-2
   review sheet, which has been unsendable for three separate reasons and would gain a fourth if these
   corrections are not in it.
2. **Send the reply** (below) — do not wait for the rest, because C1–C5 are blocking B, D and E.
3. **B1** while waiting, since it is a source check rather than a decision.
4. **B2 / D / E** once the answers land.

---

## What to send back

Short, and structured as *fixed / checked / need you*. Suggested shape:

> Thank you — these are all actionable. Five of the table points are fixed and verified: HGVS is off for
> SVs/CNVs (it was appearing as a must-have on clinical SV queries), symbol is off for purely regulatory
> queries, LOEUF is on for SV/CNV, MaveDB is now reachable for short-variant clinical interpretation —
> it previously could not appear in any configuration at all, which Jamie's row-1 comment was also
> pointing at — and paralogues is now gated off for non-human, which was the one part of your L24 note
> that was a live bug; ClinVar, AlphaMissense and PolyPhen-2 were already correctly excluded for mouse.
>
> Five things I would rather not guess at: [C1–C5, one line each].
>
> On recommending option types rather than specific tools — agreed, and it is the biggest change here,
> so I would like to confirm the shape before building it: [C2].

Do not send the ask-rate or ablation numbers in this reply. They are answers to a question nobody asked
and they will bury the five questions that actually need answering.
