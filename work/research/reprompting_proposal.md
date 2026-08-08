# Re-prompting: what the assistant assumes, what it states, and what it asks

Status: proposal, with measurements. This is the third design decision the project had to invent rather
than inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). It changes the interface contract, so I would like sign-off before
it is final.

`underspecification_proposal.md` is the companion: it states the problem and holds the raw measurements.
This document is the design that answers it.

**Renamed from `input_design_proposal.md` (2026-08-07), and the emphasis corrected with it.** The earlier
version led with the input fields and read as "make the user fill in blanks", which is not the design and
is not what the measurements support. The fields are one of four responses to a gap, and the least used.

---

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes **nothing**, so every option it would have supplied silently disappears. The user gets a
shorter configuration with no indication that anything is missing.

*"I have human tumour WGS and want to know which variants are damaging"* never says whether the interest
is coding or regulatory. That costs about 4.5 options, and nothing on screen says so.

**How often real users do this is still unmeasured, and I am not going to pretend otherwise.** An earlier
version of this document reported "18 of 20 real VEP questions leave a decision-relevant factor open",
with nine of the twenty described as verbatim from Ensembl's issue trackers. Checking all nine against
their sources found **none was verbatim**: similarity ran 0.03–0.98, none was even a substring, and five
had VEP command lines stripped out, up to twenty-four flags in one case. Removing a command line that
names `--overlaps`, `--numbers`, `--protein` makes a question look *more* under-specified than the user's
real one, so the edits ran in the direction that flattered the conclusion. **That set and every figure
from it are withdrawn**, including the "7 of 9 on the verbatim slice" reassurance, which rested on the
same false claim.

What replaced it:

- `fetch_real_queries.py` pulls issues verbatim, with a per-body SHA-256 and a `--verify` re-fetch, from
  a stated sampling frame. Of 43 drawn, only **8** are configuration questions at all. Biostars is
  Cloudflare-blocked at both the HTML and the API.
- `ablate_queries.py` removes one fact from each of our own 31 queries and re-reads the result, so the
  counterfactual is observable in a way it never is in the wild. 124 attempted, **81 clean**. Everything
  quantitative below comes from these.

So: **cost and consequence are measured; frequency is not.** Frequency is what decides how aggressive to
be, and the cheapest route to it is the `real_data` Likhitha has already offered.

## 2. The five factors do not fail equally

Splitting them by the taxonomy's own **data fact / intent** distinction sorts every observed failure onto
one side:

| factor | kind | how it behaved |
|---|---|---|
| `species` | data fact | resolved deterministically from keywords, not by the model |
| `variant_size_class` | data fact | the only genuine classifier error across all 31 review rows |
| `origin` | data fact | the two rows the classifier could not answer: the questions genuinely never said |
| `region_focus` | intent | classified correctly on 31 of 31 |
| `analysis_goal` | intent | correct once scored the way the pipeline itself scores it |

What you *want* from the annotation, the model reads well. What your variant set *is*, it cannot read
when the text does not say, and that is where every failure lives.

The ablations sharpen this. When `variant_size_class` was deliberately removed, the fact was still
recoverable from surrounding context only **2 times in 31**: it is simply not in the prose, so no better
prompt and no larger model recovers it. `analysis_goal` was still recoverable **17 of 31**, so it is
rarely genuinely missing.

It is also the data-fact half that carries the only *dangerous* failure. Guessing `germline` for a tumour
sample lets the common-variant frequency filter through, which discards exactly the variants a somatic
analysis exists to find. An error on the intent side costs an annotation column; an error here costs the
user their findings.

## 3. The design: four responses to a gap, and asking is the rarest

**Assumptions are the mechanism. Asking is the exception.** A recommender that interrogates its users has
moved the work back onto them, which is the opposite of what the tool is for.

| | when | friction |
|---|---|---|
| **assume, silently** | the answer is already determined | none |
| **assume and say so** | one answer is safe. *The normal case.* | none |
| **read what the user stated** | they filled in a field | none, and it is optional |
| **ask** | no safe assumption **and** a must-have is at stake | real |

A vague question returns a working configuration plus lines like:

```
  Assumed origin = somatic — you didn't say germline or somatic, so the safer reading is taken:
    it keeps the common-variant filter off, which would otherwise discard real tumour variants.
    Say 'germline' if these are inherited variants.
  Assumed region_focus = coding, regulatory-noncoding — you didn't say which regions matter,
    so both are covered.
```

Nobody is blocked. Every line can be ignored. **The change that matters is that the tool stopped making
invisible choices**, not that it gained the ability to ask.

