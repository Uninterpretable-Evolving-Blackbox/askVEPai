#!/usr/bin/env python3
"""Minimal pairs for the 24 keyword traps: the same sentence with the trap taken OUT.

WHY. Every trap in `factor_traps.py` tests one direction -- a misleading cue is present and the answer
must NOT move. Passing tells you the model was not fooled; it does not tell you the model read
anything, because a model biased toward the safe answer passes too. Measured: a model that reads
nothing and always returns the majority value per factor scores 18 of the 24 traps. So 24/24 had six
cases genuinely at risk.

The pair is the trap with its trap removed, so the correct answer FLIPS:

    trap  "not a mouse study btw, its human"   -> human
    pair  "a mouse study, mouse reference"     -> non-human

On the pairs the safe answer is always WRONG, so the always-majority baseline scores near zero. Get
both members right and the model is reading. Get the trap right and the pair wrong and it was never
reading the cue, it was preferring a default.

This is the contrast-set construction of Gardner et al. (Findings of EMNLP 2020): a small edit that
changes the correct label, giving a local view of the decision boundary rather than a random sample.

SCORED IN PAIRS. The unit is the pair, not the sentence. `both` is the number that means something;
`trap only` is the column that exposes a model answering from a prior.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/legacy_superseded/keyword_traps/factor_pairs.py [--model gemma4:26b]
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "evidence" / "legacy_decisions" / "classifier"))  # rules_vs_model
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
import factor_traps as FT                                               # noqa: E402
from rules_vs_model import model_read, norm                             # noqa: E402

# One entry per trap, same order as factor_traps.CASES. Each is (flipped truth, the paired query).
# The edit is deliberately small: remove the negation, the disclaimer, the idiom or the wrong
# attachment, and let the cue mean what it looks like it means.
PAIRS = [
    # 1-7  origin
    ("somatic",  "Human exome from a tumour study; we are calling acquired coding SNVs in the cancer tissue."),
    ("somatic",  "Tumour samples from a cancer registry cohort, human exome SNVs, coding, just the consequences please."),
    ("somatic",  "Tumour-only BRCA1/2 sequencing from a breast cancer biopsy. Human, coding SNVs, pathogenicity."),
    ("somatic",  "We pulled this cohort straight out of COSMIC -- tumour samples, human, exome SNVs, basic consequences."),
    ("somatic",  "Tumour samples only -- the matched normal half was dropped from this batch. Human WES, coding, clinical interpretation."),
    ("germline", "De novo mutations in a rare-disease trio, inherited constitutional variants, human, coding SNVs, which are likely causal?"),
    ("somatic",  "Somatic mutations acquired in the tumour are exactly what I mean; these are not constitutional, human exome, clinical."),
    # 8-13 variant_size_class
    (["structural-CNV"], "Only CNVs and SVs were called on this human exome; no SNVs or indels, coding, clinical interpretation."),
    (["structural-CNV"], "Manta was run and we trust the output, so this is the SV callset from a human tumour, coding, clinical."),
    (["structural-CNV"], "A multi-exon duplication and a handful of whole-gene deletions from a human rare-disease cohort, coding, pathogenicity."),
    (["small"],          "Exome capture data, and we are only interested in single-base substitutions and short indels in a human germline cohort, clinical."),
    (["small"],          "Single-nucleotide substitutions and short indels for a human germline cohort, clinical interpretation."),
    (["structural-CNV"], "We dropped the indels and kept the structural variants; human somatic, coding, what do these do?"),
    # 14-18 region_focus
    (["regulatory-noncoding"], "Non-coding SNVs from a human WGS run -- we are ignoring everything inside exons. Germline, clinical."),
    (["regulatory-noncoding"], "Intronic and intergenic variants only, nothing protein-altering, human germline, clinical interpretation."),
    (["regulatory-noncoding"], "The data are human germline variants in gene promoters, whole genome, clinical."),
    (["regulatory-noncoding"], "Human somatic SNVs in enhancer elements, what are their consequences?"),
    (["coding"],               "Human germline variants in exons only -- no enhancers, no promoters, no intergenic interest -- want protein consequences."),
    # 19-24 analysis_goal
    (["population-frequency"],    "A population cohort of human donors, SNVs, I want the allele frequencies for these variants."),
    (["population-frequency"],    "How frequently do these human somatic SNVs occur in the general population? Give me the allele frequencies."),
    (["clinical-interpretation"], "This is a clinical question and diagnostic yield is the aim: human germline coding SNVs, are any pathogenic?"),
    (["clinical-interpretation"], "Pathogenicity is assessed by us here; human germline exome SNVs, coding, we need the pathogenicity evidence."),
    (["basic-consequence"],       "The patient cohort is small and no ACMG call is needed yet: human germline exome, coding SNVs, just what they hit."),
    (["clinical-interpretation"], "This is a clinical question -- I want pathogenicity evidence for these human germline coding SNVs, not frequencies."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--json", default=str(ROOT / "evidence/local_runs/results/factor_pairs.json"))
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",")]

    assert len(PAIRS) == len(FT.CASES), f"{len(PAIRS)} pairs for {len(FT.CASES)} traps"
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")

    # The always-majority baseline, computed from the TRAP truths -- the thing the pairs exist to expose.
    maj = {}
    for f in ("origin", "variant_size_class", "region_focus", "analysis_goal"):
        c = Counter(norm(t) for ff, t, _q, _w in FT.CASES if ff == f)
        maj[f] = c.most_common(1)[0][0]

    rows, tally = [], defaultdict(int)
    base = defaultdict(int)
    for (f, t_truth, t_q, why), (p_truth, p_q) in zip(FT.CASES, PAIRS):
        assert norm(p_truth) != norm(t_truth), f"pair does not flip: {why}"
        def read(q):
            outs = [(model_read(client, a.model, q, s) or {}).get(f) for s in seeds]
            return outs, all(norm(o) == o_ok for o, o_ok in
                             [(o, norm(p_truth if q == p_q else t_truth)) for o in outs])
        t_out, t_ok = read(t_q)
        p_out, p_ok = read(p_q)
        tally["trap_ok"] += t_ok; tally["pair_ok"] += p_ok
        tally["both"] += (t_ok and p_ok)
        tally["trap_only"] += (t_ok and not p_ok)
        tally["pair_only"] += (p_ok and not t_ok)
        tally["neither"] += (not t_ok and not p_ok)
        base["trap"] += (maj[f] == norm(t_truth)); base["pair"] += (maj[f] == norm(p_truth))
        mark = {(True, True): "both", (True, False): "TRAP ONLY", (False, True): "pair only",
                (False, False): "neither"}[(t_ok, p_ok)]
        print(f"  {f:20} {mark:10} {why}")
        rows.append({"factor": f, "why": why, "trap_query": t_q, "pair_query": p_q,
                     "trap_truth": t_truth, "pair_truth": p_truth,
                     "trap_read": t_out, "pair_read": p_out, "trap_ok": t_ok, "pair_ok": p_ok})

    n = len(PAIRS)
    print(f"\n=== {n} minimal pairs, {a.model}, seeds {seeds} ===")
    print(f"  trap side correct        {tally['trap_ok']:>3}/{n}")
    print(f"  pair side correct        {tally['pair_ok']:>3}/{n}")
    print(f"  BOTH (the real number)   {tally['both']:>3}/{n}")
    print(f"  trap only  <- answering from a prior, not reading   {tally['trap_only']:>3}")
    print(f"  pair only                                           {tally['pair_only']:>3}")
    print(f"  neither                                             {tally['neither']:>3}")
    print(f"\n  always-majority baseline: {base['trap']}/{n} on the traps, "
          f"{base['pair']}/{n} on the pairs, {0}/{n} on both")
    json.dump({"model": a.model, "seeds": seeds, "tally": dict(tally),
               "baseline": dict(base), "rows": rows}, open(a.json, "w"), indent=2)
    print(f"\n  wrote {Path(a.json).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
