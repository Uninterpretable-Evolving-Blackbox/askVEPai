# Re-prompting: what the assistant assumes, what it states, and what it asks

Status: **applied, and open to being overturned.** The third design decision the project had to invent
rather than inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). `underspecification_proposal.md` holds the raw measurements.

---

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes nothing, so every option it would have supplied disappears. The user gets a shorter
configuration with no sign that anything is missing.

## 2. What silence actually costs

Each of our 31 generated queries states all five factors, so exactly one fact can be deleted with
everything else held fixed. A model rewrites the query to read naturally with that fact simply absent,
and every rewrite is re-read before it is used. It counts as **clean** only when the target fact really
went and no other factor moved: **78 of 124 attempts**. Of the remaining 46, 24 lost the words but left
the fact still inferable from context, 16 took a second factor with them, and 6 failed to remove the
words at all. The build is reproducible: three seeds matching the LOO's, spread zero.

Each clean case then goes through the tool's normal path. The classifier reads the rewritten query, the
gap it leaves is **filled with the default under test**, and the resulting configuration is compared
against the one the true factor values produce. So the table measures what silence plus that default
costs, which is why each row names the value it filled in.

**Lost** is options the true configuration has and ours does not, averaged per query, so annotations the
user should have received and did not. **Added** is the reverse. **Exactly right** counts queries where
the two sets match completely, and **losing something** counts queries missing at least one option,
however many. The n differs per row because rewrites for some factors more often failed the purity check.

| fact deleted | n | mean options **lost** | mean options added | exactly right | queries losing something |
|---|---|---|---|---|---|
| `region_focus` — guessed *both* | 23 | **0.00** | 1.70 | 11/23 | **0/23** |
| `origin` — guessed *somatic* | 20 | 0.35 | 0.75 | 14/20 | 6/20 |
| `variant_size_class` — guessed *both* | 23 | **0.00** | 4.43 | 9/23 | **0/23** |
| `analysis_goal` — asked; *basic-consequence* on skip | 12 | 1.00 | 0.00 | 7/12 | 5/12 |

Lost and added are not the same error. An extra annotation column is noise the user can ignore; a missing
predictor is a finding they never see. Read that way, the table decides which factors are safe to guess
and what to guess for each:

- **`region_focus`: guess both.** It loses nothing on any of 23 queries, at a cost of about 1.7 extra
  columns. A deterministic sweep over the 31 rows agrees and is the reason this value was chosen:
  F1 **0.92** for *both*, against 0.86 for *coding*, 0.85 for *regulatory* and 0.78 for leaving it blank.
- **`origin`: guess somatic.** Not because somatic is more likely, but because the two directions fail
  very differently. Guessing somatic withholds one pre-filter from a germline user; guessing
  germline applies a filter that deletes a somatic user's findings. Across the review rows, guessing
  somatic harms 0 of 16 germline rows, while leaving it empty lets that filter through on 6 of 15 somatic
  rows, which is the identical harm to guessing germline outright.

  Leaving it empty is **strictly worse than either value**. Silence carries germline's risk on
  `frequency` *and* additionally drops `check_existing`, which germline and somatic both enable — on all
  31 rows. So the first half of this decision is that something must be guessed at all; only the second
  half is that the something is somatic.

  **This is the one default that is not loss-free, and the cost is not an add-on.** Measured on the 31
  rows, guessing somatic costs `frequency` on **7 of 31**, and `frequency` resolves at `recommended`,
  which the two-tier merge puts in the RECOMMENDED bucket the user sees switched on. So a germline user
  on a frequency question loses something that would have been on for them. That is the price of the
  fail-closed direction, paid deliberately.
- **`variant_size_class`: guess both.** Nothing lost on any of 23 queries, at a cost of about 4.4 extra
  columns. This is only expressible because the factor is multi-select; neither single value is safe,
  since `small` and `structural-CNV` gate away opposite halves of the catalogue. §5.
