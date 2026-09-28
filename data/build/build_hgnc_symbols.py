#!/usr/bin/env python3
"""Reduce HGNC's approved-symbol file to the list the engine reads: vep_ai_demo/hgnc_symbols.json.

Used only by `mentions_result_filter`, which says when a query names genes the form cannot restrict to.
Approved symbols only. Alias and previous symbols are left out: they include VCF, AF, GO, OS and QC,
which appear in ordinary queries (checked against the 1,774 stored test queries, 2026-09-23).

EXCLUDED are approved symbols that are also words in Ensembl's own docs and form code or in common use
here: IMPACT (a VEP output column), MAF, MAX (MAX_AF), REST (the REST API), MTR (a VEP plugin), DBI
(Perl DBI), PC, MB, IDS, NHS, PDF. The engine matches any whole word, so abbreviations a query uses for
something else are excluded too: CAD (coronary artery disease), FAP and FH (disease names), GC (GC
content), TF (transcription factor), TG, and CAT, SET, SHE in capitalised text.

  python3 data/build/build_hgnc_symbols.py [--write]
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reference/ensembl_source/hgnc_non_alt_loci_set_2026-09-18.txt"
OUT = ROOT / "vep_ai_demo/hgnc_symbols.json"
EXCLUDED = ["IMPACT", "MAF", "MAX", "REST", "MTR", "DBI", "PC", "MB", "IDS", "NHS", "PDF",
            "CAD", "FAP", "FH", "GC", "TF", "TG", "CAT", "SET", "SHE"]


def main():
    rows = list(csv.DictReader(open(SRC), delimiter="\t"))
    approved = sorted({r["symbol"] for r in rows if r["status"] == "Approved"} - set(EXCLUDED))
    out = {"_source": "HGNC non_alt_loci_set.txt, https://storage.googleapis.com/public-download-files/"
                      "hgnc/tsv/tsv/non_alt_loci_set.txt, last-modified 2026-09-18, fetched 2026-09-23",
           "_what": "approved human gene symbols, for recognising gene names in a query",
           "_excluded": EXCLUDED, "_n": len(approved), "symbols": approved}
    print(f"{len(rows)} rows, {len(approved)} symbols kept, {len(EXCLUDED)} excluded")
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
        print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    else:
        print("dry run; --write to write")


if __name__ == "__main__":
    main()
