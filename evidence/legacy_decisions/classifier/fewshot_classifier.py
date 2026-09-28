#!/usr/bin/env python3
"""Does few-shot help the FACTOR CLASSIFIER? 31-row LOO, tuples only.

WHY THIS IS THE MISSING ARM. `FACTOR_CLASSIFIER_PROMPT` is 1545 characters and zero-shot: a schema,
prose guidance per factor, then the query. Not one worked example. Every examples experiment in the
ledger (Exp 11's 62% -> 85%, Exp 9's ordering, the corpus sweep) put examples in the SECOND call's
prompt, and the second call's draft is rebuilt by the checker. Under `--single-pass` the classifier
is the only thing the model decides, so this is the one place examples could still matter.

The overnight `hint` arm is a different thing: it showed the model a keyword rule's MATCHES. This
shows it worked query -> tuple pairs.

TUPLES ONLY, NOT CONFIGURATIONS. The classifier's job is the five factor values; showing it option
sets would teach the draft task it no longer performs.

LOO throughout: the row under test is never in its own prompt. Same masking as
`eval_factor_set.py:183`.

THE HYPOTHESIS WORTH NAMING BEFORE LOOKING. `analysis_goal` is the weak factor (24/31), and 5 of 7
misses are one pattern: truth carries `basic-consequence` alongside another goal, the model returns
only the other. The prompt INSTRUCTS that ("Use basic-consequence only when the question really is
just 'what are these variants'"), so the gold and the prompt disagree. Few-shot should fix that by
teaching the gold's convention -- an accuracy gain that is really a convention alignment, and worth
labelling as such rather than as better understanding.

  NO_PROXY=localhost,127.0.0.1 python3 evidence/legacy_decisions/classifier/fewshot_classifier.py --shots 0,3,8,30
"""
import argparse, json, os, random, statistics as st, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

FACTORS = ("species", "origin", "variant_size_class", "region_focus", "analysis_goal")


def norm(v):
    return tuple(sorted(v)) if isinstance(v, list) else ((v,) if v else ())


def f1(p, g):
    if not p or not g:
        return 0.0
    ov = len(p & g)
    if not ov:
        return 0.0
    pr, rc = ov / len(p), ov / len(g)
    return 2 * pr * rc / (pr + rc)


def shot_block(rows, k, seed):
    """k worked query -> tuple pairs, sampled from the LOO pool with a fixed seed."""
    if k == 0:
        return ""
    rnd = random.Random(seed)
    pick = rows if k >= len(rows) else rnd.sample(rows, k)
    # DELIMITERS MATTER. The first version labelled each example "Question: " -- the exact marker
    # the live query is appended after -- so the model saw N indistinguishable blocks and had to
    # infer which one it was being asked about from position alone. Exact tuples fell 22 -> 12 as
    # shots rose, which is as consistent with that ambiguity as with few-shot being harmful.
    # Examples are now fenced and the live query is announced separately.
    out = ["\n=== SOLVED EXAMPLES (for reference only — do NOT classify these) ==="]
    for i, r in enumerate(pick, 1):
        fl = {f: r["factor_labels"].get(f) for f in FACTORS}
        out.append(f"\n--- example {i} ---\nINPUT: {r['user_query'][:400]}\n"
                   f"CORRECT OUTPUT: {json.dumps(fl)}")
    out.append("\n=== END OF EXAMPLES ===\n\nNow classify the question below, and only that one.\n")
    return "\n".join(out)


def classify(client, model, query, shots, seed):
    """The shipped classifier call with the shot block spliced in before the query."""
    base = va.FACTOR_CLASSIFIER_PROMPT
    tail = "Question: "
    head = base[: base.rindex(tail)] if tail in base else base
    prompt = head + shots + "\n" + tail + (query or "")
    resp = client.chat.completions.create(
        model=model, temperature=0.0, seed=seed,
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": "Return the JSON classification."}])
    return va.parse_factor_classification(resp.choices[0].message.content or "")


def enabled_from(tuple_, cat, ex, query):
    resolved = va.resolve_for_query(tuple_, cat) or {}
    en, dis = set(), set()
    va.restore_missing_recommended(en, dis, resolved, cat, query)
    return en


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--shots", default="0,3,8,30")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--json", default=str(ROOT / "evidence/legacy_decisions/classifier/results/fewshot_classifier.json"))
    args = ap.parse_args()
    client = OpenAI(base_url=args.base_url, api_key="ollama")
    cat, legacy = va.load_knowledge_base()
    rows = json.load(open(ROOT / "data/iced.json"))
    ks = [int(x) for x in args.shots.split(",")]
    out = {"model": args.model, "seed": args.seed, "shots": ks, "arms": {}}

    for k in ks:
        per, t0 = [], time.perf_counter()
        for r in rows:
            pool = [x for x in rows if x["id"] != r["id"]]              # LOO
            got = classify(client, args.model, r["user_query"],
                           shot_block(pool, k, args.seed), args.seed)
            if got is None:
                per.append({"id": r["id"], "fail": True})
                continue
            truth = r["factor_labels"]
            hit = {f: norm(got.get(f)) == norm(truth.get(f)) for f in FACTORS}
            gold = enabled_from(truth, cat, legacy, r["user_query"])
            # the shipped species override is NOT applied: this measures the classifier
            pred = enabled_from({**got, "analysis_goal": got.get("analysis_goal") or
                                 ["basic-consequence"]}, cat, legacy, r["user_query"])
            per.append({"id": r["id"], "hit": hit, "exact": all(hit.values()),
                        "e2e": f1(pred, gold)})
        ok = [p for p in per if not p.get("fail")]
        out["arms"][str(k)] = {
            "n_ok": len(ok), "n_fail": len(per) - len(ok),
            **{f: sum(p["hit"][f] for p in ok) for f in FACTORS},
            "exact": sum(p["exact"] for p in ok),
            "e2e": st.mean(p["e2e"] for p in ok) if ok else 0.0,
            "secs": round(time.perf_counter() - t0, 1), "rows": per}
        a = out["arms"][str(k)]
        print(f"  {k:2d}-shot: exact {a['exact']:2d}/{a['n_ok']}  e2e {a['e2e']:.3f}  "
              f"goal {a['analysis_goal']:2d}  fail {a['n_fail']}  {a['secs']:.0f}s", flush=True)

    print(f"\n=== {args.model}, 31 rows LOO, seed {args.seed} ===\n")
    print(f"  {'shots':>6s} " + " ".join(f"{f[:9]:>10s}" for f in FACTORS)
          + f" {'exact':>7s} {'e2e F1':>8s} {'fail':>5s}")
    for k in ks:
        a = out["arms"][str(k)]
        print(f"  {k:6d} " + " ".join(f"{a[f]:10d}" for f in FACTORS)
              + f" {a['exact']:7d} {a['e2e']:8.3f} {a['n_fail']:5d}")
    Path(args.json).write_text(json.dumps(out, indent=1))
    print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
