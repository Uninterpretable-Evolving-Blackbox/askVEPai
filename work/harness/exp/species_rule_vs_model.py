#!/usr/bin/env python3
"""Species: keyword rule vs the model's own answer vs the model with hints, on species-removed text.

WHY. `infer_species()` overrides the classifier's species answer (vep_assistant.py ~951). On the 31
review rows both score 31/31 because every row states its species, so that set cannot rank them.
The species ablations in `ablated_queries_rerun.json` can: 31 rows with the species cue rewritten
out, of which 14 are PURE (cue gone, no collateral). Exp 18 found the rule reads *human* on 11 of
those 14 -- it does not know it is guessing. This asks whether the model, or the model with the
scan's matches as rejectable hints (VEP_SPECIES_HINT design), knows any better.

ARMS
  rule     infer_species() -> human / unknown / <species>   (mapped to human / unstated / non-human)
  model    the classifier's own `species` field, which the shipped path discards
  hinted   the classifier with `format_species_hint()` appended (the 356-species index as hints)

TEXTS   every row twice: the ORIGINAL (species stated; truth = the row's label) and the ABLATED
        rewrite (truth = "unstated" on pure rows; reported per outcome class for the rest).

  NO_PROXY=localhost,127.0.0.1 python3 work/harness/exp/species_rule_vs_model.py [--model gemma4:26b]
"""
import argparse, json, os, statistics as st, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

ARMS = ("rule", "model", "hinted")


def rule_read(q):
    s = va.infer_species(q)
    return "human" if s == "human" else ("unstated" if s == "unknown" else "non-human")


def model_read(client, model, q, seed, hint):
    from openai import OpenAI                                           # noqa: F401
    resp = client.chat.completions.create(
        model=model, temperature=0.0, seed=seed, max_tokens=va._CLASSIFY_MAX_TOKENS,
        messages=va.classifier_messages(q, va.format_species_hint(q) if hint else ""),
        extra_body={"keep_alive": va.KEEP_ALIVE, "think": False})
    rec = va.parse_factor_classification(resp.choices[0].message.content or "")
    if rec is None:
        return "PARSE_FAIL"
    v = rec.get("species")
    return v if v in ("human", "non-human") else "unstated"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--file", default=str(ROOT / "work/preliminary_examples/ablated_queries_rerun.json"))
    ap.add_argument("--json", default=str(ROOT / "work/results/species_rule_vs_model.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rule-only", action="store_true", help="no model calls; structural check")
    args = ap.parse_args()
    idx = va.load_species_index()
    print(f"species index: {len(idx)} names", flush=True)

    rows = [x for x in json.load(open(args.file)) if x["target"] == "species"
            and x["outcome"] != "rewrite failed"]
    if args.limit:
        rows = rows[:args.limit]
    client = None
    if not args.rule_only:
        from openai import OpenAI
        client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                        api_key="ollama")

    t = time.perf_counter()
    rec = []
    for x in rows:
        truth = x["truth"]["species"]
        r = {"row": x["row"], "outcome": x["outcome"], "pure": x["pure"], "truth": truth,
             "hints_original": [h["name"] for h in va.species_candidates(x["original"])],
             "hints_ablated": [h["name"] for h in va.species_candidates(x["ablated"])]}
        for text in ("original", "ablated"):
            q = x[text]
            reads = {"rule": rule_read(q)}
            if client:
                reads["model"] = model_read(client, args.model, q, args.seed, False)
                reads["hinted"] = model_read(client, args.model, q, args.seed, True)
            r[text] = reads
        rec.append(r)
        print(f"  row {x['row']:2d} {x['outcome']:9s} truth={truth:9s} "
              f"orig={r['original']}  abl={r['ablated']}", flush=True)
    Path(args.json).write_text(json.dumps({"model": args.model, "seed": args.seed,
                                           "rows": rec}, indent=1))
    arms = [a for a in ARMS if all(a in r["original"] for r in rec)]

    print(f"\n=== species: rule vs model vs hinted -- {args.model}, seed {args.seed}, "
          f"{len(rec)} rows, {time.perf_counter() - t:.0f}s ===")
    print(f"\nORIGINAL text (species stated) -- correct / {len(rec)}")
    print("  " + "".join(f"{a:>10s}" for a in arms))
    print("  " + "".join(f"{sum(r['original'][a] == r['truth'] for r in rec):10d}" for a in arms))

    pure = [r for r in rec if r["pure"]]
    print(f"\nABLATED text, PURE rows (cue gone) -- n={len(pure)}")
    print(f"  {'says unstated (knows it does not know)':42s}"
          + "".join(f"{sum(r['ablated'][a] == 'unstated' for r in pure):10d}" for a in arms))
    print(f"  {'says human on a non-human row (masked)':42s}"
          + "".join(f"{sum(r['ablated'][a] == 'human' and r['truth'] == 'non-human' for r in pure):10d}"
                    for a in arms))
    print(f"  {'says non-human on a non-human row':42s}"
          + "".join(f"{sum(r['ablated'][a] == 'non-human' and r['truth'] == 'non-human' for r in pure):10d}"
                    for a in arms))
    print(f"  {'says human on a human row':42s}"
          + "".join(f"{sum(r['ablated'][a] == 'human' and r['truth'] == 'human' for r in pure):10d}"
                    for a in arms))
    for oc in ("redundant", "entangled"):
        sub = [r for r in rec if r["outcome"] == oc]
        if not sub:
            continue
        print(f"\nABLATED text, {oc.upper()} rows -- n={len(sub)}, answer distribution")
        for a in arms:
            print(f"  {a:8s} " + str(dict(Counter(r["ablated"][a] for r in sub))))
    print("\n  rule = infer_species (shipped, overrides the model); model = the classifier's own "
          "species field;\n  hinted = classifier shown the 356-species scan's matches as rejectable hints.")
    print(f"\n  wrote {args.json}")
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
