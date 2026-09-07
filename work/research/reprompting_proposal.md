EDITING!

# Re-prompting: what the assistant assumes, what it states, and what it asks

## 1. The problem

The tool reads five factor values out of a free-text scenario. A factor the question never mentions
contributes nothing, so every option it would have supplied disappears. The user gets a shorter
configuration with no sign that anything is missing.

Re-prompting can close that gap, but it moves the work back onto the user. So the design keeps the
interaction as prompt-free as it can: guess where a safe value exists, tell the user which value was
guessed, and only ask when neither route works.

## 2. The policy

For every factor the classifier failed to fill, one of three things happens:

| | when | friction |
|---|---|---|
| **take it from the text** | the question settles it | none |
| **guess and say explicitly** | one answer is clearly safer than the others. *The normal case.* | none |
| **ask** | no safe guess, and changes RECOMMENDED options outputted | real |

Every guess is stated. A vague question comes back with a working configuration plus one line per
guess, naming what was assumed and how to override it: *"Assumed origin = somatic; say germline if
these are inherited."* Nothing is blocked, and the lines can be ignored.

Four of the five factors have a safe guess: `region_focus`, `variant_size_class`, `origin` and
`species`, argued factor-by-factor in §3. One does not: `analysis_goal` is asked. Assembly, which is not a factor at all, is also
asked when the text does not name it — §5.

**PENDING, should we just default to Ghr38 like thw web?**

Species does the same take from text, guess, or ask, but because it is a hard gate rather than a soft priority factor, its disclosure lives in the constraint checker's removal report rather than in the upfront ask-lines. Same policy, different disclosure surface.

## 3. What we guess, and why each

Four different methods chose the four guessed values. None of them was the ablation table in §4; that
table prices these choices rather than making them. `defaults_evidence.py` re-derives every argument
below and fails if one no longer holds.

### `region_focus` = *both* — deterministic sweep

Resolve every one of the 31 rows under each candidate `region_focus` value and score enable-F1
against the truth. *Both* wins, ahead of leaving it blank by a wide margin:

| value | mean F1 |
|---|---|
| **both** | **0.91** |
| coding | 0.88 |
| regulatory-noncoding | 0.79 |
| (left blank) | 0.79 |

The factor is `select: multi` in `factors.json`, so *both* is expressible; the resolver's hard gate
removes an option only when every active value rules it out, which is why a coding+regulatory query
keeps its predictors.

### `variant_size_class` = *both* — the only expressible safe value

This factor describes the **variant set**, not one variant. A single variant is one or the other, but
a WGS callset routinely contains both classes, so both is the normal answer for whole-genome work.
Review row 1 is such a question. The values `small` and `structural-CNV` gate away opposite halves of
the catalogue, so neither single value is safe:

| policy for `variant_size_class` | mean lost | mean added | queries losing something |
|---|---|---|---|
| single-select, no safe value, asked | 1.13 | 4.13 | 13/23 |
| **multi-select, guessed *both*** | **0.00** | 4.22 | **0/23** |

Multi-select makes *both* available and the error becomes purely additive at no measurable cost in
added options. `variant_size_class` is `select: multi` in `factors.json` and
`UNDERSPECIFIED_POLICY["variant_size_class"].assume` is `["small", "structural-CNV"]`. This amends
the taxonomy signed off in `taxonomy_proposal.md` §3, so the argument is spelled out in full; one
field plus one line of policy overturns it. [unverified — the single-select row predates the tier
split and needs regenerating once `score_ablations.py` carries the arm.]

Offering "both" as a third choice in the question would not fix this. The classifier's schema is
generated from the same `select` field, so it can only ever return one value under single-select, and
review row 1 *states* both in its text rather than leaving it out. Under a prompt-only fix, someone
who writes "SNVs and CNVs" still has half of it discarded and is never asked, because the factor
looks answered. Only someone who says nothing gets the right answer.

**On the output side, one configuration per size.** The web form cannot cover both sizes in one
configuration: CADD's control is a drop-down over four annotation files (SNVs and InDels / SNVs /
InDels / CADD-SV) and the files are mutually exclusive. So a both-size scenario emits **one
configuration per size, two VEP runs**, instead of one union nobody can enter on the form. CADD-SV
is GRCh38-only, so a stated GRCh37 drops CADD from the structural pass with a reason rather than
leaving it on with no data behind it. Across all 36 both-size factor tuples, the two passes together
enable exactly what the single configuration did (`verify_pipeline.py` §8b).

