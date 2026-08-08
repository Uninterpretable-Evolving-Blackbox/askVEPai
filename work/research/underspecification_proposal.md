# Under-specified queries: what to assume, what to say, and what to ask

Status: proposal, with measurements. Nothing here changes the priority table — that is what the mentor
review is deciding, and it is untouched. This is about a different question the review was never shown:
**what should the tool do when the user's question simply doesn't say?**

## 1. The problem, measured

The recommender reads a question into five factor values, and the priority table turns those values into
options. A factor the question never mentions contributes **nothing** — so every option it would have
supplied silently disappears.

How much that costs, resolving all 31 review rows with one factor blanked (deterministic, no LLM):

| factor left unstated | mean options lost | mean gained | rows unaffected | worst row |
|---|---|---|---|---|
| `origin` | 1.0 | 0.2 | 0/31 | 1 |
| `variant_size_class` | 1.0 | 3.5 | 16/31 | 2 |
| `region_focus` | 4.4 | 0.2 | 0/31 | 9 |
| `analysis_goal` | 5.4 | 0.0 | 0/31 | 17 |

And separately, the goal is not left blank at all — `infer_factors` silently rewrites an empty
`analysis_goal` to `['basic-consequence']`, the *narrowest* possible reading:

```
mean options lost 2.4   max 14   rows affected 21/31
```

**How often this actually happens — WITHDRAWN, and replaced.** This section previously reported that
**18 of 20** real forum questions in `preliminary_examples/real_queries_biostars.json` leave a
decision-relevant factor open, with 1.50 such factors per query and a `region_focus` 16 /
`variant_size_class` 8 / `analysis_goal` 6 / `origin` 0 breakdown.

**That set is discredited and every figure from it is withdrawn.** All nine items it flagged `verbatim`
were checked against their GitHub sources: none is verbatim, similarity runs 0.03–0.98, none is even a
substring, and five had VEP command lines stripped out — up to twenty-four flags in one case. Removing a
command line that names `--overlaps`, `--numbers`, `--protein` makes a question look *more*
under-specified than the user's actual one, i.e. the edits ran in the direction that flattered the
conclusion the set was used to support. The caveat that used to sit here ("the verbatim slice is 7/9")
rested on the same false claim of verbatimness and is withdrawn with it.

Two replacements, both in §7.4:

- **Frequency in the wild is still unmeasured.** `fetch_real_queries.py` pulls issues verbatim with a
  per-body SHA-256 and a `--verify` re-fetch, from a stated sampling frame — but of 43 drawn, only **8**
  are configuration questions at all. Biostars is Cloudflare-blocked at both the HTML and the API. The
  cheapest honest route is the `real_data` Likhitha has already offered.
- **Cost and consequence are measured, on ground truth we constructed.** `ablate_queries.py` removes one
  fact from each of our own 31 queries and re-reads the result, so the counterfactual is observable in a
  way it never is in the wild. 124 attempted, **81 clean**. §7.4 reports what each gap costs.

The 31 generated rows still never show the problem directly — Stage 3 wrote those questions specifically
to express their factor tuple, so all 31 tuples are fully specified. That is why the ablations exist.

## 2. Why "just pick a default" is not enough

A default is only safe when one answer is rarely harmful. Six cases where that fails:

**(a) Guessing wrong causes harm, not omission.** `origin` carries a hard rule — *somatic ⇒ never apply
the common-variant frequency filter*, because in a tumour sample a common variant may be the finding.
Default it to germline on a tumour query and the config can switch on a filter that **discards the user's
variants**. The table above says this factor costs "1.0 options"; that number counts *how many* options
changed and is blind to the fact that one of them destroys data. **The option-count measure ranks by
quantity, not by danger, and must not be used alone to decide what is safe to assume.**

**(b) The scheme cannot express the honest answer.** `variant_size_class` is `select: single`, so there is
no "both" to default to. Review row 1 is a genuine query naming *"both coding SNVs and larger structural
variants or CNVs"* — no value is correct. This is a vocabulary limitation, not a missing-information
problem, and a default cannot repair it. (`region_focus` had the same problem and was already made
multi-select; `variant_size_class` was not.)

