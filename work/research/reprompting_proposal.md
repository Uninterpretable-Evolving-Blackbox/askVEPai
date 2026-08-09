# Re-prompting: what the assistant assumes, what it states, and what it asks

Status: proposal, with measurements. The third design decision the project had to invent rather than
inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). It changes the interface contract, so I would like sign-off before
it is final. `underspecification_proposal.md` holds the raw measurements.

---

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes nothing, so every option it would have supplied silently disappears. The user gets a shorter
configuration with no indication that anything is missing.

## 2. The design: four responses to a gap

A recommender that interrogates its users has
moved the work back onto them, which is the opposite of what the tool is for.

| | when | friction |
|---|---|---|
| **take it from the text** | the question settles it, so nothing is chosen | none |
| **assume, and say which** | the question does not settle it, but one answer is clearly safer. *The normal case.* | none |
| **let user state factor value optionally?** | they set one of optional fields | it is optional |
| **ask** | no safe assumption **and** a must-have is at stake | real |

The first two rows are easy to confuse, so: 
**species** is read out of the question by a keyword rule that returns `human` only when the text positively says so. No option was preferred over another, so there is nothing to disclose. 

**`origin`** is different — the question does not settle it, we pick somatic, and a different pick would give a different configuration. That is why it is announced and species is not. The test is not how confident we are; it is whether a choice was made at all.

**Whether to assume or ask when answer is not fully certain**:
How much the options lost or added after assumption
For `origin` there is: guessing somatic withholds a filter, guessing germline applies one that discards
tumour variants, so the two directions fail very differently and we take the cheap one. For `variant_size_class` there is no such direction, which is why it is the only thing ever asked about.

A question that leaves something open returns a working configuration plus a line naming each assumption
and how to override it. Nobody is blocked; every line can be ignored. no invisible choices is ever made in those cases.

**The optional fields, which you have not seen.** Row three refers to something built but never put in
front of you: an *About your data* panel beside the query box, with four dropdowns — species,
germline/somatic, small/structural, and assembly. Every one defaults to *from my description*, so a user
who types a sentence and presses go gets exactly what they got before. If someone does set one, it wins
outright over whatever the model read. The reasoning is §5; I am flagging it here because the table
refers to it as though it were established, and it is not.

Asking is opt-in, because the evaluation harness and the generation pipeline call the same code
non-interactively and would otherwise hang.

## 3. When it asks

For each still-open factor, resolve the configuration under every candidate answer and compare. If no
must-have option differs, the question cannot change what the user gets and is never asked.

No model decides this. It is arithmetic over the priority table, costs about 1 ms against a ~1000 ms
classifier call, and is auditable per query.

It is judged per query, not per factor. `origin` changes nothing on a purely clinical question and
decides the common-variant filter on a frequency one, so no fixed per-factor rule is right for both.

**A limitation of this rule, which `origin` exposes.** 
We tested asking about origin. Even with nothing suppressing the question, the rule never asks, because answering it wouldn't add anything essential. Its real risk is a filter being switched on, which the somatic default already prevents.

## 4. What it assumes, and what each assumption costs

Measured on 81 controlled ablations: one fact removed from each of our own 31 queries, everything else
held fixed, so the right answer is known. Each is resolved and compared to the true configuration.

Each ablated query goes through the normal path: classifier, then assumptions, no asking — and the resulting configuration is compared to the one the true factor values produce. So this measures what silence plus a default costs, not what a question would buy.

Reading the columns: **lost** is options the true configuration has that ours does not, averaged per
query — annotations the user should have got and did not. **Added** is the reverse, options we switch on
that the true configuration does not have. **Exactly right** is queries where the two sets match
completely, and **losing something** is queries missing at least one option, however many.

| fact removed | n | mean options **lost** | mean options added | exactly right | queries losing something |
|---|---|---|---|---|---|
| `region_focus` — assume *both* | 22 | **0.00** | 1.64 | 11/22 | **0/22** |
| `origin` — assume *somatic* | 19 | 0.32 | 0.58 | 14/19 | 5/19 |
| `analysis_goal` — assume *basic-consequence* | 11 | 1.09 | 0.00 | 6/11 | 5/11 |
| `variant_size_class` — left open | 29 | 1.03 | 4.21 | 14/29 | **15/29** |

