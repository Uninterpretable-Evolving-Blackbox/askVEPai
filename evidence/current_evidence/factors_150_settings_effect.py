#!/usr/bin/env python3
"""The 150 tricky cases, scored on settings: does a misread change what the user is told to tick?

WHY. factors_150_tricky_cases.py scores labels: a query is right when the model's value for the tested
factor equals the truth. A label miss is not always a wrong configuration: [basic, clinical] and
[clinical] resolve to the same options, and origin moves no option on most tuples.
factors_31_review_scenarios.py scores its 31 rows the same way. This re-scores a saved results JSON of
the 150 cases, offline, no model.

HOW. For every (case, test type, read) where the label is wrong, the shipped run_recommend is called twice
with infer_factors stubbed: once with the true tuple (the case's background + the tested factor's truth),
once with the model's value in its place. Both use the real query text, so a build or organism named in
the prose reaches the checker exactly as it would for a user. clarify="state": unstated factors are filled
by the shipped policy and disclosed. The printed configuration is compared:

  RECOMMENDED   the lines under RECOMMENDED on every pass (what the user must tick)
  FULL          RECOMMENDED + OPTIONAL + NOT AVAILABLE + the two-run split
  DISCLOSURE    the set of "Assumed <factor> = ..." lines (a filled gap loses its disclosure)

LIMITS. Only the tested factor is swapped; background misreads are reported as a count, not scored (the
grid JSON keeps only whether the background was read right). The grid does not store the model's organism,
so a species case is compared on the organism the query text names (resolve_species_name), for both sides.

  python3 evidence/current_evidence/factors_150_settings_effect.py \
      evidence/current_evidence/results/factors_150_tricky_cases_reasoning_on.json [more.json ...] [--json out.json]
"""
import argparse, contextlib, io, json, os, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("PYTHONHASHSEED", "0")
import vep_assistant as va  # noqa: E402

TEST_TYPES = ("plain", "trap", "twin", "absent")
FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")
MULTI = {"variant_size_class", "region_focus", "analysis_goal"}


def as_value(f, v):
    """A grid value as the classifier would hand it to run_recommend with apply_defaults=False."""
    if f in MULTI:
        return list(v) if isinstance(v, (list, tuple)) else ([] if v in (None, "unstated", "") else [v])
    return v if v not in (None, "", []) else "unstated"


def norm(f, v):
    v = as_value(f, v)
    return tuple(sorted(v)) if f in MULTI else v


_cache = {}


def configuration(query, tup):
    """Run the shipped CLI path on a fixed tuple; return (recommended, full, disclosed) from stdout."""
    key = (query, json.dumps(tup, sort_keys=True))
    if key in _cache:
        return _cache[key]
    va.infer_factors = lambda *a, **k: dict(tup)
    va.save_result = lambda *a, **k: None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        va.run_recommend(None, "stub", OPTIONS, [], query, clarify="state")
    out = buf.getvalue()
    if "YOUR VEP CONFIGURATION" not in out:
        raise RuntimeError(f"no configuration printed for {tup} / {query[:60]}")
    rec, full, section = [], [], None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("RECOMMENDED"):
            section = "rec"
        elif s.startswith("OPTIONAL"):
            section = "opt"
        elif s.startswith("ALREADY ON") or s.startswith("=") or s.startswith("PASS ") or not s:
            section = None if not s.startswith("PASS ") else section
            if s.startswith("PASS "):
                rec.append(s); full.append(s)
            continue
        elif s.startswith("NOT AVAILABLE") or s.startswith("TWO VEP RUNS"):
            full.append(s)
            section = "na" if s.startswith("NOT AVAILABLE") else None
            continue
        if section == "rec" and not s.startswith("RECOMMENDED"):
            rec.append(s); full.append(s)
        elif section in ("opt", "na") and not s.startswith("OPTIONAL"):
            full.append(s)
    disclosed = frozenset(re.findall(r"^\s*Assumed (\w+) = (.+)$", out, re.M))
    res = (tuple(rec), tuple(full), disclosed)
    _cache[key] = res
    return res


