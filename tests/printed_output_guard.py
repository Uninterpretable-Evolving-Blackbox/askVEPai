#!/usr/bin/env python3
"""Snapshot and diff what the tool PRINTS, over every factor tuple, with the model stubbed.

WHY. Resolver-level sweeps (resolve_for_query) print nothing, so a change that breaks or alters the
printed configuration passes them: on 2026-09-22 the default run printed no configuration at all and
every sweep stayed green. This calls the shipped `run_recommend` with `infer_factors` replaced by a
fixed tuple and records stdout, so a before/after diff shows every line an engine change moves.

CASES. 6 organisms (human; pig, chicken, mouse and dingo resolved; non-human with no organism) x 2
origins x 3 sizes x 3 regions x 7 goals = 756 tuples. Human tuples run under 4 query texts (no build,
GRCh37, GRCh38, and one naming both builds); every run at --standard and --full. 2,268 runs.

  python3 tests/printed_output_guard.py --snapshot before.json
  python3 tests/printed_output_guard.py --snapshot after.json --diff before.json
"""
import argparse, contextlib, difflib, io, itertools, json, os, sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("PYTHONHASHSEED", "0")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va  # noqa: E402

ORGANISMS = [("human", None), ("non-human", "sus_scrofa"), ("non-human", "gallus_gallus"),
             ("non-human", "mus_musculus"), ("non-human", "canis_lupus_dingo"), ("non-human", None)]
HUMAN_QUERIES = {"nobuild": "germline and somatic variants from our samples",
                 "grch37": "variants called on GRCh37",
                 "grch38": "variants called on GRCh38",
                 "both": "calls lifted over from hg19 to GRCh38"}
SIZES = (["small"], ["structural-CNV"], ["small", "structural-CNV"])
REGIONS = (["coding"], ["regulatory-noncoding"], ["coding", "regulatory-noncoding"])
GOALS = [list(c) for r in (1, 2, 3) for c in itertools.combinations(
    ("basic-consequence", "clinical-interpretation", "population-frequency"), r)]


def run(tup, query, level):
    va.infer_factors = lambda *a, **k: dict(tup)
    va.save_result = lambda *a, **k: None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = va.run_recommend(None, "stub", OPTIONS, [], query, level=level, clarify="state")
    out = buf.getvalue().replace("Reading the scenario… 0.0s", "Reading the scenario…")
    return out + (f"\n[return {rc}]" if rc else "")


def snapshot():
    snap = {}
    for (sp, org), origin, size, region, goal in itertools.product(ORGANISMS, ("germline", "somatic"),
                                                                 SIZES, REGIONS, GOALS):
        tup = {"species": sp, "origin": origin, "variant_size_class": size, "region_focus": region,
               "analysis_goal": goal, "_request_type": "configure"}
        if org:
            tup["_organism"] = org
        queries = HUMAN_QUERIES if sp == "human" else {"animal": "variants from our animals"}
        for qk, q in queries.items():
            for level in ("standard", "full"):
                key = "|".join([org or sp, origin, "+".join(size), "+".join(region), "+".join(goal), qk, level])
                snap[key] = run(tup, q, level)
    return snap


def main():
    global OPTIONS
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="write this run's outputs here")
    ap.add_argument("--diff", help="compare with an earlier snapshot")
    ap.add_argument("--show", type=int, default=3, help="example diffs to print per changed line")
    a = ap.parse_args()
    kb = va.load_knowledge_base()
    OPTIONS = kb[0] if isinstance(kb, tuple) else kb
    snap = snapshot()
    Path(a.snapshot).write_text(json.dumps(snap, indent=0, sort_keys=True))
    missing = [k for k, v in snap.items() if "YOUR VEP CONFIGURATION" not in v]
    print(f"{len(snap)} runs; {len(missing)} printed no configuration")
    if not a.diff:
        sys.exit(1 if missing else 0)
    old = json.loads(Path(a.diff).read_text())
    changed = [k for k in snap if snap[k] != old.get(k)]
    print(f"{len(changed)} of {len(snap)} outputs differ from {a.diff}")
    lines, examples = Counter(), {}
    for k in changed:
        for d in difflib.unified_diff(old.get(k, "").splitlines(), snap[k].splitlines(), lineterm="", n=0):
            if d.startswith(("---", "+++", "@@")):
                continue
            lines[d] += 1
            examples.setdefault(d, []).append(k)
    for d, n in lines.most_common():
        eg = ", ".join(examples[d][:a.show])
        print(f"  {n:5}  {d[:150]}\n         e.g. {eg}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
