# D2 · five factors replace the seven use cases

The configuration is priced by five factors (species, origin, variant size, region focus, analysis
goal) instead of one of seven hand-made use-case labels. The scheme itself is specified in
[`../../../docs/research/taxonomy_proposal.md`](../../../docs/research/taxonomy_proposal.md).

| number | experiment | script | file |
|---|---|---|---|
| enable-F1: unpriced prompt 69.9 → factor-priced from the classifier 88.0 ± 0.2 → from the true labels 89.0 | Exp 17, 2026-09-04, Colab L4 | `../model_choice/eval_factor_set.py --factors {none,inferred,oracle}` | `results/colab_2026-09-04/enable_f1_live_{none,inferred,oracle}.json`, `SUMMARY.json`, one log per arm |

So pricing the prompt by factor is worth about 18 points, and classifier mistakes cost about one.

**Limits.** Scored on the draft call (see D3) against the 31 review rows' own resolved configurations,
so it is self-consistency with a provisional table. The script needs the `evaluate` import fixed
(see `../model_choice/README.md`).