**Lost and added are not the same error.** An extra annotation column is noise the user can ignore; a
missing predictor is a finding they never see. Read that way:

- **`region_focus = both` is the strongest assumption in the design.** Zero loss on all 22 queries.
- **`origin = somatic` is fail-closed.** The *somatic ⇒ no common-variant filter* rule fires only on an
  explicit somatic, so leaving it open lets that filter through on 6 of the 15 somatic review rows, the
  identical harm to guessing germline. Guessing somatic harms 0 of 16 germline rows.
- **`analysis_goal` is the weakest**, and the only assumption whose errors are subtractive: reading a
  question as a plain consequence call drops ClinVar and the predictors. There is no safe middle, so it
  is disclosed loudly rather than defended.
- **`variant_size_class`, the one factor left open, is the worst of the four.** See §6.

## 5. What the user can state outright (questionable, not too sure)
Three of the five factors are **facts about the sample** — species, germline/somatic, small/structural —
and the person asking knows all three without thinking. They are optional fields, in the web form and as
flags, and whatever is set overrides whatever the model read.

This is not a retreat from the natural-language interface. The value of the tool was never that it
guesses what species you have; it is that it knows which of sixty-five options that implies. The scenario
text keeps carrying the part a form cannot hold: what you are trying to find out.

Precedent: VEP's own web form asks for species in a dropdown rather than inferring it.

Verified not to change anything for a user who ignores the fields: with none set, the resolved
configuration, the priority labels, the checker's changes and the classifier's output are identical
(`test_user_context.py`, 15 checks, deterministic, no GPU).

**Assembly is here despite not being a factor**, and its absence is a correctness bug rather than a gap.
MANE Select transcripts exist only for GRCh38, and `InputForm.pm:694-702` gates the MANE checkbox on
species alone, so VEP's own form offers it to a GRCh37 user with no data behind it. Our checker can
enforce the restriction, but only when it knows the build, and a description that never names an
assembly contains no assembly to infer. Either a field or a stated GRCh38 default fixes it; §8.5 asks
which. Whichever it is, assembly is a property of the input data, like the file format, not a
description of the analysis, so it does not belong in the factor scheme.
(Open as `../generation/candidates/review/DECISIONS.md` §8.)

## 6. The blocker: the tool asks a question it cannot accept the honest answer to

It asks whether the variants are small or structural, and `variant_size_class` is `select: single`.
**A user answering *both* has half their answer silently discarded.**

To be clear about what "both" means, because the factor name invites the wrong reading: a single variant
is of course one or the other. The factor describes the **variant set** — the whole callset handed to
VEP — and a WGS callset routinely contains both classes. So both is not an edge case, it is the normal
answer for whole-genome work. Review row 1 is such a question, and it is the row carrying the
`factor_unrecoverable` flag you queried.

The values `small` and `structural-CNV` are not the problem. Declaring the factor single-select is: it
forces one answer per dataset, where the honest unit is a set that can hold both.

Interrupting someone, receiving the truthful answer and throwing half of it away is worse than not
asking. **The asking behaviour does not ship until this is resolved.**

The fix is to allow both values, as `region_focus` already does. On the same 29 ablations:

| policy for `variant_size_class` | mean lost | mean added | rows losing something |
|---|---|---|---|
| today — single-select, left open | 1.03 | 4.21 | 15/29 |
| **multi-select, assumed *both* when unstated** | **0.00** | 4.28 | **0/29** |

The error becomes purely additive at no measurable cost in added options, and the questions the tool
needs across all 81 ablations go from **16 to zero**. Every one of those 16 was this factor; nothing else
is ever asked.

There is a second reason this factor is the one that breaks. When it was removed, the fact was still
recoverable from surrounding context only **2 times in 31** — it is not in the prose, so no better prompt
and no larger model recovers it. `analysis_goal` was recoverable 17 of 31, so it is rarely genuinely
missing.