- **`analysis_goal`: ask.** It is the only factor whose error is subtractive — reading a question as a
  plain consequence call drops ClinVar and the predictors — and it fails both conditions for guessing.
  §4.

Two further findings from the same ablations. When `variant_size_class` was deleted, the fact was still
recoverable from surrounding context only **2 times in 31**, so it is genuinely not in the prose and no
better prompt or larger model recovers it. `analysis_goal` was recoverable **17 of 31**, so it is rarely
truly missing.

## 3. The design

A recommender that interrogates its users has moved the work back onto them, which is the opposite of
what the tool is for. So a gap has three possible outcomes, and asking is the last of them:

| | when | friction |
|---|---|---|
| **take it from the text** | the question settles it | none |
| **guess, and say which** | one answer is clearly safer than the others. *The normal case.* | none |
| **ask** | no safe guess, and something in the RECOMMENDED bucket is at stake | real |

Every guess is stated. A vague question comes back with a working configuration plus one line per guess,
naming what was assumed and how to override it: *"Assumed origin = somatic; say germline if these are
inherited."* Nothing is blocked, and the lines can be ignored.

Species is guessed too, and announced by the constraint checker rather than by the lines above, which is
plumbing rather than a different policy. A keyword rule reads it from the text and returns `unknown` when
it cannot tell — **4 of the 8** real tracker questions — and `unknown` runs as human, because treating it
as non-human would strip gnomAD, ClinVar and the predictors from human studies that merely never use the
word. It fails in the other direction: a non-human query that never says so keeps the human-only options.
This is the one guessed value chosen by judgement rather than by a measurement, and the weakest of them.

## 4. When it asks

For each still-empty factor, resolve the configuration under every candidate answer and compare. If
nothing in the RECOMMENDED bucket differs, the question cannot change what the user is shown, so it is
never asked. Asking is also opt-in, because the evaluation harness and the generation pipeline call
this code with nobody present and would otherwise hang.

No model decides this. It is arithmetic over the priority table, costs about 1 ms against a ~1000 ms
classifier call, and is auditable per query.

It is judged per query, not per factor. `origin` changes nothing on a purely clinical question and
decides the common-variant filter on a frequency one, so no fixed per-factor rule is right for both.

**Why `origin` is not simply asked about.** Being wrong is cheap here, and the guess is disclosed rather
than silent: it costs a line the user can correct in a sentence, and interrupting everyone to avoid that
is a bad trade.

That is now the whole argument, and it used to have a second leg that no longer holds. Under the
narrower bar — the internal must-have tier — removing the guess produced **0** origin questions across
the 20 ablations, so the rule appeared to agree independently. Widening the bar to the RECOMMENDED
bucket the user actually sees (§7) changes that: with the guess removed it asks about `origin` on
**6 of the 20**. Reproduce both with `ask_rate.py --by-row --arm ask-all` and
`--arm "ask-all, narrow bar"`. The guess still stands on the asymmetry of being wrong, but it no longer
gets corroboration from the ask rule, and it would be dishonest to keep claiming it does.

**Why `analysis_goal` is asked.** We guess where one answer is safe and ask where none is, and it meets
neither condition: the rule asks about it on 12 of 12 ablations, and the fallback value loses options on
5 of 12 — subtractive error, the direction that costs a user a finding rather than a column.

The ablations overstate how often this interrupts anyone, because they delete the fact on purpose. On
the eight real configuration questions from the trackers, `analysis_goal` is genuinely absent **once**;
it reads as absent three more times only because the two readers recovered it and disagreed, which is a
fact about our classifier rather than about the prose. Eight questions cannot carry a frequency claim and
none is made. Skipping is free: the fallback supplies `basic-consequence` and announces itself, because
a configuration cannot resolve without a goal at all — an empty one gives about 6 options instead of
about 13.

## 5. A variant set can be both sizes

`variant_size_class` is `select: multi` in `factors.json` and the policy guesses *both*. This amends the
taxonomy signed off in `taxonomy_proposal.md` §3, so the argument for it is set out in full rather than
summarised, and it is one field plus one line of policy to overturn.

