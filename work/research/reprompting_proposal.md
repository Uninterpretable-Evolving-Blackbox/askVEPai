# Re-prompting: what the assistant assumes, what it states, and what it asks

Status: **applied, and open to being overturned.** The third design decision the project had to invent
rather than inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). `underspecification_proposal.md` holds the raw measurements.

An earlier version of this document ended in five questions. Four of them turned out to be answerable
from measurements already in this repository, so they have been decided and applied rather than left
waiting on a meeting — §9 lists what changed, what it cost and which single line reverses each one. One
of the four amends the taxonomy you signed off (§5), which is the reason that section still carries the
full argument rather than a summary. The two questions that genuinely need a domain view are still in §9,
and one of them is Jamie's.

---

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes nothing, so every option it would have supplied disappears. The user gets a shorter
configuration with no sign that anything is missing.

## 2. What silence actually costs

Each of our 31 generated queries states all five factors, so exactly one fact can be deleted with
everything else held fixed. A model rewrites the query to read naturally with that fact simply absent,
and every rewrite is re-read before it is used. It counts as **clean** only when the target fact really
went and no other factor moved: **81 of 124 attempts**. Of the remaining 43, 22 lost the words but left
the fact still inferable from context, 15 took a second factor with them, and 6 failed to remove the
words at all.

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
| `region_focus` — filled with *both* | 22 | **0.00** | 1.64 | 11/22 | **0/22** |
| `origin` — filled with *somatic* | 19 | 0.32 | 0.58 | 14/19 | 5/19 |
| `analysis_goal` — filled with *basic-consequence* | 11 | 1.09 | 0.00 | 6/11 | 5/11 |
| `variant_size_class` — left empty | 29 | 1.03 | 4.21 | 14/29 | **15/29** |

Lost and added are not the same error. An extra annotation column is noise the user can ignore; a missing
predictor is a finding they never see. Read that way, the table decides which factors are safe to guess
and what to guess for each:

- **`region_focus`: guess both.** It loses nothing on any of 22 queries. Silence about which regions
  matter is best read as "all of them", and the cost is about 1.6 extra columns.
- **`origin`: guess somatic.** Not because somatic is more likely, but because the two directions fail
  very differently. Guessing somatic withholds one optional pre-filter from a germline user; guessing
  germline applies a filter that deletes a somatic user's findings. Across the review rows, guessing
  somatic harms 0 of 16 germline rows, while leaving it empty lets that filter through on 6 of 15 somatic
  rows, which is the identical harm to guessing germline outright.
- **`analysis_goal`: guess basic-consequence, but see §4.** It is the only guess whose errors are
  subtractive, because reading a question as a plain consequence call drops ClinVar and the predictors.
- **`variant_size_class`: guess both — after fixing the scheme, not before.** Under the single-select
  declaration these measurements were taken under, no value was safe: this is the worst row in the
  table, and leaving it empty was the least-bad of two bad options. The fix was to the scheme rather
  than to the default, and §5 is that fix.

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
| **ask** | no safe guess, and a must-have is at stake | real |

Every guess is stated. A vague question comes back with a working configuration plus one line per guess,
naming what was assumed and how to override it: *"Assumed origin = somatic; say germline if these are
inherited."* Nothing is blocked, and the lines can be ignored.

Species is guessed too. If the question does not say, it runs as human and keeps the human-only tools.
That one is announced by the constraint checker rather than by the lines above, which is plumbing rather
than a different policy.

## 4. When it asks

For each still-empty factor, resolve the configuration under every candidate answer and compare. If no
must-have option differs, the question cannot change what the user gets, so it is never asked. Asking is
also opt-in, because the evaluation harness and the generation pipeline call this code with nobody
present and would otherwise hang.

No model decides this. It is arithmetic over the priority table, costs about 1 ms against a ~1000 ms
classifier call, and is auditable per query.

It is judged per query, not per factor. `origin` changes nothing on a purely clinical question and
decides the common-variant filter on a frequency one, so no fixed per-factor rule is right for both.

**Why `origin` is not simply asked about.** Because being wrong is cheap, and we say so. A wrong guess
costs a disclosure line the user can correct in a sentence, and interrupting everyone to avoid that is a
bad trade. The rule agrees independently: with the guess removed so that nothing suppressed the question,
it asks about `origin` on 0 of the 19 ablations where `origin` was the deleted fact.

**`analysis_goal` did not fit this rule, so it is now asked rather than guessed.** We guess where one
answer is safe and ask where none is. With its guess removed, the rule asks about `analysis_goal` on 11
of 11 ablations, and the value we were substituting loses options on 5 of 11 — subtractive error, the
direction that costs a user a finding rather than a column. Neither condition for guessing held.

It was guessed anyway on the grounds that asking would interrupt on nearly every vague query. That
objection was measuring the wrong set. The 11 of 11 comes from ablations, which delete the fact on
purpose; it is not the rate on real input. On the eight real configuration questions from the trackers,
`analysis_goal` is genuinely absent **once**. It reads as absent three more times only because the two
readers recovered it and disagreed, which the earlier 7-of-8 headline folded into "unstated" — the same
conflation `underspecification_proposal.md` is being corrected for. Eight questions cannot carry a
frequency claim and none is made here; they are enough to show that the reason for guessing did not
hold. Skipping stays free, and the fallback that supplies `basic-consequence` now announces itself
instead of substituting in silence.

