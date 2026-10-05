#!/usr/bin/env python3
"""askVEPai against general chat models, on 20 cases: given the same job, does a chat model recommend what
the priority table recommends, and does it avoid options that cannot work for the case or delete results?

The priority table (vep_ai_demo/priority_by_factor.json) is the standard here: it is the project's statement
of which options each kind of analysis should get, and the reference configuration for a case is what it
gives for the case's true factors. askVEPai is that table applied to the model's reading of the factors, so
its score measures the reading; the chat models' score measures the whole job.

Every arm gets the same short system prompt (cases/chat_models_system_prompt.txt), one question per case.
The website answers (ChatGPT, claude.ai) were pasted by hand; the API arms are asked by this script.

  python3 evidence/current_evidence/chat_models_20_cases.py                  # score every arm in results/
  python3 evidence/current_evidence/chat_models_20_cases.py --detail         # and list each case's differences
  python3 evidence/current_evidence/chat_models_20_cases.py --ask claude-opus-5-5 [--pdf] [--effort medium]
  python3 evidence/current_evidence/chat_models_20_cases.py --ours           # run askVEPai on the 20 cases

--ask reads the key from ~/.anthropic_key or ANTHROPIC_API_KEY and never writes it. --pdf puts Ensembl's VEP
web documentation (27 pages, vep_ai_demo/legacy/VEP_web_documentation.pdf) before every case. The PDF is not
in the repository: the runs used a 27-page Safari print of Ensembl's VEP web documentation from March 2026.
Put a copy at that path to re-run.

A free-text answer is mapped to catalogue options by OPTION_PATTERNS, entry by entry (entries split on
semicolons, bullets and lines); an entry that says not to tick something, or gives a form field an off
value ("Filter by frequency: No filtering"), is dropped. Options the form ticks by default are left out.

  reference options recommended   of the table's RECOMMENDED options, how many the arm recommends
                                  (the 16 cases with known facts: 1-12, 17-20)
  not in the reference            options the arm recommends that the table does not (the same 16)
  cannot work for the case        recommended options Ensembl does not offer for the case's species, or
                                  short-variant options on a case whose variants are structural only (all 20)
  row-deleting filters            recommended entries that switch on pick, pick_allele, per_gene, most_severe,
                                  summary, coding regions only or the frequency filter (all 20)

The scores file also scores the 12 review scenarios against their round-1 configuration
(cases/chat_models_reference_round1.json), which predates later changes to the table.
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
          "claude-opus-4-8": (5.00, 25.00, 6.25, 0.50), "claude-opus-4-7": (5.00, 25.00, 6.25, 0.50),
          "claude-opus-4-6": (5.00, 25.00, 6.25, 0.50), "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
          "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20), "claude-haiku-4-5-20251001": (1.00, 5.00, 1.25, 0.10)}

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
    "protein": r"(?:^\s*|[;:,(]\s*)(?:ensembl )?protein(?: ids?| identifiers?)?\s*(?=[;,)(\n]|$)",
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
NEGATED = re.compile(r"\b(?:do not|don't|not select|avoid|leave\b[^;\n]{0,90}\b(?:off|unticked)|untick(?:ed)?|skip)\b"
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
    return "\n".join(re.findall(r"(?<!NOT )RECOMMENDED(.*?)(?:\n\s*\*?\s*OPTIONAL|\bOPTIONAL\s*[:\[]|$)",
                                text or "", re.S))


# ---------------------------------------------------------------- asking
def ask(model, effort, pdf):
    if pdf and not PDF.exists():
        sys.exit(f"--pdf needs {PDF.relative_to(ROOT)}: Ensembl's VEP web documentation saved as a PDF "
                 f"(27 pages). It is not in the repository (*.pdf is gitignored).")
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
        # Thinking on for every model, so only the model changes: adaptive thinking at the given effort;
        # Haiku 4.5 takes neither, so it thinks with a fixed budget instead.
        if model.startswith("claude-haiku"):
            think = {"thinking": {"type": "enabled", "budget_tokens": 8000}}
        else:
            think = {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort}}
        r = client.messages.create(model=model, max_tokens=16000, system=system, **think,
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
    arm = (model.replace("claude-", "").replace("-20251001", "").replace("-", "")
           + ("" if effort == "medium" else f"_{effort}") + ("_pdf" if pdf else ""))
    setting = "thinking budget 8000" if model.startswith("claude-haiku") else f"effort {effort}, adaptive thinking"
    out = {"arm": f"{model} via the API, {setting}" + (", VEP documentation PDF" if pdf else ""),
           "how": "Anthropic API, minimal system prompt, one call per case", "date": str(datetime.date.today()),
           "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 3), "cases": rows}
    path = RESULTS / f"{PREFIX}_answers_{arm}.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"total ${out['total_cost_usd']} -> {path.relative_to(ROOT)}")


def ours():
    env = dict(os.environ, NO_PROXY="localhost,127.0.0.1")
    rows, failed = [], []
    for c in load_cases():
        r = subprocess.run([sys.executable, str(ENGINE / "vep_assistant.py"), "--no-ask", c["query"]],
                           capture_output=True, text=True, env=env, timeout=600)
        rows.append({"case": c["case"], "answer": r.stdout})
        print(f"case {c['case']:2d}  exit {r.returncode}", flush=True)
        if r.returncode:
            failed.append((c["case"], r.stdout + r.stderr))
    for line in "\n".join(r["answer"] for r in rows).splitlines():
        if line.startswith("Result saved to: "):
            Path(line.split(": ", 1)[1].strip()).unlink(missing_ok=True)
    if failed:
        n, out = failed[0]
        sys.exit(f"askVEPai failed on case(s) {[f[0] for f in failed]}; "
                 f"{PREFIX}_answers_ask_vepai.json and the scores were not rewritten.\ncase {n}:\n{out}")
    for r in rows:
        r["answer"] = re.sub(r"\n?Result saved to: [^\n]*\n?", "\n", r["answer"])
    out = {"arm": "Ask VEPai (gemma4:26b, reasoning on)", "how": "vep_assistant.py --no-ask, one run per case",
           "date": str(datetime.date.today()), "cases": rows}
    (RESULTS / f"{PREFIX}_answers_ask_vepai.json").write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------- scoring
def reference_configuration(va, cat, facts, query, organism):
    """The priority table's RECOMMENDED options for these true factors, as the tool would print them."""
    resolved = va.resolve_for_query(facts, cat) or {}
    enabled, disabled = set(), set()
    va.restore_missing_recommended(enabled, disabled, resolved, cat, query)
    return {o for o in enabled if va.offer_available(o, cat, organism, "GRCh38")}


