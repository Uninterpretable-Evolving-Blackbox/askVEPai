#!/usr/bin/env python3
"""One-off: run the current model on a user-supplied query/expected-config set.

Practical "does it get these right?" check (NOT a benchmark): runs each query through
the SAME pipeline as the eval (all-examples prompt -> LLM -> extract_recommendations ->
deterministic checker), then scores the final enabled set against the user's expected
config after NORMALISING option names to the expanded-catalogue ids.

Greedy (temp 0) + fixed seed for a reproducible single shot.

Run (env vars select the expanded catalogue + 20-example corpus):
  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json \
  VEP_EXAMPLES_FILE=vep_ai_demo/legacy/training_examples.json \
  python evidence/legacy_superseded/use_cases/run_user_queries.py --model gemma4:26b --concurrency 3
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEMO = Path(__file__).resolve().parents[3] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va        # noqa: E402
import evaluate as ev             # noqa: E402
from openai import OpenAI         # noqa: E402

# (query, expected config as the user wrote it -> list of raw names)
CASES = [
    ("Prioritize rare protein-altering variants in a patient with a suspected Mendelian disorder.",
     ["mane_select", "pick", "canonical", "af_gnomad", "sift", "polyphen", "gene_symbol"]),
    ("I have a trio with a child affected by developmental delay. I want to prioritize likely pathogenic de novo variants.",
     ["mane_select", "pick", "canonical", "gene_symbol", "transcript_version", "hgvs", "gene_phenotype",
      "gnomad_exomes", "gnomad_genomes", "sift", "polyphen", "check_existing"]),
    ("I only want the most clinically relevant transcript reported for each variant.",
     ["mane_select", "pick", "canonical"]),
    ("I am preparing a diagnostic report and need HGVS nomenclature using clinically accepted transcripts.",
     ["mane_select", "pick", "canonical", "hgvs", "transcript_version", "gene_symbol"]),
    ("Show me variants that affect known disease genes and have already been reported clinically.",
     ["clinvar", "check_existing", "gene_phenotype", "gene_symbol", "mane_select"]),
    ("This variant is two bases from an exon boundary. Could it affect splicing?",
     ["hgvs", "mane_select", "transcript_version", "gene_symbol", "spliceai"]),
    ("I have a 500 kb deletion identified in a rare disease patient. Which genes are affected?",
     ["symbol", "gene_phenotype", "overlaps", "mane_select"]),
    ("I am looking for novel candidate genes in a rare disease cohort.",
     ["af_gnomad", "sift", "polyphen", "symbol", "gene_phenotype", "canonical", "mane_select"]),
    ("I have variants from a tumour panel. Which ones are likely to be functionally important?",
     ["sift", "polyphen", "protein", "symbol", "clinvar"]),
    ("I want to identify variants that may disrupt splicing.",
     ["spliceai", "hgvs", "mane_select", "transcript_version"]),
    ("Give me the most severe consequence for each variant.",
     ["most_severe"]),
    ("I need a report-ready annotation for a BRCA1 variant that can be included in a clinical report.",
     ["mane_select", "pick", "canonical", "hgvs", "transcript_version", "gene_symbol", "clinvar"]),
]

# user-written name -> set of acceptable expanded-catalogue ids (a "slot" is satisfied
# if the model enables ANY id in the set). Empty set => no catalogue equivalent (N/A).
NORM = {
    "mane_select": {"mane"},
    "pick": {"pick"},
    "canonical": {"canonical"},
    "af_gnomad": {"af_gnomade", "af_gnomadg"},   # generic gnomAD AF -> exomes or genomes
    "gnomad_exomes": {"af_gnomade"},
    "gnomad_genomes": {"af_gnomadg"},
    "sift": {"sift"},
    "polyphen": {"polyphen"},
    "gene_symbol": {"symbol"},
    "symbol": {"symbol"},
    "transcript_version": {"transcript_version"},
    "hgvs": {"hgvs"},
    "gene_phenotype": {"phenotypes"},
    "check_existing": {"check_existing"},
    "clinvar": {"clinvar"},
    "spliceai": {"spliceai"},
    "protein": {"protein"},
    "most_severe": {"most_severe"},
    "overlaps": set(),                            # not in the 58-option catalogue
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")
    vep_options, examples = va.load_knowledge_base()
    aliases = va.build_option_aliases(vep_options)
    print(f"Model={args.model}  options={len(vep_options)}  examples={len(examples)}  "
          f"cases={len(CASES)}  temp={args.temperature}  seed={args.seed}", file=sys.stderr)

    def work(i):
        query, _ = CASES[i]
        prompt = va.build_system_prompt(vep_options, examples, query, retrieval_mode="all")
        resp = ev.call_llm(client, args.model, prompt, query,
                           temperature=args.temperature, seed=args.seed)
        en, dis = va.extract_recommendations(resp, aliases)
        # checker mutates en/dis in place -> final deployed sets
        va.check_and_fix_violations(en, dis, vep_options, query)
        return i, sorted(en), sorted(dis), resp

    t0 = time.time()
    out = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for fut in as_completed([ex.submit(work, i) for i in range(len(CASES))]):
            i, en, dis, resp = fut.result()
            out[i] = {"enabled": en, "disabled": dis, "response": resp}
            print(f"  done {len(out)}/{len(CASES)}  ({time.time()-t0:.0f}s)", file=sys.stderr)

    # ---- score with normalisation ----
    rows, tot_hit = [], 0
    tot_expect = tot_extra = 0
    cit_found = cit_total = 0
    for i, (query, expected_names) in enumerate(CASES):
        en = set(out[i]["enabled"])
        c_rate, c_found, c_tot = ev.measure_citation_rate(out[i]["response"])
        cit_found += c_found; cit_total += c_tot
        matched_ids = set()
        hit, miss = [], []
        for name in expected_names:
            accept = NORM.get(name, {name})
            if not accept:                       # no catalogue equivalent
                miss.append(f"{name} (N/A)")
                continue
            got = accept & en
            if got:
                hit.append(f"{name}→{'/'.join(sorted(got))}")
                matched_ids |= got
            else:
                miss.append(name)
        scored = [n for n in expected_names if NORM.get(n, {n})]   # exclude N/A from denom
        extra = sorted(en - matched_ids)
        tot_hit += len(hit); tot_expect += len(scored); tot_extra += len(extra)
        rows.append({"i": i + 1, "query": query, "hit": hit, "miss": miss,
                     "extra": extra, "n_hit": len(hit), "n_exp": len(scored),
                     "citation": [c_found, c_tot],
                     "enabled": sorted(en), "disabled": out[i]["disabled"],
                     "response": out[i]["response"]})

    report = {"model": args.model, "temperature": args.temperature, "seed": args.seed,
              "recall_overall": tot_hit / tot_expect if tot_expect else None,
              "total_hit": tot_hit, "total_expected": tot_expect, "total_extra": tot_extra,
              "citation_rate": cit_found / cit_total if cit_total else None,
              "citation_found": cit_found, "citation_total": cit_total,
              "rows": rows}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