The factor describes the **variant set**, not one variant. A single variant is of course one or the
other, but a WGS callset routinely contains both classes, so both is the normal answer for whole-genome
work rather than an edge case. Review row 1 is such a question, and it carries the `factor_unrecoverable`
flag. The values `small` and `structural-CNV` are not the problem; single-select is, because it forces
one answer per dataset where the honest unit holds both — and a user who answers *both* has half of it
discarded, which is worse than never asking.

Allowing both values, as `region_focus` already does, is what makes the safe guess expressible. On the
same 23 ablations:

| policy for `variant_size_class` | mean lost | mean added | queries losing something |
|---|---|---|---|
| single-select, no safe value, asked | 1.13 | 4.13 | 13/23 |
| **multi-select, guessed *both*** | **0.00** | 4.22 | **0/23** |

The error becomes purely additive at no measurable cost in added options, and this factor asks nothing:
it accounts for every one of the 14 questions the single-select policy raises across the 78 ablations.

Offering "both" as a third choice in the question would not fix this. The resolver already accepts two
values and returns exactly the union of the two configurations, so the prompt could offer it today. But
the classifier's schema is generated from the same `select: single` field, so it can only ever return one
value, and review row 1 *states* both in its text rather than leaving it out. Under a prompt-only fix,
someone who writes "SNVs and CNVs" still has half of it discarded and is never asked, because the factor
looks answered; only someone who says nothing gets the right answer. That is backwards, and it leaves the
exhibit unfixed.

Nothing else in the pipeline needs to change for it. `MULTI_FACTORS` and the classifier's prompt schema
both derive from `factors.json`; the sampler, dedup key and tuple slug are cardinality-agnostic. The hard
gate has the right semantics for a mixed set: it removes an option only when every active value rules it
out, which is why a coding+regulatory query keeps its predictors.

**Where it lives.** `factors.json` `variant_size_class.select` is `multi`, carrying a `_select_note` with
the evidence; `UNDERSPECIFIED_POLICY["variant_size_class"].assume` is `["small", "structural-CNV"]`. The
31 review rows are unaffected, all being single-valued, and the review export totals 391 recommended and
121 add-ons. `verify_pipeline.py` 36/36, `test_user_context.py` 15/15.

**The consequence worth knowing.** Guessing *both* switches gnomAD-SV on for almost every query. That is
the "added options" cost the table already prices, and it is harmless as a column — but gnomAD-SV is
GRCh38-only, so it also drags the assembly question of §6 into scope on queries that never mentioned
structural variants. The rule in §6 is scored on what the user stated for exactly this reason.

## 6. Assembly, which no factor covers

A related gap, and the only one where silence produces a wrong answer rather than a thin one. MANE Select
transcripts exist only for GRCh38, but `InputForm.pm:694-702` shows the MANE checkbox to any human user
and pre-ticks it, so a GRCh37 user gets an option with no data behind it without opting in. Our checker
can enforce the restriction once it knows the build, and a query that never names one gives it nothing to
infer from.

**Asked, never guessed.** Guessing GRCh38 and saying so would be the same shape as every other guess
here, but it is a worse guess than the others: it is wrong for exactly the GRCh37 users the bug already
affects, which is a large part of clinical practice. It is also the one place where the safer-direction
argument that settles `origin` does not apply, because both directions delete something real. So
assembly runs through the same three outcomes as every factor — read it from the text, or ask — with no
guess in the middle.

Asking is cheaper than it sounds, because the text usually says. `infer_assembly` reads a build out of
**4 of the 8** real configuration questions from the trackers, and one of those four is GRCh37, which is
the whole argument against guessing GRCh38 arriving in a sample of eight. The question is raised only for
the other four. The 31 generated review queries name a build **0** times, which is a property of a
generator that only writes about factors: the ablation set is structurally blind to assembly and is not
asked to measure it.

