#!/usr/bin/env python3
"""Does removing the second model call change what the user receives? 31 rows, both paths.

Runs the shipped CLI twice per row -- once normally, once with --single-pass -- and diffs the
rendered RECOMMENDED block, which is what is on screen.

Expectation, from `restore_missing_recommended` reconstructing the set from the factor tuple: the
CORE is identical and the two-pass run carries extra options the priority table prices for nothing.
Those unpriced extras are the `pick` class the output has to tag and cap, so losing them is the
point rather than the cost. Anything else that differs is a finding.

  NO_PROXY=localhost,127.0.0.1 python3 work/harness/singlepass_vs_twopass.py
"""
import argparse, json, os, re, subprocess, statistics as st, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOCK = re.compile(r"^RECOMMENDED —.*?\[(\d+)\]\n(.*?)(?=\n(?:OPTIONAL|=====)|\Z)", re.S | re.M)


def run(query, model, single):
    env = dict(os.environ, VEP_MODEL=model, VEP_FACTOR_MODEL=model)
    cmd = ["python3", "-u", "vep_assistant.py"] + (["--single-pass"] if single else ["--two-pass"]) + [query]
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=ROOT / "vep_ai_demo", env=env,
                       capture_output=True, text=True, timeout=900)
    el = time.perf_counter() - t
    m = BLOCK.search(p.stdout)
    if not m:
        return None, None, el, p.stdout[-160:]
    names = [l.strip() for l in m.group(2).split("\n")
             if l.strip() and not l.startswith("      ")]
    return int(m.group(1)), names, el, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--json", default=str(ROOT / "work/results/singlepass_vs_twopass.json"))
    args = ap.parse_args()
    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    res = []
    for i, r in enumerate(rows, 1):
        q = r["user_query"]
        n2, two, t2, e2 = run(q, args.model, False)
        n1, one, t1, e1 = run(q, args.model, True)
        if two is None or one is None:
            print(f"{i:3d} PARSE FAIL", flush=True)
            res.append({"id": r["id"], "fail": True})
            continue
        s2, s1 = set(two), set(one)
        res.append({"id": r["id"], "n_two": n2, "n_single": n1,
                    "identical": s2 == s1, "core_subset": s1 <= s2,
                    "only_two": sorted(s2 - s1), "only_single": sorted(s1 - s2),
                    "secs_two": round(t2, 1), "secs_single": round(t1, 1)})
        print(f"{i:3d} two={n2:3d}({t2:5.1f}s) single={n1:3d}({t1:4.1f}s) "
              f"single⊆two={s1 <= s2!s:5s} only_two={len(s2-s1)} only_single={len(s1-s2)}",
              flush=True)
        Path(args.json).write_text(json.dumps(res, indent=1))
    ok = [x for x in res if not x.get("fail")]
    print(f"\n=== {len(ok)}/{len(rows)} compared, {args.model} ===")
    print(f"  identical block          {sum(x['identical'] for x in ok)}/{len(ok)}")
    print(f"  single-pass ⊆ two-pass   {sum(x['core_subset'] for x in ok)}/{len(ok)}"
          "   <- the core survives; two-pass only ADDS")
    print(f"  mean options  two={st.mean(x['n_two'] for x in ok):.1f}"
          f"  single={st.mean(x['n_single'] for x in ok):.1f}")
    print(f"  mean latency  two={st.mean(x['secs_two'] for x in ok):.1f}s"
          f"  single={st.mean(x['secs_single'] for x in ok):.1f}s")
    from collections import Counter
    c = Counter(o.split("  ")[0] for x in ok for o in x["only_two"])
    print("\n  options ONLY the two-pass run adds (the unpriced extras):")
    for k, v in c.most_common(10):
        print(f"    {v:2d}x  {k}")
    c2 = Counter(o.split("  ")[0] for x in ok for o in x["only_single"])
    if c2:
        print("\n  options ONLY the single-pass run has (should be empty):")
        for k, v in c2.most_common(6):
            print(f"    {v:2d}x  {k}")
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
