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

## 2. The design

A recommender that interrogates its users has moved the work back onto them, which is the opposite of
what the tool is for. So a gap has four possible outcomes, and asking is the last of them:

| | when | friction |
|---|---|---|
| **take it from the text** | the question settles it | none |
| **assume, and say which** | the question does not settle it, but one answer is clearly safer. *The normal case.* | none |
| **take what the user stated** | they set one of the optional fields | none, and optional |
| **ask** | no safe assumption, and a must-have is at stake | real |

Every guess is stated. A vague question comes back with a working configuration plus one line per guess,
naming what was assumed and how to override it: *"Assumed origin = somatic; say germline if these are
inherited."* Nothing is blocked, and the lines can be ignored.

Species is guessed too. If the question does not say, it runs as human and keeps the human-only tools.
That one is announced by the constraint checker rather than by the lines above.

**The optional fields have not been put in front of you.** Beside the query box are four dropdowns:
species, germline or somatic, small or structural, and assembly. Each defaults to reading the
description, so anyone who ignores them gets exactly what they got before, and anything set overrides
what the model read. §5 has the reasoning. It is flagged here because the table refers to the fields as
though they were established, and they are not.

## 3. When it asks

For each still-open factor, resolve the configuration under every candidate answer and compare. If no
must-have option differs, the question cannot change what the user gets, so it is never asked. Asking is
also opt-in, because the evaluation harness and the generation pipeline call this code with nobody
present and would otherwise hang.

No model decides this. It is arithmetic over the priority table, costs about 1 ms against a ~1000 ms
classifier call, and is auditable per query.

It is judged per query, not per factor. `origin` changes nothing on a purely clinical question and
decides the common-variant filter on a frequency one, so no fixed per-factor rule is right for both.

**Why `origin` is not simply asked about.** Because being wrong is cheap, and we say so. Guessing somatic withholds one optional pre-filter from a germline user; guessing germline applies a filter that deletes a somatic user's findings. Across the review rows, assuming somatic harms 0 of 16 germline rows. A wrong guess costs a disclosure line the user can correct in a sentence, and interrupting everyone to avoid that is a bad trade. The rule agrees independently: with the assumption removed so that nothing suppressed the question, it asks about origin on 0 of the 19 ablations where origin was the removed fact.

## 4. What it assumes, and what each assumption costs

Measured on 81 controlled ablations. One fact is removed from each of our own 31 queries and everything
else held fixed, so the right answer is known. Each ablated query then goes through the normal path,
classifier and assumptions with no asking, and the resulting configuration is compared to the one the
true factor values produce. This measures what silence plus a default costs, not what a question buys.

Reading the columns: **lost** is options the true configuration has that ours does not, averaged per
query, so annotations the user should have got and did not. **Added** is the reverse. **Exactly right**
is queries where the two sets match completely, and **losing something** counts queries missing at least
one option, however many.

| fact removed | n | mean options **lost** | mean options added | exactly right | queries losing something |
|---|---|---|---|---|---|
| `region_focus` — assume *both* | 22 | **0.00** | 1.64 | 11/22 | **0/22** |
| `origin` — assume *somatic* | 19 | 0.32 | 0.58 | 14/19 | 5/19 |
| `analysis_goal` — assume *basic-consequence* | 11 | 1.09 | 0.00 | 6/11 | 5/11 |
| `variant_size_class` — left open | 29 | 1.03 | 4.21 | 14/29 | **15/29** |

Lost and added are not the same error. An extra annotation column is noise the user can ignore; a
missing predictor is a finding they never see. Read that way:

- **`region_focus = both`** is the strongest assumption here, losing nothing on any of 22 queries.
- **`origin = somatic`** is fail-closed. The *somatic ⇒ no common-variant filter* rule fires only on an
  explicit somatic, so leaving it open lets that filter through on 6 of the 15 somatic review rows, which
  is the identical harm to guessing germline. Guessing somatic harms 0 of 16 germline rows.
- **`analysis_goal`** is the weakest, and the only assumption whose errors are subtractive: reading a
  question as a plain consequence call drops ClinVar and the predictors.
- **`variant_size_class`**, the one factor left open, is the worst of the four. See §6.

`analysis_goal` also does not fit our own rule, which is to assume where one answer is safe and ask where
none is. With its assumption removed, the rule would ask about it on 11 of 11 ablations, and the value we
assume instead loses options on 5 of 11. Neither condition for assuming holds. Asking would mean
interrupting on nearly every vague query, which is why it was assumed, but the honest choice is either to
ask or to stop describing all three assumptions as safe. §9.3.

## 5. What the user can state outright

Beside the query box are four optional dropdowns: species, germline or somatic, small or structural, and
assembly. Set one and that value is used; leave them alone, which is the default, and the model reads the
query exactly as before.

Those three factors are facts about the *sample* rather than about the analysis. Whoever is asking knows
them without thinking, and they are where every classifier error we measured landed. What a dropdown
cannot capture is what the user is trying to find out, so that stays in the text. VEP's own form already
asks for species in a dropdown rather than inferring it.

Ignoring the fields changes nothing, and this is tested: with none set, the resolved configuration, the
priority labels, the checker's changes and the classifier's output are all identical to before
(`test_user_context.py`, 15 checks, no GPU).

**The fourth box, assembly, is not a factor.** It exists to fix a correctness bug. MANE Select transcripts
exist only for GRCh38, but `InputForm.pm:694-702` shows the MANE checkbox to any human user and
pre-ticks it, so a GRCh37 user gets an option with no data behind it without opting in. We can enforce
the restriction once we know the build, and a query that never names one gives us nothing to infer from.

