#!/usr/bin/env python3
"""Ask VEPai against general chat models, on 20 cases: does a chat model given the same job recommend the
options the reviewer asked for, and does it avoid the ones that delete results or do not apply?

Every arm gets the same short system prompt (cases/chat_models_system_prompt.txt), one question per case.
The chat-app answers (ChatGPT, Claude chat) were pasted by hand; the API arms are asked by this script.

  python3 evidence/current_evidence/chat_models_20_cases.py                  # score every arm in results/
  python3 evidence/current_evidence/chat_models_20_cases.py --detail         # and list each case's misses
  python3 evidence/current_evidence/chat_models_20_cases.py --ask claude-opus-5-5 [--pdf] [--effort medium]
  python3 evidence/current_evidence/chat_models_20_cases.py --ours           # run Ask VEPai on the 20 cases

--ask reads the key from ~/.anthropic_key or ANTHROPIC_API_KEY and never writes it. --pdf puts Ensembl's VEP
web documentation (27 pages, vep_ai_demo/legacy/VEP_web_documentation.pdf) before every case.

Scored on the 12 cases the reviewer marked, against her round-1 sheet with her edits
(cases/chat_models_reference.json). Options the form ticks by default are left out on both sides. A
free-text answer is mapped to catalogue options by OPTION_PATTERNS, entry by entry (entries split on
semicolons, bullets and lines); an entry that says not to tick something, or gives a form field an off
value ("Filter by frequency: No filtering"), is dropped.

  her options in RECOMMENDED   her recommended options found in the RECOMMENDED part of the answer
  named anywhere               the same options found anywhere in the answer
  row-deleting filters         RECOMMENDED entries that switch on pick, pick_allele, per_gene, most_severe,
                               summary, coding regions only or the frequency filter, where her reference
                               does not recommend it
  short-variant tools on SV    options the priority table marks not applicable to structural variants,
                               recommended on the cases whose variants are structural only
"""
import argparse
import base64
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = HERE / "cases"
RESULTS = HERE / "results"
ENGINE = ROOT / "vep_ai_demo"
PDF = ENGINE / "legacy" / "VEP_web_documentation.pdf"
PREFIX = "chat_models_20_cases"
ROW_DELETING = {"pick", "pick_allele", "per_gene", "most_severe", "summary", "coding_only", "frequency"}
# $ per million tokens: input, output, 5-minute cache write, cache read
PRICES = {"claude-opus-5-5": (4.00, 20.00, 5.00, 0.20), "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
          "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20)}

OPTION_PATTERNS = {
    "core_type": r"transcript database",
    "hgvs": r"\bhgvs",
    "af_gnomade": r"gnomad[^;\n]{0,25}exome|exomes?[^;\n]{0,6}\(?gnomad",
    "af_gnomadg": r"gnomad(?![ -]?sv)[^;\n]{0,25}genome|genomes?\)?[^;\n]{0,6}gnomad",
    "gnomad_sv": r"gnomad[ -]?sv|gnomad[^;\n]{0,15}structural",
    "tsl": r"transcript support level|\btsl\b",
    "domains": r"protein matches|protein domains?|\bpfam|interpro",
    "frequency": r"filter(?:ing)?[^;\n]{0,25}(?:by )?(?:allele )?frequenc|by frequency|exclude common",
    "most_severe": r"most severe consequence|most_severe",
    "dbnsfp": r"dbnsfp",
    "loeuf": r"loeuf",
    "mastermind": r"mastermind",
    "symbol": r"gene symbol",
    "check_existing": r"co-?located|existing variant|known variants",
    "allofus": r"all ?of ?us",
    "appris": r"appris",
    "regulatory": r"regulatory (?:region|build|feature|consequence|annotation)|regulatorybuild",
    "gencode_promoter": r"gencode promoter",
    "coding_only": r"coding regions? only|coding[- ]only",
    "buffer_size": r"buffer size",
    "clinpred": r"clinpred",
    "dosage_sensitivity": r"dosage ?sensitivity",
    "geno2mp": r"geno2mp",
    "transcript_version": r"transcript version",
    "clinvar": r"clinvar(?![^;\n]{0,12}\(?sv\b)|clinical significance(?! \(sv\))",
    "clinvar_sv": r"clinical significance \(sv\)|clinvar[^;\n]{0,12}\(?sv\b|clinvar[^;\n]{0,20}structural",
    "pubmed": r"pubmed",
    "mane": r"\bmane\b",
    "cell_type": r"cell types?\b",
    "pick": r"one selected consequence per variant(?! allele)|\bpick\b(?![ _]?(?:allele|per gene))",
    "shift_3prime": r"right align|shift_3prime|3'? ?shift",
    "eve": r"\beve\b",
    "nmd": r"\bnmd\b",
    "phenotypes": r"phenotype",
    "var_synonyms": r"variant synonym",
    "failed": r"flagged variant",
    "canonical": r"canonical",
    "pick_allele": r"per variant allele|pick_allele|pick allele",
    "cadd": r"\bcadd",
    "spliceai": r"spliceai",
    "utrannotator": r"utrannotator|utr ?annotator",
    "enformer": r"enformer",
    "protein": r"(?:^|[;:,(]\s*)(?:ensembl )?protein(?: ids?| identifiers?)?\s*(?=[;,)\n]|$)",
    "af": r"1000 ?genomes?[^;\n]{0,25}global|global (?:minor )?allele freq|\b1kg global",
    "biotype": r"biotype",
    "distance": r"upstream/downstream distance|\bdistance\b",
    "sift": r"\bsift\b",
    "per_gene": r"consequence per gene|per_gene|pick per gene",
    "revel": r"\brevel\b",
    "maxentscan": r"maxentscan",
    "paralogues": r"paralog",
    "uniprot": r"uniprot",
    "af_1kg": r"continental",
    "numbers": r"exon[^;\n]{0,12}intron|exon numbers",
    "mirna": r"mirna",
    "polyphen": r"polyphen",
    "summary": r"only list of consequences|\bsummary\b",
    "alphamissense": r"alphamissense",
    "dbscsnv": r"dbscsnv",
    "mutfunc": r"mutfunc",
    "ancestral_allele": r"ancestral allele",
    "blosum62": r"blosum",
    "go": r"gene ontology|\bgo\b(?: term| annotation)?",
    "intact": r"\bintact\b",
    "mavedb": r"mavedb",
    "opentargets": r"open ?targets",
    "riboseqorfs": r"riboseq",
    "avi": r"\bavi\b",
    "protvar": r"protvar",
    "species_frequency": r"population frequency data for this species|species[- ]specific (?:allele )?frequenc",
}
PATTERNS = {k: re.compile(v, re.I | re.M) for k, v in OPTION_PATTERNS.items()}
# "do not select X", "leave X unticked", and a form field listed with an off value ("Filter by frequency: No
# filtering", "Return results for variants in coding regions only: unticked") recommend nothing.
NEGATED = re.compile(r"\b(?:do not|don't|not select|avoid|leave\b[^;\n]{0,90}\b(?:off|unticked)|untick|skip)\b"
                     r"|:\s*(?:no\b|none\b|off\b|unticked\b|not (?:ticked|selected))", re.I)


def load_cases():
    d = json.loads((CASES / "chat_models_20_cases.json").read_text())
    return d["cases"]


def items(text):
    parts = re.split(r";|\n|(?:^|\s)\*\s", text or "")
    return [p for p in parts if p.strip() and not NEGATED.search(p)]


def options_in(text):
    return {oid for it in items(text) for oid, p in PATTERNS.items() if p.search(it)}


def recommended_part(text):
    m = re.search(r"RECOMMENDED(.*?)(?:\n\s*\*?\s*OPTIONAL|\bOPTIONAL\s*[:\[]|$)", text or "", re.S)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- asking
def ask(model, effort, pdf):
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    kf = Path.home() / ".anthropic_key"
    if not key and kf.exists():
        key = kf.read_text().strip()
    if not key:
        sys.exit("No key: put it in ~/.anthropic_key (chmod 600) or ANTHROPIC_API_KEY.")
    client = anthropic.Anthropic(api_key=key)
    system = (CASES / "chat_models_system_prompt.txt").read_text().strip()
    doc = None
    if pdf:
        doc = {"type": "document", "cache_control": {"type": "ephemeral"},
               "source": {"type": "base64", "media_type": "application/pdf",
                          "data": base64.standard_b64encode(PDF.read_bytes()).decode()}}
    rows = []
    for c in load_cases():
        t0 = time.perf_counter()
        # No refusal fallback: it would answer with another model and mix the arms.
        r = client.messages.create(model=model, max_tokens=16000, system=system,
                                   output_config={"effort": effort},
                                   messages=[{"role": "user", "content": ([doc] if doc else [])
                                              + [{"type": "text", "text": c["query"]}]}])
        u = r.usage
        pin, pout, pw, pr = PRICES[model]
        cost = (u.input_tokens * pin + u.output_tokens * pout + (u.cache_creation_input_tokens or 0) * pw
                + (u.cache_read_input_tokens or 0) * pr) / 1e6
        rows.append({"case": c["case"], "answer": "".join(b.text for b in r.content if b.type == "text"),
                     "stop_reason": r.stop_reason, "usage": u.model_dump(), "cost_usd": round(cost, 4),
                     "seconds": round(time.perf_counter() - t0, 1)})
        print(f"case {c['case']:2d}  {r.stop_reason}  {rows[-1]['seconds']}s", flush=True)
    arm = model.replace("claude-", "").replace("-", "") + ("_pdf" if pdf else "")
    out = {"arm": f"{model} API, effort {effort}" + (", VEP documentation PDF" if pdf else ""),
           "how": "Anthropic API, minimal system prompt, one call per case", "date": str(datetime.date.today()),
           "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 3), "cases": rows}
    path = RESULTS / f"{PREFIX}_answers_{arm}.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"total ${out['total_cost_usd']} -> {path.relative_to(ROOT)}")


def ours():
    env = dict(os.environ, NO_PROXY="localhost,127.0.0.1")
    rows = []
    for c in load_cases():
        r = subprocess.run([sys.executable, str(ENGINE / "vep_assistant.py"), "--no-ask", c["query"]],
                           capture_output=True, text=True, env=env, timeout=600)
        rows.append({"case": c["case"], "answer": r.stdout})
        print(f"case {c['case']:2d}  exit {r.returncode}", flush=True)
    for line in "\n".join(r["answer"] for r in rows).splitlines():
        if line.startswith("Result saved to: "):
            Path(line.split(": ", 1)[1].strip()).unlink(missing_ok=True)
    for r in rows:
        r["answer"] = re.sub(r"\n?Result saved to: [^\n]*\n?", "\n", r["answer"])
    out = {"arm": "Ask VEPai (gemma4:26b, reasoning on)", "how": "vep_assistant.py --no-ask, one run per case",
           "date": str(datetime.date.today()), "cases": rows}
    (RESULTS / f"{PREFIX}_answers_ask_vepai.json").write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------- scoring
def score(detail=False):
    ref = json.loads((CASES / "chat_models_reference.json").read_text())["cases"]
    cat = json.loads((ENGINE / "vep_options.json").read_text())
    cat = cat if isinstance(cat, list) else cat["options"]
    defaults = {o["id"] for o in cat if o.get("web_default_on")}
    pbf = json.loads((ENGINE / "priority_by_factor.json").read_text())["priorities"]
    short_only = {o for o, r in pbf.items() if r.get("variant_size_class", {}).get("structural-CNV") == "not_applicable"}
    sv_only = {int(c) for c, r in ref.items() if r["facts"]["variant_size_class"] == ["structural-CNV"]}

    table = {}
    for f in sorted(RESULTS.glob(f"{PREFIX}_answers_*.json")):
        d = json.loads(f.read_text())
        ans = {c["case"]: c["answer"] for c in d["cases"]}
        s = {"her_in_recommended": 0, "named_anywhere": 0, "reference_total": 0, "row_deleting": 0,
             "short_tools_on_sv": 0, "file": f.name, "per_case": {}}
        for c, r in ref.items():
            c = int(c)
            must = set(r["recommended"]) - defaults
            rec = recommended_part(ans.get(c))
            got_rec, got_all = options_in(rec) - defaults, options_in(ans.get(c))
            dele = [it.strip()[:120] for it in items(rec) if options_in(it) & (ROW_DELETING - set(r["recommended"]))]
            sv = sorted(got_rec & short_only) if c in sv_only else []
            s["reference_total"] += len(must)
            s["her_in_recommended"] += len(must & got_rec)
            s["named_anywhere"] += len(must & got_all)
            s["row_deleting"] += len(dele)
            s["short_tools_on_sv"] += len(sv)
            s["per_case"][c] = {"missed": sorted(must - got_rec), "row_deleting": dele, "short_tools_on_sv": sv}
        table[d["arm"]] = s

    print(f"{'arm':66s} {'her options in REC':>18s} {'named anywhere':>15s} {'row-deleting':>13s} {'short tools on SV':>18s}")
    for arm, s in table.items():
        t = s["reference_total"]
        print(f"{arm:66s} {s['her_in_recommended']:>11d}/{t:<6d} {s['named_anywhere']:>8d}/{t:<6d}"
              f" {s['row_deleting']:>13d} {s['short_tools_on_sv']:>18d}")
        if detail:
            for c, p in s["per_case"].items():
                print(f"    case {c:2d} missed {p['missed']}  row-deleting {p['row_deleting']}  short-on-SV {p['short_tools_on_sv']}")
    (RESULTS / f"{PREFIX}_scores.json").write_text(json.dumps(table, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", metavar="MODEL", help="ask an Anthropic model the 20 cases")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--ours", action="store_true", help="run Ask VEPai on the 20 cases")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    if a.ask:
        ask(a.ask, a.effort, a.pdf)
    elif a.ours:
        ours()
    score(a.detail)


if __name__ == "__main__":
    main()
