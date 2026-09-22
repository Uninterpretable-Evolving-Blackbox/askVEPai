#!/usr/bin/env python3
"""Keyword rules versus the classifier, per factor. 31 rows + the 124 factor-removed rewrites.

WHY. `species` is the one factor read by a keyword rule; the other four are read by the model. The
question is whether that split is justified: would a rule per factor do as well (then the model call
is unnecessary), or does the model add judgement a rule cannot (then the species rule is the odd one
out and should become a hint, as VEP_SPECIES_HINT already does)?

THREE ARMS, same truth, same rows.
  rule      a keyword scan per factor, built from the classifier prompt's own guidance words plus the
            obvious synonyms. First-match, word-bounded, negation-blind -- the same shape as
            `infer_species`, deliberately.
  model     `FACTOR_CLASSIFIER_PROMPT` + query, parsed by `parse_factor_classification`. The shipped
            path for the four non-species factors.
  hinted    the model, with the rule's matches appended as HINTS it may reject -- the species-hint
            design applied to every factor.

TWO SETS.
  31 rows   `iced.json`; truth = `factor_labels`. Every row states every factor, so this is the
            easy case and an upper bound.
  124       `ablated_queries.json`; one factor's cue rewritten out of each row. Truth for the
            removed factor is "unstated" ([] for a multi) on the 78 PURE rows; the other factors keep
            the row's labels. Only pure rows are scored on the removed factor; every row is scored on
            the untouched factors. This is the case that matters: a rule cannot say "unstated" for a
            value it has no keyword for, and a model that hallucinates a value is scored wrong.

  NO_PROXY=localhost,127.0.0.1 python3 work/harness/exp/rules_vs_model.py [--model gemma4:26b] [--seed 42]
"""
import argparse, json, os, re, statistics as st, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

FACTORS = ("origin", "variant_size_class", "region_focus", "analysis_goal")
MULTI = set(va.MULTI_FACTORS)

# Word-bounded, lower-cased. Built from the prompt's guidance line for each factor, plus synonyms a
# person writing the rule on day one would add. Not tuned on the rows.
RULES = {
    "origin": {
        "somatic": ["somatic", "tumour", "tumor", "cancer", "carcinoma", "oncolog\\w*", "malignan\\w*",
                    "metasta\\w*", "leukaemia", "leukemia", "lymphoma", "melanoma", "glioma",
                    "sarcoma", "neoplas\\w*", "tumou?r-normal", "matched normal", "cosmic"],
        "germline": ["germline", "inherited", "constitutional", "hereditary", "rare disease",
                     "rare-disease", "mendelian", "proband", "trio", "de novo", "family",
                     "familial", "healthy", "carrier", "congenital", "paediatric", "pediatric",
                     "cohort", "population"],
    },
    "variant_size_class": {
        "structural-CNV": ["structural variant\\w*", "\\bsvs?\\b", "cnvs?", "copy.number", "large deletion\\w*",
                           "large duplication\\w*", "deletions?", "duplications?", "inversions?",
                           "translocations?", "\\bdels?\\b", "\\bdups?\\b", "breakpoint\\w*",
                           "long.read", "manta", "delly", "lumpy", "cnvkit", "aneuploid\\w*"],
        "small": ["snvs?", "snps?", "indels?", "point mutation\\w*", "single.nucleotide", "substitution\\w*",
                  "missense", "nonsense", "frameshift", "small variant\\w*", "short variant\\w*",
                  "exome", "\\bwes\\b", "panel", "rs\\d+"],
    },
    "region_focus": {
        "coding": ["coding", "protein.coding", "missense", "exon\\w*", "exome", "\\bwes\\b", "amino.acid",
                   "protein.altering", "synonymous", "nonsense", "frameshift", "\\bcds\\b",
                   "loss.of.function", "\\blof\\b", "truncat\\w*"],
        "regulatory-noncoding": ["regulatory", "non.coding", "noncoding", "enhancer\\w*", "promoter\\w*",
                                 "intron\\w*", "intergenic", "\\butrs?\\b", "splice\\w*", "\\bwgs\\b",
                                 "whole.genome", "\\btfbs\\b", "transcription factor binding",
                                 "chromatin", "\\bgwas\\b", "eqtl\\w*"],
    },
    "analysis_goal": {
        "clinical-interpretation": ["pathogenic\\w*", "clinical\\w*", "diagnos\\w*", "patient\\w*", "disease\\w*",
                                    "disorder\\w*", "syndrome\\w*", "phenotype\\w*", "acmg", "clinvar",
                                    "variant of uncertain", "\\bvus\\b", "prioriti[sz]\\w*",
                                    "causal", "deleterious", "damaging", "therap\\w*", "actionab\\w*"],
        "population-frequency": ["allele frequenc\\w*", "frequenc\\w*", "\\bmaf\\b", "gnomad",
                                 "1000 genomes", "topmed", "exac", "\\baf\\b", "common variant\\w*",
                                 "rare variant\\w*", "population\\w*"],
        "basic-consequence": ["consequence\\w*", "annotat\\w*", "what (?:are|do) these", "quick",
                              "basic", "functional impact", "effect of", "which gene", "transcript\\w*"],
    },
}


