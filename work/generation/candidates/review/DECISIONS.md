# Decisions needed before this can become gold

The review queue next to this file contains 31 candidate `(question → configuration)` rows, **all
distinct** (no duplicate configs). They are evidence that the priority table produces sensible
configurations. **They cannot tell you whether the table is right** — they are derived *from* it, so if a
priority is wrong the row is wrong-but-coherent and will look fine. Only the decisions below can settle that.

There are **eleven**. Each says what we chose, what it rests on, and what changes if you disagree.

> **The one-line summary:** the *factual* half of this catalogue is grounded in the Ensembl `public-plugins`
> web configuration (release/115) — flags, form sections, species restrictions, conflicts, dependencies,
> defaults. The *priorities* are not, because **VEP does not rank its own options**. Every judgement below
> exists because that ranking had to come from somewhere, and it came from us.

---

## 1. The predictor tiering — the big one *(this is "essential vs optional")*

Ten options answer "is this protein change damaging?". We split them:

| tier | options | in the output |
|---|---|---|
| **core** (recommended) | SIFT, PolyPhen, CADD, AlphaMissense, EVE | on |
| **add-on** (optional) | REVEL, ClinPred, dbNSFP | offered, off by default |

**The axis is method independence**, read from each plugin's own description. SIFT reads conservation,
PolyPhen reads structure, CADD trains its own genome-wide model, AlphaMissense is a neural net, EVE is an
unsupervised generative model — each forms its own opinion. REVEL *"combines 13 individual pathogenicity
predictors"*, ClinPred *"incorporates existing pathogenicity scores"*, dbNSFP is *"a meta-resource
aggregating many in-silico predictors"* — these re-package the first group.

**What it rests on:** ACMG PP3/BP4 as refined by ClinGen SVI (Pejaver et al. 2022) — correlated in-silico
predictors are **one** line of evidence, not several. Recommending REVEL beside SIFT/PolyPhen/CADD looks
like corroboration but is partly those same tools echoing back.

**What it does NOT rest on: VEP.** `vep_plugins_web_config.txt` is a flat `available => 1` map with no rank
field; `vep_web_interface_reference.md:149` lists "Missense pathogenicity | SIFT, PolyPhen, CADD, REVEL,
AlphaMissense, dbNSFP, ClinPred, EVE" as one undifferentiated family. **VEP expresses no preference among
these at all.** This tier is entirely our reading of a clinical-genetics standard external to VEP.

**Please rule on:** is method-independence the right axis? Is the core set right — should EVE be in it (it
is the most methodologically independent, but the least established clinically)? Should the tier depend on
whether the lab already has a pipeline preference?

**If you disagree:** one edit to `seed_priorities.py`'s `PREDICTOR_DISTINCT` / `PREDICTOR_DERIVATIVE`, then
regenerate. No other code changes.

---

## 2. Should `region_focus` remove options, or only rank them? *(amends the taxonomy proposal)*

`taxonomy_proposal.md` §3 calls `region_focus` **"purely soft"** — it shifts importance, never removes.
**We have implemented it as a hard gate**, against the proposal, on this evidence:

- the catalogue rates **9 of the 10** missense predictors `regulatory_noncoding: not_applicable` — the same
  label it uses for species
- `constraints_dossier.md:123`: *"Model as a soft dependency (**recommender gate**, not a CLI requirement):
  apply only to missense/coding variants"*
- CADD is the documented exception (it scores *"coding and non-coding variants"*) and is **not** gated

**Practically:** SIFT on a non-coding variant doesn't error — it prints an empty column. So this is weaker
than species (where the data doesn't exist at all) but stronger than a preference. Recommending five tools
that all output blanks is bad advice.

**Safeguard:** the gate needs **every** active region to be non-coding. A coding **and** regulatory variant
set keeps its predictors; only a purely regulatory one loses them.

**Please rule on:** gate, or rank? If you prefer ranking, we can demote them to add-ons instead of removing
them — that needs a mechanism we don't have yet (factors can currently only raise an option's priority,
never cap it), so it's a small build, not a config change.

---

## 3. Four options are always on, whatever the scenario

`core_type`, `symbol`, `biotype`, `check_existing` are core in **every** row. They're unconditional by
construction, so the rows can only confirm "always on" — there is no per-scenario judgement to check.

