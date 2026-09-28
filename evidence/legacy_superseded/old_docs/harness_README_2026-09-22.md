# `work/harness/` — what each script is, and which version of the project it belongs to

58 scripts, 26 numbered experiments, June to September 2026.

**Layout changed 2026-09-22.** The directory was flat; the scripts are now in four subdirectories by
kind. Paths were updated everywhere they must resolve — code, CI, `EXPERIMENTS.md`, the live docs.
**The dated handovers (`HANDOVER_*.md`, `HANDOFF*.md`) were deliberately left alone**: they are
snapshots of what was true on a date, and a path inside one is a record, not a link. When a handover
names `work/harness/<script>.py`, look for it under the kind directory below.

```
harness/
  suites/   4   run every session. Pass/fail, no model, seconds.
  build/    7   regenerates a data file from a source. Run when the source changes.
  exp/     28   an experiment whose result is still quoted. Re-run after a change to what it measures.
  done/    18   answered. The reproduction record for its experiment; do not re-run for a number.
  _remote_guard.py   shared: refuses a model call against localhost. Imported, not run.
  legacy/            priority_by_use_case_snapshot.json — the retired stage-B priority field.
```

Nothing was renamed. `EXPERIMENTS.md` and the handovers cite these filenames 460 times, so the names
are load-bearing; only their directory changed.

---

## The five stages, so any script can be dated

| stage | dates | what the system was | what ended it |
|---|---|---|---|
| **A · demo** | to 2026-06 | 26-option KB, 8 examples, inherited from the `vep_ai_demo` prototype | replaced by the 58-option catalogue |
| **B · use-case** | 2026-06 → 07-15 | 58-option catalogue, 20 simulated gold examples, **7 use-case categories** keyed by `priority_by_use_case`, **3 tiers**, **two model calls** (draft, then checker) | the 7 use-cases replaced by 5 factors; the Opus silver set withdrawn 07-15 |
| **C · factor** | 2026-07-15 → 09-09 | **5 factors** (species, origin, variant size, region focus, analysis goal), 31 pipeline-generated review rows, priority table keyed by factor value. Tiers merged 3 → 2 on 08-19. Still two-pass. | the draft call was measured to add nothing the checker keeps |
| **D · single-pass** | 2026-09-09 → 09-15 | **one model call**: prose → factor tuple. The resolver and checker build the configuration. `enable-F1` becomes undefined on the default path, so the classifier itself becomes the thing under test | the classifier's own reading became the open question |
| **E · classifier hardening** | 2026-09-15 → 09-22 | species from the model rather than the keyword scan (09-16), **prompt v2** (09-16), `organism` field and **reasoning on by default** (09-20), Ensembl's per-plugin species lists over our prose (09-20) | current |

**One cross-cutting correction.** The alias/parser fix of **2026-07-15** (`reparse_bare_fix.py`)
invalidated the `bare` baselines of Exp 1–3, 10 and 11. Every stage-B `bare` figure published before
that date is withdrawn. Nothing else moved.

---

## Suites — run these every session

| script | stage | exp | what it does |
|---|---|---|---|
| `defaults_evidence.py` | E | 18, 23 | 28 assertions. Re-derives the justification for every guessed default and fails when a published number stops matching the table. |
| `test_user_context.py` | C→E | — | 15 assertions. A fact the user states beats the classifier; the assembly gate fires and `restore_missing_recommended` does not undo it. |
| `ask_rate.py` | D→E | — | How often the tool interrupts, per candidate policy. Shipped is 12/78, all `analysis_goal`. Every ask-rate figure in `reprompting_proposal.md` comes from here. |
| `fallback_e2e.py` | D | 24 | Does a factor the query never states reach the decided fallback, end to end through the shipped CLI, and get disclosed. |

Two more live in `work/generation/`: `verify_pipeline.py` (79 invariants) and `check_round2_ready.py`
(the shipped table against what the mentors were told).

## Builders — regenerate a data file from a source

| script | stage | exp | writes | from |
|---|---|---|---|---|
| `build_plugin_species.py` | E | — | `species_data.json` → `plugin_species` | VEP_plugins release/116 `plugin_config.txt` |
| `build_species_data.py` | D | 25 | `generation_config/species_data.json` | Ensembl's pathogenicity page, `InputForm.pm`, `vep_custom_web_config.json` |
| `build_species_index.py` | C→D | — | `species_index.json`, 356 species | Ensembl's own species list |
| `build_output_effects_dossier.py` | D | 22 | `research/output_effects_dossier.md` | the release-116 options, web-form and plugins pages |
| `build_mentor_gold.py` | C→D | — | `results/mentor_gold.json` | the reviewer's returned round-1 sheet, not our own table |
| `assemble_catalogue.py` | B→E | — | `vep_options_expanded.json` | the catalogue-build workflow output. Fixed 2026-09-20: it was silently dropping nine fields on a rebuild. |
| `build_output_json.py` | B | 8 (follow-up) | schema-valid recommendation JSON | logged `✓/✗ [source: id]` responses — proves our code assembles the JSON the model cannot emit |

## Live experiments — results still quoted