## 5. The blocker, and what was done about it

**Applied.** `variant_size_class` is now `select: multi` in `factors.json`, and the policy guesses
*both*. What follows is the argument that was put to you; it is left standing rather than rewritten into
a summary, because the change amends a taxonomy you signed off and you should be able to see what it
rested on and overturn it. One field, one line of policy, and both are named at the end of this section.

It asked whether the variants are small or structural, and `variant_size_class` was `select: single`. A
user answering *both* had half their answer discarded.

The factor describes the **variant set**, not one variant. A single variant is of course one or the
other, but a WGS callset routinely contains both classes, so both is the normal answer for whole-genome
work rather than an edge case. Review row 1 is such a question, and it carries the `factor_unrecoverable`
flag you queried. The values `small` and `structural-CNV` are not the problem; declaring the factor
single-select is, because it forces one answer per dataset where the honest unit holds both.

Interrupting someone, receiving the truthful answer and throwing half of it away is worse than not
asking, which is why the asking behaviour was held back until this was resolved.

The fix is to allow both values, as `region_focus` already does. On the same 29 ablations:

| policy for `variant_size_class` | mean lost | mean added | queries losing something |
|---|---|---|---|
| was — single-select, left empty | 1.03 | 4.21 | 15/29 |
| **now — multi-select, filled with *both*** | **0.00** | 4.28 | **0/29** |

The error becomes purely additive at no measurable cost in added options, and the questions the tool
needs across all 81 ablations go from 16 to zero. Every one of those 16 was this factor.

Offering "both" as a third choice in the question would not fix this. The resolver already accepts two
values and returns exactly the union of the two configurations, so the prompt could offer it today. But
the classifier's schema is generated from the same `select: single` field, so it can only ever return one
value, and review row 1 *states* both in its text rather than leaving it out. Under a prompt-only fix,
someone who writes "SNVs and CNVs" still has half of it discarded and is never asked, because the factor
looks answered; only someone who says nothing gets the right answer. That is backwards, and it leaves the
exhibit unfixed.

The plumbing was already done. `MULTI_FACTORS` and the classifier's prompt schema both derive from
`factors.json`, the sampler, dedup key and tuple slug are cardinality-agnostic, and both configurations
pass the full invariant suite. The hard gate already had the right semantics for a mixed set: it removes
an option only when every active value rules it out, which is why a coding+regulatory query keeps its
predictors.

**What changed, and what did not.** `factors.json` `variant_size_class.select` is `multi`, carrying a
`_select_note` with the evidence; `UNDERSPECIFIED_POLICY["variant_size_class"].assume` is
`["small", "structural-CNV"]`. Nothing else. The 31 review rows are unchanged, all being single-valued,
and the review export still totals 391 recommended and 121 add-ons. `verify_pipeline.py` is 36/36 and
`test_user_context.py` 15/15 — the one test that failed asserted the field was a scalar rather than
asserting what it was there to check, and was fixed rather than worked around.

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

**Resolved by asking, not guessing.** Guessing GRCh38 and saying so is the same shape as every other
guess here, but it is a worse guess than the others: it is wrong for exactly the GRCh37 users the bug
already affects, which is a large part of clinical practice. It is also the one place where the
safer-direction argument that settled `origin` does not apply, because both directions delete something
real. So assembly runs through the same three outcomes as every factor — read it from the text, or ask —
with no guess in the middle.

Asking is cheaper than it sounds, because the text usually says. `infer_assembly` reads a build out of
**4 of the 8** real configuration questions from the trackers, and one of those four is GRCh37, which is
the whole argument against guessing GRCh38 arriving in a sample of eight. The question is raised only for
the other four. The 31 generated review queries name a build **0** times, which is a property of a
generator that only writes about factors: the ablation set is structurally blind to assembly and is not
asked to measure it.

**The question is scored on what the user stated, not on what we assumed for them.** That distinction is
worth more than it sounds: because §5 now guesses *both* variant sizes, gnomAD-SV — GRCh38-only — is
switched on for almost every query, and scoring the filled tuple would raise the assembly question on 42
of the 81 ablations against 33 for the stated one. Nine of those interruptions would exist only because
*we* guessed. That follows the same asymmetry the whole policy rests on: an option we added is a column
the user can ignore and is not worth a question, while an option their own words called for is. MANE is
unaffected either way — 17 either way — because a stated clinical goal is what puts it there.

Suppressed for non-human queries, whose options are gated on species long before a build could matter,
and for a query that described no analysis at all.
(Was open as `../generation/candidates/review/DECISIONS.md` §8.)