**Consequence.** Guessing *both* switches gnomAD-SV on for almost every query. That is the "added
options" cost the table already prices, and it is harmless as a column, but gnomAD-SV is GRCh38-only,
so it also drags the assembly question of §5 into scope on queries that never mentioned structural
variants. The assembly rule is scored on what the user stated for exactly this reason.

### `origin` = *somatic* — danger audit

Not because somatic is more likely. Because the two directions fail very differently.

- Across the review rows, guessing somatic harms **0 of 16** germline rows.
- Leaving `origin` empty lets the common-variant filter through on **6 of 15** somatic rows, which is
  the identical harm to guessing germline outright.

Leaving it empty carries germline's risk on `frequency` without germline's benefit, so something has
to be guessed at all. Only the second half of the decision is that the something is somatic.

**This is the one guess that is not loss-free, and the cost is not an add-on.** Guessing somatic
costs `frequency` on **7 of 31** rows, and `frequency` resolves at `recommended`, which puts it in
the RECOMMENDED bucket the user sees switched on. So a germline user on a frequency question loses
something that would have been on for them. That is the price of the fail-closed direction, paid
deliberately.

Being wrong is cheap for the *other* direction, though — guessing somatic and being wrong costs a
line the user can correct in a sentence, which is why the factor is not asked. §4 gives the ablation
side of this argument.

### `species` = *human on unknown* — judgement

A keyword rule reads it from the text and returns `unknown` when it cannot tell — **4 of the 8** real
tracker questions — and `unknown` runs as human, because treating it as non-human would strip
gnomAD, ClinVar and the predictors from human studies that merely never use the word. It fails in the
other direction: a non-human query that never says so keeps the human-only options. This is the one
guessed value chosen by judgement rather than by a measurement, and the weakest of them.

## 4. What silence costs, given those guesses

The four fallbacks above were chosen before this measurement ran. This section validates them: it
does not choose them, and it cannot, because filling the gap with the value under test is what the
tool already does at runtime.

**Method.** Each of the 31 generated queries states all five factors. One of the four ablatable
factors is deleted (species is not ablated — §3) with the other four held fixed, and a rewrite model
recasts the query to read naturally with that fact absent. Every rewrite is re-read before use. A
case counts as **clean** only when the target fact really went and no other factor moved: **78 of 124
attempts** (31 × 4). Of the remaining 46, 24 lost the words but left the fact still inferable from
context, 16 took a second factor with them, and 6 failed to remove the words at all. Reproducible:
three seeds matching the LOO's, spread zero.

Each clean case then goes through the tool's normal path. The classifier reads the rewritten query,
the gap is filled with the fallback under test, and the resulting configuration is compared against
the one the true factor values produce. Each row of the table names the value that filled the gap.

**Scored per output tier.** Losing a RECOMMENDED option costs a finding the user never learns they
missed. Losing an ADD-ON costs an option they were never shown they could have. **Lost** is options
the true configuration has and ours does not, per query. **Added** is the reverse. Regenerate with
`work/harness/score_ablations.py --markdown`; it re-resolves through the current priority table, so
it moves when the table moves.

| fact deleted | n | REC lost | REC added | ADD lost | ADD added | rows losing a REC option |
|---|---|---|---|---|---|---|
| `region_focus` — filled with *both* | 23 | **0.00** | 1.83 | 0.26 | 1.35 | **0/23** |
| `variant_size_class` — filled with *both* | 23 | **0.00** | 5.35 | 0.30 | 4.00 | **0/23** |
| `origin` — filled with *somatic* | 20 | 0.35 | 0.75 | 0.20 | 0.85 | 6/20 |
| `analysis_goal` — asked; *basic-consequence* on skip | 12 | 1.00 | 0.00 | 0.75 | 0.50 | 5/12 |

