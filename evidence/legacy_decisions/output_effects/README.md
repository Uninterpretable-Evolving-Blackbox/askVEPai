# D7 · an option is judged by what it does to VEP's output

A recommendation is scored by the columns and rows it changes in the user's file, from Ensembl's
documentation and from real VEP runs, not by counting option names. Options the form already ticks
are shown once under ALREADY ON; the rest are RECOMMENDED or OPTIONAL.

| number | experiment | script | file |
|---|---|---|---|
| going from clinical to basic loses 19 columns at cohort scale; population → basic loses 0 | Exp 16 (corrected 2026-09-07) | `run_vep_ab.py` | `results/output_axis_2026-09-07/ab_*.json` |
| all 17 checkable options deliver on a five-class variant panel | Exp 16 follow-up | `run_vep_rest.py` | `results/rest_sweep_panel.json` |
| what a dropped option costs in VEP's output | Exp 16 | `exp_output_loss.py` (`--cached` reads the original payload) | `results/rest_output_loss.json` (original table, corrected 2026-09-07) |
| each option's output fields and incompatibilities, from the release-116 pages | Exp 22 | `build_output_effects_dossier.py` (private working repository) | `output_effects_dossier.md` (private working repository) |
| `--check_frequency` at its default population deletes nothing on a 116 cache | Exp 22 | local VEP (`results/local_vep_2026-09-10/*.sh`) | `results/local_vep_2026-09-10/f_*.tsv` |
| every option one at a time on a local install | Exp 22 | `local_option_sweep.py` | `results/local_option_sweep_2026-09-10/sweep.json` |
| the restrict-results options delete rows (per_gene: 334 → 19) | leak rate, 2026-09-08 | — | `results/leak_rate_README.md`, `results/leak_rate_26b_seed42.json` |

**Limits.** The local sweep's percentages depend on the input VCF and its plugin rows are void (the
plugins never loaded); only its summary, baseline and frequency files are tracked. The other 86 files
(60 TSVs and 26 plugin warning logs) stay on the development machine in
`evidence/local_runs/results/local_option_sweep_2026-09-10/` (gitignored). The two `local_vep` shell
scripts point at a scratch path that no longer exists.
