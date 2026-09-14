#!/usr/bin/env python3
"""Factor-tuple accuracy, and the end-to-end metric it implies.

WHY THIS EXISTS. Every published agreement figure scores the model's DRAFT configuration
(`eval_factor_set.py` parses `extract_recommendations` and stops there). The draft does not reach the
user: `restore_missing_recommended` reconstructs the RECOMMENDED set from the factor tuple, and it
does so whatever the model said. Verified three ways on 2026-09-09:

    empty draft            -> all 20 table-recommended options present
    draft = {"sift"}       -> all 20 present
    draft explicitly DISABLING sift/clinvar/mane -> all three still present

So on the RECOMMENDED set the model has no authority in either direction, and enable-F1 measures how
closely it guesses a table the resolver already knows. The only thing the model decides that survives
is the FACTOR TUPLE -- which selects the row of the priority table everything else follows from.

WHAT THIS MEASURES.
  per-factor accuracy   for each of the five factors, inferred == the row's own label
  exact-tuple accuracy  all five right at once
  end-to-end F1         gold  = config resolved from the row's TRUE tuple
                        pred  = post-checker config from the INFERRED tuple, empty draft
                        so the only thing that can move it is a factor misread, weighted by how many
                        options that misread costs. region_focus costs ~4.4 options, origin ~1.

WHY THE PREDICTION USES AN EMPTY DRAFT. Not a simplification -- it is the point. Scoring the
post-checker output of a REAL draft against the true-tuple gold gives 0.985 whether the draft is
empty or actively hostile, because the checker overwrites it. Feeding an empty draft isolates the
tuple, which is the only input that matters.

CAVEAT ON `species`. It is NOT classified by the model: `infer_factors` takes it from
`infer_species()`, a keyword rule. And all 31 rows state their species outright, so a perfect score
here measures the generator, not the rule -- see the 2026-09-08 adversarial probe, where the same
rule read "rabbit hole" as rabbit and "somatic ... zebra finch" as human.

  OLLAMA_BASE_URL=https://<tunnel>/v1 python work/harness/factor_accuracy.py [--seeds 42,43,44]
"""
import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
from _remote_guard import require_remote                                # noqa: E402
import vep_assistant as va                                              # noqa: E402

FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")
ROWS = ROOT / "work" / "generation" / "candidates" / "iced.json"


def norm(v):
    """Compare multi-select lists order-insensitively; treat None/[] as the empty tuple."""
    if isinstance(v, list):
        return tuple(sorted(v))
    return (v,) if v else ()


def f1(pred, gold):
    if not gold:
        return 0.0
    ov = len(pred & gold)
    if not ov:
        return 0.0
    p, r = ov / len(pred), ov / len(gold)
    return 2 * p * r / (p + r)


def score_row(client, model, row, catalogue, examples, seed):
    truth = row["factor_labels"]
    got = va.infer_factors(client, model, row["user_query"], apply_defaults=True,
                           seed=seed, temperature=0.0)
    if got is None:
        return None
    per = {f: norm(got.get(f)) == norm(truth.get(f)) for f in FACTORS}
    gold = {o for o, (e, _p, _g) in (va.resolve_for_query(truth, catalogue) or {}).items() if e}
    pred_resolved = va.resolve_for_query(got, catalogue) or {}
    enabled, disabled = set(), set()
    va.restore_missing_recommended(enabled, disabled, pred_resolved, catalogue, examples,
                                   row["user_query"])
    return {"id": row["id"], "per": per, "exact": all(per.values()),
            "e2e_f1": f1(enabled, gold), "n_gold": len(gold), "n_pred": len(enabled),
            "truth": {f: truth.get(f) for f in FACTORS},
            "got": {f: got.get(f) for f in FACTORS}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("VEP_MODEL", "gemma4:26b"))
    ap.add_argument("--seeds", default="42")
    ap.add_argument("--json", help="write per-row detail here")
    args = ap.parse_args()
    require_remote()
    from openai import OpenAI                                           # noqa: PLC0415
    client = OpenAI(base_url=os.environ["OLLAMA_BASE_URL"], api_key="ollama")

    catalogue, examples = va.load_knowledge_base()
    rows = json.load(open(ROWS))
    seeds = [int(s) for s in args.seeds.split(",")]
    per_seed, detail = [], []

    for seed in seeds:
        scored = [s for s in (score_row(client, args.model, r, catalogue, examples, seed)
                              for r in rows) if s]
        detail.append({"seed": seed, "rows": scored})
        n = len(scored)
        per_seed.append({"seed": seed, "n": n,
                         **{f: sum(s["per"][f] for s in scored) for f in FACTORS},
                         "exact": sum(s["exact"] for s in scored),
                         "e2e": st.mean(s["e2e_f1"] for s in scored)})
        print(f"seed {seed}: {n}/{len(rows)} classified", flush=True)

    print(f"\n{args.model}, {len(rows)}-row set, seeds {seeds}\n")
    print(f"  {'factor':22} {'correct':>18}")
    for f in FACTORS:
        vals = [p[f] for p in per_seed]
        note = "   <- keyword rule, not the model" if f == "species" else ""
        print(f"  {f:22} {st.mean(vals):8.1f}/{per_seed[0]['n']:<9}{note}")
    print(f"  {'EXACT TUPLE':22} {st.mean(p['exact'] for p in per_seed):8.1f}/{per_seed[0]['n']}")
    print(f"\n  end-to-end F1 (true-tuple gold vs post-checker config from the inferred tuple):")
    print(f"     {st.mean(p['e2e'] for p in per_seed):.3f}"
          + (f" ± {st.stdev(p['e2e'] for p in per_seed):.3f}" if len(seeds) > 1 else ""))
    print("\n  A factor can be wrong and cost nothing: `origin` moves exactly one option")
    print("  (`frequency`) and only on human population-frequency scenarios.")
    if args.json:
        Path(args.json).write_text(json.dumps(detail, indent=1))
        print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
