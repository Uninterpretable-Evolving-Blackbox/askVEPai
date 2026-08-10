# Re-prompting: what the assistant assumes, what it states, and what it asks

Status: proposal, with measurements. The third design decision the project had to invent rather than
inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). It changes the interface contract, so I would like sign-off before
it is final. `underspecification_proposal.md` holds the raw measurements.

---

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes nothing, so every option it would have supplied disappears. The user gets a shorter
configuration with no sign that anything is missing.

## 2. What silence actually costs

Two experiments sit behind everything below and they do different jobs, so both come first.

**Choosing the values.** For each factor, blank it across the 31 review rows, resolve the configuration
under every candidate value, and score each against that row's known-correct configuration. That is how
*both* was chosen for `region_focus`: F1 0.92, against 0.86 for *coding*, 0.85 for *regulatory* and 0.78
for leaving it blank. `origin` was settled differently, by a danger audit asking which wrong guess
switches on something destructive rather than which loses most options. `analysis_goal` was never chosen
at all: the code already defaulted to it silently, and the change was to say so.

**Checking them on harder input.** Blanking a tuple is artificial, because no real query arrives as a
tuple with a hole in it. So the values were re-tested against prose.

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
- **`variant_size_class`: do not guess.** No value is safe, so it is left empty and asked about instead.
  This is the worst row in the table and the subject of §5.

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

**`analysis_goal` does not fit this rule, and I would rather say so than defend it.** We guess where one
answer is safe and ask where none is. With its guess removed, the rule would ask about `analysis_goal` on
11 of 11 ablations, and the value we substitute loses options on 5 of 11. Neither condition for guessing
holds. Asking would mean interrupting on nearly every vague query, which is why it was guessed, but the
honest choice is either to ask or to stop describing all three guesses as safe. §9.2.

## 5. The blocker: the tool asks a question it cannot accept the honest answer to

It asks whether the variants are small or structural, and `variant_size_class` is `select: single`. A
user answering *both* has half their answer discarded.

The factor describes the **variant set**, not one variant. A single variant is of course one or the
other, but a WGS callset routinely contains both classes, so both is the normal answer for whole-genome
work rather than an edge case. Review row 1 is such a question, and it carries the `factor_unrecoverable`
flag you queried. The values `small` and `structural-CNV` are not the problem; declaring the factor
single-select is, because it forces one answer per dataset where the honest unit holds both.

Interrupting someone, receiving the truthful answer and throwing half of it away is worse than not
asking, so the asking behaviour does not ship until this is resolved.

The fix is to allow both values, as `region_focus` already does. On the same 29 ablations:

| policy for `variant_size_class` | mean lost | mean added | queries losing something |
|---|---|---|---|
| today — single-select, left empty | 1.03 | 4.21 | 15/29 |
| **multi-select, filled with *both*** | **0.00** | 4.28 | **0/29** |

The error becomes purely additive at no measurable cost in added options, and the questions the tool
needs across all 81 ablations go from 16 to zero. Every one of those 16 was this factor.

Offering "both" as a third choice in the question would not fix this. The resolver already accepts two
values and returns exactly the union of the two configurations, so the prompt could offer it today. But
the classifier's schema is generated from the same `select: single` field, so it can only ever return one
value, and review row 1 *states* both in its text rather than leaving it out. Under a prompt-only fix,
someone who writes "SNVs and CNVs" still has half of it discarded and is never asked, because the factor
looks answered; only someone who says nothing gets the right answer. That is backwards, and it leaves the
exhibit unfixed.

The plumbing is done. `MULTI_FACTORS` and the classifier's prompt schema both derive from `factors.json`,
the sampler, dedup key and tuple slug are cardinality-agnostic, and both configurations pass the full
invariant suite. The hard gate already has the right semantics for a mixed set: it removes an option only
when every active value rules it out, which is why a coding+regulatory query keeps its predictors. The 31
review rows are unchanged, all being single-valued.

It is one field in `factors.json`, but it changes the taxonomy that was signed off, so it needs a ruling
rather than a commit.

## 6. Assembly, which no factor covers

A related gap, and the only one where silence produces a wrong answer rather than a thin one. MANE Select
transcripts exist only for GRCh38, but `InputForm.pm:694-702` shows the MANE checkbox to any human user
and pre-ticks it, so a GRCh37 user gets an option with no data behind it without opting in. Our checker
can enforce the restriction once it knows the build, and a query that never names one gives it nothing to
infer from.

Guessing GRCh38 and saying so is the same shape as every other guess here, but it is a worse guess than
the others: it is wrong for exactly the GRCh37 users the bug already affects, which is a large part of
clinical practice. Asking is the alternative, and it would be the only question the tool asks that is not
about the analysis itself. §9.3 asks which.
(Open as `../generation/candidates/review/DECISIONS.md` §8.)

## 7. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Guess by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when a must-have is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. On 81 ablations it fires 16 times, all on the one factor genuinely unrecoverable from text **[Meas]** |
| Guesses are stated, never silent | **[Judg]** | the failure this design answers is invisible omission, and a silent fix reproduces it |
| `region_focus` guessed *both* | **[Meas]** | 0.00 options lost across 22 ablations, confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it empty lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| `variant_size_class` never guessed | **[Meas]** | the only factor where no value is safe: leaving it empty loses on 15 of 29 queries, and the two candidate values gate opposite halves of the catalogue |
| Assembly is not a factor | **[Src]** + **[Judg]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it describes the input data rather than the analysis is my reading **[Judg]** |
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
python work/harness/try_reprompting.py --multi "human WGS with SNVs and CNVs" # simulates §5
```

`--factors` needs no model. `--multi` applies the §5 change in memory only, so trying it cannot leave the
repository half-changed. `--ask` shows the blocker from §5 directly: it offers *small* or
*structural-CNV* and no way to say both.

## 9. What I would like you to rule on

1. **Can a variant set be both small and structural?** (§5) Blocking. It unblocks deployment and removes
   the only question the system ever asks. `region_focus` already works this way, and 13 of the 31 rows
   you reviewed carry both of its values, so this is precedent rather than a novel request. A third
   answer is possible, and it is Jamie's, from his note on row 1: that a mixed set is really two
   analyses and the tool should say so rather than emit one configuration covering both. That changes
   what the tool outputs rather than what the factor can hold, so it needs deciding here as well.
2. **Is `analysis_goal` in the right bucket?** (§4) It fails our own test for guessing, on our own
   measurements. Should it be asked instead, accepting that this means interrupting on nearly every vague
   query? Related and smaller: an empty goal resolves to 6 options instead of about 13, so the
   configuration collapses rather than failing. Something therefore fills it in even when someone is
   asked and skips, and that currently happens with no announcement.
3. **Assembly** (§6): guess GRCh38 and say so, or ask? This is the one where silence produces a wrong
   answer rather than an incomplete one.
4. **Is "it changes something essential" the right bar for interrupting someone?** (§4) The bar is a
   clinical judgement encoded in the priority table you are reviewing, so it is really yours. A more
   consistent alternative is to guess only where the guess costs nothing, which is `region_focus` alone,
   and ask about everything else with today's values as the fallback on skip. Priced on the eight real
   configuration questions pulled from the trackers, that raises 13 questions instead of 4 and
   interrupts all 8 users instead of 4, because `origin` is unstated in every one of them. The
   measurements cannot settle whether that trade is worth making.
5. **Are there facts the tool should be capturing and is currently guessing?** `cell_type` is the one I
   am least sure about, since it needs a value only the user has. Aleena's note on row 13, that users
   often specify which populations they care about, is a second candidate.
