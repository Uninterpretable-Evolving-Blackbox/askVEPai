#!/usr/bin/env python3
"""Keyword TRAPS for the four model-read factors: the cue word is present and WRONG.

WHY. `rules_vs_model.py` showed a keyword rule loses to the model on stated rows (9 vs 22 exact) and
that hints do not help 26b on those rows. Neither set tests the case that decides the design David
asked for -- keywords as a SIGN the model may reject -- because neither contains a keyword that
should be rejected. `species_rule_vs_model` did ("going down this rabbit hole" -> rabbit; "used as a
guinea pig" -> pig) and there the hint design won 14/14 against the override's 7/14. This is the
same test for origin, variant_size_class, region_focus and analysis_goal.

EACH CASE targets ONE factor: a query where the rule's own keyword list (imported, not copied) fires
on a value that is wrong for the user's data -- negated, idiomatic, about a database or a tool, or a
different sense of the word. Truth is what a careful reader would say. Only the target factor is
scored; the case is written so the other factors are either stated plainly or irrelevant.

THREE ARMS, from rules_vs_model:  rule (override) · model (shipped prompt) · hinted (matches shown as
rejectable hints, the species design). A trap is "caught" when the arm returns the truth.

  NO_PROXY=localhost,127.0.0.1 VEP_ALLOW_LOCAL_MODEL=1 OLLAMA_BASE_URL=http://localhost:11434/v1 \\
      python3 work/harness/factor_traps.py [--model gemma4:26b] [--seed 42]
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo")); sys.path.insert(0, str(ROOT / "work" / "harness"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402
from rules_vs_model import rule_read, hint_block, model_read, norm       # noqa: E402
from openai import OpenAI                                               # noqa: E402

# (target factor, truth, query, why the keyword is a trap)
CASES = [
    # ---- origin: a cancer/tumour word that does not describe the sample, or a germline word that does not
    ("origin", "germline", "Human exome from a rare-disease trio. This is not a tumour study; we are calling inherited coding SNVs for diagnosis.", "'tumour' negated"),
    ("origin", "germline", "Healthy controls recruited through a cancer registry, human exome SNVs, coding, just the consequences please.", "'cancer' names the registry, not the sample"),
    ("origin", "germline", "Germline BRCA1/2 testing in a family with a strong history of breast cancer. Human, coding SNVs, pathogenicity.", "'cancer' is the family history; the variants are inherited"),
    ("origin", "germline", "We keep COSMIC open for lookups but this cohort is population controls, human, exome SNVs, basic consequences.", "'COSMIC' is a database the user browses"),
    ("origin", "germline", "Matched normal samples only -- the tumour half was dropped from this batch. Human WES, coding, clinical interpretation.", "'tumour' refers to the discarded half"),
    ("origin", "somatic",  "De novo mutations acquired in a glioma, tumour-only sequencing, human, coding SNVs, which are likely drivers?", "'de novo' is a germline cue; the sample is a tumour"),
    ("origin", "germline", "Somatic hypermutation of the antibody genes is NOT what I mean; these are constitutional variants from blood, human exome, clinical.", "'somatic' in a different sense, explicitly disclaimed"),
    # ---- variant_size_class: a size word that is negated, or names a tool/threshold, or a 1-bp 'dup'
    ("variant_size_class", ["small"], "No CNVs or SVs were called on this human exome; SNVs and indels only, coding, clinical interpretation.", "'CNV'/'SV' negated"),
    ("variant_size_class", ["small"], "Manta was run but produced nothing we trust, so this is the SNV callset from a human tumour, coding, clinical.", "'Manta' names a tool whose output was discarded"),
    ("variant_size_class", ["small"], "A 1-bp duplication and a handful of single-base deletions from a human rare-disease exome, coding, pathogenicity.", "'duplication'/'deletion' at 1 bp are small variants"),
    ("variant_size_class", ["structural-CNV"], "Exome capture data, but we are only interested in multi-exon deletions and duplications (CNVs) in a human germline cohort, clinical.", "'exome' cues small; the variants are CNVs"),
    ("variant_size_class", ["structural-CNV"], "Single-nucleotide-resolution breakpoints for a set of large translocations and inversions, human, germline, clinical interpretation.", "'single nucleotide' describes breakpoint resolution, not the variant"),
    ("variant_size_class", ["small"], "We dropped the structural variants and kept the indels; human somatic, coding, what do these do?", "'structural variants' were removed"),
    # ---- region_focus: 'enhancer'/'promoter'/'WGS' in another sense, or 'intronic' negated
    ("region_focus", ["coding"], "Coding SNVs from a human WGS run -- we are ignoring everything outside exons. Germline, clinical.", "'WGS' cues non-coding; the question is exon-only"),
    ("region_focus", ["coding"], "Nothing intronic or intergenic: exonic, protein-altering variants only, human germline, clinical interpretation.", "'intronic'/'intergenic' negated"),
    ("region_focus", ["coding"], "Our PI is the main promoter of this project; the data are human germline missense variants, exome, clinical.", "'promoter' is a person"),
    ("region_focus", ["coding"], "This finding is a real enhancer of the hypothesis: human somatic missense SNVs in exons, what are their consequences?", "'enhancer' is idiomatic"),
    ("region_focus", ["regulatory-noncoding"], "Human germline variants in enhancers and promoters only -- no exome, no coding interest -- want regulatory consequences.", "'exome'/'coding' negated"),
    # ---- analysis_goal: 'population', 'patient', 'diagnos', 'frequently' in another sense
    ("analysis_goal", ["basic-consequence"], "A population of cultured cells with induced mutations, human, SNVs, just annotate what these variants hit.", "'population' is cells, not people"),
    ("analysis_goal", ["basic-consequence"], "How frequently does this VEP pipeline fail on our human somatic SNV set? Separately: give me basic consequences for the variants.", "'frequently' is about the pipeline"),
    ("analysis_goal", ["basic-consequence"], "No clinical question here and diagnostic yield is not the aim: human germline coding SNVs, which gene and what consequence.", "'clinical'/'diagnostic' negated"),
    ("analysis_goal", ["basic-consequence"], "Pathogenicity is assessed downstream by another team; for now, human germline exome SNVs, coding, just the consequence calls.", "'pathogenicity' is deferred elsewhere"),
    ("analysis_goal", ["clinical-interpretation"], "The patient population is small but every variant needs an ACMG-style call: human germline exome, coding SNVs.", "'population' is the clinical cohort; goal is clinical"),
    ("analysis_goal", ["population-frequency"], "Not a clinical question -- I want gnomAD and 1000 Genomes allele frequencies for these human germline coding SNVs.", "'clinical' negated; frequency stated"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--json", default=str(ROOT / "work/results/factor_traps.json"))
    args = ap.parse_args()
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")

    ARMS = ("rule", "model", "hinted")
    res, hits = [], {a: 0 for a in ARMS}
    for f, truth, q, why in CASES:
        rr = rule_read(q)
        reads = {"rule": rr, "model": model_read(client, args.model, q, args.seed),
                 "hinted": model_read(client, args.model, q, args.seed, hint_block(rr))}
        got = {a: (reads[a] or {}).get(f) for a in ARMS}
        ok = {a: norm(got[a]) == norm(truth) for a in ARMS}
        for a in ARMS:
            hits[a] += ok[a]
        res.append({"factor": f, "truth": truth, "why": why, "query": q, "got": got, "ok": ok,
                    "rule_fired_on": rr.get(f + "__hits")})
        marks = "  ".join(f"{a}:{'Y' if ok[a] else '-'}" for a in ARMS)
        print(f"  {f:20} {marks}   {why}", flush=True)

    n = len(CASES)
    print(f"\n=== {n} keyword traps, {args.model}, seed {args.seed} ===")
    print(f"  {'arm':8} caught")
    for a in ARMS:
        print(f"  {a:8} {hits[a]:3}/{n}")
    print("\n  per factor:")
    for f in ("origin", "variant_size_class", "region_focus", "analysis_goal"):
        sub = [r for r in res if r["factor"] == f]
        print(f"    {f:20} " + "  ".join(f"{a} {sum(r['ok'][a] for r in sub)}/{len(sub)}" for a in ARMS))
    print("\n  rule = keyword override (first match wins); model = shipped classifier; hinted = model shown")
    print("  the matches as rejectable hints. A trap is caught when the arm returns what a careful reader would.")
    Path(args.json).write_text(json.dumps({"model": args.model, "seed": args.seed, "hits": hits, "cases": res}, indent=1))
    print(f"  wrote {args.json}")


if __name__ == "__main__":
    main()
