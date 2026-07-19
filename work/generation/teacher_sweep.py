#!/usr/bin/env python3
"""Teacher-model SELECTION sweep — find the best query-writing teacher for the deployed gemma4:26b student.

NOT a size study. Pure model selection: fix the student, vary the teacher, hold configs/tuples/axes fixed
per seed (the SAME prompt per row goes to every teacher — only the teacher model differs), and pick the
teacher whose queries the student best acts on.

MULTI-SEED (>=3, mean±SD) per the project's experiment discipline — a single seed on this small,
critical-set-only ICE sample is noise. Degenerate (empty) student generations are EXCLUDED from the ICE
recall mean (they measure student robustness, not teacher query quality) and reported separately.

Metric of record = mean ICE critical-recall across seeds (mean±SD). Guardrail = query diversity
(distinct-2 n-grams + mean pairwise BGE cosine; lower cosine = more diverse).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json PYTHONHASHSEED=0 \
  python work/generation/teacher_sweep.py \
      --teachers gemma4:e4b,gemma4:12b,gemma4:26b,gemma4:31b --student gemma4:26b \
      --n 16 --seeds 42,43,44 --out candidates/teacher_sweep.json
"""
import argparse
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
from persona_ablation import diversity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teachers", default="gemma4:e4b,gemma4:12b,gemma4:26b,gemma4:31b")
    ap.add_argument("--student", default="gemma4:26b")
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--out", default="candidates/teacher_sweep.json")
    args = ap.parse_args()
    teachers = [t.strip() for t in args.teachers.split(",")]
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

    # per teacher: list of per-seed ICE means, pooled recalls, degenerate count, diversity per seed
    agg = {T: {"seed_ice": [], "pooled_recalls": [], "degenerate": 0, "d2": [], "cos": []} for T in teachers}

    for seed in seeds:
        tuples, _ = sf.sample(args.n, factors, seed=seed)
        rows = [rc.resolve_row(t, cat, pbf, factors, va, corpus) for t in tuples]
        prompts = [gq._teacher_prompt(r["factor_labels"],
                                      gq._sample_axes(axes, random.Random(seed + i)), seed_queries)
                   for i, r in enumerate(rows)]
        for T in teachers:
            qrows = []
            for i, (row, prompt) in enumerate(zip(rows, prompts)):
                text = ev.call_llm(client, T, prompt, "Write the question now.",
                                   temperature=0.8, seed=seed + i)
                r = dict(row)
                r["user_query"] = " ".join(text.strip().split())
                qrows.append(r)
                print(f"  [seed {seed}][{T}] gen {i + 1}/{len(rows)}", file=sys.stderr)
            div = diversity([r["user_query"] for r in qrows], va)
            iced = [ice.ice_row(r, client, va, ev, cat, corpus, aliases, args.student, seed) for r in qrows]
            # exclude degenerate (empty) generations from the recall mean
            recalls = [x["_ice"]["critical_recall"] for x in iced
                       if x["_ice"]["critical_recall"] is not None and not x["_ice"]["degenerate_generation"]]
            agg[T]["pooled_recalls"] += recalls
            agg[T]["seed_ice"].append((sum(recalls) / len(recalls)) if recalls else None)
            agg[T]["degenerate"] += sum(x["_ice"]["degenerate_generation"] for x in iced)
            agg[T]["d2"].append(div["distinct2"])
            agg[T]["cos"].append(div["mean_pairwise_cos"])
            m = agg[T]["seed_ice"][-1]
            print(f"    -> [seed {seed}][{T}] ICE={m:.0%} (rows={len(recalls)})" if m is not None
                  else f"    -> [seed {seed}][{T}] ICE n/a", file=sys.stderr)

    report = {"experiment": "teacher-selection-sweep", "student": args.student,
              "n": args.n, "seeds": seeds, "teachers": {}}
    print(f"\n{'teacher':14s} {'ICE mean±SD':>14s} {'pooled_n':>9s} {'degen':>6s} {'distinct2':>10s} {'cos':>7s}")
    print("-" * 66)
    for T in teachers:
        d = agg[T]
        sm = [m for m in d["seed_ice"] if m is not None]
        mean_ice = statistics.mean(sm) if sm else None
        sd_ice = statistics.stdev(sm) if len(sm) > 1 else 0.0
        d2 = statistics.mean(d["d2"]) if d["d2"] else None
        cos = statistics.mean(d["cos"]) if d["cos"] else None
        report["teachers"][T] = {"ice_mean": mean_ice, "ice_sd": sd_ice, "per_seed_ice": d["seed_ice"],
                                 "pooled_n": len(d["pooled_recalls"]), "degenerate": d["degenerate"],
                                 "distinct2_mean": d2, "pairwise_cos_mean": cos}
        ice_str = f"{mean_ice:.0%} ± {sd_ice:.0%}" if mean_ice is not None else "n/a"
        print(f"{T:14s} {ice_str:>14s} {len(d['pooled_recalls']):>9d} {d['degenerate']:>6d} "
              f"{d2:>10.3f} {cos:>7.3f}")

    scored = {T: d["ice_mean"] for T, d in report["teachers"].items() if d["ice_mean"] is not None}
    if scored:
        best = max(scored, key=scored.get)
        report["best_by_ice"] = best
        print(f"\nBest by ICE: {best} ({scored[best]:.0%}). Guardrail — check its pairwise_cos isn't the "
              f"worst (highest); and read alongside SD + degenerate count before switching off self-gen.")

    out = genlib.GEN_DIR / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(out, "w"), indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
