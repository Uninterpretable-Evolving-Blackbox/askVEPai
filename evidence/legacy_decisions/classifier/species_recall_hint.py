#!/usr/bin/env python3
"""Does the species hint buy RECALL the bare model does not already have?

WHY. `VEP_SPECIES_HINT` is on by default and it is the only model-assist still enabled. Everywhere a
bare-model-vs-intervention comparison has been run at 26b, the bare model won:

    31 review rows, exact tuple     rule  9   hinted 21   model 22
    118 ablated queries, exact      rule 27   hinted 65   model 71
    24 keyword traps                rule  6   hinted 23   model 24

The hint's recorded justification is "14/14 against the override's 7/14" -- a comparison against the
RULE, never against the plain model. `species_rule_vs_model.py` cannot settle it either: on its pure
rows every arm scores 14/14 on the original text and 0/14 on the ablated, so it discriminates nothing.

So the hint's COST has been measured and its BENEFIT has not. The claimed benefit is recall over the
356 species Ensembl serves -- names a model might not recognise as an organism at all. That is the
opposite skill to the trap tests, which measure REJECTING a false match. This measures the benefit.

DESIGN
  Truth is the binary factor value, human / non-human, because that is the granularity the table uses.
  Cases name the organism ONLY by a Latin binomial or an uncommon common name, and deliberately avoid
  `germline`, `somatic`, `tumour`, `cancer` -- seven of `infer_species`'s own _HUMAN_SIGNALS are
  species-neutral analysis words, so those would bias the arms rather than test them.
  Human controls are included: a hint that raises recall by making everything non-human is not a win.
  Every case is checked at startup to be IN the index and to actually fire the hint, because a case
  the hint cannot see measures nothing.

CONFOUND, stated up front: the hinted arm has extra text in its prompt. A difference could be the
hint's CONTENT or merely the perturbation. This can separate "the hint helps" from "the hint does not
help"; it cannot attribute a small win to the content.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/legacy_decisions/classifier/species_recall_hint.py [--model gemma4:26b]
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
from species_rule_vs_model import model_read                            # noqa: E402

# (query, truth, why this case is here). No germline/somatic/tumour/cancer anywhere.
CASES = [
    # --- obscure binomials: the case the hint is supposed to exist for -------------------------
    ("Variant calls from Nothobranchius furzeri, coding regions, what do the changes do?",
     "non-human", "turquoise killifish; binomial unlikely to be common knowledge"),
    ("Ficedula albicollis SNVs and short indels in exons, need consequence calls.",
     "non-human", "collared flycatcher"),
    ("I have a small variant callset for Dasypus novemcinctus, exonic changes only.",
     "non-human", "nine-banded armadillo"),
    ("Astyanax mexicanus exome variants, protein-coding consequence annotation please.",
     "non-human", "Mexican cavefish"),
    ("Monodelphis domestica short variants, coding regions, functional annotation.",
     "non-human", "grey short-tailed opossum"),
    ("Annotating coding SNVs from Tetraodon nigroviridis sequence data.",
     "non-human", "green spotted pufferfish"),
    ("Ciona intestinalis variant calls, exonic, what consequences do they have?",
     "non-human", "sea squirt; not a vertebrate"),
    ("Anolis carolinensis SNVs in protein-coding exons, consequence annotation.",
     "non-human", "green anole lizard"),
    ("Oryzias latipes coding variants, need functional consequence calls.",
     "non-human", "medaka"),
    ("Salmo salar exonic short variants, annotate what they hit.",
     "non-human", "Atlantic salmon; also a bioinformatics tool name (Salmon)"),
    ("Xenopus tropicalis coding SNVs, consequence annotation for a small callset.",
     "non-human", "western clawed frog; genus-level name"),
    # --- uncommon COMMON names --------------------------------------------------------------
    ("Zebra finch coding variants from a small panel, what do they hit?",
     "non-human", "common name, two words, neither of which is an organism alone"),
    ("Rambouillet sheep exonic variants, consequence calls for a coding panel.",
     "non-human", "a breed name in front of the species"),
    ("Collared flycatcher short variants in exons, annotate the consequences.",
     "non-human", "common name of Ficedula albicollis"),
    # --- human controls: a hint that wins by saying non-human everywhere is not a win ---------
    ("Exome short variants from a patient cohort, coding regions, consequence calls.",
     "human", "plain human, no species word at all"),
    ("Homo sapiens coding SNVs, GRCh38, annotate the consequences.",
     "human", "stated outright"),
    ("Paediatric exome panel, exonic variants, what do these changes hit?",
     "human", "clinical context implies human"),
    ("Coding variants from a UK Biobank participant subset, consequence annotation.",
     "human", "a human cohort named without the word human"),
    # --- human controls carrying a species word that is NOT the subject ----------------------
    ("We ran the Salmon quantification tool first; now annotate the exome coding SNVs.",
     "human", "Salmon is the tool here, and `salmon` is in the index"),
    ("Our lab mascot is a zebra finch. The data are exome coding variants from donors.",
     "human", "species named, explicitly not the sample"),
]


def check_cases():
    """Every case must be visible to the hint, or it measures nothing."""
    bad = []
    for q, truth, why in CASES:
        fires = bool(va.format_species_hint(q))
        if truth == "non-human" and not fires:
            bad.append((q[:60], "hint does NOT fire on a non-human case"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--json", default=str(ROOT / "evidence/legacy_decisions/classifier/results/species_recall_hint.json"))
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",")]

    bad = check_cases()
    if bad:
        print("SETUP FAILURE — these cases cannot test the hint:")
        for q, why in bad:
            print(f"   {why}: {q}")
        sys.exit(1)
    print(f"{len(CASES)} cases, hint fires on every non-human one. "
          f"model={a.model} seeds={seeds}\n")

    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")

    rows, correct = [], defaultdict(Counter)
    for i, (q, truth, why) in enumerate(CASES, 1):
        got = {}
        for arm, hint in (("bare", False), ("hinted", True)):
            answers = [model_read(client, a.model, q, s, hint) for s in seeds]
            got[arm] = answers
            for ans in answers:
                correct[arm][ans == truth] += 1
        agree = got["bare"] == got["hinted"]
        flag = "" if agree else "   <- arms differ"
        print(f"{i:>2}. truth={truth:9} bare={'/'.join(got['bare']):26} "
              f"hinted={'/'.join(got['hinted']):26}{flag}")
        rows.append({"query": q, "truth": truth, "why": why, **got})

    # SCORE THE WAY THE TOOL RESOLVES. `unstated` is not a wrong answer: infer_factors falls back,
    # and the fallback is human. Scoring it as wrong measures a step the user never sees, and it was
    # the difference between "the arms tie" and the actual result.
    def resolved(a):
        return a if a in ("human", "non-human") else "human"

    n = len(CASES) * len(seeds)
    print(f"\n{'arm':8} {'raw':>7} {'resolved':>10}  of {n}   (resolved = unstated falls back to human)")
    for arm in ("bare", "hinted"):
        res = sum(1 for r in rows for a in r[arm] if resolved(a) == r["truth"])
        print(f"{arm:8} {correct[arm][True]:>7} {res:>10}  of {n}")

    nh = [r for r in rows if r["truth"] == "non-human"]
    hu = [r for r in rows if r["truth"] == "human"]
    for label, subset in (("non-human (recall — what the hint is FOR)", nh),
                          ("human (control — a hint must not over-trigger)", hu)):
        tot = len(subset) * len(seeds)
        line = "  ".join(
            f"{arm} {sum(1 for r in subset for x in r[arm] if resolved(x) == r['truth']):>2}/{tot}"
            for arm in ("bare", "hinted"))
        print(f"  {label:48} {line}")

    differ = [r for r in rows
              if [resolved(x) for x in r["bare"]] != [resolved(x) for x in r["hinted"]]]
    print(f"\ncases where the two arms differ at all: {len(differ)} of {len(CASES)}")
    for r in differ:
        print(f"   truth={r['truth']:9} bare={r['bare']} hinted={r['hinted']}")
        print(f"      {r['query'][:92]}")

    json.dump({"model": a.model, "seeds": seeds,
               "correct": {k: dict(v) for k, v in correct.items()}, "rows": rows},
              open(a.json, "w"), indent=2)
    print(f"\nwrote {Path(a.json).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
