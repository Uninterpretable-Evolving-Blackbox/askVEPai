# Overnight runs — 2026-09-10

Launched 00:04 as an unattended overnight queue. Apple M5 Max 128 GB, Ollama
local (version per `ollama -v`), `OLLAMA_CONTEXT_LENGTH=16384` confirmed via `launchctl getenv`,
temperature 0, concurrency 1 throughout. `queue.log` has the step timestamps; each step has its own
`.log` and `.json`. `run_queue.sh` is the exact command sequence.

Nothing here is written into `EXPERIMENTS.md`. Everything is gitignored under `work/results/`.

## What was asked, and which file answers it

| question | files |
|---|---|
| Does the 0.898 vs 0.872 single-vs-two-pass gap survive repeat runs? | `pass_corpus_ablation_26b_rep2.*`, `_rep3.*` (rep 1 is `../pass_corpus_ablation.json`) |
| Would a keyword rule per factor do the classifier's job? Does showing the model the rule's matches as hints help? | `rules_vs_model_26b.*`, `rules_vs_model_e4b.*` (`work/harness/rules_vs_model.py`, new) |
| How much of the 26b→e4b→e2b gap is the draft call? Factor accuracy, end-to-end F1, species, single-vs-two on each | `singlepass_eval_e4b.*`, `singlepass_eval_e2b.*`, `singlepass_vs_twopass_e4b.*`, `_e2b.*` |
| Does one pass help the laptop model as much as the big one? | `pass_corpus_ablation_e4b.*` |
| Species on species-removed text: does the model, or the model with the 356-species index as hints, know it is guessing where the keyword rule reads "human" on 11/14? | `species_rule_vs_model_26b.*`, `_e4b.*` (`work/harness/species_rule_vs_model.py`, new; runs from `run_followup.sh` after the queue, added after the queue was written) |

## Read before quoting

- **The two-pass arms are not seeded.** The CLI's draft call (`stream_response`) sets no seed and no
  temperature, so the two-pass F1 in the four-arm ablation is the shipped path at Ollama's default
  temperature. Repeats 2 and 3 therefore measure the shipped path's own run-to-run spread, which is
  the right quantity for "what the user gets". The single arm is fixed-seed 42 and should reproduce
  exactly.
- `gemma4:e2b` was pulled tonight (not previously on this machine). If the pull failed, the e2b
  steps will show a model-not-found error in their logs and the queue continues past them.
- The rules in `rules_vs_model.py` were written from the classifier prompt's guidance words plus
  obvious synonyms, before seeing any result. They were not tuned on the rows.
- 31 synthetic rows that state their factors, so every "31 rows" figure is an upper bound. The
  ablated set (78 pure of 124) is the harder case: truth for the removed factor is "unstated".

## Results (written 02:45 when the queue finished; read the logs for the full tables)

**1. Four-arm ablation, 26b, three repeats.** single 0.898 ± 0.000 (identical on 31/31 rows every
repeat); two_23 0.870 ± 0.002; two_31loo 0.866 ± 0.001; two_none 0.855 ± 0.001. Between repeats the
two-pass arms changed on 16 / 10 / 6 rows respectively and the single arm on 0. The CLI's draft call
(`stream_response`) sets no seed or temperature, so every two-pass figure is the shipped path at
Ollama's default temperature; the single arm is fixed-seed. The 3-point gap survives that.

**2. Rules vs model vs hinted, 26b** (`rules_vs_model_26b.log`). New keyword rules for origin /
size / region / goal, built from the classifier prompt's own guidance words (a best case for the
rule arm), lose to the model on every factor on the 31 rows (all four right: rule 9, model 22,
hinted 21). On the 118 cue-removed rewrites the model says "unstated" more often than the rule on
origin (15 vs 11 / 20) and region (22 vs 10 / 23), ties on goal (9 / 12), and is better on the
untouched factors of the same texts. Hints do not help 26b. David's "rules for the other factors"
idea is refuted at 26b; the species rule is the odd one out.

**3. Single-pass ladder.** e4b: exact tuple 19/31, end-to-end F1 0.927 ± 0.000, 0.9 s/row, single ⊆
two on 31/31 at the option level (row 29's "only_single" lines are the type-grouped predictor line
listing different members, a rendering artifact). e2b: the direct classifier call returned
unparseable output on the same 7 rows on every seed, all 7 non-human; on the 24 it managed, e2e F1
0.952 but exact tuple 14/24. The CLI path classified all 31 (see the probe below for why the two
differ). e2b stays below the floor.

**4. Four-arm ablation, e4b.** single 0.874 / two_23 0.834 / two_31loo 0.826 / two_none 0.803. One
call on e4b (0.874) matches the shipped two-call 26b (0.870) on the same metric, in 1.2 s. The gain
from dropping the draft is larger on the small model (4 points) than on 26b (3).

**5. Rules vs model, e4b.** On stated rows e4b is close to 26b and hints help slightly (all four
right 19 -> 21). On cue-removed rows e4b almost never says "unstated": 0 / 23 on variant size, 4 / 12
on goal, 8 / 20 on origin, where 26b managed 23 / 9 / 15. The keyword rule out-detects e4b on three
of four factors as an "I don't know" signal, which is what the ask-when-it-matters policy keys on.

**6. Species on species-removed text** (`species_rule_vs_model_*.log`). 14 pure rows. 26b: the rule
reads "human" on 11 and "unstated" on 3 (Exp 18 reproduced); the model's own species answer says
"unstated" on 14 / 14, masked on 0; hints change nothing. So at 26b the masking Exp 18 found is
entirely the rule's, and an ask policy could catch 14 instead of 3. Cost: on the 10 human rows whose
context still implies human, the model says "unstated" on all 10 (the rule says human), so the model
would raise species asks on human queries that never say "human" unless the assume-human default
stays behind it. e4b: the model masks on 13 / 14, worse than the rule. The species judgement is a
26b capability.

**Read with the standing caveats:** gold is our own priority table, under review; the 31 rows and
their rewrites are synthetic and state their factors; one seed on the rules and species runs; Ollama
version and Apple M5 Max Metal throughout.

**7. Why e2b "failed" 7 rows** (`probe_e2b_failures.log`). It did not fail to classify. On all three
probed rows e2b returns a correct, complete JSON object minus the final closing brace
(`finish_reason=stop`, content ends after the last `]`), with and without `think: False`.
`parse_factor_classification` does `raw.rfind("}")`, finds nothing, and returns None. The 7 rows are
therefore a parser-robustness gap, not a model failure: species, origin, size and region were right
on every probed row. Not fixed tonight because it is an engine change; a one-line tolerance for a
missing trailing brace would rescue them, and the e2b figures in §3 should be re-read after it.
