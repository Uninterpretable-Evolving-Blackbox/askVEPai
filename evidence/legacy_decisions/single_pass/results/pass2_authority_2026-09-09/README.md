# What the LLM actually decides — 2026-09-09

Raw evidence. `gemma4:26b` over a cloudflared tunnel, `OLLAMA_CONTEXT_LENGTH=16384`, temperature 0,
seed 42, the 31-row factor set. Nothing here is written into `EXPERIMENTS.md` yet.

## 1. Pass 2 has no authority over the RECOMMENDED set

Three deterministic checks, no model needed (`restore_missing_recommended` on a clinical human
germline tuple, 20 table-recommended options):

| model draft | table-recommended options present afterwards |
|---|---|
| empty | **all 20** |
| `{"sift"}` | all 20 |
| explicitly DISABLING `sift`, `clinvar`, `mane` | **all 20** — the disables are overridden |

So the model can neither add to nor subtract from the set the user receives. Over the whole 31-row
set, post-checker F1 against the true-tuple gold is **0.985 whether the draft is empty or hostile**.

`enable-F1` (`eval_factor_set.py`) parses `extract_recommendations` and stops there, so it scores the
draft — the half that is discarded.

## 2. The examples feed pass 2 -- and, through the checker, the retired taxonomy

`infer_factors` builds its prompt as `FACTOR_CLASSIFIER_PROMPT + user_query`. No examples.
`build_system_prompt`, which assembles all 23, has exactly one call site: the pass-2 draft.

BUT the examples reach the output by a second route that is easy to miss. `check_and_fix_violations`
calls `_detect_use_case(enabled, vep_options, training_examples, user_query)`, which keyword-matches
the query against the 23 examples and returns one of the **retired seven use-case categories**. That
category then feeds `_get_priority_rank(oid, use_case, vep_options)`, which reads the legacy
`priority_by_use_case` field, and the rank decides **which option survives a conflict**.

So the shipped conflict resolver routes through a taxonomy the project deleted, keyed off a corpus
labelled for that taxonomy. This is why removing the examples changed `clinvar` on two rows below --
a RECOMMENDED option, which the draft cannot touch. `ONBOARDING.md` §7 records the legacy field as
load-bearing for the SV gate; conflict ranking is a second reader nobody had listed.

The 23 in `training_examples.json` are keyed by the **retired seven-use-case scheme**
(`rare_disease_germline`, `somatic_cancer`, …), not by the five factors. The 31 factor-keyed rows are
the generation pipeline's output and are used only as the evaluation set — the corpus was never
switched over. Handover §5 records why: the 31 rows' stored configs have drifted 133 option-instances
from the live table, and using table-generated rows as the corpus would make the metric
self-referential.

## 3. Factor-tuple accuracy — the first measurement of it

| factor | correct |
|---|---|
| `species` | 31/31 — **keyword rule, not the model**, and all 31 rows state it outright |
| `origin` | 28/31 |
| `variant_size_class` | 30/31 |
| `region_focus` | 31/31 |
| `analysis_goal` | **24/31** |
| **exact tuple** | **21/31** |

Identical on seeds 42, 43 and 44 -- every count above, and the F1 below, moved **zero** across
seeds. Exp 17 found the pass-2 draft DID vary by seed (88.2 / 87.9 / 87.9), so the deterministic
half is deterministic and the discarded half is the part that wobbles.

**End-to-end F1 = 0.969 ± 0.000** (3 seeds). Gold is the config resolved from the row's true tuple; prediction is the
post-checker config from the *inferred* tuple. The only thing that can move it is a factor misread,
weighted by how many options that misread costs.

Reproduce: `work/harness/exp/factor_accuracy.py`. One seed; the ± is unmeasured.

## 4. Most of the misses are gold-labelling artifacts, not classifier errors

10 rows had at least one factor wrong. **6 of those 10 cost nothing** (end-to-end F1 = 1.000).

**Five of the seven `analysis_goal` misses are the same pattern:** the truth carries
`basic-consequence` alongside another goal, and the model returns only the other one.

    ['basic-consequence', 'clinical-interpretation']  ->  ['clinical-interpretation']       x3
    ['basic-consequence', 'clinical-interpretation', 'population-frequency']
                                        ->  ['clinical-interpretation', 'population-frequency']  x2

The classifier prompt instructs exactly this: *"Use basic-consequence only when the question really
is just 'what are these variants', with no clinical or disease framing."* So the model follows the
prompt and the gold label contradicts it. Four of those five cost nothing, because
`clinical-interpretation` already subsumes `basic-consequence` in the priority table.

**All three `origin` misses are `germline` -> `unstated`, all on non-human rows, all costing nothing.**
The prompt says to answer `unstated` when the question does not indicate a characteristic, and
`origin` moves exactly one option (`frequency`), which is human-only.

So `analysis_goal 24/31` is not a 77% classifier. It is a classifier obeying its prompt against a
generator that labelled implied values as stated ones.

## 5. The four misses that do cost something are all over-inclusion

| end-to-end F1 | what happened | gold -> predicted |
|---|---|---|
| 0.652 | `variant_size_class` guessed *both* when truth was structural-only, plus a goal error | 15 -> 31 |
| 0.786 | goal `basic` read as `clinical` | 11 -> 17 |
| 0.952 | dropped `basic-consequence` | 10 -> 11 |
| 0.966 | dropped `basic-consequence` | 14 -> 15 |

Every one predicts MORE options than the gold. The error direction is additive — extra columns a user
can ignore — not subtractive, which is the direction that deletes a finding. That is the same
asymmetry the ask/assume policy is built on, now observed end to end.

## Files

| file | what |
|---|---|
| `factor_accuracy_seed42.json` | per-row truth vs inferred tuple, per-factor hit, end-to-end F1 |
| `factor_accuracy_3seed.json` | the same across seeds 42/43/44 |
| `noexamples_vs_examples.json` | the 31-row corpus comparison |

## 6. Dropping the 23 examples changes what the user gets -- by ADDING options

31 rows, each run twice through the full pipeline, `VEP_EXAMPLES_FILE` the only variable, comparing
the rendered RECOMMENDED block:

| | |
|---|---|
| identical block | **9/31** |
| mean options with the 23 | 12.1 |
| mean options without | **12.9** |
| more options WITHOUT examples | 17/31 |
| more options WITH examples | 3/31 |
| same count | 11/31 |

The prediction that it would be identical was wrong. Removing the corpus makes the model propose
MORE, and almost all of it is add-ons the table rates `optional`:

    10x NMD    6x PubMed IDs    6x UniProt    3x GO terms    3x Find co-located    2x LOEUF

So the 23 examples' measurable effect on the user's output is **suppressing over-recommendation**,
not improving the recommended core -- the core is the checker's, as §1 shows. Two rows also moved
`clinvar`, which is a RECOMMENDED option, and that is the `_detect_use_case` route in §2, not the
draft.

Net: the corpus earns its place, but for a reason nobody had measured, and it does so while keyed to
a deleted taxonomy. Exp 11's 62% -> 85% enable-F1 gain measured the draft; this measures the output.

## Caveats

One seed, one model, 31 synthetic rows that state their factors by construction — which is why
`species` scores 31/31 here and got 2 of 8 real tracker questions wrong on 2026-09-08. This measures
the classifier on prose written to express its own labels, so it is an upper bound.