Two ways to supply it, and they are not equally good. A field asks the user. A stated GRCh38 default
guesses, and it guesses wrong for exactly the GRCh37 users the bug already affects, which is a large part
of clinical practice. §9.4 asks which. Either way assembly describes the input data, like the file
format, rather than the analysis, so it does not belong in the factor scheme.
(Open as `../generation/candidates/review/DECISIONS.md` §8.)

## 6. The blocker: the tool asks a question it cannot accept the honest answer to

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
| today — single-select, left open | 1.03 | 4.21 | 15/29 |
| **multi-select, assumed *both* when unstated** | **0.00** | 4.28 | **0/29** |

The error becomes purely additive at no measurable cost in added options, and the questions the tool
needs across all 81 ablations go from 16 to zero. Every one of those 16 was this factor.

There is a second reason this factor is the one that breaks. When it was removed, the fact was still
recoverable from surrounding context only 2 times in 31, so it is not in the prose and no better prompt
or larger model recovers it. `analysis_goal` was recoverable 17 of 31, so it is rarely genuinely missing.

The plumbing is done. `MULTI_FACTORS` and the classifier's prompt schema both derive from `factors.json`,
the sampler, dedup key and tuple slug are cardinality-agnostic, and both configurations pass the full
invariant suite. The hard gate already has the right semantics for a mixed set: it removes an option only
when every active value rules it out, which is why a coding+regulatory query keeps its predictors. The 31
review rows are unchanged, all being single-valued.

It is one field in `factors.json`, but it changes the taxonomy that was signed off, so it needs a ruling
rather than a commit.

## 7. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Assume by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when a must-have is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. On 81 ablations it fires 16 times, all on the one factor genuinely unrecoverable from text **[Meas]** |
| Assumptions are stated, never silent | **[Judg]** | the failure this design answers is invisible omission, and a silent fix reproduces it |
| `region_focus` assumed *both* | **[Meas]** | 0.00 options lost across 22 ablations, confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it open lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| Facts stated, intent inferred | **[Meas]** + **[Judg]** | every classifier failure across the 31 rows fell on a data fact; both intent factors classified correctly. The split is the taxonomy's existing distinction **[Judg]** |
| A stated value overrides the model | **[Judg]** | a field the model can overrule is not a field |
| Untouched fields fall back to inference | **[Judg]** | the tool's premise is that a plain description is enough, so the fields must be optional or that premise is withdrawn |
| Species offered as a field as well as inferred | **[Src]** | VEP's own form asks for species in a dropdown; `InputForm.pm` gates fields on the selection. Ours still infers it when the field is left alone |
| Assembly beside the query, not in the factor scheme | **[Src]** + **[Judg]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it is a property of the input rather than of the analysis is my reading **[Judg]** |
| How often users omit things | **not established** | `fetch_real_queries.py` pulls tracker issues verbatim with a per-body SHA-256 and a `--verify` re-fetch, but only 8 of 43 are configuration questions. Biostars is Cloudflare-blocked at both the HTML and the API. Too few to carry a frequency claim |

The structure is my own reading, grounded in measurements taken on this repository and in how VEP's own
form behaves. Nothing derives from a published interface standard, because I did not find one that
applies. The measurements are reproducible (`ablate_queries.py` for the 81 ablations,
`test_user_context.py` for the field behaviour, both without a GPU), and the judgement calls are marked.

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
python vep_assistant.py "human tumour WGS, which variants are damaging?"          # assumptions, stated
python vep_assistant.py --assume "..."                                            # assumptions, silent
python vep_assistant.py --ask "..."                                               # also prompt

python work/harness/try_reprompting.py --why "human tumour WGS, ..."              # what the rule did, and why
python work/harness/try_reprompting.py --factors species=human,analysis_goal=population-frequency
python work/harness/try_reprompting.py --multi "human WGS with SNVs and CNVs"     # simulates §6
```

`--factors` needs no model. `--multi` applies the §6 proposal in memory only, so trying it cannot leave
the repository half-changed. `--ask` will show the blocker from §6 directly: it offers *small* or
*structural-CNV* and no way to say both.

## 9. What I would like you to rule on

1. **Can a variant set be both small and structural?** (§6) Blocking. It unblocks deployment and removes
   the only question the system ever asks. `region_focus` already works this way, so this is precedent
   rather than a novel request.
2. **Is "it changes something essential" the right bar for interrupting someone?** (§3) The bar is a
   clinical judgement encoded in the priority table you are reviewing, so it is really yours.
3. **Are the assumptions clinically safe, and is `analysis_goal` in the right bucket?** (§4)
   Somatic-by-default is the conservative direction, since it withholds a filter rather than applying
   one, but a germline user loses one optional pre-filter. `analysis_goal` is the one that fails our own
   test for assuming, as §4 sets out. Should it be asked instead? Related and smaller: the priority table
   cannot resolve without a goal, so if someone is asked and skips, something still fills it in, and that
   currently happens with no announcement.
4. **Assembly** (§5): a field, or assume GRCh38 and say so? A field cannot affect option *priorities*,
   only availability; a factor could. This is the one with a correctness consequence rather than a
   completeness one.
5. **Are there facts I have missed** that a user knows and we are currently guessing? `cell_type` is the
   candidate I am least sure about: it needs a value only the user has, which is part of why you asked
   for it to be optional. Aleena's note on row 13, that users often specify which populations they care
   about, is a second candidate.