**(c) There is no safe middle.** `analysis_goal` decides what the user actually wants. Assume the narrow
value — as the code does today — and a clinical question loses ClinVar and every pathogenicity predictor,
up to 17 options. Assume the broad value and a quick lookup returns thirty. Every fixed choice is badly
wrong for a large fraction of users. This is the signature of a question that has to be asked.

**(d) The request is unsatisfiable, and no value helps.** *"Population frequencies for my mouse variants"*
— gnomAD, 1000 Genomes and `--frequency` are all human-only, so no configuration answers it. Today the
tool returns a config with no frequency source **and says nothing**. The right response is neither a
default nor a question but a statement: *"VEP has no non-human frequency source; here is the
alternative."* This is a third response type the tool does not currently have.
(Already raised as `DECISIONS.md` §5.)

**(e) The information was present and we lost it.** Row 1 again — the user *said* SNVs and CNVs. Nothing
was under-specified; the representation dropped half of it. A mechanism aimed at "the user didn't say" is
the wrong tool for "the user said and we couldn't hold it".

**(f) Nothing in the five factors covers it.** Nine catalogue options (`buffer_size`, `distance`,
`most_severe`, `per_gene`, `pick`, `pick_allele`, `shift_3prime`, `summary`, `transcript_version`) can
never be recommended by any combination of the five factors, because they answer operational questions no
biological factor implies. The reviewer reached this independently on row 31: *"when dealing with short
variants and structural variants, buffer size can be tricky to set, do we want to ask the user a question
here?"* — and on row 24 for `--distance`. No default can produce an option the table cannot reach.

## 3. Proposal: three response types, not two

| factor | treatment | reason |
|---|---|---|
| `species` | leave as-is | already deterministic (`infer_species`) and fail-closed |
| `region_focus` | **assume both** | "both" is expressible, and it is the honest reading of silence — and the only assumption that loses nothing: 0.00 options lost on 22 ablations (§7.4) |
| `origin` | **assume somatic** (fail-closed) | **corrected by measurement — see §7.2.** "Stay empty" was the original proposal and it is *not* safe |
| `variant_size_class` | **stay empty, and disclose** | case (b): "both" is inexpressible *today* — but see §7.3, which argues it should become expressible |
| `analysis_goal` | **stop defaulting silently; disclose** | case (c): no safe middle, and today's default is invisible |

So the tool needs three ways to respond to a gap:

1. **Assume** — where one answer is safe. Silent.
2. **Disclose** — state the assumption and how to override it, without blocking. *"Read as a quick
   consequence call; say so if you are assessing pathogenicity or need population frequencies."*
3. **Ask** — reserved for gaps where no assumption is safe AND the answer materially changes the
   configuration.

**When to ask is a deterministic decision, not a model judgement.** For a candidate factor, resolve the
configuration under every possible value and take the largest pairwise difference; below a threshold, do
not ask. This costs ~1 ms and no LLM call. It is why `origin` is never asked about: the assumption resolves it,
and where it does not, the answer usually moves nothing. The naive "ask whenever the model is unsure"
design would have asked about it constantly — 52 questions
across 20 queries, 16 of them about the factor that matters least.

## 4. Modes

Asking cannot be unconditional: the evaluation harness and the generation pipeline call the classifier
non-interactively and would hang. So the behaviour is a mode, defaulting to the honest-but-non-blocking
middle.

| mode | behaviour | for |
|---|---|---|
| `--assume` | apply safe defaults, say nothing | scripting, batch, the harness |
| *(default)* | apply safe defaults, **state what was assumed** | ordinary use |
| `--ask` | additionally re-prompt for gaps with no safe default and a material effect | interactive use |

## 5. What to measure before adopting any of it

