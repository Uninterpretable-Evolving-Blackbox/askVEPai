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
`species`, argued factor-by-factor in §3. One does not: `analysis_goal` is asked. Assembly, which is not a factor at all, is also asked when the text does not name it — §5. `[assembly-default pending]`

**PENDING, should we just default to Ghr38 like thw web?** `[assembly-default pending]`

Species does the same take from text, guess, or ask, but because it is a hard gate rather than a soft priority factor, its disclosure lives in the constraint checker's removal report rather than in the upfront ask-lines. Same policy, different disclosure surface.

## 3. What we guess, and why each

Four different methods chose the four guessed values. None of them was the ablation table in §4; that
table prices these choices rather than making them. `defaults_evidence.py` re-derives every argument
below and fails if one no longer holds.

### `region_focus` = *both* — deterministic sweep

Resolve every one of the 31 rows under each candidate `region_focus` value and score enable-F1
against the true options. *Both* win:

| value | mean F1 |
|---|---|
| **both** | **0.91** |
| coding | 0.88 |
| regulatory-noncoding | 0.79 |
| (left blank) | 0.79 |

The factor is `select: multi` in `factors.json`, so *both* is expressible; the resolver's hard gate
removes an option only when every active value rules it out, which is why a coding+regulatory query
keeps its predictors.

### `variant_size_class` = *both* — the only expressible safe value (if default to ghr38 then we can just do both) `[assembly-default pending]`

**Input-side: the factor is multi-select.** This factor describes the variant *set*, not one
variant. A WGS callset routinely holds both classes, so *both* is the normal answer for whole-genome
work. Review row 1 is such a query. The values `small` and `structural-CNV` gate opposite halves of
the catalogue, so neither single value is safe:

| policy | options missing per query | options added per query | queries missing a RECOMMENDED option |
|---|---|---|---|
| single-select, no safe value, asked | 1.70 | 5.22 | 13/23 |
| **multi-select, guessed *both*** | **0.00** | 5.35 | **0/23** |

Multi-select in Ask VEPai makes *both* available. The error becomes purely additive, and the factor
asks nothing. This amends `taxonomy_proposal.md` §3, which had signed off `select: single`. One
field flips it back.

## Two VEP runs when both sizes are present

**Output-side: one configuration per size.** The web form cannot express both sizes in one
configuration. CADD's control is a drop-down over four mutually exclusive annotation files
(SNVs and InDels / SNVs / InDels / CADD-SV). A both-size scenario emits **two configurations, two
VEP runs**: one small, one structural.

Across all 36 both-size factor tuples, the two passes together enable exactly what the single
configuration did (`verify_pipeline.py` §8b).

### `origin` defaulting to *somatic* — danger audit

Two arms wearing three labels, measured on the 31 review rows (15 somatic, 16 germline).

| origin arm | somatic rows destroyed | germline rows costed |
|---|---|---|
| **somatic** (the guess) | **0/15** | 7/16 |
| germline or unstated (identical lookup) | 6/15 | 0/16 |

The two harms are not symmetric:

- **Destructive** — on a somatic row, `frequency` switched on filters out the common variants the
  study is looking for. The analysis is destroyed.
- **Recoverable** — on a germline row, `frequency` switched off is a RECOMMENDED option the user
  might have wanted. They turn it back on in one line.

Somatic is the only arm with zero destructive harm; it costs 7 recoverable ones. The other arm
destroys 6 somatic analyses. Silence is not the neutral choice — it shares a code path with
germline, so it inherits germline's destructive-side failure.

### `species` = *human on unknown* — judgement

THIS NEEDS ANOTHER RUN WITH THE ABLATION

A keyword rule reads it from the text and returns `unknown` when it cannot tell — **4 of the 8** real
tracker questions — and `unknown` runs as human, because treating it as non-human would strip
gnomAD, ClinVar and the predictors from human studies that merely never use the word. It fails in the
other direction: a non-human query that never says so keeps the human-only options. This is the one
guessed value chosen by judgement rather than by a measurement, and the weakest of them.

## 4. What silence costs, given those guesses

§3 chose the four fallback values. This section measures what each one costs when the classifier
returns nothing and the tool has to fill the gap with the fallback under test.

**Method.** 31 queries, each naming all five factors. For every query we produce four test versions,
each with one factor removed (species is not tested this way; see §3).

Removing a factor is not just a delete: a rewrite model recasts the sentence naturally with that
fact absent, so the query still reads like a real one. Every rewrite is checked before use.

A case counts as **clean** only when the target fact is truly gone and no other factor moved.
**78 of 124 attempts (31 × 4) qualified.** The other 46 broke as follows:

- 24 removed the words but left the fact still inferable from context
- 16 also removed a second factor
- 6 failed to remove the words at all

Reproduced across three seeds, matching the seeds used in the main evaluation. Zero variance across
seeds.