**The question is scored on what the user stated, not on what we assumed for them.** That distinction is
worth more than it sounds: because §5 now guesses *both* variant sizes, gnomAD-SV — GRCh38-only — is
switched on for almost every query, and scoring the filled tuple would raise the assembly question on 42
of the 78 ablations against 32 for the stated one. Eight of those interruptions would exist only because
*we* guessed. That follows the same asymmetry the whole policy rests on: an option we added is a column
the user can ignore and is not worth a question, while an option their own words called for is. MANE is
unaffected either way — 17 either way — because a stated clinical goal is what puts it there.

Suppressed for non-human queries, whose options are gated on species long before a build could matter,
and for a query that described no analysis at all.

## 7. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** a design judgement, with no external source behind it.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Guess by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when something in the RECOMMENDED bucket is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. Fires 44 times over the 78 clean ablations — 32 assembly, 12 `analysis_goal` **[Meas]**. Reproduce with `work/harness/ask_rate.py`, which prices every candidate policy on the same 78 cases |
| The bar is the RECOMMENDED bucket the user is shown | **[Meas]** | the alternative is the internal `critical` tier, and that boundary is the one the review found unstable — twelve of the twenty mentor edits were critical↔recommended moves, which is why the display was merged. An interruption should not depend on a label the reviewer redrew twelve times and the user never sees. Priced before choosing: on the current guesses both bars raise identical questions, diverging only if the guesses are removed (+6 `origin`). `ASK_BAR_PRIORITIES` keeps the comparison runnable |
| Guesses are stated, never silent | **[Judg]** | the failure this design answers is invisible omission, and a silent fix reproduces it |
| `region_focus` guessed *both* | **[Meas]** | 0.00 options lost across 22 ablations, confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it empty lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| `variant_size_class` guessed *both* | **[Meas]** | under single-select no value was safe — leaving it empty loses on 13 of 23 queries and the two candidates gate opposite halves of the catalogue. Multi-select makes *both* available and it loses on 0 of 23, for 4.22 added options against 4.13 |
| `analysis_goal` asked, not guessed | **[Meas]** | fails both conditions for guessing on our own measurements: asked on 12 of 12 ablations with the guess removed, and the fallback value loses options on 5 of 12. The objection that asking would interrupt everyone was measured on ablations that delete the fact; on the 8 real questions it is genuinely absent once |
| Assembly is not a factor, but is asked | **[Src]** + **[Judg]** + **[Meas]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**. Assembly describes the input data rather than the analysis **[Judg]**. Not guessed because both directions delete something real, and asking is affordable: the text names a build on 4 of the 8 real questions, one of them GRCh37 **[Meas]** |
| How often users omit things | **not established** | `fetch_real_queries.py` pulls tracker issues verbatim with a per-body SHA-256 and a `--verify` re-fetch, but only 8 of 43 are configuration questions. Biostars is Cloudflare-blocked at both the HTML and the API. Too few to carry a frequency claim |

The structure is a synthesis, grounded in measurements taken on this repository and in how VEP's own
form behaves. No published interface standard was found that applies. The ablations are reproducible with `ablate_queries.py`, without a GPU, and the judgement calls
are marked.

Cost and consequence are measured; the tables above say what each gap does to the configuration. How
often real users leave a fact out is not, and that number decides how aggressive to be. The cheapest
route to it is the `real_data` Likhitha has offered.

Nearest literature: Gervits et al., ICMI '21 (arXiv:2110.06288) select clarification questions by maximum
expected utility over a decision network, setting the utility of asking about an already-known property
to zero. Our relevance gate is the same principle in deterministic form. Theirs needs priors, a corpus
and a model of the interlocutor; ours needs none and is auditable per query, at the cost of not being
able to trade the cost of asking against its benefit. Read pp. 1–5 of 9, with §5–6 not read, so no claim
is made about how their model performed.

## 8. Trying it