1. **Does "region_focus = both" recover the lost options**, and what does it cost in precision? It will
   switch on missense predictors that print empty columns for purely regulatory variants — the same
   trade-off `DECISIONS.md` §2 is already asking the reviewer to rule on.
2. **Re-measure afterwards on evidence that survives checking.** How many queries still carry a gap that
   matters? That number is the honest size of the "must ask" problem and the only justification for
   building the interaction. Done in §7.4 on the 81 controlled ablations: **16 of 81**, all one factor.
3. **A danger audit the option-count sweep cannot do** (see case (a)): for each factor, which *wrong*
   guesses enable something destructive rather than merely omit something. Smaller list, and the one worth
   putting in front of the reviewer.

## 6. Relationship to the mentor review

Nothing here edits `priority_by_factor.json` or the `DRIVES` spec that generates it. `region_focus=coding`
continues to mean exactly what the review is deciding it means. What changes is only the handling of a
factor the user never supplied — a case that appears in **0 of the 31 reviewed rows** (all 31 tuples are
fully specified, verified) and, by construction, on all 81 controlled ablations (§7.4). So this cannot
alter any reviewed row, including the ten approved.

It is still a design decision that changes what a vague question returns, so it should go to the reviewer
before it ships — bundled with the tier question and the CLI-vs-web scope question rather than sent
separately. Her row 31 and row 24 comments show she is already thinking about it.

---

## 7. Results (measured 2026-08-03)

All deterministic unless noted. Under-specification is *simulated* on the 31 review rows by blanking one
factor and scoring the resulting configuration against that row's own true configuration.

### 7.1 `region_focus` — assuming "both" is right, and right on every subgroup

| policy for an unstated `region_focus` | precision | recall | F1 |
|---|---|---|---|
| today — contributes nothing | 0.98 | 0.65 | 0.78 |
| **assume both** | 0.86 | **1.00** | **0.92** |
| assume coding | 0.91 | 0.82 | 0.86 |
| assume regulatory | 0.91 | 0.80 | 0.85 |

The precision worry was real but small, and it does not create a losing subgroup — "both" beats "today" even
when the truth is purely one side (true=coding 0.88 vs 0.84; true=regulatory 0.86 vs 0.80; true=both
1.00 vs 0.72, n=9/9/13).

### 7.2 `origin` — the original proposal was wrong, and the danger audit is what caught it

§2(a) argued that leaving `origin` open is safer than guessing. **It is not.** The
`somatic ⇒ frequency not_applicable` hard rule fires only when `origin` is *explicitly* somatic, so an
unstated origin lets the common-variant pre-filter through on **6 of the 15 somatic rows** — the identical
harm to guessing germline. In the other direction, guessing somatic enables a suppressing option on
**0 of the 16 germline rows**.

So `somatic` is the fail-closed value, exactly as `infer_species` returns human only when positively
indicated. In the priority table `germline` and `somatic` differ *only* by this rule (both merely recommend
`check_existing`), so assuming somatic costs a germline user one optional pre-filter and costs a somatic
user nothing. After the change, the audit is **0/31 on every factor** (was 6/31 on `origin` alone).

**This is the finding the option-count sweep could not have produced.** That sweep ranked `origin` as the
*least* important factor at 1.0 options. It was measuring quantity; the one option in question deletes the
user's variants.

### 7.3 `variant_size_class` — the whole remaining case for asking is one factor, and it is a taxonomy bug

~~Re-running the 20 real forum queries against the new defaults: 18/20 → 13/20 needing a question, 1.50
→ 0.65 questions per query, 1.90 assumptions stated.~~ **Withdrawn — those numbers came from the
discredited set (§1).** Re-measured on the 81 clean ablations, where the removed fact is known:

| | |
|---|---|
| ablations needing ≥1 question | **16/81** |
| assumptions stated per ablation | **0.69** |
| which factor | `variant_size_class` 16, everything else **0** |

Every question is `variant_size_class` — 16 of 16. `origin` and `region_focus` are assumed and
disclosed; nothing else is ever asked. The conclusion is the one the withdrawn figures pointed at, now
resting on evidence where the counterfactual is observable.