**Please rule on:** is an unconditional floor right, and are these the right four? `core_type` is rated
critical in all seven of the catalogue's columns (*"Always choose a transcript database"*), and
`symbol`/`biotype` are form defaults. `check_existing` is unconditional partly for a mechanical reason —
nine options depend on it, so the checker auto-enables it anyway.

---

## 4. Nine options carry no priority — seven never appear at all, by our choice

`pick`, `per_gene`, `pick_allele`, `summary`, `most_severe`, `transcript_version`, `distance`,
`buffer_size`, `shift_3prime` carry **no priority for any factor**. Of these, `most_severe` and `summary`
still appear as explicit *disables* on every row; the other **seven never appear anywhere**.

Our reasoning: the "Restrict results" family (`pick`/`per_gene`/`summary`/`most_severe`) suppresses
per-transcript detail, and the compute knobs (`buffer_size`, `distance`, `shift_3prime`) are infrastructure
the web tool manages rather than recommendations a user needs.

**Please rule on:** if you think `pick` (say) should be recommended for some scenario, **no row in this set
can tell us** — the sampler cannot offer an unpriced option. This one needs a direct answer, not a
spot-check.

---

## 5. VEP cannot answer "population frequencies for mouse" — is that a row, or a feature?

`non-human + population-frequency` and `non-human + structural-CNV` are **unsatisfiable**: gnomAD, 1000
Genomes, `--frequency` and gnomAD-SV are all human-only, so for a non-human sample the configuration
contains **no frequency source at all** while the question asks for one.

**We have excluded those two pairs from sampling** — a gold row whose question is unanswerable is a bad
gold row, and excluding the *pair* costs no coverage (non-human still reaches 15+ rows via other goals, so
the species safety net is still fully exercised; frequency options still reach 15+ via human rows). No row
in this set is unsatisfiable.

*(Note: a human **somatic structural-CNV** population query is **satisfiable** — gnomAD-SV answers it — even
though the SNV frequency options are gated out. An earlier version of the check wrongly flagged those rows;
it now asks "did any frequency-data option survive?" rather than "did the SNV frequency options survive?",
so cross-factor supply like gnomAD-SV is counted correctly.)*

**But the underlying scenario is real.** *"Can I get population frequencies for my mouse variants?"* is a
question someone will ask, and the correct answer is *"VEP has no non-human frequency source — here is what
you can do instead."* Right now the tool would hand back a config with no frequencies and **say nothing**.

**Please rule on:** should the assistant *answer* unsatisfiable requests explicitly? That's a scope
question — it makes the tool say what it *can't* do, which is arguably its most useful behaviour and is not
currently in the design.

---

## 6. Two catalogue gaps

- **SV overlap output is missing.** VEP's essential structural-variant output (`--overlaps` /
  `OverlapBP`/`OverlapPC`) is **not in the 58-option catalogue**, so no SV row can express it. Should it be
  added?
- **`clinvar` has no standalone control.** ClinVar significance arrives via `check_existing`, so we model it
  as derived. Confirming this is right matters because `clinvar` is `critical` for clinical interpretation.

---

## 7. The ACMG frequency threshold

Where a frequency cut-off is implied we use **AF > 5% = benign standalone (BA1)**, per ACMG/AMP as refined
by ClinGen SVI (2018). VEP itself sets no threshold. Is 5% the right default to encode, or should the
assistant stay silent on thresholds and only recommend *reporting* the AF columns?

---

## 8. Assembly is not a factor, and it bites

**MANE exists only for GRCh38.** It does not exist for GRCh37, which clinical labs still widely use — and
**the web form does not protect you**: it shows the MANE checkbox for any human assembly
(`InputForm.pm:694-702` gates on species alone), so a GRCh37 user can tick a box with no data behind it.

We've added an assembly check to the constraint checker (GRCh37 drops `mane`/`eve`; GRCh38 drops
`geno2mp`), but **only when the question names a build** — most don't. There is no `assembly` factor.

**Please rule on:** should assembly be a sixth factor, or is inferring it from the question good enough?

---

## 9. What the model wrote vs what it was told

The teacher model writes **only the question**; the configuration is built by deterministic code, and the
model never sees an option id. It is instructed never to name a VEP option — so that the question describes
the *scenario* and the configuration has to be *inferred* from it.