| script | stage | exp | what it answers |
|---|---|---|---|
| `factor_grid.py` | E | — | 150 balanced cases × 4 versions (plain/trap/twin/absent) = 600 queries. Reasoning on 142/150, off 138/150, keyword rules 27/150, always-most-common 0/150. **Supersedes `factor_traps.py` and `factor_pairs.py`.** |
| `organism_naming.py` | E | — | Does the classifier name the organism, and does the name agree with the binary factor. 121 organisms × 2; 0/242 contradictions with reasoning on, 20/242 off. |
| `factor_accuracy.py` | D→E | 21 | Factor-tuple accuracy on the 31 rows, scored by label **and** by whether the configuration changes at all. |
| `rules_vs_model.py` | D | 21 | A keyword rule per factor against the classifier. Rules 9/31 exact, model 22/31. |
| `species_rule_vs_model.py` | D | — | Species specifically: keyword rule vs the model vs the model with hints, on species-removed queries. |
| `species_recall_hint.py` | D | — | Does the species hint buy recall the bare model lacks. It does not: 42/42 both arms. |
| `ablate_queries.py` | C→D | 18 | Controlled ablation: remove one fact, keep the prose natural, measure what the gap costs. Produces the 78 clean ablations everything else replays. |
| `score_ablations.py` | C→D | 16, 18 | Scores those ablations per output tier. |
| `default_direction_sweep.py` | D | 23 | Every candidate default for every factor, in both directions, over the full space of the other four. No model. |
| `default_candidates_output.py` | D | 23 | The same question priced on real VEP output rather than on the option list. |
| `class_weighted_f1.py` | D | 20 | Scores a recommendation by what each error *does* to the output, not by counting options. |
| `singlepass_vs_twopass.py` | D | 20 | Does removing the second model call change what the user receives. 31 rows, both paths. |
| `pass_and_corpus_ablation.py` | D | 20 | Single vs two-pass crossed with which corpus the second pass sees. Four arms. |
| `full_eval_singlepass.py` | D | — | Factor accuracy, species model-vs-rule, and end-to-end F1 in one sweep. Its species arm is now historical: the model's answer is no longer discarded. |
| `exp_output_loss.py` | D | 16 | What a dropped option costs in VEP's own output, via the REST proxy. |
| `run_vep_rest.py` | D | 16 | Runs a recommended configuration through real VEP and checks the output. |
| `run_vep_ab.py` | D | 16 | A/B two configurations through real VEP — columns and rows. |
| `local_option_sweep.py` | D | — | What each option does to a real VEP result, one at a time, on a local install. Reaches the four row-deleting options REST silently ignores. |
| `checklist_matrix.py` | D | — | Lays the 219 existing cases out as a CheckList matrix (Ribeiro et al., ACL 2020): capability × test type. |
| `score_try_queries.py` | D | — | Scores the 20 hand-written sloppy-student scenarios on the tuple, after the assume policy. |
| `try_reprompting.py` | C→D | — | The assume/ask behaviour as a user meets it. `--why` adds the audit view. |
| `try_queries.sh` | D | — | Sloppy realistic queries for poking the system by hand. |
| `eval_factor_set.py` | C | 14, 15, 17, 19 | Factor-keyed leave-one-out on a generated set, scored against each row's own deterministic gold. The stage-C workhorse. |
| `measure_underspecification.py` | C | — | How often a real VEP question leaves a factor open, and whether it matters. |
| `fewshot_classifier.py` | C→D | — | Does few-shot help the factor classifier. 31-row LOO, tuples only. |
| `fetch_real_queries.py` | C | — | Fetches real VEP questions from Ensembl's issue trackers, verbatim and reproducibly. |
| `factor_traps.py` | D | 21 | The 24 keyword traps: the cue word is present and wrong. **Superseded by `factor_grid.py`** (24 freely-written pairs vs 150 balanced). |
| `factor_pairs.py` | D | 21 | The same 24 traps with the trap removed, scored as pairs. **Superseded by `factor_grid.py`.** |
| `_remote_guard.py` | — | — | Infrastructure. Import first in any GPU harness: refuses to run a model call against localhost. |

## Done — the reproduction record, not a live measurement

All stage-B, all on the 7-use-case taxonomy and the two-pass design, none re-run since 15 August.
They are kept because `EXPERIMENTS.md` cites them as how each number was produced.

| script | exp | what it produced |
|---|---|---|
| `run_parallel_eval.py` | 3, 10, 11 | The parallel leave-one-out driver behind the stage-B headline (26b + all-examples, 84% enable-F1). |
| `run_example_sweep.py` | 2 | Corpus-size sweep. Invalidated by the parser fix and never re-run on 26b. |
| `run_order_sensitivity.py` + `run_order_experiment.sh` | 9 | Example-order sensitivity: 10 orderings, mean ± SD. |
| `run_attribution.py` | 5, 6 | Per-recommendation KB-faithfulness. |
| `run_exp6.sh` · `run_exp6_seeds.sh` · `resume_attribution.sh` | 6 | Attribution decomposition, its seed replication, and the resume for the three runs that died on 2026-09-04. |
| `score_metrics.py` | 3 | Clinically-meaningful offline re-scoring from `results/raw/*.jsonl`. |
| `rescore_offline.py` | 7 | Offline re-score of the logged responses with the hardened code. |
| `reparse_bare_fix.py` | — | **The 2026-07-15 alias fix.** Re-parsed every logged run to quantify the `bare` correction that withdrew the Exp 1–3/10/11 baselines. |
| `compute_run_sd.py` | 10 | Run-level mean ± SD for the logged 26b eval. |
| `aggregate_results.py` | — | Cross-model crossover table from `evaluation_results_*.md`. |
| `structured_pilot.py` | 8 | Structured-output pilot. **Negative result**: the local 26b cannot reliably emit JSON, which is why `build_output_json.py` exists. |
| `run_experiment.sh` | — | Turnkey wrapper for the stage-B expanded-catalogue run. |
| `run_user_queries.py` | — | One-off: current model against a user-supplied query/expected-config set. |
| `show_tiered_output.py` | — | Prototype renderer for the **three-tier** output. Tiers merged 3 → 2 on 2026-08-19; kept as the record of what the third tier looked like. |
| `bench_latency.py` | — | Latency of the full stage-B path: prose → LLM → parser → checker. Superseded by `--latency-sample` in `factor_grid.py`. |
