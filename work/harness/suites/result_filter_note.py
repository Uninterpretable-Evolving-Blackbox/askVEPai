#!/usr/bin/env python3
"""The out-of-scope note: fires on gene-list and loss-of-function requests, stays quiet elsewhere.

The form has no gene or consequence-class filter; Ensembl's results page does that after the run
(research/ensembl_docs_116/vep_online_results.html). `mentions_result_filter` is wording rules only,
so the classifier prompt is untouched. This checks the mentors' four example queries (2026-09-16
agenda) fire, a handful of variants behave, and every stored test query stays quiet except the two
grid cases that do restrict to PRKAR1A. No model, seconds.

  python3 work/harness/suites/result_filter_note.py
"""
import glob, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va                                              # noqa: E402

FIRE = {
    "Find variants in genes associated with colorectal cancer.": ["a set of genes"],
    "Which variants in my sample affect genes associated with breast cancer?": ["a set of genes"],
    "Show me variants affecting BRCA1, BRCA2": ["genes: BRCA1, BRCA2"],
    "Which variants produce loss-of-function consequences in my hereditary cancer gene panel?":
        ["a set of genes", "loss-of-function consequences"],
    "germline variants in the BRCA2 gene": ["genes: BRCA2"],
    "variants in MLH1 or MSH2 in a Lynch panel": ["genes: MLH1, MSH2"],
    "list protein-truncating variants": ["loss-of-function consequences"],
    # Digit-free names need the HGNC list (vep_ai_demo/hgnc_symbols.json, 2026-09-23).
    "variants in KRAS": ["genes: KRAS"],
    "genes such as APC, MLH1 and PTEN": ["genes: APC, MLH1, PTEN"],
    "variants in the ATM gene": ["genes: ATM"],
    "variants in C9orf72": ["genes: C9orf72"],
    "variants in HLA-A or HLA-B": ["genes: HLA-A, HLA-B"],
    "in KIT/PDGFRA": ["genes: KIT, PDGFRA"],
    # Any whole word counts, so a gene named first is caught (2026-09-23).
    "BRCA1 variants only please": ["genes: BRCA1"],
    "TP53: which variants are pathogenic?": ["genes: TP53"],
    "A TP53 variant present in blood, saliva and every tissue": ["genes: TP53"],
}
QUIET = [
    "I have GRCh38 SNVs from NA12878", "Use BLOSUM62 and CADD on my exome",
    "annotate variants aligned to CHM13", "report ENST00000380152 only", "which genes do my variants hit?",
    "I want the IMPACT column", "use the REST API", "SNVs in VCF format", "All data are in MB",
    "annotate variants in my set of samples", "Results in GRCh38 please",
    "BRCA1.vcf please", "the file Homo_sapiens-GCA_009914755.4-2022_10-gnomad.vcf.gz",
    "GWAS hits for CAD and T2D", "a FAP family", "FH cohort", "GC content of the region",
    "TF binding sites", "PLEASE SET THE OPTIONS FOR MY CAT, SHE SAID",
]
# Stored queries that name a gene, so the note is right there: the grid's PRKAR1A cases ("upstream of
# PRKAR1A") and TP53 cases ("A TP53 variant present in blood").
ALLOWED_STORED = {"PRKAR1A", "TP53"}


def stored_queries():
    out = []
    for p in (glob.glob(str(ROOT / "work/generation/candidates/*.json"))
              + glob.glob(str(ROOT / "work/preliminary_examples/*.json"))):
        try:
            d = json.load(open(p))
        except Exception:                                               # noqa: BLE001
            continue
        items = d if isinstance(d, list) else d.get("rows") or d.get("examples") or []
        for x in items:
            if isinstance(x, dict):
                for k in ("user_query", "query", "ablated"):
                    if x.get(k):
                        out.append((os.path.basename(p), x[k]))
    return out


def local_result_queries():
    """The grid's 600 and organism naming's 242 queries, when last night's results are on disk."""
    out = []
    r = ROOT / "work/results/overnight_2026-09-23"
    try:
        g = json.load(open(r / "factor_grid_natural_think.json"))["rows"]
        out += [("grid", c[t + "_query"]) for c in g for t in ("plain", "trap", "twin", "absent")]
        o = json.load(open(r / "organism_naming_think.json"))
        out += [("organism", c[k]) for c in o.get("rows", []) for k in ("plain_query", "decoy_query") if k in c]
    except Exception:                                                   # noqa: BLE001
        pass
    return out


def main():
    ok = fail = 0
    def check(name, cond, detail=""):
        nonlocal ok, fail
        ok += cond; fail += not cond
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail and not cond else ""))
    for q, want in FIRE.items():
        got = va.mentions_result_filter(q)
        check(f"fires: {q[:70]}", got == want, f"got {got}")
    for q in QUIET:
        got = va.mentions_result_filter(q)
        check(f"quiet: {q[:70]}", not got, f"got {got}")
    check("HGNC symbol list loaded", len(va.load_gene_symbols()) > 40000, str(len(va.load_gene_symbols())))
    stored = stored_queries() + local_result_queries()
    loud = [(f, q, va.mentions_result_filter(q)) for f, q in stored]
    loud = [x for x in loud if x[2] and not any(s in x[2][0] for s in ALLOWED_STORED)]
    check(f"quiet on {len(stored)} stored test queries", not loud, str(loud[:3]))
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