**Read the REC-lost column and the three fallbacks are confirmed.** `region_focus` and
`variant_size_class` lose no user-visible finding on any query, so the *both* fallbacks are additive
only. `origin` loses 0.35 REC options on average and hits 6 of 20 queries — the deliberate cost
already argued in §3.

**`analysis_goal` fails both conditions for guessing.** It loses on both tiers while gaining nothing.
That is why it has no fallback and is asked instead. §5 gives the argument.

**Where this table stops.** It counts options; whether a lost option would have carried DATA for the
user's variants is measured in `EXPERIMENTS.md` Exp 16, which runs the truth configuration through
VEP itself. The same "1.00 lost" line spans a total loss on a known missense variant and a near
no-op on a synonymous one. Score realized ANSWER losses, not counts, is the proposed refinement; it
lives there.

## 5. What we ask, and why

Two things are asked, on the same mechanism: `analysis_goal` and assembly. For each still-empty
factor, the resolver reruns the configuration under every candidate answer and compares. If nothing
in the RECOMMENDED bucket differs, the question cannot change what the user is shown, so it is never
asked. No model decides this; it is arithmetic over the priority table, cheap against a classifier
call, and auditable per query.

Asking is opt-in, because the evaluation harness and the generation pipeline call this code with
nobody present and would otherwise hang.

### `analysis_goal`

The only factor whose error is subtractive: reading a question as a plain consequence call drops
ClinVar and the predictors. It fails both conditions for guessing on the ablation set:

- asked on **12 of 12** ablations with the guess removed;
- fallback value loses REC options on **5 of 12**.

The ablations overstate how often this interrupts anyone, because they delete the fact on purpose.
On the eight real configuration questions from the trackers, `analysis_goal` is genuinely absent
**once**; it reads as absent three more times only because the two readers recovered it and
disagreed, which is a fact about our classifier rather than about the prose. Eight questions cannot
carry a frequency claim and none is made. Skipping is free: the fallback supplies `basic-consequence`
and announces itself, because a configuration cannot resolve without a goal at all — an empty one
gives about 6 options instead of about 13.

### Assembly

Not a factor. Assembly describes the input data rather than the analysis, and the taxonomy is a
description of the analysis. But it is the only gap where silence produces a *wrong* answer rather
than a thin one. MANE Select transcripts exist only for GRCh38, and `InputForm.pm:694-702` shows the
MANE checkbox to any human user and pre-ticks it, so a GRCh37 user gets an option with no data
behind it without opting in. Our checker enforces the restriction once it knows the build; a query
that never names one gives it nothing to infer from.

**Asked, never guessed.** Guessing GRCh38 would be wrong for exactly the GRCh37 users the bug
already affects, and it is the one place where the safer-direction argument that settles `origin`
does not apply, because both directions delete something real. So assembly runs through the same
three outcomes as every factor — take it from the text, or ask — with no guess in the middle.

Asking is cheaper than it sounds. `infer_assembly` reads a build out of **4 of the 8** real
configuration questions from the trackers, and one of those four is GRCh37, which is the whole
argument against guessing GRCh38 arriving in a sample of eight. The question is raised only for the
other four. The 31 generated review queries name a build **0** times, which is a property of a
generator that only writes about factors: the ablation set is structurally blind to assembly and is
not asked to measure it.

**The question is scored on what the user stated, not on what we assumed for them.** Because §3
guesses *both* variant sizes, gnomAD-SV — GRCh38-only — is switched on for almost every query, and
scoring the filled tuple would raise the assembly question on 42 of the 78 ablations against 32 for
the stated one. That follows the same asymmetry the whole policy rests on: an option we added is a
column the user can ignore and is not worth a question, while an option their own words called for
is. Suppressed for non-human queries, whose options are gated on species long before a build could
matter, and for a query that described no analysis at all. [unverified — 42/32 come from a scoring
alternative not exposed by `ask_rate.py`; the shipped run reports 34 assembly questions.]

### Why `origin` is asked-by-others rather than by-us

`origin` failed the guessing conditions less badly than `analysis_goal`: it does lose REC options
under silence (0.35 on average, 6 of 20 queries), but being wrong the other way is cheap and
disclosed. Interrupting everyone to save a line they can correct in a sentence is a bad trade. The
argument used to have a second leg: under the narrow `critical` bar, removing the origin guess
produced 0 origin questions across the 20 ablations, so the ask rule appeared to corroborate the
guess independently. That tier was deleted on 2026-08-19, so the corroboration went with it. The
guess still stands on the asymmetry alone.

