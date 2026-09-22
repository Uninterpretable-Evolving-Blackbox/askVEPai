#!/usr/bin/env python3
"""Single vs two pass, crossed with what corpus the second pass is shown. 31-row LOO.

ARMS
  single      --single-pass. No corpus reaches any prompt: the draft call is skipped entirely.
  two_none    two-pass, empty corpus. Isolates the draft itself from the examples.
  two_23      two-pass, the 23 shipped `training_examples.json` -- the legacy simulated set, keyed by
              the RETIRED seven-use-case scheme.
  two_31loo   two-pass, the other 30 factor rows as the corpus, the row under test MASKED.

METRIC. F1 of the RECOMMENDED block the user is shown against the configuration resolved from that
row's OWN TRUE factor tuple. Same gold for every arm, so the arms are comparable.

Not scored against the table generically: the checker rebuilds the table's answer from the tuple, so
that comparison returns ~1.0 for any arm and measures the resolver against itself.

TWO CAVEATS ON `two_31loo`, both worth reporting rather than hiding.
  1. The 31 rows' stored configs have drifted 133 option-instances from the live table (handover §5),
     so this corpus teaches configurations the table no longer produces.
  2. Their `use_case_category` is null, so `_detect_use_case` -- which keyword-matches the query
     against the corpus to pick a legacy use case, and whose result RANKS options in conflict
     resolution -- gets nothing. That is a real difference between arms, not noise.

  NO_PROXY=localhost,127.0.0.1 python3 work/harness/exp/pass_and_corpus_ablation.py
"""
import argparse, json, os, re, statistics as st, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

BLOCK = re.compile(r"^RECOMMENDED —.*?\[(\d+)\]\n(.*?)(?=\n(?:OPTIONAL|ALREADY ON|=====)|\Z)", re.S | re.M)
# Since 2026-09-14 options the form ships ticked are listed once under ALREADY ON instead of inside
# RECOMMENDED. They are still ENABLED, and gold (resolve + restore) still contains them, so they must
# be counted as shown or every arm's F1 drops together and the number stops matching Exp 20.
ALREADY = re.compile(r"^ALREADY ON when the form loads.*?\[(\d+)\]\n\s*(.*?)$", re.M)



def block_names(stdout):
    m = BLOCK.search(stdout)
    if not m:
        return None
    out = []
    for line in m.group(2).split("\n"):
        if not line.strip() or line.startswith("      "):
            continue
        # strip the trailing "   (Section section)" and any "(add-on)"/"(model-suggested)" tag
        out.append(re.split(r"\s{2,}\(", line.strip())[0])
    a = ALREADY.search(stdout)
    if a:
        out.extend(n.strip() for n in a.group(2).split(",") if n.strip())
    return set(out)


DEFAULTS = frozenset()   # names of the form's ticked-by-default options; set in main()


def form_default_names(catalogue):
    """Options the web form ships ticked. Excluded from BOTH sides of the plain F1 since 2026-09-15:
    the display lists them once under ALREADY ON (enabled and merely offered alike), so they cannot be
    read back as enabled-or-not, and they cannot change the user's file either way. Exp 20's 0.898
    counted them; the number of record from here on does not, and says so."""
    return frozenset(o.get("name", o["id"]) for o in catalogue if o.get("web_default_on"))


def gold_names(row, catalogue, examples):
    """The names the user WOULD see for this row's true factor tuple, minus the form defaults."""
    resolved = va.resolve_for_query(row["factor_labels"], catalogue) or {}
    en, dis = set(), set()
    va.restore_missing_recommended(en, dis, resolved, catalogue, row["user_query"])
    by_id = {o["id"]: o.get("name", o["id"]) for o in catalogue}
    return {by_id.get(o, o) for o in en} - DEFAULTS


def f1(p, g):
    if not p or not g:
        return 0.0
    ov = len(p & g)
    if not ov:
        return 0.0
    pr, rc = ov / len(p), ov / len(g)
    return 2 * pr * rc / (pr + rc)


def run(query, model, single, examples_path):
    env = dict(os.environ, VEP_MODEL=model, VEP_FACTOR_MODEL=model)
    if examples_path:
        env["VEP_EXAMPLES_FILE"] = examples_path
    cmd = ["python3", "-u", "vep_assistant.py"] + (["--single-pass"] if single else ["--two-pass"]) + [query]
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=ROOT / "vep_ai_demo", env=env,
                       capture_output=True, text=True, timeout=900)
    names = block_names(p.stdout)
    return (names - DEFAULTS if names is not None else None), time.perf_counter() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--json", default=str(ROOT / "work/results/pass_corpus_ablation.json"))
    args = ap.parse_args()
    catalogue, legacy = va.load_knowledge_base()
    global DEFAULTS
    DEFAULTS = form_default_names(catalogue)
    rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
    tmp = Path(tempfile.mkdtemp())
    (tmp / "none.json").write_text("[]")
    legacy_path = str(ROOT / "vep_ai_demo" / "legacy" / "training_examples.json")

    ARMS = ["single", "two_none", "two_23", "two_31loo"]
    res = []
    for i, r in enumerate(rows, 1):
        gold = gold_names(r, catalogue, legacy)
        # LOO corpus: the other 30 rows, this one masked
        # The factor rows carry neither `use_case_category` nor `justification`. Rather than invent
        # prose, the use-case line states the row's own factor tuple -- which is what the row IS --
        # and the rationale is left empty.
        loo = []
        for x in rows:
            if x["id"] == r["id"]:
                continue                                   # LOO: mask the row under test
            fl = x["factor_labels"]
            loo.append({**x,
                        "use_case_category": ", ".join(
                            f"{k}={','.join(v) if isinstance(v, list) else v}"
                            for k, v in fl.items()),
                        "justification": x.get("justification") or ""})
        loo_path = tmp / f"loo_{i}.json"
        loo_path.write_text(json.dumps(loo))
        got = {}
        for arm in ARMS:
            single = arm == "single"
            ex = {"single": None, "two_none": str(tmp / "none.json"),
                  "two_23": legacy_path, "two_31loo": str(loo_path)}[arm]
            names, secs = run(r["user_query"], args.model, single, ex)
            got[arm] = {"n": len(names) if names else None,
                        "f1": round(f1(names, gold), 4) if names else None,
                        "secs": round(secs, 1),
                        "extra": sorted(names - gold) if names else None,
                        "missing": sorted(gold - names) if names else None}
        res.append({"id": r["id"], "n_gold": len(gold), "arms": got})
        print(f"{i:3d} gold={len(gold):2d} " + "  ".join(
            f"{a}={got[a]['f1'] if got[a]['f1'] is not None else 'FAIL'}" for a in ARMS), flush=True)
        Path(args.json).write_text(json.dumps(res, indent=1))

    print(f"\n=== {len(res)} rows, {args.model}, gold = each row's TRUE-tuple config ===\n")
    print(f"  {'arm':11s} {'F1':>7s} {'options':>8s} {'extra':>7s} {'missing':>8s} {'secs':>7s}")
    for a in ARMS:
        ok = [x["arms"][a] for x in res if x["arms"][a]["f1"] is not None]
        print(f"  {a:11s} {st.mean(v['f1'] for v in ok):7.3f} "
              f"{st.mean(v['n'] for v in ok):8.1f} "
              f"{st.mean(len(v['extra']) for v in ok):7.2f} "
              f"{st.mean(len(v['missing']) for v in ok):8.2f} "
              f"{st.mean(v['secs'] for v in ok):7.1f}")
    print("\n  extra   = options shown that the row's true tuple does NOT call for")
    print("  missing = options the true tuple calls for that were not shown")
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