And the resolver **already accepts a multi-valued `variant_size_class`** (verified: it resolves cleanly).
Only `factors.json` declares it `select: single`. The hard gate already has the right semantics for a mixed
set — it fires only when *every* active value marks an option `not_applicable`, which is exactly why a
coding+regulatory query keeps its predictors.

What each policy costs, on the 16 rows whose true class is `small`:

| policy | F1 (all 31) | what it does to a true-`small` row |
|---|---|---|
| today — nothing | 0.86 | — |
| assume `structural-CNV` | **0.95** | **destroys 10 pathogenicity + 10 splice + 11 protein + 4 frequency options** |
| assume both | 0.90 | **loses nothing**; adds 2 |

**F1 picks the wrong policy here.** It ranks `structural-CNV` highest because it counts a removed predictor
and an added gene-constraint column as the same size of error. They are not, and the direction matters: the
mentor review asks for *more* predictors on rows 12, 14, 18, 20, 26 and 28. Assuming "both" makes only
additive errors; assuming `structural-CNV` makes subtractive ones.

This is the third time in this work that a symmetric count chose the wrong answer — after the option-count
sweep in §7.2 and strict set-equality in Exp 15. **Symmetric metrics are the wrong instrument for a
recommender whose errors are asymmetric in cost.**

### 7.4 What each gap costs, against constructed ground truth (measured 2026-08-07)

The controlled ablation is the only fixture in this line of work where the right answer is known. Each
of the 31 review queries states all five factors, so exactly one can be removed and everything else held
fixed. A model rewrites the question so it reads naturally with the fact simply absent; every rewrite is
re-read and kept only if the target fact really went **and** no other factor moved. 124 attempted, **81
clean** (22 redundant — words gone, fact still inferable; 15 entangled; 6 rewrite failed).

Resolving each clean ablation and comparing to the configuration the true tuple produces:

| fact removed | n | mean options **lost** | mean added | exactly right | rows losing something |
|---|---|---|---|---|---|
| `region_focus` — assumed *both* | 22 | **0.00** | 1.64 | 11/22 | **0/22** |
| `origin` — assumed *somatic* | 19 | 0.32 | 0.58 | 14/19 | 5/19 |
| `analysis_goal` — assumed *basic-consequence* | 11 | 1.09 | 0.00 | 6/11 | 5/11 |
| `variant_size_class` — left open | 29 | 1.03 | 4.21 | 14/29 | **15/29** |

**Lost and added are not the same error, and the table is only readable if they are kept apart.** An
extra annotation column is noise the user can ignore; a missing predictor is a finding they never see.
This is the same asymmetry §7.3 found F1 blind to. Read that way:

- **`region_focus = both` is the strongest assumption in the design** — zero loss on all 22 rows. This
  is a second, independent confirmation of §7.1, on ablated prose rather than a blanked tuple.
- **`analysis_goal` is the weakest** — it is the only assumption whose errors are *subtractive*, because
  reading a question as a plain consequence call drops ClinVar and the predictors. There is no safe
  middle (§2c), so it is disclosed loudly rather than defended.
- **`variant_size_class`, the one factor left open, is the worst outcome of the four** — it both loses
  and adds, and half the rows lose something.

And what the proposed taxonomy change does to that last row, on the same 29 ablations:

| policy for `variant_size_class` | mean lost | mean added | rows losing something |
|---|---|---|---|
| today — single-select, left open | 1.03 | 4.21 | 15/29 |
| **multi-select, assumed *both* when unstated** | **0.00** | 4.28 | **0/29** |

The error becomes purely additive — the same shape `region_focus` already has — at no measurable cost in
added options. Questions needed across all 81 ablations go from 16 to **zero**.

**One finding about recoverability that no policy can change.** `variant_size_class` came out cleanly
**29 of 31** times and was still inferable from context only twice. The fact is simply not in the
surrounding prose, so no better prompt and no larger model recovers it. By contrast `analysis_goal` was
redundant or entangled **17 of 31**, so it is rarely genuinely missing. That asymmetry is the argument
for treating the two factors differently.