It doesn't always comply: in the previous draft **5 of 30 questions named "MANE Select"** unprompted —
realistic (clinicians talk that way), but off-spec for a scenario→configuration example. Rows where this
happens are now flagged `query_names_tool` and their usefulness score is voided rather than reported
(a question naming its own answer scores well for the wrong reason).

**Please rule on:** should questions that name tools be dropped, or kept as a legitimate second kind of
request (a user who already knows what they want)? Roughly a fifth of real forum queries look like this.

---

## 10. Does "clinical interpretation" imply wanting population frequencies?

The allele-frequency options (gnomAD exome/genome, 1000G) are driven **only** by the
`population-frequency` goal. So a query tagged `clinical-interpretation` but **not** also
`population-frequency` receives **no frequency options at all**.

This follows the where/why split: "population frequency" is treated as a distinct *intent* from "clinical
interpretation". But clinical practice pulls the other way — **ACMG BA1/BS1 use allele frequency as core
evidence** (a variant above 5% is benign), so a rare-disease clinical workup essentially always wants
gnomAD frequencies. Under the current table it only gets them if the query also explicitly asks for
frequencies.

The catalogue's own columns side with clinical practice: `af_gnomade`/`af_gnomadg`/`af` are rated
**critical for rare_disease_germline**, not just for population genetics.

**Please rule on:** should `clinical-interpretation` also drive the gnomAD frequency options (as
`recommended`, say)? We left it as-is rather than silently change the design, because "is frequency part of
clinical interpretation, or a separate intent?" is exactly the kind of modelling call this review is for.

---

## 11. Is MANE critical for *somatic* clinical interpretation?

`mane` (the MANE Select transcript) is `critical` for `clinical-interpretation`. But the catalogue rates
`mane` **optional for somatic cancer** — somatic workflows deliberately keep multiple transcripts (different
oncology databases use different reference transcripts), so pinning to MANE is less appropriate.

The current scheme can't express "critical for germline-clinical but optional for somatic-clinical": a
factor value proposes one priority, and priorities compose by taking the **maximum**, so there is no way for
`origin=somatic` to *lower* what `analysis_goal=clinical` raised. (Same limit as the MaxEntScan case in the
generation notes — the scheme can raise a priority on a factor conjunction, never cap it.) So MANE is
currently critical for *all* clinical rows, including somatic ones.

The same effect makes `hgvs` and `clinvar` critical for somatic-clinical where the catalogue rates them
`recommended`.

**Please rule on:** (a) is MANE-critical acceptable for somatic clinical, or (b) should somatic demote the
transcript-nomenclature options — which needs a "priority ceiling" mechanism the scheme doesn't yet have?

---

## How to read the review queue

| column | what it is |
|---|---|
| `critical` / `recommended` | the **core** configuration — switched on (critical = must-have; recommended = standard default) |
| `optional_addons` | offered, **not** on by default |
| `critical_ok` / `optional_ok` / `query_ok` / `notes` | **for you** — blank on purpose |

There is deliberately **no "off" column**: the deterministic checker turns off everything not listed
(conflicts, dependencies, species) at runtime, so a row only ever claims what to switch **on**.

**Flags you will see, and what they actually mean:**

- `judge_solvability_fail` — an LLM judge's opinion that the question may not be answerable from a config
  alone. It is **known to be over-conservative** and fired on ~1/3 of the previous draft. Treat as a
  prompt to look, not a defect.
- `factor_check_unparseable` — the cross-checking model failed to emit valid JSON. A tooling hiccup, says
  nothing about the row.
- `query_names_tool` — the question names a VEP tool (see §9).
- `unsatisfiable_factor` — should no longer appear (see §5); if it does, it's a bug.
- `conflict_arbitrary` — the checker had to break a tie between two equally-important options and did it
  arbitrarily. **These genuinely need a human**; we deliberately do not let the model resolve them.

**One number to distrust:** the usefulness score (`ice_critical_recall`) is **flattered**, because
`core_type` is `critical` in every row and is trivially recovered. Rows whose only critical option is
`core_type` score 100% for free. Read the *spread*, not the level.

---

**Nothing here is gold.** Every row is `review_status: pending`, on a priority table that self-labels
`PROVISIONAL`. Sign-off on the nine decisions above is what turns the table real — and one file changes
(`generation_config/priority_by_factor.json`), not the code.
