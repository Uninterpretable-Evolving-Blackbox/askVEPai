#!/usr/bin/env python3
"""Run the 20 hand-written scenarios and score the factor tuple against what a careful reader says.

Companion to `try_queries.sh`, which runs the same queries through the full CLI for eyeballing. This
one reports only the parts that decide a configuration: the tuple, which values were ASSUMED rather
than read, whether anything was left open, and whether the query was refused as out of scope.

EXPECTED is the tuple AFTER the assume policy, because that is what reaches the resolver. Where the
text genuinely says nothing, the expectation is the assumed value and the row is marked `assumed`, so
a filled-in default is not scored as a misread.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/legacy_decisions/missing_facts/score_try_queries.py [--model gemma4:26b]
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402

SMALL, SV = "small", "structural-CNV"
COD, REG = "coding", "regulatory-noncoding"
BASIC, CLIN, POP = "basic-consequence", "clinical-interpretation", "population-frequency"

# (query, expected tuple after the assume policy, expected scope, note)
CASES = [
    ("Human germline exome, SNVs and indels in coding regions, GRCh38. I need pathogenicity assessment for a rare disease diagnosis.",
     ("human", "germline", [SMALL], [COD], [CLIN]), "configure", "all stated"),
    ("Somatic structural variants and CNVs from a human tumour biopsy, protein-coding impact, looking for drivers.",
     ("human", "somatic", [SV], [COD], [CLIN]), "configure", "all stated"),
    ("Mouse germline SNVs and short indels in enhancers and promoters, I just want the regulatory consequences.",
     ("non-human", "germline", [SMALL], [REG], [BASIC]), "configure", "all stated"),

    ("hey so i got some vcf back from our mouse experiment, its the tumour tissue not the normal, theres like snps and a few small indels, i just wanna know what genes theyre in and whether they break the protein",
     ("non-human", "somatic", [SMALL], [COD], [BASIC]), "configure", "buried; the sample IS the mouse"),
    ("my supervisor wants to know how common these are in the general population before we take it further. theyre from a patient exome, single base changes in exons",
     ("human", "germline", [SMALL], [COD], [POP]), "configure", "buried; 'how common' is the goal"),
    ("we have blood samples from a family, the changes are big deletions and duplications spanning several exons, inherited through the mother. what do they actually do",
     ("human", "germline", [SV], [COD], [BASIC]), "configure", "buried; multi-exon = SV"),
    ("human tumour sample, we've got both the small mutations and some large copy number changes in the same callset, need to work out whats driving it",
     ("human", "somatic", [SMALL, SV], [COD, REG], [CLIN]), "configure", "both sizes; region unstated -> both"),
    ("so we sequenced a bunch of zebra finches for a behaviour study and got a load of snvs, wanna see which ones land in protein coding stuff",
     ("non-human", "somatic", [SMALL], [COD], [BASIC]), "configure", "origin unstated -> somatic"),

    ("ok so we went down a bit of a rabbit hole with this one but its just human wgs, germline, and were mostly interested in promoters and enhancers",
     ("human", "germline", [SMALL, SV], [REG], [BASIC]), "configure", "TRAP: rabbit hole"),
    ("i got used as a guinea pig for the new pipeline lol. anyway its human blood, inherited variants, coding snvs, want clinvar and predictions",
     ("human", "germline", [SMALL], [COD], [CLIN]), "configure", "TRAP: guinea pig"),
    ("not a mouse study btw, its human. coding snvs, germline, i want to check clinvar and the pathogenicity scores",
     ("human", "germline", [SMALL], [COD], [CLIN]), "configure", "TRAP: mouse negated"),
    ("we ran salmon first for the expression side, but now i need the exome coding snvs annotated, human, from patients",
     ("human", "somatic", [SMALL], [COD], [BASIC]), "configure", "TRAP: Salmon the tool; origin+goal unstated"),
    ("no cnvs or svs were called on this one, its snvs and indels only, human germline exome, coding, clinical interpretation please",
     ("human", "germline", [SMALL], [COD], [CLIN]), "configure", "TRAP: CNVs negated"),
    ("healthy controls recruited through a cancer registry, human exome, coding snvs, just the basic consequences",
     ("human", "germline", [SMALL], [COD], [BASIC]), "configure", "TRAP: cancer = the registry"),
    ("theres a 1bp duplication and a handful of single base deletions, human rare disease exome, coding, want pathogenicity",
     ("human", "germline", [SMALL], [COD], [CLIN]), "configure", "TRAP: 1bp dup is SMALL"),

    ("ive got a vcf, what should i turn on",
     ("human", "somatic", [SMALL, SV], [COD, REG], [BASIC]), "configure", "everything assumed"),
    ("human germline data, coding regions, i want to know if anything is pathogenic",
     ("human", "germline", [SMALL, SV], [COD], [CLIN]), "configure", "size unstated -> both"),

    ("why is my vep output showing NA for everything in the SIFT column", None, "vep-support", "should refuse"),
    ("hiya", None, "not-vep", "should refuse"),
    ("how do i install the offline cache for vep on a mac, it keeps failing on the perl bit",
     None, "vep-support", "should refuse"),
]

FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")


def norm(v):
    return sorted(v) if isinstance(v, list) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--json", default=str(ROOT / "evidence/legacy_decisions/missing_facts/results/try_queries_scored.json"))
    a = ap.parse_args()

    cat, examples = va.load_knowledge_base()
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")

    rows, n_ok, n_scored = [], 0, 0
    for i, (q, exp, exp_scope, note) in enumerate(CASES, 1):
        raw = va.infer_factors(client, a.model, q, apply_defaults=False)
        scope = (raw or {}).get("_request_type", "configure")
        filled, assembly = va.resolve_underspecified(dict(raw or {}), cat, mode="assume", user_query=q)
        assumed = filled.get("_assumed", [])
        _f, _a, questions = va.clarification_plan(dict(raw or {}), cat, q)

        print(f"\n{i:>2}. {note}")
        print(f"    {q[:104]}")
        if exp is None:
            ok = (scope == exp_scope)
            n_scored += 1; n_ok += ok
            print(f"    scope: got {scope!r}, expected {exp_scope!r}   {'OK' if ok else 'MISS'}")
            rows.append({"n": i, "query": q, "scope": scope, "expected_scope": exp_scope, "ok": ok})
            continue

        got = tuple(norm(filled.get(f)) for f in FACTORS)
        want = tuple(norm(v) for v in exp)
        bad = [FACTORS[k] for k in range(5) if got[k] != want[k]]
        ok = not bad and scope == "configure"
        n_scored += 1; n_ok += ok
        for k, f in enumerate(FACTORS):
            mark = " " if got[k] == want[k] else "X"
            tag = "  (assumed)" if f in assumed else ""
            shown = ",".join(got[k]) if isinstance(got[k], list) else got[k]
            wanted = ",".join(want[k]) if isinstance(want[k], list) else want[k]
            print(f"      {mark} {f:20} {str(shown):32}{tag}"
                  + ("" if got[k] == want[k] else f"   expected {wanted}"))
        if assembly:
            print(f"        assembly {assembly}  (assumed)" if "assembly" in assumed
                  else f"        assembly {assembly}")
        if questions:
            print(f"        REPROMPTS on: {', '.join(qq[0] for qq in questions)}")
        rows.append({"n": i, "query": q, "note": note, "got": list(got), "want": list(want),
                     "assumed": assumed, "reprompts": [qq[0] for qq in questions], "ok": ok,
                     "wrong_factors": bad})

    print(f"\n{'='*78}\n{n_ok} of {n_scored} fully correct")
    wrong = [r for r in rows if not r["ok"]]
    if wrong:
        print("\nnot fully correct:")
        for r in wrong:
            if "wrong_factors" in r:
                print(f"  #{r['n']:>2} {r['note']:38} wrong: {', '.join(r['wrong_factors'])}")
            else:
                print(f"  #{r['n']:>2} scope {r['scope']} != {r['expected_scope']}")
    rep = [r for r in rows if r.get("reprompts")]
    print(f"\nqueries that reprompt: {len(rep)} of {len(CASES)}")
    for r in rep:
        print(f"  #{r['n']:>2} asks about {', '.join(r['reprompts'])}")
    json.dump({"model": a.model, "rows": rows}, open(a.json, "w"), indent=2)
    print(f"\nwrote {Path(a.json).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