```bash
python vep_assistant.py "human tumour WGS, which variants are damaging?"      # guesses, stated
python vep_assistant.py --assume "..."                                        # guesses, silent
python vep_assistant.py --ask "..."                                           # also prompt

python work/harness/try_reprompting.py --why "human tumour WGS, ..."          # what it did, and why
python work/harness/try_reprompting.py --factors species=human,analysis_goal=population-frequency

python work/harness/ask_rate.py                                              # how often it interrupts
python work/harness/ask_rate.py --by-row --arm shipped                       # and on which cases
python work/harness/defaults_evidence.py --verbose                           # why each default is that
```

`defaults_evidence.py` re-derives the justification for **every** guessed value and fails if one no
longer holds — the sweep table above, the danger audit's 0-of-16 and 6-of-15, the 0-of-29, the 4-of-8
abstention rate, and the two conditions `analysis_goal` fails. It is the answer to "how did you decide
that?" being executable rather than a paragraph.

`--factors` needs no model. Neither does `ask_rate.py`: the classifier was already run on every ablated
query and its reading recorded, so it replays the decision half of the path exactly, over every candidate
policy on the same 78 cases, in seconds. It is the file to read first if you want to argue with any
number in this document — including by adding an arm of your own.

## 9. What this costs, and what needs your ruling

Each decision below is one named constant or one field, so any of them can be overturned by editing a
single line — and `ask_rate.py` already carries an arm that prices the alternative.

| decision | where | cost, measured |
|---|---|---|
| A variant set can be both sizes (§5) | `factors.json` | this factor asks nothing; review rows and export totals unaffected |
| `analysis_goal` is asked (§4) | `UNDERSPECIFIED_POLICY` | 12 questions over the 78 ablations; genuinely absent on 1 of the 8 real questions |
| Assembly is asked (§6) | `assembly_question` | 32 over the 78 ablations; the text already names it on 4 of the 8 real questions |
| The interrupt bar is the visible RECOMMENDED bucket (§4) | `ASK_BAR_PRIORITIES` | identical to the narrow bar on the current guesses; the two diverge only without them (+6 `origin`) |

**The headline cost.** The tool interrupts on **38 of the 78 ablations**, raising 44 questions. That is a
lot for a design whose first principle is that asking is the exception, and it deserves your eye rather
than a footnote. Two things temper it and neither disposes of it: 32 of the 44 are about assembly, which
the ablation set can only overstate because its queries never name a build while 4 of 8 real ones do; and
skipping any question is free and leaves an announced assumption rather than a silent one. If that is
still too talkative, the lever is §6's relevance test, and `ask_rate.py --arm "goal guessed"` prices the
other direction.

**Needing your ruling:**

1. **Jamie's alternative to §5.** From his note on row 1: a mixed set is really two analyses, and the tool
   should say so rather than emit one configuration covering both. What is implemented is the union,
   because that is what the resolver computes and what the hard gate's semantics already support. His
   version changes what the tool *outputs*, not what the factor can hold, so the measurements above do not
   settle it. It is a change to the output shape rather than to the taxonomy.
2. **Does `origin` earn its place in the taxonomy?** Measured across every tuple, germline and somatic
   produce *identical* configurations except for one option — `frequency` — and they differ on only 9 of
   54 tuples, all of them human population-frequency scenarios. They never even differ in priority. The
   taxonomy's own bar is that a factor must gate or shift a **cluster** of options, and one option is not
   a cluster. Two honest readings: the factor is carrying a single hard safety rule and that is enough to
   justify it, or the rule belongs on `analysis_goal` and `origin` should be a checker concern rather than
   a factor. The first reading is the stronger one, since the rule it carries is the only one that can
   destroy data — but the measurement does not settle it, and the taxonomy is yours. Re-derive with
   `work/harness/defaults_evidence.py`.
3. **Are there facts the tool should be capturing and is currently guessing?** `cell_type` is the one I am
   least sure about, since it needs a value only the user has. Aleena's note on row 13, that users often
   specify which populations they care about, mostly 1000 Genomes, is a second candidate — `frequency` is
   a switch in our catalogue but what they want is a value.

Both remaining questions need a domain view rather than another experiment. Everything above them was a
question I should have measured instead of asked.
