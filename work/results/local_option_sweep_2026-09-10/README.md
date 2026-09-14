# Local option sweep — 2026-09-10 (superseded)

Every catalogue option added one at a time on top of the web form's 16 defaults, on Ensembl's own
example VCF (173 human SNVs, chr21/22), local VEP 116.2, offline cache. Produced by
`harness/local_option_sweep.py`; `sweep.json` holds every arm.

**Read with two caveats.** The 25 plugin arms are VOID: VEP warns "Failed to compile plugin" and
exits 0, so their "+0 columns" means the plugin did not load, not that it does nothing. And every
percentage is input-dependent (this file is coding-heavy, all known SNVs), so the sweep establishes
direction, not magnitude. The record of what each option does is `research/output_effects_dossier.md`,
taken from Ensembl's documentation; this run's only irreplaceable finding is that `--check_frequency`
deletes nothing at its own default population on a release-116 cache (dossier §5).
