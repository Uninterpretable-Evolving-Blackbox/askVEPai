#!/usr/bin/env python3
"""Controlled ablation: remove one fact from a question, keep the prose natural, measure what happens.

WHY THIS RATHER THAN COLLECTING REAL QUESTIONS. Two attempts to measure under-specification from the
wild failed for different reasons. Hand-transcribed forum posts turned out to be edited, in the direction
that flattered the conclusion. A scripted fetch from the issue trackers was honest but found that only
19% of issues are configuration questions at all, leaving n=8. Neither gives a controlled comparison.

Here the ground truth is constructed instead of found. Each of the 31 review queries states all five
factors by design, so exactly one can be removed and everything else held fixed — which is the
comparison the wild data cannot provide, because there the counterfactual is unobservable.

WHY REWRITE RATHER THAN MASK. The earlier probe deleted cue words, leaving text no human would write;
that measures how redundantly a fact is signalled, not what happens when it is absent, and a fluency
artifact is indistinguishable from the effect. A model rewrites the question instead, so the result reads
as something a person would actually ask, with the fact simply not mentioned.

PURITY IS CHECKED, NOT ASSUMED. A rewrite that quietly drops a second fact would contaminate the result.
Every ablation is re-read and kept only if the target factor became unstated AND the others survived
unchanged. Impure rewrites are counted and reported rather than silently dropped.

  python work/harness/ablate_queries.py [--rows N] [--model gemma4:26b]
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "generation"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import genlib                                                            # noqa: E402
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

OUT = ROOT / "work" / "preliminary_examples" / "ablated_queries.json"
TARGETS = ("origin", "variant_size_class", "region_focus", "analysis_goal")

# Phrased in the researcher's own vocabulary, never the scheme's: naming the factor would teach the
# rewriter the label we are about to test for, and naming an option would leak the answer entirely.
WHAT_TO_REMOVE = {
    "origin": "whether the variants are inherited/germline or arose in a tumour/somatic",
    "variant_size_class": "whether the variants are small changes (SNVs/indels) or large structural "
                          "changes (SVs/CNVs)",
    "region_focus": "whether the interest is in protein-coding regions or in regulatory/non-coding ones",
    "analysis_goal": "what the annotation is for — a quick consequence call, assessing disease "
                     "significance, or population frequencies",
}

REWRITE = (
    "Rewrite a researcher's question so that it no longer says anything about {what}.\n\n"
    "Rules:\n"
    "- Keep every other detail of the original exactly as it is.\n"
    "- The result must read naturally, as a question a researcher would actually write. Do not leave "
    "gaps, placeholders, or obviously deleted clauses.\n"
    "- Do not replace the removed detail with a different one, and do not hint at it.\n"
    "- Do not name any VEP option, flag or column.\n"
    "- Reply with the rewritten question only. No preamble, no quotes.\n\n"
    "Original question:\n{q}"
)


def rewrite(client, model, query, target):
    r = client.chat.completions.create(
        model=model, temperature=0.0, seed=42,
        messages=[{"role": "system", "content": REWRITE.format(what=WHAT_TO_REMOVE[target], q=query)},
                  {"role": "user", "content": "Rewrite it."}])
    return (r.choices[0].message.content or "").strip()


# Whether the ABLATED TEXT still contains an explicit cue for the factor. This separates two outcomes
# the first version conflated: a rewrite that failed to delete the words, and a rewrite that deleted them
# while the fact stayed inferable from surrounding context. Only the first is a broken ablation; the
# second is a result — the fact was over-determined, which is precisely what the old cue-masking probe
# could not distinguish, because deleting every cue also deletes the context a reader would use.
CUES = {
    "origin": ("germline", "somatic", "inherited", "constitutional", "tumour", "tumor", "cancer"),
    "variant_size_class": ("snv", "indel", "single letter", "single-letter", "point mutation", "spelling",
                           "structural", "cnv", "copy number", "deletion", "duplication", "large-scale"),
    "region_focus": ("coding", "protein", "exon", "missense", "regulatory", "non-coding", "noncoding",
                     "enhancer", "promoter", "intron", "intergenic", "gene control"),
    "analysis_goal": ("pathogenic", "clinical", "disease", "diagnos", "frequency", "frequencies",
                      "population", "quick", "top-line", "consequence"),
}


def cue_present(text, f):
    t = (text or "").lower()
    return any(c in t for c in CUES[f])


def same(a, b, f):
    x, y = a.get(f), b.get(f)
    return sorted(x) == sorted(y) if isinstance(x, list) and isinstance(y, list) else x == y


def is_empty(rec, f):
    v = rec.get(f)
    return (not v) if f in va.MULTI_FACTORS else (v in (None, "unstated"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=0)
    ap.add_argument("--model", default="gemma4:26b")
    a = ap.parse_args()

    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    if a.rows:
        rows = rows[:a.rows]
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    cat = genlib.load_catalogue(); pbf = genlib.load_priority_by_factor(); fc = genlib.load_factors()

    out, stats = [], Counter()
    for i, r in enumerate(rows, 1):
        original = r["user_query"]
        base_read = va.infer_factors(client, a.model, original, apply_defaults=False)
        for target in TARGETS:
            new_q = rewrite(client, a.model, original, target)
            read = va.infer_factors(client, a.model, new_q, apply_defaults=False)
            if read is None:
                stats["classifier failed"] += 1
                continue
            removed = is_empty(read, target)
            cue_left = cue_present(new_q, target)
            # everything else must survive: a factor that was readable before and is not now was
            # collateral damage, and the ablation is not clean
            collateral = [f for f in TARGETS
                          if f != target and not is_empty(base_read, f) and not same(base_read, read, f)]
            pure = removed and not collateral
            if pure:
                outcome = "pure"
            elif collateral:
                outcome = "entangled"
            elif cue_left:
                outcome = "rewrite failed"          # the words are still there
            else:
                outcome = "redundant"               # words gone, fact still inferable — a finding
            stats[outcome] += 1
            out.append({"row": i, "target": target, "pure": pure, "outcome": outcome,
                        "cue_left_in_text": cue_left,
                        "target_removed": removed, "collateral": collateral,
                        "original": original, "ablated": new_q,
                        "read_before": base_read, "read_after": read,
                        "truth": r["factor_labels"]})
            print(f"  row {i:2d} −{target:19s} {outcome:14s} "
                  f"{('collateral:'+','.join(collateral)) if collateral else ''}")
    json.dump(out, open(OUT, "w"), indent=1)
    n = len(out)
    print(f"\n{'='*72}")
    print(f"  {n} ablations attempted: {dict(stats)}")
    print(f"  usable (pure): {stats['pure']}/{n}  ({stats['pure']/max(1,n):.0%})")
    print(f"  -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
