#!/usr/bin/env python3
"""Stage 5 — ICE (In-Context Evaluation) usefulness screen.

A (query, config) pair can be correct yet UNHELPFUL as an in-context example. This screen holds out the
candidate, runs the STUDENT (gemma4:26b) over the approved corpus in the all-examples condition, and
scores priority-weighted CRITICAL-RECALL on the candidate: of the config's `critical` options, how many
does the student recover from the query alone? Critical-recall 0 on a non-minimal query is FLAGGED
(query too vague / config misaligned) — a screen for review, not an auto-reject.

Reuses the exact eval path (build_system_prompt / extract_recommendations) and honours the Metal/MoE
determinism rule: greedy (temp 0), fixed seed, concurrency 1. Also the empirical teacher selector —
run with --student set to each candidate Stage-3 teacher and compare ICE (do NOT assume a larger
sibling wins; Xu et al. NAACL 2025).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/generation/ice_screen.py --in candidates/filtered.json --out candidates/iced.json \
         --student gemma4:26b --seed 42
"""
import argparse
import json
import os

import genlib


def critical_options(row):
    return {k for k, v in row["recommended_options"].items()
            if v.get("enabled") and v.get("priority") == "critical"}


def is_minimal(row):
    """A deliberately minimal query (basic-consequence only) legitimately has ~no critical options."""
    return row["factor_labels"]["analysis_goal"] == ["basic-consequence"]


def ice_row(row, client, va, ev, catalogue, corpus, aliases, student, seed):
    q = row.get("user_query") or ""
    prompt = va.build_system_prompt(catalogue, corpus, q, retrieval_mode="all")
    resp = ev.call_llm(client, student, prompt, q, temperature=0.0, seed=seed)
    en, _ = va.extract_recommendations(resp, aliases)
    crit = critical_options(row)
    recall = (len(crit & set(en)) / len(crit)) if crit else None
    # Distinguish a degenerate/empty model generation (a robustness no-op) from a genuine
    # low-recall misalignment — both warrant review but mean different things to the mentor.
    degenerate = len(en) == 0
    flag = (recall == 0) and not is_minimal(row) and bool(crit)

    # CONTAMINATED: the query names a tool (Stage 4's query_names_tool gate). ICE asks "can the student
    # INFER the critical options from the scenario?" — if the query says "MANE Select transcripts", the
    # student can copy the answer out of the question and ICE scores reading comprehension instead. That
    # inflates the number we use to decide the row is useful, so refuse to score it rather than report a
    # flattered one. The row is not dropped; only its ICE is void.
    leaked = row.get("_query_leaks_tools") or []
    contaminated = bool(leaked) and bool(crit)

    row = dict(row)
    row["_ice"] = {
        "student": student, "seed": seed,
        "n_critical": len(crit), "critical_recovered": sorted(crit & set(en)),
        "critical_recall": None if contaminated else recall,
        "critical_recall_raw": recall,
        "model_enabled": len(en),
        "degenerate_generation": degenerate,
        "flag_low_usefulness": (flag and not degenerate) and not contaminated,
        "flag_degenerate": flag and degenerate,
        "void_query_names_tool": leaked or None,
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--student", default="gemma4:26b")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from openai import OpenAI
    va = genlib.load_va()
    ev = genlib.load_evaluate()
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    catalogue = genlib.load_catalogue()
    corpus = genlib.load_corpus()
    aliases = va.build_option_aliases(catalogue)
    rows = json.load(open(args.inp))

    out = []
    for i, row in enumerate(rows):          # concurrency 1 (determinism rule)
        r = ice_row(row, client, va, ev, catalogue, corpus, aliases, args.student, args.seed)
        out.append(r)
        ic = r["_ice"]
        rc = "n/a" if ic["critical_recall"] is None else f"{ic['critical_recall']:.0%}"
        tag = "FLAG-misalign" if ic["flag_low_usefulness"] else ("FLAG-degenerate" if ic["flag_degenerate"] else "")
        print(f"  [{i+1}/{len(rows)}] {r['id'][:44]:44s} crit={ic['n_critical']:2d} "
              f"recall={rc:>4s} {tag}")

    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    n_mis = sum(r["_ice"]["flag_low_usefulness"] for r in out)
    n_deg = sum(r["_ice"]["flag_degenerate"] for r in out)
    print(f"\nWrote {len(out)} ICE-screened rows -> {args.out}   "
          f"({n_mis} flagged misaligned, {n_deg} flagged degenerate generation)")


if __name__ == "__main__":
    main()