The plumbing is done: `MULTI_FACTORS` and the classifier's prompt schema both derive from `factors.json`,
and the sampler, dedup key and tuple slug are cardinality-agnostic. Both configurations pass the full
invariant suite. The hard gate already has the right semantics for a mixed set, removing an option only
when *every* active value rules it out, which is why a coding+regulatory query keeps its predictors. The
31 review rows are unchanged, all being single-valued.

**It is one field in `factors.json`, but it changes the taxonomy that was signed off, so it needs a
ruling rather than a commit.**

## 7. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Assume by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when a must-have is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. On 81 ablations it fires 16 times, all on the one factor genuinely unrecoverable from text **[Meas]** |
| Assumptions are stated, never silent | **[Judg]** | the failure this design answers is invisible omission; a silent fix reproduces it |
| `region_focus` assumed *both* | **[Meas]** | 0.00 options lost across 22 ablations, confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it open lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| Facts stated, intent inferred | **[Meas]** + **[Judg]** | every classifier failure across the 31 rows fell on a data fact; both intent factors classified correctly. The split is the taxonomy's existing distinction **[Judg]** |
| A stated value overrides the model | **[Judg]** | a field the model can overrule is not a field |
| Untouched fields fall back to inference | **[Judg]** | the tool's premise is that a plain description is enough; the fields must be optional or that premise is withdrawn |
| Species asked rather than inferred | **[Src]** | VEP's own form asks for species in a dropdown; `InputForm.pm` gates fields on the selection |
| Assembly beside the query, not in the factor scheme | **[Src]** + **[Judg]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it is a property of the input rather than of the analysis is my reading **[Judg]** |
| How often users omit things | **not established** | `fetch_real_queries.py` pulls tracker issues verbatim with a per-body SHA-256 and a `--verify` re-fetch, but only **8 of 43** are configuration questions. Biostars is Cloudflare-blocked at both the HTML and the API. Too few to carry a frequency claim |

**Honest summary:** the structure is my own reading, grounded in measurements taken on this repository
and in how VEP's own form behaves. Nothing derives from a published interface standard, because I did
not find one that applies. The measurements are reproducible (`ablate_queries.py` for the 81 ablations,
`test_user_context.py` for the field behaviour, both without a GPU); the judgement calls are marked.

**What is and is not measured.** Cost and consequence are: the tables above say what each gap does to the
configuration. **Frequency is not** — how often real users leave a fact out. Frequency decides how
aggressive to be, and the cheapest route to it is the `real_data` Likhitha has offered.

**Nearest literature.** Gervits et al., ICMI '21 (arXiv:2110.06288) select clarification questions by
maximum expected utility over a decision network, setting the utility of asking about an already-known
property to zero. Our relevance gate is the same principle in deterministic form. Theirs needs priors, a
corpus and a model of the interlocutor; ours needs none and is auditable per query, at the cost of not
being able to trade the cost of asking against its benefit. **Read pp. 1–5 of 9; §5–6 not read**, so no
claim is made about how their model performed.

## 8. What I would like you to rule on

1. **Can a variant set be both small and structural?** (§6) Blocking. It unblocks deployment and removes
   the only question the system ever asks. `region_focus` already works this way, so this is precedent
   rather than a novel request.
2. **Is "it changes something essential" the right bar for interrupting someone?** (§3) The bar is a
   clinical judgement encoded in the priority table you are reviewing, so it is really yours. Note what
   it cannot catch: a factor whose wrong answer switches a *harmful* option on rather than leaving a
   must-have off is invisible to it, and `origin` is exactly that case. Should the bar also cover
   options that are dangerous to include, and if so, which ones are they?
3. **Are the three assumptions clinically safe?** (§4) Especially somatic-by-default: conservative, but a
   germline user loses one optional pre-filter. And `analysis_goal`, the one assumption that loses rather
   than adds.
4. **Assembly** (§5): a field, or assume GRCh38 and say so? A field cannot affect option *priorities*,
   only availability; a factor could. This is the one with a correctness consequence rather than a
   completeness one.
5. **Are there facts I have missed** that a user knows and we are currently guessing? `cell_type` is the
   candidate I am least sure about: it needs a value only the user has, which is part of why you asked
   for it to be optional.