def score_file(path):
    d = json.load(open(path))
    rows = d["rows"]
    per_query = []
    for r in rows:
        f = r["factor"]
        for t in TEST_TYPES:
            truth = r[f"{t}_truth"]
            for i, read in enumerate(r["result"][t]["model"]):
                label_ok = norm(f, read) == norm(f, truth)
                rec = {"id": r["id"], "factor": f, "trick": r["trick"], "test": t, "read_index": i,
                       "truth": truth, "read": read, "label_ok": label_ok,
                       "background_read_ok": r["result"][t]["background_read_ok"]}
                if label_ok:
                    rec.update(same_recommended=True, same_full=True, same_disclosure=True)
                else:
                    base = {k: as_value(k, v) for k, v in r["background"].items()}
                    base["_request_type"] = "configure"
                    t_tup = dict(base, **{f: as_value(f, truth)})
                    p_tup = dict(base, **{f: as_value(f, read)})
                    q = r[f"{t}_query"]
                    tr, tf, td = configuration(q, t_tup)
                    pr, pf, pd = configuration(q, p_tup)
                    rec.update(same_recommended=tr == pr, same_full=tf == pf, same_disclosure=td == pd,
                               recommended_only_truth=sorted(set(tr) - set(pr)),
                               recommended_only_read=sorted(set(pr) - set(tr)),
                               disclosure_lost=sorted(f"{a} = {b}" for a, b in td - pd))
                per_query.append(rec)
    return d, per_query


def summarise(path, d, per_query):
    n_reads = max(len(r["result"]["plain"]["model"]) for r in d["rows"])
    n_cases = len(d["rows"])
    print(f"\n=== {path}  ({d.get('model')}, reader {d.get('reader')}, {n_cases} cases x 4, reads/query {n_reads}) ===")
    by = Counter()
    for q in per_query:
        by["queries"] += 1
        by["label_ok"] += q["label_ok"]
        by["same_recommended"] += q["same_recommended"]
        by["same_full"] += q["same_full"]
        by["same_disclosure"] += q["same_disclosure"]
        by["background_misread"] += not q["background_read_ok"]
    nq = by["queries"]
    print(f"  queries: label right {by['label_ok']}/{nq}; RECOMMENDED unchanged {by['same_recommended']}/{nq}; "
          f"full configuration unchanged {by['same_full']}/{nq}; disclosure unchanged {by['same_disclosure']}/{nq}")
    print(f"  (background factors misread on {by['background_misread']}/{nq} queries: not scored here)")

    def case_ok(key):
        ids = {}
        for q in per_query:
            ids.setdefault(q["id"], True)
            ids[q["id"]] &= q[key]
        return sum(ids.values())
    print(f"  cases, all four right: label {case_ok('label_ok')}/{n_cases}; "
          f"RECOMMENDED {case_ok('same_recommended')}/{n_cases}; full {case_ok('same_full')}/{n_cases}")
    print(f"\n  {'factor':20} {'label':>9} {'recommended':>12} {'full':>9}   (queries of 120 per factor x reads)")
    for f in FACTORS:
        sel = [q for q in per_query if q["factor"] == f]
        print(f"  {f:20} {sum(q['label_ok'] for q in sel):>5}/{len(sel)} {sum(q['same_recommended'] for q in sel):>7}/{len(sel)}"
              f" {sum(q['same_full'] for q in sel):>5}/{len(sel)}")
    misses = [q for q in per_query if not q["label_ok"]]
    if misses:
        print(f"\n  label misses ({len(misses)}): does the user see a different configuration?")
        for q in misses:
            verdict = ("SAME ticks" if q["same_recommended"] else "DIFFERENT ticks")
            extra = ""
            if not q["same_recommended"]:
                extra = (f"  truth-only: {q['recommended_only_truth']}  read-only: {q['recommended_only_read']}")
            if q.get("disclosure_lost"):
                extra += f"  disclosure lost: {q['disclosure_lost']}"
            print(f"    {q['id']:16} {q['test']:6} truth {json.dumps(q['truth']):34} read {json.dumps(q['read']):34} {verdict}{extra}")
    return {"file": str(path), "model": d.get("model"), "reader": d.get("reader"), "n_cases": n_cases,
            "reads_per_query": n_reads, "totals": dict(by),
            "cases_all_four": {k: case_ok(k) for k in ("label_ok", "same_recommended", "same_full")},
            "misses": misses}


def main():
    global OPTIONS
    ap = argparse.ArgumentParser()
    ap.add_argument("grid_json", nargs="+")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    kb = va.load_knowledge_base()
    OPTIONS = kb[0] if isinstance(kb, tuple) else kb
    out = []
    for p in a.grid_json:
        d, pq = score_file(p)
        out.append(summarise(p, d, pq))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