Each clean case then goes through the tool's normal path. The classifier reads the rewritten query,
the gap is filled with the default under test, and the resulting configuration is compared against
the one the true factor values produce. Each row of the table names the value that filled the gap.

**Scored per output tier.** RECOMMENDED and ADD-ONS drift independently, so both are counted.

- **RECOMMENDED lost** — options in the truth configuration's RECOMMENDED bucket that aren't in
  ours. The tool didn't tell the user to switch these on. Depending on where the option landed, it
  either sits in our ADD-ONS list (visible, but the user has to opt in) or disappears entirely.
- **ADD-ONS lost** — options in the truth configuration's ADD-ONS bucket that aren't in ours. 
- **Added** — the reverse of each: options in our bucket but not the truth's.

Regenerate with `work/harness/score_ablations.py --markdown`; it re-resolves through the current
priority table, so it moves when the table moves.

| fact deleted | n | REC lost | REC added | ADD lost | ADD added | rows losing a REC option |
|---|---|---|---|---|---|---|
| `region_focus` — filled with *both* | 23 | **0.00** | 1.83 | 0.26 | 1.35 | **0/23** |
| `variant_size_class` — filled with *both* | 23 | **0.00** | 5.35 | 0.30 | 4.00 | **0/23** |
| `origin` — filled with *somatic* | 20 | 0.35 | 0.75 | 0.20 | 0.85 | 6/20 |
| `analysis_goal` — asked; *basic-consequence* on skip | 12 | 1.00 | 0.00 | 0.75 | 0.50 | 5/12 |

**From the REC-lost column.**:
`region_focus = both` and `variant_size_class = both` both show **0.00** — silence plus these
fallbacks removes no RECOMMENDED option from any query in the set (0/23 queries lose). The only
cost is a few extra options in ADD-ONS.

`origin = somatic` shows **0.35** — silence plus somatic removes at least one RECOMMENDED option
on **6 of 20** queries.

**`analysis_goal` has no fallback and is asked.** The ablation shows why: silence plus the
`basic-consequence` fallback loses 1.00 RECOMMENDED options per query on average (5 of 12 queries
losing at least one) and adds none in their place. ADD-ONS drift the same way: 0.75 lost against
0.50 added. Both tiers move against the fallback, so no candidate value earns the trade. §5 gives
the ask-side argument.


QUANTIFY THIS:
**What this table misses.** It counts every lost option the same. i.e. Losing SIFT costs a real column
on a missense variant, where SIFT would have scored something, and costs nothing on a synonymous
variant, where SIFT would have been empty anyway. `EXPERIMENTS.md` Exp 16 runs the truth
configuration through VEP itself to see which fields actually get populated for each variant class,
and proposes scoring the options that would have carried a value rather than the raw count.

## 5. What we ask, and why

Two things are asked, on the same mechanism: `analysis_goal` and assembly. For each still-empty
factor, the resolver checks whether any candidate answer would change what the tool would show. If
not, the question is skipped. No model decides this — it's arithmetic over the priority table,
auditable per query.

### `analysis_goal`

The only factor whose error is subtractive: the fallback value basic-consequence drops ClinVar and the predictors that clinical-interpretation would have brought in. It fails both conditions for guessing on the ablation set:

- asked on **12 of 12** ablations with the guess removed;
- fallback value loses REC options on **5 of 12**.

The ablations overstate how often this interrupts anyone, because they delete the fact on purpose.
Real users likely mention their analysis goal more often than the ablation set assumes, though we
don't have the sample size to say by how much. Skipping is free either way: the fallback supplies
`basic-consequence` and announces itself, because a configuration cannot resolve without a goal at
all — an empty one gives about 6 options instead of about 13.


### Assembly `[assembly-default pending]`

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
scoring the filled tuple would raise the assembly question on 40 of the 78 ablations against 34 for
the stated one. That follows the same asymmetry the whole policy rests on: an option we added is a
column the user can ignore and is not worth a question, while an option their own words called for
is. Suppressed for non-human queries, whose options are gated on species long before a build could
matter, and for a query that described no analysis at all.

### Why `origin` is asked-by-others rather than by-us GONE IF WE ASSUME GRCh38 `[assembly-default pending]`

`origin` failed the guessing conditions less badly than `analysis_goal`: it does lose REC options
under silence (0.35 on average, 6 of 20 queries), but being wrong the other way is cheap and
disclosed. Interrupting everyone to save a line they can correct in a sentence is a bad trade. The
argument used to have a second leg: under the narrow `critical` bar, removing the origin guess
produced 0 origin questions across the 20 ablations, so the ask rule appeared to corroborate the
guess independently. That tier was deleted on 2026-08-19, so the corroboration went with it. The
guess still stands on the asymmetry alone.


## 6. Trying it

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
```