def rule_read(query):
    q = query.lower()
    out = {}
    for f in FACTORS:
        hits = []
        for value, pats in RULES[f].items():
            words = [p for p in pats if re.search(r"(?<![\w-])" + p + r"(?![\w-])", q)]
            if words:
                hits.append((value, words))
        if f in MULTI:
            vals = [v for v, _ in hits]
            # basic-consequence is subsumed by any other goal in the priority table, and the prompt
            # says to use it only when nothing else is framed; the rule mirrors that.
            if f == "analysis_goal" and len(vals) > 1 and "basic-consequence" in vals:
                vals = [v for v in vals if v != "basic-consequence"]
            out[f] = vals
        else:
            out[f] = hits[0][0] if len(hits) == 1 else ("unstated" if not hits else
                                                        max(hits, key=lambda h: len(h[1]))[0])
        out[f + "__hits"] = {v: w for v, w in hits}
    return out


def hint_block(rr):
    lines = ["\n\nA keyword scan of the question matched these cue words. They are HINTS, not the "
             "answer: a match is often idiomatic, negated, or about something other than the "
             "user's own data. Judge from the whole question and reject a hint that does not fit."]
    any_hit = False
    for f in FACTORS:
        hits = rr[f + "__hits"]
        if hits:
            any_hit = True
            lines.append(f"  - {f}: " + "; ".join(f"{v} <- {', '.join(w)}" for v, w in hits.items()))
    return "\n".join(lines) if any_hit else ""


def model_read(client, model, query, seed, hint=""):
    resp = client.chat.completions.create(
        model=model, temperature=0.0, seed=seed, max_tokens=va._CLASSIFY_MAX_TOKENS,
        messages=va.classifier_messages(query, hint),
        extra_body={"keep_alive": va.KEEP_ALIVE, "think": False})
    return va.parse_factor_classification(resp.choices[0].message.content or "")


def norm(v):
    if isinstance(v, list):
        return tuple(sorted(v))
    return (v,) if v and v != "unstated" else ()


