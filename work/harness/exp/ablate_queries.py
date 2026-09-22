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

  python work/harness/exp/ablate_queries.py [--rows N] [--model gemma4:26b]
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "generation"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import genlib                                                            # noqa: E402
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

OUT = ROOT / "work" / "preliminary_examples" / "ablated_queries.json"
TARGETS = ("origin", "variant_size_class", "region_focus", "analysis_goal", "species")

# Phrased in the researcher's own vocabulary, never the scheme's: naming the factor would teach the
# rewriter the label we are about to test for, and naming an option would leak the answer entirely.
WHAT_TO_REMOVE = {
    "origin": "whether the variants are inherited/germline or arose in a tumour/somatic",
    "variant_size_class": "whether the variants are small changes (SNVs/indels) or large structural "
                          "changes (SVs/CNVs)",
    "region_focus": "whether the interest is in protein-coding regions or in regulatory/non-coding ones",
    "analysis_goal": "what the annotation is for — a quick consequence call, assessing disease "
                     "significance, or population frequencies",
    "species": "which organism the samples come from",
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


def rewrite(client, model, query, target, seed=42, temperature=0.0):
    """Native endpoint, reasoning OFF, streamed.

    Three layers of scar tissue, each earned:
    - think=False, because the compat endpoint DROPS the think parameter, so the model reasons by
      default -- and at temp 0 the reasoning phase loops on some prompts and returns EMPTY content
      (3 of 5 rewrites on row 1, 2026-09-07; the same pathology as the priced-prompt loop in
      work/results/thinking_arms_2026-09-06/). Exp 14: reasoning off costs nothing on this model.
    - streamed, because a cloudflared tunnel cuts any single request at ~100s and the client then
      retries the same too-slow call silently. Same seed, same temperature, same tokens.
    - empty retries vary the seed, exactly as evaluate.call_llm does and for its reason: at true
      temp-0 determinism, re-asking with the same seed re-fetches the same empty answer forever.
      First attempt uses the caller's seed, so a first-try success is bit-identical to before.
    """
    import urllib.request
    for attempt in range(3):
        this_seed = seed if attempt == 0 else seed + attempt * 1000
        body = {"model": model, "stream": True, "keep_alive": -1, "think": False,
                "messages": [{"role": "system",
                              "content": REWRITE.format(what=WHAT_TO_REMOVE[target], q=query)},
                             {"role": "user", "content": "Rewrite it."}],
                "options": {"num_predict": 2048, "temperature": temperature, "seed": this_seed}}
        req = urllib.request.Request(va._native_chat_url(), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        parts = []
        with urllib.request.urlopen(req, timeout=600) as r:
            for line in r:
                if line.strip():
                    parts.append(json.loads(line.decode()).get("message", {}).get("content") or "")
        text = "".join(parts).strip()
        if text:
            return text
    return ""                                             # counted as "rewrite empty" by build()


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
    # Species-PROPER words only, derived from the 31 rows' own text. Two exclusions are deliberate:
    # "cohort" appears in 9 rows across both truth values (it signals study design, not species), and
    # the _HUMAN_SIGNALS overlap words (germline/clinical/grch38/gnomad...) belong to OTHER factors —
    # a species rewrite must not remove those, so their survival is "redundant", not "rewrite failed".
    "species": ("human", "patient", "patients", "people", "person", "individuals", "pediatric",
                "paediatric", "mouse", "mice", "murine", "mus musculus", "zebrafish", "danio",
                "rerio", "rat ", "rats", "homo sapiens"),
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


def build(client, model, rows, seed, temperature):
    """One complete ablation set at one seed. Sequential by construction: the reproducibility note in
    `infer_factors` is that temp=0 is NOT reproducible under concurrency, so this must not be
    parallelised even though it is the slow part."""
    out, stats = [], Counter()
    for i, r in enumerate(rows, 1):
        original = r["user_query"]
        base_read = va.infer_factors(client, model, original, apply_defaults=False,
                                     seed=seed, temperature=temperature)
        for target in TARGETS:
            new_q = rewrite(client, model, original, target, seed=seed, temperature=temperature)
            # An empty rewrite must not reach the classifier: "" reads as every factor unstated, which
            # flags all four others as collateral and mislabels a generation failure as entanglement.
            if not new_q:
                stats["rewrite empty"] += 1
                print(f"  row {i:2d} \u2212{target:19s} rewrite EMPTY after 3 attempts", flush=True)
                continue
            read = va.infer_factors(client, model, new_q, apply_defaults=False,
                                    seed=seed, temperature=temperature)
            if read is None:
                stats["classifier failed"] += 1
                continue
            # SPECIES CANNOT USE is_empty: infer_factors line ~951 collapses it to human/non-human
            # unconditionally (unknown -> "human"), so rec["species"] is never empty and every species
            # ablation would be judged impure. Ask the underlying reader directly instead. The collapse
            # is also what makes score_ablations price these rows correctly with no change: read_after
            # says "human", which IS the guess under test.
            cue_left = cue_present(new_q, target)
            if target == "species":
                # ASYMMETRIC BY TRUTH, because infer_species is fail-closed. On a NON-HUMAN row,
                # deleting "mouse" leaves the human-signal words (tumour, clinical, germline...) and
                # infer_species reads "human" -- the wrong species, which is precisely the failure
                # under test, so it counts as removed (the explicit cue must also be gone, or a
                # rewrite that swapped "mouse" for "patients" would pass as pure). On a HUMAN row a
                # residual "human" reading is CORRECT inference from context -- genuinely redundant --
                # so only "unknown" proves the evidence gone. Consequence, stated up front: clean
                # species ablations come almost entirely from the 15 non-human rows.
                sp_after = va.infer_species(new_q)
                if r["factor_labels"]["species"] == "non-human":
                    removed = sp_after in ("unknown", "human") and not cue_left
                else:
                    removed = sp_after == "unknown"
            else:
                removed = is_empty(read, target)
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
            rec = {"species_read_before": va.infer_species(original),
                   "species_read_after": va.infer_species(new_q)} if target == "species" else {}
            out.append({**rec, "row": i, "target": target, "pure": pure, "outcome": outcome,
                        "cue_left_in_text": cue_left,
                        "target_removed": removed, "collateral": collateral,
                        "original": original, "ablated": new_q,
                        "read_before": base_read, "read_after": read,
                        "truth": r["factor_labels"]})
            print(f"  row {i:2d} −{target:19s} {outcome:14s} "
                  f"{('collateral:'+','.join(collateral)) if collateral else ''}", flush=True)
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=0)
    ap.add_argument("--model", default="gemma4:26b")
    # Three seeds, matching the factor-scheme LOO (`eval_factor_set.py --seeds 42,43,44`), so the two
    # measurements are quoted with the same rigour rather than one carrying a spread and the other a
    # single draw. Temperature stays at the 0.0 this experiment was designed around: at temp 0 a spread
    # across seeds is not sampling noise, it is the Metal/MoE non-determinism the classifier docstring
    # warns about, and finding out which we have is the point.
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--update-primary", action="store_true",
                    help="replace the committed ablated_queries.json with this run. Off by default: "
                         "the published figures are scored on that file.")
    a = ap.parse_args()

    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    partial = bool(a.rows)
    if partial:
        rows = rows[:a.rows]
    # Env-driven so a remote GPU (tunnel) is usable; hardcoded localhost once loaded 18.6 GB onto a
    # 17 GB laptop. See work/harness/_remote_guard.py.
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")
    seeds = [int(s) for s in a.seeds.split(",")]

    # A PARTIAL RUN MUST NEVER BECOME THE PRIMARY ARTEFACT. `--rows 1` is the natural way to smoke-test
    # a change to this script, and writing its 4 rows over ablated_queries.json would destroy the
    # 124-ablation dataset that the proposal, ask_rate.py and defaults_evidence.py all read.
    # Nor may a multi-seed run silently REPLACE the published set. `ablated_queries.json` is committed
    # and every figure in the proposal is scored on it, so a re-run that quietly swapped it would
    # change published numbers with no diff to notice. Default is to write beside it and compare;
    # --update-primary is the deliberate act of adopting a new set.
    if partial:
        base = OUT.with_name(f"{OUT.stem}_partial{a.rows}.json")
        print(f"  partial run ({a.rows} rows) — writing to {base.name}, NOT to {OUT.name}", flush=True)
    elif a.update_primary:
        base = OUT
        print(f"  --update-primary: {OUT.name} WILL be replaced", flush=True)
    else:
        base = OUT.with_name(f"{OUT.stem}_rerun.json")
        print(f"  writing to {base.name}; {OUT.name} is left alone. "
              f"Pass --update-primary to adopt this run.", flush=True)

    per_seed = []
    for seed in seeds:
        print(f"\n=== seed {seed} (temperature {a.temperature}) ===", flush=True)
        out, stats = build(client, a.model, rows, seed, a.temperature)
        n = len(out)
        clean = stats["pure"]
        per_seed.append({"seed": seed, "n": n, "clean": clean, "outcomes": dict(stats)})
        dest = base if seed == seeds[0] else base.with_name(f"{base.stem}_seed{seed}.json")
        json.dump(out, open(dest, "w"), indent=1)
        print(f"  seed {seed}: clean {clean}/{n} ({clean/max(1,n):.0%})  -> {dest.name}", flush=True)

    print(f"\n{'='*72}")
    counts = [s["clean"] for s in per_seed]
    mean = sum(counts) / len(counts)
    sd = (sum((c - mean) ** 2 for c in counts) / len(counts)) ** 0.5
    for s in per_seed:
        print(f"  seed {s['seed']}: clean {s['clean']}/{s['n']}  {s['outcomes']}")
    print(f"\n  clean ablations across {len(seeds)} seeds: {mean:.1f} ± {sd:.1f}"
          f"   (min {min(counts)}, max {max(counts)})")
    if sd == 0:
        print("  spread is ZERO — at temperature 0 this run was exactly reproducible across seeds,")
        print("  so the single-draw figure this experiment published was not an artefact of its seed.")
    else:
        print("  spread is NON-ZERO at temperature 0, which is the Metal/MoE non-determinism the")
        print("  classifier docstring warns about. Quote this number with its spread, not bare.")
    summary = base.with_name(f"{base.stem}_seed_summary.json")
    json.dump({"seeds": seeds, "temperature": a.temperature, "model": a.model,
               "per_seed": per_seed, "clean_mean": mean, "clean_sd": sd},
              open(summary, "w"), indent=1)
    print(f"  -> {base.relative_to(ROOT)}  (+ per-seed files, summary in {summary.name})")


if __name__ == "__main__":
    main()
