#!/usr/bin/env python3
"""The mentors' example queries (meeting of 2026-09-16 agenda), read by the shipped classifier.

The four queries are copied from the meeting's "Example queries" list as given. Each is classified at
seeds 42, 43, 44 (temperature 0, the project standard) with apply_defaults=False, so an unstated
factor stays "unstated" and a value the model supplied itself is visible as such.

What none of the five factors can hold is recorded per query (`outside_scheme`): a gene list or a
loss-of-function filter. The tool's answer is printed beside it.

  NO_PROXY=localhost,127.0.0.1 OLLAMA_BASE_URL=http://localhost:11434/v1 \
    python3 evidence/current_evidence/mentor_queries.py [--seeds 42,43,44] [--json out.json]
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402

QUERIES = [
    ("Find variants in genes associated with colorectal cancer.", ["gene set by disease"]),
    ("Which variants in my sample affect genes associated with breast cancer?", ["gene set by disease"]),
    ("Show me variants affecting BRCA1, BRCA2", ["named gene list"]),
    ("Which variants produce loss-of-function consequences in my hereditary cancer gene panel?",
     ["gene panel", "loss-of-function filter"]),
]
FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("VEP_MODEL", "gemma4:26b"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    from openai import OpenAI                                           # noqa: PLC0415
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    seeds = [int(s) for s in a.seeds.split(",")]
    out = []
    for q, outside in QUERIES:
        reads = []
        for sd in seeds:
            got = va.infer_factors(client, a.model, q, apply_defaults=False, seed=sd, temperature=0.0)
            if got is None:
                sys.exit(f"classifier failed ({va.LAST_CLASSIFIER_ERROR}); nothing written")
            reads.append({"seed": sd, **{f: got.get(f) for f in FACTORS},
                          "organism": got.get("_organism"), "request_type": got.get("_request_type")})
        stable = all({f: r[f] for f in FACTORS} == {f: reads[0][f] for f in FACTORS} for r in reads)
        print(f"\n{q}\n  outside the factors: {', '.join(outside)}   stable across seeds: {stable}")
        for r in reads:
            print(f"  seed {r['seed']}: " + "  ".join(f"{f}={r[f]}" for f in FACTORS))
        out.append({"query": q, "outside_scheme": outside, "stable": stable, "reads": reads})
    if a.json:
        Path(a.json).write_text(json.dumps({"model": a.model, "seeds": seeds,
                                            "think": os.environ.get("VEP_FACTOR_THINK", "default(on)"),
                                            "rows": out}, indent=1))
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
