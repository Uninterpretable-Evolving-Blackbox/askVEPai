#!/usr/bin/env python3
"""Score a recommendation by what each error DOES to the output, not by counting options.

WHY. enable-F1 treats every option as one unit. But a volunteered `pick` deletes 96% of a user's rows
and a volunteered `uniprot` adds one ignorable column, while a missed `mane` costs a navigation flag
the user needed. The dossier (`research/output_effects_dossier.md` §1) classes every option by its
documented effect; this scores errors by class. It is the candidate replacement for enable-F1 that
item 11 of the round-2 sheet asked for, and it is undefined on nothing: it needs only the shown set
and the gold set, so it works for single-pass, two-pass and any external model.

WEIGHTS (proposed 2026-09-15, to be looked at before they are quoted):
    extra option that REMOVES ROWS         5.0   the one error that deletes findings
    extra option that adds a real column   0.25  a column the user ignores
    extra option already ON on the form    0.0   changes no file
    missing option that adds a real column 1.0   an annotation the user needed
    missing option already ON on the form  0.0   they had it anyway
    missing/extra with no output verdict   1.0   unknown -> counted like a real column
Weighted precision and recall follow from the weighted true/false positives; F1 as usual.

INPUT. The four-arm ablation JSON (`results/singlepass_2026-09-09/pass_corpus_ablation.json`, and the
overnight repeats) already carries, per row and arm, the shown set's `extra` and `missing` against the
true-tuple gold. That is everything this needs.

  python3 work/harness/class_weighted_f1.py [results/.../pass_corpus_ablation.json ...]
"""
import json, os, sys, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo")); sys.path.insert(0, str(ROOT / "work" / "harness"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

REMOVES_ROWS = {"coding_only", "most_severe", "summary", "per_gene", "pick", "pick_allele", "frequency"}
W = {"extra_rows": 5.0, "extra_column": 0.25, "extra_on": 0.0,
     "missing_column": 1.0, "missing_on": 0.0, "unknown": 1.0}


def classes(catalogue):
    on = {o["id"] for o in catalogue if o.get("web_default_on")}
    name2id = {o["name"]: o["id"] for o in catalogue}
    name2id.update({o["id"]: o["id"] for o in catalogue})
    return on, name2id


def weight(oid, kind, on):
    if kind == "extra":
        if oid in REMOVES_ROWS: return W["extra_rows"]
        if oid in on: return W["extra_on"]
        return W["extra_column"]
    if oid in on: return W["missing_on"]
    return W["missing_column"]


def score_row(gold_n, extra, missing, on, name2id):
    extra = [name2id.get(x, x) for x in extra]; missing = [name2id.get(x, x) for x in missing]
    fp = sum(weight(o, "extra", on) for o in extra)
    fn = sum(weight(o, "missing", on) for o in missing)
    # true positives: gold minus missing, each worth its own missing-weight (what it would have cost)
    tp_n = gold_n - len(missing)
    tp = tp_n * W["missing_column"]        # gold options are real columns by construction of the table
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return f1, fp, fn


def main():
    files = sys.argv[1:] or [str(ROOT / "work/results/singlepass_2026-09-09/pass_corpus_ablation.json")]
    catalogue, _ = va.load_knowledge_base(); on, name2id = classes(catalogue)
    print(f"weights: {W}\n")
    for f in files:
        d = json.load(open(f)); rows = d["rows"] if isinstance(d, dict) else d
        arms = sorted({a for r in rows for a in r["arms"]})
        print(f"== {Path(f).name}: {len(rows)} rows ==")
        print(f"  {'arm':10} {'plain F1':>9} {'weighted F1':>12} {'row-deleting extras':>20} {'real cols missed':>17}")
        for a in arms:
            plain, wf1, rowdel, missed = [], [], 0, 0
            for r in rows:
                x = r["arms"].get(a) or {}
                if x.get("f1") is None: continue
                plain.append(x["f1"])
                f1, fp, fn = score_row(r["n_gold"], x.get("extra") or [], x.get("missing") or [], on, name2id)
                wf1.append(f1)
                rowdel += sum(1 for o in (x.get("extra") or []) if name2id.get(o, o) in REMOVES_ROWS)
                missed += sum(1 for o in (x.get("missing") or []) if name2id.get(o, o) not in on)
            print(f"  {a:10} {st.mean(plain):9.3f} {st.mean(wf1):12.3f} {rowdel:20d} {missed:17d}")
        print()
    print("  plain F1 counts options; weighted F1 prices a volunteered row-deleter at 5 and an extra column at 0.25,")
    print("  and prices anything the form already ships ticked at 0 in both directions.")


if __name__ == "__main__":
    main()