### 7.5 What to put to the reviewer

Not "should the tool ask questions?" — the measurement makes that nearly moot. The question is narrower and
has a precedent she can reason about:

> `region_focus` was made multi-select because a variant set can be coding **and** regulatory.
> `variant_size_class` has the identical problem — review row 1 is a real query naming *"both coding SNVs
> and larger structural variants or CNVs"*, and it is the single reason any question is ever asked — 16 of
> 16, across 81 controlled ablations. The resolver already supports it. Should `variant_size_class` become multi-select too?

If yes, the asking mechanism may not be needed at all, and row 1's `factor_unrecoverable` flag — which she
queried directly — resolves as a modelling fix rather than a bad row.

## 8. Literature grounding

**[Lit ✓ partial] Gervits, Briggs, Roque, Kadomatsu, Thurston, Scheutz & Marge (2021), "Decision-Theoretic
Question Generation for Situated Reference Resolution: An Empirical Study and Computational Model",
ICMI '21, arXiv:2110.06288, doi:10.1145/3462244.3479925.** Read pages 1–5 of 9 (abstract, background,
empirical study, §4 model specification). **§5 (evaluation) and §6 (discussion) NOT read**, so no claim is
made here about how their model performed.

What the paper actually does: it models which clarification question to ask as a **decision network** — a
Bayesian graphical model with chance, decision and utility nodes — and selects the single question with
**maximum expected utility**, `MEU(e) = argmax_a Σ_s P(s|e)U(a,s)` (their Equation 1). Utilities are set by
an entropy-driven method over object properties, derived from question-type frequencies in their corpus,
and — the detail that matters for us — **"the known properties are set to 0"**: a question about something
the agent already knows carries no utility and is therefore never selected.

**Where our design agrees.** Our relevance gate is the same principle in deterministic form: a factor whose
answer cannot change the resolved configuration scores zero and is never asked. Their justification for
zeroing known properties is our justification for suppressing all 16 `origin` questions.

**Where it differs, stated as a difference and not as a borrowing.** Theirs is probabilistic and requires
priors, a corpus to derive utilities from, and a model of the interlocutor. Ours resolves the configuration
under each candidate value and measures the actual symmetric difference — no priors, no training data, and
auditable per query, which suits a tool whose whole architecture is "the LLM proposes, deterministic Python
disposes". The cost of our simpler form is that it cannot trade the *cost of asking* against the benefit;
it applies a fixed threshold where theirs computes an expectation. If we ever need that trade-off, their
formulation is the thing to adopt.

**One calibration datum, used as context and not as a target.** In their study (22 participants: 10
commander-initiative, 12 robot-initiative; 11 female; mean age 37 ± 7; all native English speakers), the
mean number of questions people asked to resolve a single referential ambiguity was **1.72 ± 0.40**. Our
design caps at 1, so it is stricter than what humans did in their task. This does **not** transfer as a
benchmark — their task is situated human-robot reference resolution, ours is configuration recommendation,
and the quantities are not the same thing. It is offered only as evidence that a ~1-question budget is not
implausibly stingy.

**[Lit ✗] Asymmetric error cost — no anchor found, and none is claimed.** A search for work on symmetric
metrics (F1) misleading evaluation under asymmetric error costs returned mostly secondary material (blog
posts, tutorial pages) and papers on cost-sensitive *regression*, which is not our setting. **Nothing was
read in full, so nothing is cited.** The §7.3 finding — that F1 selects `structural-CNV` while the errors
it makes are subtractive (10 predictors, 10 splice, 11 protein annotations removed) where "both" makes only
additive ones — rests entirely on our own measurements and is presented as our own reasoning, not as a
literature-supported principle. If this becomes load-bearing in the write-up, it needs a proper
cost-sensitive-learning citation read from full text, and that has not been done.
