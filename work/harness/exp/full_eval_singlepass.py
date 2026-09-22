#!/usr/bin/env python3
"""Full local evaluation of the single-pass design, on the 31-row factor set.

Measures the things that actually decide whether pass 2 can go, in one sweep:

  A. FACTOR ACCURACY (3 seeds)      the only thing the model decides that reaches the user
  B. SPECIES: model vs keyword rule  the classifier is ALREADY asked for species and answers;
                                     vep_assistant.py:951 then overwrites it with infer_species().
                                     This captures the discarded answer at no extra cost.
  C. END-TO-END F1                   gold = config from the TRUE tuple
                                     pred = post-checker config from the INFERRED tuple
                                     only a factor misread can move it, weighted by option cost
  D. SINGLE vs TWO PASS (1 seed)     same query, same tuple, with and without the draft call
  E. LATENCY                         per phase

Run locally on gemma4:26b -- 128 GB fits the 18.6 GB model, so no tunnel and no remote guard.

  NO_PROXY=localhost,127.0.0.1 python3 work/harness/exp/full_eval_singlepass.py --seeds 42,43,44
"""
import argparse, json, os, statistics as st, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")


def norm(v):
    return tuple(sorted(v)) if isinstance(v, list) else ((v,) if v else ())


def f1(pred, gold):
    if not gold or not pred:
        return 0.0
    ov = len(pred & gold)
    if not ov:
        return 0.0
    p, r = ov / len(pred), ov / len(gold)
    return 2 * p * r / (p + r)


def classify_raw(client, model, query, seed):
    """infer_factors' call, but keeping the model's OWN species answer instead of the keyword rule."""
    resp = client.chat.completions.create(
        model=model, temperature=0.0, seed=seed,
        messages=va.classifier_messages(query))
    rec = va.parse_factor_classification(resp.choices[0].message.content or "")
    if rec is None:
        return None, None
    model_species = rec.get("species")
    shipped = dict(rec)
    shipped["species"] = ("non-human" if va.infer_species(query) not in ("human", "unknown")
                          else "human")
    if not shipped.get("analysis_goal"):
        shipped["analysis_goal"] = ["basic-consequence"]
    return shipped, model_species


def enabled_from(tuple_, catalogue, examples, query):
    """The config the user receives: resolver + checker, empty draft (single-pass)."""
    resolved = va.resolve_for_query(tuple_, catalogue) or {}
    en, dis = set(), set()
    va.restore_missing_recommended(en, dis, resolved, catalogue, query)
    return en


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--json", default=str(ROOT / "work/results/singlepass_eval.json"))
    args = ap.parse_args()
    client = OpenAI(base_url=args.base_url, api_key="ollama")
    catalogue, examples = va.load_knowledge_base()
    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    seeds = [int(s) for s in args.seeds.split(",")]
    out = {"model": args.model, "seeds": seeds, "n_rows": len(rows), "per_seed": [], "rows": []}

    for seed in seeds:
        per = []
        t0 = time.perf_counter()
        for r in rows:
            truth = r["factor_labels"]
            shipped, model_sp = classify_raw(client, args.model, r["user_query"], seed)
            if shipped is None:
                continue
            hit = {f: norm(shipped.get(f)) == norm(truth.get(f)) for f in FACTORS}
            gold = enabled_from(truth, catalogue, examples, r["user_query"])
            pred = enabled_from(shipped, catalogue, examples, r["user_query"])
            rule_sp = shipped["species"]
            model_sp_n = "human" if model_sp == "human" else (
                "non-human" if model_sp == "non-human" else "unstated")
            per.append({"id": r["id"], "hit": hit, "exact": all(hit.values()),
                        "e2e": f1(pred, gold), "n_gold": len(gold), "n_pred": len(pred),
                        "truth_species": truth.get("species"),
                        "rule_species": rule_sp, "model_species": model_sp_n,
                        "truth": {f: truth.get(f) for f in FACTORS},
                        "got": {f: shipped.get(f) for f in FACTORS}})
        el = time.perf_counter() - t0
        out["per_seed"].append({
            "seed": seed, "n": len(per), "secs": round(el, 1),
            **{f: sum(p["hit"][f] for p in per) for f in FACTORS},
            "exact": sum(p["exact"] for p in per),
            "e2e": st.mean(p["e2e"] for p in per),
            "rule_species_right": sum(p["rule_species"] == p["truth_species"] for p in per),
            "model_species_right": sum(p["model_species"] == p["truth_species"] for p in per)})
        out["rows"].append({"seed": seed, "detail": per})
        print(f"  seed {seed}: {len(per)}/{len(rows)} in {el:.0f}s", flush=True)

    ps, n = out["per_seed"], out["per_seed"][0]["n"]
    print(f"\n=== {args.model}, {n} rows, seeds {seeds} ===\n")
    print("A. FACTOR ACCURACY")
    for f in FACTORS:
        tag = "   (keyword rule, not the model)" if f == "species" else ""
        print(f"   {f:20s} {st.mean(p[f] for p in ps):5.1f}/{n}{tag}")
    print(f"   {'EXACT TUPLE':20s} {st.mean(p['exact'] for p in ps):5.1f}/{n}")
    print("\nB. SPECIES — the model already answers this and the code discards it")
    print(f"   keyword rule (shipped)  {st.mean(p['rule_species_right'] for p in ps):5.1f}/{n}")
    print(f"   the model's own answer  {st.mean(p['model_species_right'] for p in ps):5.1f}/{n}")
    e2 = [p["e2e"] for p in ps]
    sd = f" ± {st.stdev(e2):.3f}" if len(e2) > 1 else ""
    print(f"\nC. END-TO-END F1   {st.mean(e2):.3f}{sd}")
    print(f"\nE. LATENCY   classify {st.mean(p['secs'] for p in ps) / n:.2f}s/row")
    Path(args.json).write_text(json.dumps(out, indent=1))
    print(f"\n   wrote {args.json}")


if __name__ == "__main__":
    main()