Asking is opt-in (`--ask`) because the evaluation harness and the generation pipeline call the same code
non-interactively and would otherwise hang.

## 4. When it asks: a deterministic rule, not the model's judgement

For each still-open factor, resolve the configuration under **every** candidate answer and compare. If no
must-have option differs, the question cannot change what the user gets and is never asked.

No model decides this. It is arithmetic over the priority table, costs about 1 ms against a ~1000 ms
classifier call, and is auditable per query.

It is judged **per query, not per factor**, and that matters: `origin` changes nothing on a purely
clinical question and decides the common-variant filter on a frequency one. Any fixed per-factor rule is
wrong for one of them.

The rule replaced a "three or more options differ" threshold. Three was fitted to our own 31 rows rather
than derived from anything, and it could interrupt someone over three interchangeable add-ons while
staying silent when one essential option flipped. The must-have rule needs no constant, and it lets the
question name what is at stake.

## 5. What it assumes, and what each assumption costs

Resolving each of the 81 clean ablations and comparing to the configuration the true tuple produces:

| fact removed | n | mean options **lost** | mean added | exactly right | rows losing something |
|---|---|---|---|---|---|
| `region_focus` — assume *both* | 22 | **0.00** | 1.64 | 11/22 | **0/22** |
| `origin` — assume *somatic* | 19 | 0.32 | 0.58 | 14/19 | 5/19 |
| `analysis_goal` — assume *basic-consequence* | 11 | 1.09 | 0.00 | 6/11 | 5/11 |
| `variant_size_class` — left open | 29 | 1.03 | 4.21 | 14/29 | **15/29** |

**Lost and added are not the same error.** An extra annotation column is noise the user can ignore; a
missing predictor is a finding they never see. Read that way:

- **`region_focus = both` is the strongest assumption in the design.** Zero loss on all 22 rows.
- **`origin = somatic` is fail-closed, and it corrects my own first proposal.** I had argued that leaving
  it open was safer than guessing. It is not: the *somatic ⇒ no common-variant filter* rule fires only on
  an explicit somatic, so silence let that filter through on **6 of the 15 somatic review rows**, the
  identical harm to guessing germline. Guessing somatic harms **0 of 16** germline rows.
- **`analysis_goal` is the weakest**, and the only assumption whose errors are subtractive: reading a
  question as a plain consequence call drops ClinVar and the predictors. There is no safe middle, so it
  is disclosed loudly rather than defended.
- **`variant_size_class`, the one factor left open, is the worst of the four.** See §7.

## 6. What the user can state outright, and the one field that is not a factor

Three of the five factors are **facts about the sample** — species, germline/somatic, small/structural —
and the person asking knows all three without thinking. So they are optional fields, in the web form and
as flags, and whatever is set is authoritative over whatever the model read.

This is not a retreat from the natural-language interface. The value of the tool was never that it
guesses what species you have; it is that it knows which of sixty-five options that implies. The scenario
text keeps carrying the part a form cannot hold: what you are trying to find out.

**Precedent:** VEP's own web form asks for species in a dropdown rather than inferring it.

**Verified not to change anything for a user who ignores the fields:** with no field set, the resolved
configuration, the priority labels, the checker's changes and the classifier's own output are identical
to before (`test_user_context.py`, 15 checks, deterministic, no GPU).

**Assembly (GRCh37 / GRCh38) is here despite not being a factor**, and its absence is a correctness bug
rather than a gap. MANE Select transcripts exist only for GRCh38, and `InputForm.pm:694-702` gates the
MANE checkbox on **species alone**, so VEP's own form offers it to a GRCh37 user with no data behind it.
Our checker can enforce the restriction, but only when it knows the build, and a description that never
mentions an assembly contains no assembly to infer.

*(Correcting the earlier version: it claimed a field was the **only** fix. It is not. Assuming GRCh38 and
disclosing it is a legitimate alternative, and it is the same shape as every other assumption here.
Which of the two is right is §9.5.)*

This was raised as an open decision in `../generation/candidates/review/DECISIONS.md` §8. Whichever way
it goes, assembly is a property of the **input data**, like the file format, not a description of the
analysis, so it does not belong in the factor scheme.

## 7. The blocker: the tool asks a question it cannot accept the honest answer to

It asks *"small variants (SNVs/indels), or structural (SVs/CNVs)?"* and `variant_size_class` is
`select: single`. **A user answering *both* has half their answer silently discarded.**

Both is the common case. Any WGS study has SNVs and CNVs. Review row 1 is exactly that — *"both coding
SNVs and larger structural variants or CNVs"* — and it is the row carrying the `factor_unrecoverable`
flag the reviewer queried directly.

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