def score(detail=False):
    sys.path.insert(0, str(ENGINE))
    import vep_assistant as va
    cat = va.load_knowledge_base()
    cat = cat[0] if isinstance(cat, tuple) else cat
    byid = {o["id"]: o for o in cat}
    defaults = {o for o in byid if byid[o].get("web_default_on")}
    pbf = json.loads((ENGINE / "priority_by_factor.json").read_text())["priorities"]
    short_only = {o for o, r in pbf.items() if r.get("variant_size_class", {}).get("structural-CNV") == "not_applicable"}
    cases = {c["case"]: c for c in load_cases()}
    # the review scenarios' facts are their current labels in cases/iced.json, so a label correction there
    # reaches this experiment too
    iced = json.loads((CASES / "iced.json").read_text())
    as_list = lambda v: v if isinstance(v, list) else [v]
    for c in cases.values():
        if c.get("review_row"):
            lab = iced[c["review_row"] - 1]["factor_labels"]
            assert iced[c["review_row"] - 1]["user_query"].strip() == c["query"].strip(), c["case"]
            c["facts"] = {"species": lab["species"], "origin": lab["origin"],
                          "variant_size_class": as_list(lab["variant_size_class"]),
                          "region_focus": as_list(lab["region_focus"]), "analysis_goal": as_list(lab["analysis_goal"])}
    organism = {n: ("homo_sapiens" if not c["facts"] or c["facts"]["species"] == "human"
                    else va.resolve_species_name(c["query"])) for n, c in cases.items()}
    ref = {n: reference_configuration(va, cat, c["facts"], c["query"], organism[n]) - defaults
           for n, c in cases.items() if c["facts"]}
    round1 = json.loads((CASES / "chat_models_reference_round1.json").read_text())["cases"]

    def cannot_work(n, o):
        spec = byid[o].get("species")
        if isinstance(spec, list) and not va.on_species_list(organism[n], spec):
            return True
        f = cases[n]["facts"]
        return bool(f) and f["variant_size_class"] == ["structural-CNV"] and o in short_only

    table = {}
    for f in sorted(RESULTS.glob(f"{PREFIX}_answers_*.json")):
        d = json.loads(f.read_text())
        ans = {c["case"]: c["answer"] for c in d["cases"]}
        s = {"file": f.name, "reference_total": sum(map(len, ref.values())), "reference_recommended": 0,
             "not_in_reference": 0, "cannot_work": 0, "row_deleting": 0,
             "round1": {"reference_total": 0, "reference_recommended": 0}, "per_case": {}}
        for n in cases:
            rec = recommended_part(ans.get(n))
            got = options_in(rec) - defaults
            p = {"cannot_work": sorted(o for o in got if cannot_work(n, o)),
                 "row_deleting": [it.strip()[:120] for it in items(rec) if options_in(it) & ROW_DELETING]}
            if n in ref:
                p["missed"], p["not_in_reference"] = sorted(ref[n] - got), sorted(got - ref[n])
                s["reference_recommended"] += len(got & ref[n])
                s["not_in_reference"] += len(got - ref[n])
            if str(n) in round1:
                must = set(round1[str(n)]["recommended"]) - defaults
                s["round1"]["reference_total"] += len(must)
                s["round1"]["reference_recommended"] += len(got & must)
            s["cannot_work"] += len(p["cannot_work"])
            s["row_deleting"] += len(p["row_deleting"])
            s["per_case"][n] = p
        table[d["arm"]] = s

    print(f"{'arm':66s} {'reference options':>18s} {'not in reference':>17s} {'cannot work':>12s} {'row-deleting':>13s}"
          f" {'round-1 ref':>12s}")
    for arm, s in table.items():
        print(f"{arm:66s} {s['reference_recommended']:>11d}/{s['reference_total']:<6d} {s['not_in_reference']:>17d}"
              f" {s['cannot_work']:>12d} {s['row_deleting']:>13d}"
              f" {s['round1']['reference_recommended']:>8d}/{s['round1']['reference_total']:<3d}")
        if detail:
            for n, p in s["per_case"].items():
                print(f"    case {n:2d} {p}")
    (RESULTS / f"{PREFIX}_scores.json").write_text(json.dumps(table, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", metavar="MODEL", help="ask an Anthropic model the 20 cases")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--ours", action="store_true", help="run askVEPai on the 20 cases")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    if a.ask:
        ask(a.ask, a.effort, a.pdf)
    elif a.ours:
        ours()
    score(a.detail)


if __name__ == "__main__":
    main()
