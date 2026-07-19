#!/usr/bin/env python3
"""Stage 3 — natural-language query generation (the ONLY LLM-authored artifact).

Given a FIXED resolved config + factor tuple, a local same-family teacher writes the user's
natural-language query. The teacher NEVER sees or emits option ids — the config is deterministic from
the KB (defense-in-depth: LLM proposes NL only, code disposes of the config).

Teacher model: choose EMPIRICALLY via the ICE screen (Stage 5), not by size or a "self is best" assumption.
Xu et al. NAACL 2025 (arXiv 2411.07133): a larger same-family teacher is NOT reliably better ("Larger
Models' Paradox"). A 5-seed sweep (e4b/12b/26b/31b, student=26b, N=30) found all four teachers WITHIN NOISE
of each other (~80-88% ICE, overlapping error bars) — an earlier 3-seed pilot suggesting e4b-best /
self-generation-underperforms (72%) was small-sample noise and did not survive. So the --model default
stays gemma4:26b as its own teacher: simplest, and no evidence a teacher/student split helps.

Diversity comes from the query-axes grid (query_axes.json), sampled per row (seeded → reproducible).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/generation/generate_queries.py --in candidates/resolved.json --out candidates/queried.json \
         --model gemma4:26b --k 3 --seed 42 --concurrency 1
"""
import argparse
import json
import os
import random

import genlib

FACTOR_PROSE = {
    "species": {"human": "human", "non-human": "a non-human species (e.g. mouse, zebrafish)"},
    "origin": {"germline": "germline", "somatic": "somatic (tumour)"},
    "variant_size_class": {"small": "small variants (SNVs/indels)",
                           "structural-CNV": "structural variants / CNVs"},
    "region_focus": {"coding": "protein-coding regions",
                     "regulatory-noncoding": "regulatory / non-coding regions"},
    "analysis_goal": {"basic-consequence": "a quick top-line consequence call",
                      "clinical-interpretation": "clinical interpretation / pathogenicity",
                      "population-frequency": "population allele-frequency context"},
}


def _prose(factor_tuple):
    fl = factor_tuple
    region = " and ".join(FACTOR_PROSE["region_focus"][v] for v in fl["region_focus"])
    goal = " and ".join(FACTOR_PROSE["analysis_goal"][v] for v in fl["analysis_goal"])
    return (f"{FACTOR_PROSE['species'][fl['species']]}, {FACTOR_PROSE['origin'][fl['origin']]}, "
            f"{FACTOR_PROSE['variant_size_class'][fl['variant_size_class']]}; "
            f"focus on {region}; goal: {goal}")


def _sample_axes(query_axes, rng):
    cell = {}
    for axis, cats in query_axes["axes"].items():
        if axis.startswith("_"):
            continue
        names = [c["name"] for c in cats]
        weights = [c["probability"] for c in cats]
        pick = rng.choices(names, weights=weights, k=1)[0]
        cell[axis] = next(c for c in cats if c["name"] == pick)
    return cell


def _teacher_prompt(factor_tuple, cell, seed_queries):
    axes_desc = "\n".join(f"- {a}: {c['name']} ({c['description']})" for a, c in cell.items())
    seeds = "\n".join(f"- {q}" for q in seed_queries) if seed_queries else "(none)"
    return (
        "You write realistic questions that a researcher would ask an assistant about how to configure "
        "Ensembl VEP (Variant Effect Predictor) for their analysis.\n\n"
        f"Scenario to write a question for: {_prose(factor_tuple)}.\n\n"
        "Write the question in this style:\n" + axes_desc + "\n\n"
        "Rules:\n"
        "- State the species, sample/assay, variant type and analysis goal clearly enough that an expert "
        "could choose the right VEP settings.\n"
        "- Do NOT name VEP options, flags, plugins, or column names. Describe the biology and the goal.\n"
        "- One question only. No preamble, no explanation, no quotes.\n\n"
        "Examples of the target style (different scenarios):\n" + seeds
    )


def generate_for_row(row, client, ev, model, query_axes, seed_queries, k, temperature, base_seed, idx):
    rng = random.Random(base_seed + idx)
    cell = _sample_axes(query_axes, rng)
    prompt = _teacher_prompt(row["factor_labels"], cell, seed_queries)
    cands = []
    for j in range(k):
        text = ev.call_llm(client, model, prompt, "Write the question now.",
                           temperature=temperature, seed=base_seed + idx * 100 + j)
        one = " ".join(text.strip().split())            # collapse to a single clean line
        if one:
            cands.append(one)
    row = dict(row)
    row["user_query"] = cands[0] if cands else None
    row["_query_gen"] = {
        # 'seed' is the LLM seed of the EMITTED query (cands[0], j=0). Candidate j was generated
        # with seed base_seed + idx*100 + j; axes-cell sampling used a separate RNG (base_seed + idx).
        "teacher_model": model, "seed": base_seed + idx * 100, "temperature": temperature,
        "query_axes_cell": {a: c["name"] for a, c in cell.items()},
        "candidates": cands,
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--concurrency", type=int, default=1,
                    help="keep 1 for reproducibility on the Metal/MoE stack")
    args = ap.parse_args()

    from openai import OpenAI
    from concurrent.futures import ThreadPoolExecutor
    ev = genlib.load_evaluate()
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")

    rows = json.load(open(args.inp))
    corpus = genlib.load_corpus()
    seed_queries = [ex["user_query"] for ex in corpus[:2]]

    def work(i):
        return i, generate_for_row(rows[i], client, ev, args.model, genlib.load_query_axes(),
                                   seed_queries, args.k, args.temperature, args.seed, i)

    out = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for i, r in ex.map(lambda i: work(i), range(len(rows))):
            out[i] = r
            print(f"  [{i+1}/{len(rows)}] {r['factor_labels']['species']:9s} "
                  f"axes={r['_query_gen']['query_axes_cell']}\n      Q: {r['user_query']}")

    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {len(out)} queried candidates -> {args.out}")


if __name__ == "__main__":
    main()