## 7. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Guess by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when a must-have is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. Fires 44 times over the 81 ablations under the current policy — 33 assembly, 11 `analysis_goal` — against 16 before, all of which were `variant_size_class` **[Meas]**. Reproduce with `work/harness/ask_rate.py`, which prices every candidate policy on the same 81 cases |
| The bar is the internal must-have tier, not the visible RECOMMENDED bucket | **[Meas]** | after the tier merge "essential" can be read either way, and the two are different rules. Named as `ASK_BAR_PRIORITIES` rather than hardcoded, and priced: widening it to the bucket the user sees changes nothing under the current guesses, and adds 6 `origin` questions if the guesses are removed. Kept narrow because every published number was measured under it |
| Guesses are stated, never silent | **[Judg]** | the failure this design answers is invisible omission, and a silent fix reproduces it |
| `region_focus` guessed *both* | **[Meas]** | 0.00 options lost across 22 ablations, confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it empty lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| `variant_size_class` guessed *both* | **[Meas]** | under single-select no value was safe — leaving it empty loses on 15 of 29 queries and the two candidates gate opposite halves of the catalogue. Multi-select makes *both* available and it loses on 0 of 29, for 4.28 added options against 4.21 |
| `analysis_goal` asked, not guessed | **[Meas]** | fails both conditions for guessing on our own measurements: asked on 11 of 11 ablations with the guess removed, and the substituted value loses options on 5 of 11. The objection that asking would interrupt everyone was measured on ablations that delete the fact; on the 8 real questions it is genuinely absent once |
| Assembly is not a factor, but is asked | **[Src]** + **[Judg]** + **[Meas]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it describes the input data rather than the analysis is my reading **[Judg]**. Not guessed because both directions delete something real, and asking is affordable: the text names a build on 4 of the 8 real questions, one of them GRCh37 **[Meas]** |
| How often users omit things | **not established** | `fetch_real_queries.py` pulls tracker issues verbatim with a per-body SHA-256 and a `--verify` re-fetch, but only 8 of 43 are configuration questions. Biostars is Cloudflare-blocked at both the HTML and the API. Too few to carry a frequency claim |

The structure is my own reading, grounded in measurements taken on this repository and in how VEP's own
form behaves. Nothing derives from a published interface standard, because I did not find one that
applies. The ablations are reproducible with `ablate_queries.py`, without a GPU, and the judgement calls
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
```

`--factors` needs no model. Neither does `ask_rate.py`: the classifier was already run on every ablated
query and its reading recorded, so it replays the decision half of the path exactly, over every candidate
policy on the same 81 cases, in seconds. It is the file to read first if you want to argue with any
number in this document — including by adding an arm of your own.

The `--multi` flag that used to appear here simulated §5 before it landed, and is gone.

## 9. Decisions taken, and what is actually still open

Four of the five questions this section used to ask were answerable from measurements already in this
repository, and asking them was deferring work rather than seeking a ruling. They are decided, applied
and priced below. Each is one constant or one field, named, so any of them can be overturned by editing
one line — and the arm that measures the alternative is already in `ask_rate.py`.

| decided | what it now does | where | cost, measured |
|---|---|---|---|
| A variant set can be both sizes (§5) | `select: multi`, guessed *both* | `factors.json` | questions over the 81 ablations: 16 → 0 for this factor; review rows and export totals unchanged |
| `analysis_goal` is asked (§4) | no guess; the fallback announces itself | `UNDERSPECIFIED_POLICY` | 11 questions over the 81 ablations; genuinely absent on 1 of the 8 real questions |
| Assembly is asked (§6) | read from the text, else ask | `assembly_question` | 33 over the 81 ablations; the text already names it on 4 of the 8 real questions |
| The bar stays the internal must-have tier (§4) | named, not hardcoded | `ASK_BAR_PRIORITIES` | widening it to the visible bucket changes nothing under the current guesses; +6 `origin` without them |

**What this costs overall, stated plainly.** The tool now interrupts on **38 of the 81 ablations**, where
before it interrupted on 16. That is a real change of character for a design whose first principle is
that asking is the exception, and it deserves your eye rather than a footnote. Two things temper it and
neither disposes of it: 33 of the 44 questions are about assembly, which the ablation set can only
overstate because its queries never name a build while 4 of 8 real ones do; and skipping any question is
free and now leaves an announced assumption rather than a silent one. If you think that is still too
talkative, the lever is §6's relevance test, and `ask_rate.py --arm "goal guessed"` prices the other
direction.

**Still open, and genuinely yours:**

1. **Jamie's alternative to §5.** From his note on row 1: a mixed set is really two analyses, and the tool
   should say so rather than emit one configuration covering both. What is implemented is the union,
   because that is what the resolver already computed and what the hard gate already had the right
   semantics for. His version changes what the tool *outputs*, not what the factor can hold, so it is not
   settled by the measurements above and it is his proposal to press. If he wants it, it is a change to
   the output shape rather than to the taxonomy.
2. **Are there facts the tool should be capturing and is currently guessing?** `cell_type` is the one I am
   least sure about, since it needs a value only the user has. Aleena's note on row 13, that users often
   specify which populations they care about, mostly 1000 Genomes, is a second candidate — `frequency` is
   a switch in our catalogue but what they want is a value.

Both remaining questions need a domain view rather than another experiment. Everything above them was a
question I should have measured instead of asked.
