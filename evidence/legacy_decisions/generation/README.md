# D9 · how the 31 review scenarios were generated

The 31 scenarios every figure is scored on ([`../../../data/iced.json`](../../../data/iced.json)) came from
the pipeline in [`../../../pipeline/`](../../../pipeline/): code picks a factor combination and resolves its
configuration, then a model writes only the query. Two choices in that pipeline rest on experiments here.

| decision | number | script | file |
|---|---|---|---|
| `gemma4:26b` writes its own queries | four teachers (e4b, 12b, 26b, 31b) within noise over 5 seeds, N=30; 26b kept | `teacher_sweep.py` | `results/teacher_sweep_5seed_n30.json`, log `results/_seedfix.log` |
| the persona axis stays in `query_axes.json` | it adds no measurable diversity over 5 seeds; kept for realism of who is asking | `persona_ablation.py` | `results/persona_ablation.json` |

**Limits.** Both ran in stage B (2026-07). The persona run's usefulness arm is confounded (it handles
degenerate zero scores differently from the teacher sweep). Both scripts import the pipeline, which imports
`evaluate`; that import has failed since `evaluate.py` moved to `vep_ai_demo/legacy/` on 2026-09-22.
`_seedfix.log` also holds the persona run's log.
