#!/usr/bin/env python3
"""Experiment 13 — persona-axis ablation (does the persona query-axis change anything?).

One variable = persona on/off. The SAME sampled axes cell (phrasing/premise/terminology), the SAME
resolved configs, and the SAME seeds are held fixed — for the "nopersona" arm we simply drop the persona
line from the prompt for that identical cell — so ONLY persona differs (no RNG-shift confound).

Measures: query diversity (distinct-1/2/3 n-grams + mean pairwise BGE cosine; lower cosine = more
diverse) and ICE critical-recall. Prior (DataMorgana, Filice 2025): persona is marginal for diversity.

MULTI-SEED (>=3, mean±SD) per the project's experiment discipline; an earlier N=12 single-seed pilot was
DIRECTIONAL only. Each seed re-samples tuples + axes cell and
re-generates both arms, so the seed is a genuine replicate; per-condition metrics are aggregated mean±SD
across seeds. Determinism rule: concurrency 1, fixed seeds.

  VEP_OPTIONS_FILE=work/vep_options_expanded.json PYTHONHASHSEED=0 \
  python work/generation/persona_ablation.py --n 30 --model gemma4:26b --seeds 42,43,44,45,46
"""
import argparse
import itertools
import json
import os
import random
import statistics
import sys

import genlib
import resolve_config as rc
import sample_factors as sf
import generate_queries as gq
import ice_screen as ice


def diversity(queries, va):
    from sentence_transformers.util import cos_sim

    def distinct_n(n):
        grams = []
        for q in queries:
            t = q.lower().split()
            grams += [tuple(t[i:i + n]) for i in range(len(t) - n + 1)]
        return len(set(grams)) / len(grams) if grams else 0.0

    embs = va._get_semantic_model().encode(queries)
    sims = [float(cos_sim(embs[i], embs[j])[0][0])
            for i, j in itertools.combinations(range(len(queries)), 2)]
    return {"distinct1": distinct_n(1), "distinct2": distinct_n(2), "distinct3": distinct_n(3),
            "mean_pairwise_cos": sum(sims) / len(sims) if sims else 0.0}


def run_seed(seed, args, client, va, ev, cat, corpus, factors, pbf, axes, aliases, seed_queries):
    """One replicate: sample tuples + fixed axes cell at `seed`, generate persona/nopersona arms on the
    SAME configs+cell (one variable = persona), score diversity + ICE. Returns {cond: {diversity, ice_mean,
    n_ice, queries}}."""
    tuples, _ = sf.sample(args.n, factors, seed=seed)
    rows = [rc.resolve_row(t, cat, pbf, factors, va, corpus) for t in tuples]

    conds = {"persona": [], "nopersona": []}
    for idx, row in enumerate(rows):
        cell = gq._sample_axes(axes, random.Random(seed + idx))               # fixed cell for this row
        cell_np = {k: v for k, v in cell.items() if k != "persona"}           # same cell, persona removed
        for cond, use in [("persona", cell), ("nopersona", cell_np)]:
            prompt = gq._teacher_prompt(row["factor_labels"], use, seed_queries)
            text = ev.call_llm(client, args.model, prompt, "Write the question now.",
                               temperature=0.8, seed=seed + idx)
            r = dict(row)
            r["user_query"] = " ".join(text.strip().split())
            conds[cond].append(r)
        print(f"  [seed {seed}] gen {idx + 1}/{len(rows)}", file=sys.stderr)

    out = {}
    for cond, rws in conds.items():
        qs = [r["user_query"] for r in rws]
        div = diversity(qs, va)
        iced = [ice.ice_row(r, client, va, ev, cat, corpus, aliases, args.model, seed) for r in rws]
        recs = [x["_ice"]["critical_recall"] for x in iced if x["_ice"]["critical_recall"] is not None]
        out[cond] = {"diversity": div,
                     "ice_mean": (sum(recs) / len(recs)) if recs else None,
                     "n_ice": len(recs), "queries": qs}
        icem = out[cond]["ice_mean"]
        icestr = f"{icem:.0%}" if icem is not None else "n/a"
        print(f"  [seed {seed}][{cond:9s}] distinct2={div['distinct2']:.3f} "
              f"pairwise_cos={div['mean_pairwise_cos']:.3f} ICE={icestr} (n={out[cond]['n_ice']})",
              file=sys.stderr)
    return out


def _mean_sd(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None, None
    return statistics.mean(v), (statistics.stdev(v) if len(v) > 1 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seeds", default="42,43,44,45,46",
                    help="comma-separated seeds; each is a replicate (>=3 for a claim)")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]

    from openai import OpenAI
    va = genlib.load_va()
    ev = genlib.load_evaluate()
    cat = genlib.load_catalogue()
    corpus = genlib.load_corpus()
    factors = genlib.load_factors()
    pbf = genlib.load_priority_by_factor()
    axes = genlib.load_query_axes()
    aliases = va.build_option_aliases(cat)
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    seed_queries = [ex["user_query"] for ex in corpus[:2]]

    # per condition: collect each seed's diversity metrics + ICE mean, then aggregate mean±SD across seeds.
    per_seed = {s: run_seed(s, args, client, va, ev, cat, corpus, factors, pbf, axes, aliases, seed_queries)
                for s in seeds}

    report = {"experiment": "13-persona-ablation", "n": args.n, "model": args.model,
              "seeds": seeds, "conditions": {}}
    div_keys = ["distinct1", "distinct2", "distinct3", "mean_pairwise_cos"]
    for cond in ("persona", "nopersona"):
        agg = {}
        for k in div_keys:
            m, sd = _mean_sd([per_seed[s][cond]["diversity"][k] for s in seeds])
            agg[k] = m
            agg[k + "_sd"] = sd
        ice_m, ice_sd = _mean_sd([per_seed[s][cond]["ice_mean"] for s in seeds])
        agg["ice_mean_critical_recall"] = ice_m
        agg["ice_sd"] = ice_sd
        agg["ice_pooled_n"] = sum(per_seed[s][cond]["n_ice"] for s in seeds)
        agg["per_seed_ice"] = [per_seed[s][cond]["ice_mean"] for s in seeds]
        report["conditions"][cond] = agg

    p = report["conditions"]["persona"]
    n = report["conditions"]["nopersona"]
    print(f"\n{'condition':10s} {'distinct2 (mean±SD)':>22s} {'pairwise_cos':>16s} {'ICE (mean±SD)':>16s}")
    print("-" * 68)
    for cond, a in (("persona", p), ("nopersona", n)):
        ice_str = f"{a['ice_mean_critical_recall']:.0%} ± {a['ice_sd']:.0%}" if a["ice_mean_critical_recall"] is not None else "n/a"
        print(f"{cond:10s} {a['distinct2']:.3f} ± {a['distinct2_sd']:.3f}      "
              f"{a['mean_pairwise_cos']:.3f} ± {a['mean_pairwise_cos_sd']:.3f}   {ice_str:>16s}  "
              f"(pooled_n={a['ice_pooled_n']})")
    print(f"\nΔ (persona − nopersona): distinct2={p['distinct2'] - n['distinct2']:+.3f}  "
          f"pairwise_cos={p['mean_pairwise_cos'] - n['mean_pairwise_cos']:+.3f}  "
          f"(negative pairwise_cos Δ = persona adds diversity). Read against the per-condition SD.")

    out = genlib.GEN_DIR / "candidates" / "persona_ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(out, "w"), indent=2)
    print(f"wrote {out.relative_to(genlib.ROOT)}")


if __name__ == "__main__":
    main()