The plumbing is done: `MULTI_FACTORS` and the classifier's prompt schema both derive from `factors.json`,
and the sampler, dedup key and tuple slug are cardinality-agnostic. Both configurations pass the full
invariant suite. The hard gate already has the right semantics for a mixed set: it removes an option only
when *every* active value rules it out, which is exactly why a coding+regulatory query keeps its
predictors. The 31 review rows are unchanged, all being single-valued.

**It is one field in `factors.json`, but it is a change to the taxonomy that was signed off, so it needs
a ruling rather than a commit.**

## 8. Design-choice provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Assume by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without the frequency data we lack |
| Ask only when a must-have is at stake | **[Judg]** + **[Meas]** | the alternative was a fitted "≥3 options differ" threshold **[Judg]**. On 81 ablations the rule fires 16 times, all on the one factor genuinely unrecoverable from text **[Meas]** |
| Assumptions are stated, never silent | **[Judg]** | the failure this whole design answers is invisible omission; a silent fix reproduces it |
| `region_focus` assumed *both* | **[Meas]** | 0.00 options lost across 22 ablations, and confirmed independently by a deterministic sweep (4.4 vs 4.6 options recovered by two different methods) |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it open lets the frequency filter through on 6/15 somatic rows, identical harm to guessing germline; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]** |
| Facts stated, intent inferred | **[Meas]** + **[Judg]** | every classifier failure across 31 rows fell on a data fact; both intent factors classified correctly. The split itself is the taxonomy's existing distinction **[Judg]** |
| A stated value overrides the model | **[Judg]** | a field the model can overrule is not a field. The alternative (merge, model wins ties) was tested and rejected: it silently discards what the user said |
| Untouched fields fall back to inference | **[Judg]** | the tool's premise is that a plain description is enough; the fields must be optional or that premise is withdrawn |
| Species asked rather than inferred | **[Src]** | VEP's own form asks for species in a dropdown; `InputForm.pm` gates fields on the selection |
| Assembly beside the query, not in the factor scheme | **[Src]** + **[Judg]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it is a property of the input rather than of the analysis is my reading **[Judg]** |
| How often users omit things | **not established** | the twenty-question set is withdrawn (§1). 8 usable configuration questions from 43 verbatim issues is too few to carry a frequency claim |

**Honest summary:** the *structure* is my own reading, grounded in measurements taken on this repository
and in how VEP's own form behaves. Nothing in it derives from a published interface standard, because I
did not find one that applies. The measurements are reproducible (`work/harness/test_user_context.py`,
15 checks, no GPU; `ablate_queries.py` for the 81 ablations); the judgement calls are marked as such.

**Nearest literature, and what it does and does not license.** Gervits et al., ICMI '21
(arXiv:2110.06288) select clarification questions by maximum expected utility over a decision network and
set the utility of asking about an already-known property to **zero**. Our relevance gate is the same
principle in deterministic form: a factor whose answer cannot change the configuration scores nothing and
is never asked. Theirs is probabilistic and needs priors, a corpus and a model of the interlocutor; ours
needs none of those and is auditable per query, at the cost of not being able to trade the cost of asking
against its benefit. **Read pp. 1–5 of 9; §5–6 not read**, so no claim is made about how their model
performed.

## 9. What I would like you to rule on

1. **Can a variant set be both small and structural?** (§7) Blocking. It unblocks deployment and removes
   the only question the system ever asks. `region_focus` already works this way, so this is precedent
   rather than a novel request.
2. **Is "it changes something essential" the right bar for interrupting someone?** (§4) The bar is a
   clinical judgement encoded in the priority table you are reviewing, so it is really yours.
3. **Are the three assumptions clinically safe?** (§5) Especially somatic-by-default: conservative, but a
   germline user loses one optional pre-filter. And `analysis_goal`, which is the one assumption that
   loses rather than adds.
4. **Should a hosted Ensembl tool ask follow-up questions at all?** VEP's own form never does. If the
   answer to 1 is yes this is nearly moot, but it decides whether we keep the capability for future
   factors or remove it.
5. **Assembly** (§6): assume GRCh38 and disclose, ask, or a field? A field cannot affect option
   *priorities*, only availability; a factor could. This is the one with a correctness consequence rather
   than a completeness one.
6. **Are there facts I have missed** that a user knows and we are currently guessing? `cell_type` is the
   candidate I am least sure about: it needs a value only the user has, which is part of why you asked
   for it to be optional.