## 6. Provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** a design judgement,
with no external source behind it.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Guess by default; ask only as an exception | **[Judg]** | a recommender that interrogates its users has moved the work back onto them. Not measured, and not measurable without frequency data we do not have |
| Ask only when something in the RECOMMENDED bucket is at stake | **[Judg]** + **[Meas]** | needs no threshold, and the question can name what is at stake **[Judg]**. Fires 46 times over the 78 clean ablations — 34 assembly, 12 `analysis_goal` **[Meas]** |
| The bar is the RECOMMENDED bucket the user is shown | **[Meas]** | the alternative was the internal `critical` tier, deleted on 2026-08-19 after the review found it unstable — twelve of the twenty mentor edits moved options across it |
| Guesses are stated, never silent | **[Judg]** | the failure this design answers is invisible omission, and a silent fix reproduces it |
| `region_focus` guessed *both* | **[Meas]** | deterministic sweep across the 31 rows: F1 0.91 *both*, 0.88 *coding*, 0.79 *regulatory-noncoding*, 0.79 blank. 0.00 REC lost across 23 ablations |
| `variant_size_class` guessed *both* | **[Meas]** | under single-select no value was safe — the two candidates gate opposite halves of the catalogue. Multi-select makes *both* available and it loses 0 REC on 23 of 23 ablations |
| `origin` fail-closed to somatic | **[Meas]** + **[Std]** | leaving it empty lets the frequency filter through on 6/15 somatic rows; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard `origin` rule **[Std]**. Guessing somatic costs `frequency` on 7/31 rows — paid deliberately |
| `analysis_goal` asked, not guessed | **[Meas]** | fails both conditions: asked on 12 of 12 ablations with the guess removed, and the fallback loses REC options on 5 of 12. On the 8 real questions it is genuinely absent once |
| Assembly asked, not guessed | **[Src]** + **[Judg]** + **[Meas]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**. Assembly describes the input data rather than the analysis **[Judg]**. Both directions delete something real, and the text names a build on 4 of the 8 real questions, one of them GRCh37 **[Meas]** |
| How often users omit things | **not established** | `fetch_real_queries.py` pulls tracker issues verbatim with a per-body SHA-256 and a `--verify` re-fetch, but only 8 of 43 are configuration questions. Biostars is Cloudflare-blocked at both the HTML and the API. Too few to carry a frequency claim |

The structure is a synthesis, grounded in measurements taken on this repository and in how VEP's own
form behaves. No published interface standard was found that applies. The ablations are reproducible
with `ablate_queries.py`, without a GPU, and the judgement calls are marked.

Cost and consequence are measured; the tables above say what each gap does to the configuration. How
often real users leave a fact out is not, and that number decides how aggressive to be. The cheapest
route to it is the `real_data` Likhitha has offered.

Nearest literature: Gervits et al., ICMI '21 (arXiv:2110.06288) select clarification questions by
maximum expected utility over a decision network, setting the utility of asking about an already-known
property to zero. Our relevance gate is the same principle in deterministic form. Theirs needs
priors, a corpus and a model of the interlocutor; ours needs none and is auditable per query, at the
cost of not being able to trade the cost of asking against its benefit. Read pp. 1–5 of 9, with §5–6
not read, so no claim is made about how their model performed.

## 7. Trying it

```bash
python vep_assistant.py "human tumour WGS, which variants are damaging?"      # guesses, stated
python vep_assistant.py --quiet "..."                                         # guesses, silent
python vep_assistant.py --ask "..."                                            # also prompt

python work/harness/try_reprompting.py --why "human tumour WGS, ..."          # what it did, and why
python work/harness/try_reprompting.py --factors species=human,analysis_goal=population-frequency

python work/harness/ask_rate.py                                                # how often it interrupts
python work/harness/ask_rate.py --by-row --arm shipped                         # and on which cases
python work/harness/defaults_evidence.py --verbose                             # why each default is that
python work/harness/score_ablations.py --markdown                              # the §4 table, live
