# D3 · one model call; the draft call is gone

Until 2026-09-14 the tool made two calls: the classifier, then a "draft" that wrote the configuration
as prose for a checker to repair. The checker rebuilds the RECOMMENDED set from the factor tuple
whatever the draft says, so the draft could only add options the table does not price. It was dropped.

| number | experiment | script | file |
|---|---|---|---|
| empty or hostile draft → the same 20 options; post-checker F1 0.985 either way | 2026-09-09 | — | `results/pass2_authority_2026-09-09/README.md` §1 (no JSON saved) |
| F1: single 0.898 ± 0.000 · two-pass 0.870 ± 0.002 · 0.866 · 0.855 (3 repeats, 26b) | Exp 20 | `pass_and_corpus_ablation.py` | `results/singlepass_2026-09-09/pass_corpus_ablation.json` + `results/overnight_2026-09-10/pass_corpus_ablation_26b_rep{2,3}.json` |
| class-weighted F1: single 0.942 vs 0.936 / 0.934 / 0.925 | Exp 20 | `class_weighted_f1.py` | computed from the file above at run time |
| e4b: 0.874 vs 0.834 / 0.826 / 0.803 | Exp 20 | `pass_and_corpus_ablation.py` | `results/overnight_2026-09-10/pass_corpus_ablation_e4b.json` |
| single ⊆ two on 31/31 rows; identical block 25/31; 17.9 s → 1.2 s | Exp 20 | `singlepass_vs_twopass.py` | `results/singlepass_vs_twopass.json` |
| re-run on the 2026-09-15 table: single 0.858 plain, 0.900 weighted; 0 row-deleting extras vs 5–7 | Exp 20 re-run | the same two scripts | `results/final_2026-09-15/` |

**Limits.**
- The 0.858 re-run defines F1 without the form's 16 ticked-by-default options, so it is a different
  number from 0.898, not a regression.
- `results/final_2026-09-15/` predates prompt v2, species-from-the-model and the plugin species lists
  (handover 2026-09-22 §5.6). Its latencies are not quotable: the GPU was contended overnight.
- `full_eval_singlepass.py` reproduces the pre-2026-09-16 tool (species from the keyword scan).
- `results/overnight_2026-09-10/` also holds D1 and D4 runs; their READMEs point here.
