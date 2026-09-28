# `evidence/`

| folder | what it is |
|---|---|
| [**`current_evidence/`**](current_evidence/) | **the evidence for the system as it runs today: reasoning on/off, factor value inference, species-specific options, overall accuracy. Start here.** |
| [`legacy_decisions/`](legacy_decisions/) | legacy: experiments that led to today's design, many run on earlier versions. Their conclusions still hold |
| [`legacy_superseded/`](legacy_superseded/) | legacy: experiments whose conclusion was reversed, or whose subject no longer exists |

## Legacy · why it is built this way — [`legacy_decisions/`](legacy_decisions/)

Experiments and reviews whose conclusion the system still follows, one folder per decision. Some ran on an
earlier version of the system (the two-call design); their conclusion still holds, and each README says so.

| decision | folder | headline |
|---|---|---|
| D1 · `gemma4:26b`, local | [`model_choice/`](legacy_decisions/model_choice/) | 26b 88.0 enable-F1 vs e4b 80.3, e2b 66.7 (Exp 19) |
| D2 · five factors replace seven use cases | [`factor_scheme/`](legacy_decisions/factor_scheme/) | factor-priced prompt 69.9 → 88.0 (Exp 17) |
| D3 · one model call, no draft | [`single_pass/`](legacy_decisions/single_pass/) | single 0.898 vs two-pass 0.870 F1; 17.9 s → 1.2 s (Exp 20) |
| D4 · the model reads all five factors, species included | [`classifier/`](legacy_decisions/classifier/) | keyword rule 9/31 vs model 22/31; species traps model 29/30 vs scan 17/30 |
| D5 · a missing fact is assumed out loud or asked | [`missing_facts/`](legacy_decisions/missing_facts/) | the decided fallback reached and disclosed 76/78 (Exp 24) |
| D6 · per-species data from Ensembl's own lists | [`species_data/`](legacy_decisions/species_data/) | 7 plugin lists corrected from `plugin_config.txt` (Exp 25) |
| D7 · options judged by what they do to VEP's output | [`output_effects/`](legacy_decisions/output_effects/) | clinical → basic loses 19 output columns (Exp 16) |
| D8 · the priority table's tiers | [`priority_table/`](legacy_decisions/priority_table/) | the mentor's round-1 edits and round-2 answers, applied; the review sheets and their check are in the private working repository |
| D9 · how the 31 review scenarios are generated | [`generation/`](legacy_decisions/generation/) | 26b writes its own queries; four teachers within noise (Exp 12) |

## Legacy · what it replaced — [`legacy_superseded/`](legacy_superseded/)

Experiments whose conclusion was reversed or whose subject no longer exists: the seven use cases, the
attribution experiments, the 24 keyword traps (replaced by the grid above), the withdrawn silver set.

---

The full experiment ledger is `EXPERIMENTS.md` (private working repository) (Exp 1–25). Every run ever
made on the development machine sits in `local_runs/` (gitignored).
