#!/usr/bin/env python3
"""The 150 tricky cases' 30 species cases, re-read the way the tool reads them.

WHY. `factors_150_tricky_cases.py` scores the classifier's raw answer (`parse_factor_classification`).
The tool reads a query through `infer_factors`, which adds one rule: an organism the model named that is
not human sets species to non-human. With reasoning on the rule changes nothing; with reasoning off the
model often names the organism but answers species "human" or "unstated", and the rule corrects it.
This re-reads the 30 species cases x 4 versions through `infer_factors`, so the species score is the one
a user gets. The other four factors have no such rule, so the raw grid score stands for them.

  NO_PROXY=localhost,127.0.0.1 VEP_FACTOR_THINK=0 python3 evidence/current_evidence/factors_150_species_through_tool.py \\
      results/factors_150_tricky_cases_reasoning_off.json results/factors_150_species_through_tool_reasoning_off.json
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

TESTS = ("plain", "trap", "twin", "absent")


def main():
    src, out = (HERE / sys.argv[1]), (HERE / sys.argv[2])
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    rows = [r for r in json.load(open(src))["rows"] if r["factor"] == "species"]
    jobs = [(r, t) for r in rows for t in TESTS]

    def go(job):
        r, t = job
        # think=False here means "read VEP_FACTOR_THINK", as in the tool.
        got = va.infer_factors(client, "gemma4:26b", r[t + "_query"], apply_defaults=False,
                               seed=42, temperature=0.0) or {}
        return r["id"], t, got.get("species"), got.get("_organism"), r[t + "_truth"], r["result"][t]["model"]

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(go, jobs))
    by = {}
    for i, t, sp, org, truth, raw in res:
        by.setdefault(i, {})[t] = (sp == truth, sp, org, truth, raw)
    per_test = {t: sum(by[i][t][0] for i in by) for t in TESTS}
    all_four = sum(all(by[i][t][0] for t in by[i]) for i in by)
    print(f"reasoning {os.environ.get('VEP_FACTOR_THINK', 'on (default)')}; species through infer_factors: "
          f"{per_test}, all four {all_four}/30")
    for i in sorted(by):
        for t, (ok, sp, org, truth, raw) in by[i].items():
            if not ok:
                print(f"  {i:14} {t:6} truth {truth:9} read {sp} organism={org} raw={raw}")
    json.dump({"source": src.name, "all_four": all_four, "per_test": per_test,
               "rows": [dict(zip(("id", "test", "species", "organism", "truth", "raw"), x)) for x in res]},
              open(out, "w"), indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
