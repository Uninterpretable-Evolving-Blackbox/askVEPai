# Merging the two model calls — 2026-09-09

`gemma4:26b`, Ollama 0.33.3, **local on an Apple M5 Max / 128 GB**, context 16384, temperature 0,
the 31-row factor set. First runs on this machine: the 18.6 GB model fits in RAM, so no tunnel.

Nothing here is written into `EXPERIMENTS.md` yet.

## The change

`--single-pass` skips the second model call and leaves the draft empty. It is not a degraded mode:
`restore_missing_recommended` reconstructs the RECOMMENDED set from the factor tuple whatever the
draft said. Verified separately -- an empty draft, a one-option draft, and a draft explicitly
DISABLING `sift`/`clinvar`/`mane` all yield the same 20 options.

Conflict ranking is unaffected. `_detect_use_case` retrieves over the examples using the query, and
its `enabled` parameter is dead by its own docstring, so it never read the draft.

## Result — 31/31 rows, both paths

| | |
|---|---|
| **single-pass ⊆ two-pass** | **31/31** |
| options only the single pass has | **0, on every row** |
| identical block | 17/31 |
| mean options | two 12.1, single 11.5 |
| **mean latency** | **two 14.0s, single 0.9s** |

The single pass never invents an option and never loses a core one. The second call only ever ADDS.

## What the second call adds, and whether it is worth 13 seconds

| option | times | what it is |
|---|---|---|
| `check_existing` (Find co-located short variants) | **12** | `web_default_on: true` -- **the form already has it ticked**. Recommending it tells the user to switch on something they have |
| `coding_only` | **4** | **row-affecting and destructive**: "Removes non-coding consequence lines (intronic and intergenic) from output" |
| `nmd` | 2 | one extra column |
| `gnomad_sv` | 1 | one extra column |

All four ARE priced by the factor table for some factor value -- the table simply declined to raise
them for these scenarios. So the draft is overriding the table's judgement, not filling a gap in it.

Twelve of the nineteen additions are an option the user already has. Four are a filter that deletes
output rows. That is the cost of the second call, alongside the 13 seconds.

## Factor accuracy — the metric a single-pass design needs

With the draft gone, the factor tuple is the only thing the model decides, so it is the only thing
worth scoring.

| factor | correct (mean of 3 seeds) |
|---|---|
| `species` | 31/31 -- **keyword rule, not the model** |
| `origin` | 30/31 |
| `variant_size_class` | 29/31 |
| `region_focus` | 31/31 |
| `analysis_goal` | **24/31** |
| **exact tuple** | **22/31** |

**End-to-end F1 = 0.975 ± 0.000** (gold = config from the true tuple; prediction = post-checker
config from the inferred tuple). Zero spread on seeds 42/43/44.

`analysis_goal 24/31` is largely a labelling artifact, not a classifier error: the truth carries
`basic-consequence` alongside another goal and the model returns only the other, which is what
`FACTOR_CLASSIFIER_PROMPT` instructs ("Use basic-consequence only when the question really is just
'what are these variants'"). Most of those misses cost nothing, because `clinical-interpretation`
already subsumes `basic-consequence` in the priority table.

## Species: the answer the code throws away

`_schema_lines()` generates the classifier prompt from `FACTOR_VALUES`, which includes `species`. The
model is asked for it and answers. `vep_assistant.py:951` then overwrites that with `infer_species()`.

| | correct |
|---|---|
| keyword rule (shipped) | 31/31 |
| the model's own answer | 31/31 |

A tie, and the tie is the finding: **all 31 rows state their species outright, so this set cannot
discriminate.** The 2026-09-08 adversarial probe could -- the rule scored 3/8 against `e4b`'s 7/8,
reading "going down this rabbit hole" as *rabbit* and "somatic ... zebra finch" as *human*. Deciding
species on the 31 rows would measure the generator.

## Four-arm ablation: pass count x corpus (31 rows, seed 42)

Gold = the config resolved from each row's OWN TRUE factor tuple, so the arms are comparable.
Scoring the corrected output against the table generically returns ~1.0 for any arm and measures
the resolver against itself.

| arm | F1 | options | extra | missing | secs |
|---|---|---|---|---|---|
| **single** | **0.898** | 11.3 | **1.55** | 1.26 | **1.1** |
| `two_23` (shipped) | 0.872 | 11.9 | 2.13 | 1.19 | 13.5 |
| `two_31loo` | 0.866 | 12.0 | 2.19 | 1.19 | 14.5 |
| `two_none` | 0.854 | 12.4 | 2.61 | 1.19 | 12.5 |

`extra` = shown but not called for by the true tuple. `missing` = called for but not shown.

Single-pass leads on F1 and on `extra`, and is marginally worse on `missing` (1.26 vs 1.19). The
second call's contribution is options the true tuple does not ask for; the corpus's job is to
restrain it.

Corpus ordering `none < 31loo < 23`. Examples do help the draft -- by ~2 points measured on the
OUTPUT, against Exp 11's 23 points measured on the DRAFT. Most of the corpus's benefit is absorbed
by machinery that would have corrected the draft anyway. The factor-native 31-row corpus is no
better than the 23 legacy one, consistent with the 133-option drift.

`two_31loo` needed two things that are findings in themselves: `format_example` crashed on the
factor rows (all 31 carry `justification: None` and `use_case_category: None`), and with no
`use_case_category` the corpus cannot feed `_detect_use_case`, which ranks options in conflict
resolution. That is a third blocker on the parked corpus-switch decision.

## What the second call adds, priced on the output axis

The 2026-09-08 leak study grades the leak classes by what they do to a real VEP file. Most are
advisory: `symbol` (9), `check_existing` (26) and `sift` (3) have **no output effect** -- REST
returns them unasked and the form ships them ticked, so the model contradicts mentor advice while
the file is unchanged. The destructive family (`per_gene`, `most_severe`) was **gated** in 467cfed
/ 392479f and no longer reaches the user.

What survives as live harm, from the 31-row run here: **`coding_only` on 4 of 31 rows.** It is not
in the gated family -- a separate checkbox -- and it removes non-coding consequence lines from the
output. So the case against the second call is redundancy plus one unfixed destructive addition,
not blanket harm.

## Caveats

Local 26b gives end-to-end F1 **0.975**; the same model over the Colab tunnel on 2026-09-08 gave
**0.969**, same seeds and context length. Ollama version differs (0.33.3 here). Small, but the two
are not interchangeable -- quote the Ollama version alongside the hardware.

31 synthetic rows written to express their own factor labels, so every number here is an upper
bound on prose a user would actually write.

## Files

| file | what |
|---|---|
| `singlepass_eval.json` | per-row factor hits, species comparison, end-to-end F1, 3 seeds |
| `singlepass_vs_twopass.json` | per-row option sets and latency, both paths |
| `comparison.log` | the run |

Reproduce: `work/harness/full_eval_singlepass.py`, `work/harness/singlepass_vs_twopass.py`.