def score(read, truth, factors):
    return {f: norm(read.get(f)) == norm(truth.get(f)) for f in factors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--json", default=str(ROOT / "work/results/rules_vs_model.json"))
    ap.add_argument("--limit", type=int, default=0, help="smoke: first N of each set")
    args = ap.parse_args()
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")

    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    abl = json.load(open(ROOT / "work/preliminary_examples/ablated_queries.json"))
    abl = [a for a in abl if a["outcome"] != "rewrite failed"]
    if args.limit:
        rows, abl = rows[:args.limit], abl[:args.limit]

    ARMS = ("rule", "model", "hinted")
    out = {"model": args.model, "seed": args.seed, "sets": {}}

    # ---- set 1: the 31 rows, every factor stated ----
    t = time.perf_counter()
    rec = []
    for r in rows:
        truth = r["factor_labels"]
        rr = rule_read(r["user_query"])
        reads = {"rule": rr,
                 "model": model_read(client, args.model, r["user_query"], args.seed),
                 "hinted": model_read(client, args.model, r["user_query"], args.seed, hint_block(rr))}
        rec.append({"id": r["id"], "truth": {f: truth[f] for f in FACTORS},
                    "reads": {a: {f: reads[a].get(f) for f in FACTORS} for a in ARMS},
                    "hits": {f: rr[f + "__hits"] for f in FACTORS},
                    "score": {a: score(reads[a], truth, FACTORS) for a in ARMS}})
    out["sets"]["rows31"] = {"n": len(rec), "secs": round(time.perf_counter() - t, 1), "rows": rec}
    print(f"rows31: {len(rec)} in {time.perf_counter() - t:.0f}s", flush=True)

    # ---- set 2: the ablated rewrites ----
    t = time.perf_counter()
    rec2 = []
    for a in abl:
        tgt = a["target"]
        truth = dict(a["truth"])
        if a["pure"]:
            truth[tgt] = [] if tgt in MULTI else "unstated"
        rr = rule_read(a["ablated"])
        reads = {"rule": rr,
                 "model": model_read(client, args.model, a["ablated"], args.seed),
                 "hinted": model_read(client, args.model, a["ablated"], args.seed, hint_block(rr))}
        untouched = [f for f in FACTORS if f != tgt]
        sc = {arm: score(reads[arm], truth, untouched) for arm in ARMS}
        if a["pure"]:
            for arm in ARMS:
                sc[arm][tgt] = norm(reads[arm].get(tgt)) == ()      # must say unstated
        rec2.append({"row": a["row"], "target": tgt, "pure": a["pure"], "outcome": a["outcome"],
                     "truth": {f: truth[f] for f in FACTORS},
                     "reads": {arm: {f: reads[arm].get(f) for f in FACTORS} for arm in ARMS},
                     "score": sc})
    out["sets"]["ablated"] = {"n": len(rec2), "secs": round(time.perf_counter() - t, 1), "rows": rec2}
    print(f"ablated: {len(rec2)} in {time.perf_counter() - t:.0f}s", flush=True)
    Path(args.json).write_text(json.dumps(out, indent=1))

    # ---- report ----
    print(f"\n=== rules vs model vs hinted -- {args.model}, seed {args.seed} ===")
    print(f"\n31 rows (every factor stated) -- correct / {len(rec)}")
    print(f"  {'factor':22s}" + "".join(f"{a:>10s}" for a in ARMS))
    for f in FACTORS:
        print(f"  {f:22s}" + "".join(f"{sum(x['score'][a][f] for x in rec):10d}" for a in ARMS))
    print(f"  {'all four right':22s}" + "".join(
        f"{sum(all(x['score'][a].values()) for x in rec):10d}" for a in ARMS))

    print(f"\nablated rewrites -- the REMOVED factor, pure rows only: says 'unstated' / n")
    print(f"  {'removed factor':22s}" + "".join(f"{a:>10s}" for a in ARMS) + "      n")
    for f in FACTORS:
        pr = [x for x in rec2 if x["pure"] and x["target"] == f]
        print(f"  {f:22s}" + "".join(f"{sum(x['score'][a][f] for x in pr):10d}" for a in ARMS)
              + f"{len(pr):7d}")
    print(f"\nablated rewrites -- the UNTOUCHED factors, all {len(rec2)} rows: correct / n")
    print(f"  {'factor':22s}" + "".join(f"{a:>10s}" for a in ARMS) + "      n")
    for f in FACTORS:
        un = [x for x in rec2 if x["target"] != f]
        print(f"  {f:22s}" + "".join(f"{sum(x['score'][a][f] for x in un):10d}" for a in ARMS)
              + f"{len(un):7d}")
    print("\n  rule = keyword scan; model = shipped classifier prompt; hinted = model shown the scan's")
    print("  matches as rejectable hints. Truth for a removed factor is 'unstated'.")
    print(f"\n  wrote {args.json}")
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
