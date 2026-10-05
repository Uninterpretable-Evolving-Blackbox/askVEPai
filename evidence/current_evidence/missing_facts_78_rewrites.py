#!/usr/bin/env python3
"""Does a MISSING factor reach the fallback we decided, end to end, through the shipped CLI?

WHY. The assume/ask policy is tested deterministically (test_user_context, defaults_evidence,
ask_rate) by handing it a tuple with a gap already in it. Nothing tests the live chain: cue absent in
the PROSE -> the classifier says `unstated` rather than inventing a value -> `resolve_underspecified`
applies the fallback -> the output discloses it. If the classifier fills the gap itself, the policy is
bypassed silently and the disclosure never prints. That bypass is what this measures.

INPUT. The 78 PURE rows of `ablated_queries.json`: one factor's cue rewritten out of a review row.
For each, the shipped CLI runs (single-pass default, assume mode, disclosure on) and the output is
parsed for `Assumed <factor> = <value>` and the `Detected scenario` block.

PER ROW, on the removed factor:
  FALLBACK   an `Assumed <target> = ...` line printed and the detected value is the policy default
  FILLED     no Assumed line; the classifier returned a value on its own (policy bypassed)
  OTHER      anything else (asked, error, unparseable) -- printed for inspection
Species has no disclosure line in the CLI (the rule maps unknown -> human silently), so for species
rows FILLED means "read as human with no disclosure", which is the Exp 18 masking, now end to end.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/current_evidence/missing_facts_78_rewrites.py [--reader reasoning_on|reasoning_off] [--limit N]
"""
import argparse, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = {"origin": "somatic", "variant_size_class": "small, structural-CNV",
          "region_focus": "coding, regulatory-noncoding", "analysis_goal": "basic-consequence",
          "species": "human"}


def run_cli(model, query, reasoning_on=True):
    env = dict(os.environ, VEP_MODEL=model, VEP_FACTOR_MODEL=model, NO_PROXY="localhost,127.0.0.1",
               VEP_FACTOR_THINK="1" if reasoning_on else "0")
    # stdin closed: the tool asks only on a terminal, and a question here would block unseen.
    p = subprocess.run([sys.executable, "vep_assistant.py", query], cwd=ROOT / "vep_ai_demo",
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=300)
    return p.returncode, p.stdout + p.stderr


def parse(out):
    # The CLI prints the value only since 2026-09-15 ("Assumed origin = somatic"); the old form
    # carried " — <reason>" after it. Accept both.
    assumed = dict(re.findall(r"^\s*Assumed (\w+) = (.+?)(?: —.*)?$", out, re.M))
    # Since 2026-10-05 each value carries its source: "somatic (assumed)", "small (from your text)".
    detected = {k: re.sub(r" \((?:assumed|from your text|you said|you answered)\)$", "", v)
                for k, v in re.findall(r"^- (\w+): (.+)$", out, re.M)}
    return assumed, detected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reader", choices=("reasoning_on", "reasoning_off"), default="reasoning_on",
                    help="reasoning_on = the tool's setting; reasoning_off = the same tool with reasoning off")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    a.json = a.json or str(ROOT / f"evidence/current_evidence/results/missing_facts_78_rewrites_{a.reader}.json")
    rows = [r for r in json.load(open(ROOT / "evidence/current_evidence/cases/ablated_queries.json")) if r["pure"]]
    if a.limit:
        rows = rows[:a.limit]
    tally = defaultdict(Counter); detail = []
    for i, r in enumerate(rows, 1):
        t = r["target"]
        rc, out = run_cli(a.model, r["ablated"], a.reader == "reasoning_on")
        assumed, detected = parse(out)
        got = detected.get(t, "?")
        if rc != 0:
            verdict = "OTHER(exit)"
        elif t in assumed:
            verdict = "FALLBACK" if got.strip() == POLICY[t] else f"OTHER(assumed={got})"
        elif t == "species":
            verdict = "FILLED(no disclosure)" if got.strip() == "human" else f"OTHER({got})"
        else:
            verdict = "FILLED" if got not in ("?", "unstated") else f"OTHER({got})"
        tally[t][verdict] += 1
        detail.append({"row": r["row"], "target": t, "verdict": verdict, "detected": got,
                       "assumed_line": assumed.get(t), "read_after": r.get("read_after", {}).get(t)})
        print(f"  {i:3d}/{len(rows)} row {r['row']:2d} {t:20} {verdict:24} detected={got}", flush=True)
    print(f"\n=== {len(rows)} rewrites with one fact removed, the tool as shipped, {a.model}, {a.reader} ===")
    print(f"  {'removed factor':20} {'FALLBACK':>9} {'FILLED':>8} {'other':>6}   policy default")
    for t in ("origin", "variant_size_class", "region_focus", "analysis_goal", "species"):
        c = tally[t]; fb = c.get("FALLBACK", 0); fi = sum(v for k, v in c.items() if k.startswith("FILLED"))
        oth = sum(c.values()) - fb - fi
        print(f"  {t:20} {fb:>9} {fi:>8} {oth:>6}   {POLICY[t]}")
    print("\n  FALLBACK = classifier said unstated, the decided default was applied AND disclosed.")
    print("  FILLED   = classifier supplied a value for a cue the text no longer has: policy bypassed.")
    Path(a.json).write_text(json.dumps({"model": a.model, "reader": a.reader, "tally": {k: dict(v) for k, v in tally.items()},
                                        "rows": detail}, indent=1))
    print(f"  wrote {a.json}")


if __name__ == "__main__":
    main()
