#!/usr/bin/env python3
"""Lay the existing test cases out as a CheckList matrix: capability x test type.

WHY. The project has 219 test cases across five files and reports one aggregate per file -- "model
24/24", "76/78 disclosed". CheckList's contribution (Ribeiro et al., ACL 2020) is not the idea of
writing edge cases, it is reporting a failure rate PER CAPABILITY PER TEST TYPE, so a result says
which behaviour is weak instead of only how many cases passed. A 24/24 cannot do that.

THE THREE TEST TYPES are the paper's, quoted:
  MFT  minimum functionality -- simple prototypical examples testing one capability in isolation
  INV  invariance -- "Tests if the model's prediction remains unchanged when the input is perturbed
       in ways that should not affect the expected output."
  DIR  directional expectation -- "Tests if the model's prediction changes in the expected direction
       when the input is perturbed."

THE CAPABILITY AXIS IS OURS, AND IT IS POST-HOC. CheckList's own axis (vocabulary, negation, NER,
coreference, ...) is generic NLP. Ours is derived by clustering the `why` strings already written on
the 24 traps -- written before anyone was thinking about capabilities, which is the only thing that
makes the clustering worth anything. It is still circular in a way the paper's axis is not, and any
write-up has to say so: the capabilities were read off our own failures, not from an independent
taxonomy, so the matrix shows coverage of the failures we already knew about.

  python3 evidence/legacy_superseded/keyword_traps/checklist_matrix.py            # the grid
  python3 evidence/legacy_superseded/keyword_traps/checklist_matrix.py --cases    # every case with its labels
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

MFT, INV, DIR = "MFT", "INV", "DIR"

CAPABILITIES = {
    "plain": "the cue is present, literal and correct — nothing adversarial",
    "negation": "the cue appears inside a negation or disclaimer",
    "entity-attachment": "the cue is real but attached to something that is not the sample",
    "domain-inference": "the cue is present and technically overridden by domain knowledge",
    "tool-or-database": "the cue is the name of a tool or database, not the organism or data",
    "word-sense": "the cue is an idiom or an ordinary English word in another sense",
    "absent": "the cue has been removed from the text entirely",
}

# Clustering rules over the trap `why` strings, longest-match first. Each maps a phrase actually
# written in factor_traps.py to a capability. Anything unmatched is reported, never silently binned.
WHY_RULES = [
    (r"negated|disclaimed|were removed|deferred elsewhere", "negation"),
    # NAME COLLISION ONLY. "Salmon" is genuinely two things -- a fish Ensembl serves and a
    # quantification tool -- so the model has to choose. COSMIC and Manta are NOT ambiguous: everyone
    # knows what they are, and the trap is that they are mentioned without being where the data came
    # from. That is attachment, not ambiguity, so they move to entity-attachment below (David spotted
    # this on 2026-09-15; the first clustering put all three here on the word "tool").
    (r"quantification tool|also a bioinformatics tool name", "tool-or-database"),
    (r"is a person|idiomatic|rabbit hole|guinea pig|mascot", "word-sense"),
    (r"names the registry|family history|discarded half|is cells, not people"
     r"|about the pipeline|is the clinical cohort"
     r"|database the user browses|whose output was discarded", "entity-attachment"),
    (r"at 1 bp|breakpoint resolution|cues small|cues non.coding|is a germline cue", "domain-inference"),
]


def cap_from_why(why):
    for pat, cap in WHY_RULES:
        if re.search(pat, why, re.I):
            return cap
    return None


def load_module_cases(path, mod_name):
    """Import a harness and return its CASES list without running it."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))                        # factor_traps
    sys.path.insert(0, str(ROOT / "evidence" / "legacy_decisions" / "classifier"))     # species_recall_hint
    sys.path.insert(0, str(ROOT / "evidence" / "legacy_decisions" / "missing_facts"))            # score_try_queries
    sys.path.insert(0, str(ROOT / "vep_ai_demo"))
    import os
    os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
    import importlib
    return importlib.import_module(mod_name).CASES


def collect():
    rows = []

    # ---- factor_traps: 24 cases, all INV. The cue is present and wrong; the answer must not move.
    for f, truth, q, why in load_module_cases(None, "factor_traps"):
        cap = cap_from_why(why)
        rows.append({"src": "factor_traps", "type": INV, "cap": cap or "UNMATCHED",
                     "factor": f, "why": why, "query": q})

    # ---- species_recall_hint: 20 cases. The 14 non-human ones are MFT (name the organism plainly
    #      and see if it is recognised); the 6 human controls split by why they are there.
    for q, truth, why in load_module_cases(None, "species_recall_hint"):
        if truth == "non-human":
            rows.append({"src": "species_recall", "type": MFT, "cap": "plain",
                         "factor": "species", "why": why, "query": q})
        else:
            cap = cap_from_why(why) or "plain"
            rows.append({"src": "species_recall", "type": INV if cap != "plain" else MFT,
                         "cap": cap, "factor": "species", "why": why, "query": q})

    # ---- score_try_queries: 20 scenarios, hand-labelled by the note each carries.
    for q, exp, scope, note in load_module_cases(None, "score_try_queries"):
        if exp is None:
            rows.append({"src": "try_queries", "type": MFT, "cap": "plain",
                         "factor": "request_type", "why": note, "query": q})
            continue
        cap = cap_from_why(note)
        if cap is None:
            cap = "plain" if "stated" in note or "buried" in note else "plain"
            t = MFT
        else:
            t = INV
        rows.append({"src": "try_queries", "type": t, "cap": cap, "factor": "-",
                     "why": note, "query": q})

    # ---- the ablations: the cue is REMOVED, so the answer must move to unstated. That is DIR, and
    #      the capability is `absent` -- a different thing from every trap, which keeps the cue in.
    abl = json.load(open(ROOT / "data/ablated_queries.json"))
    for a in abl:
        rows.append({"src": "ablations", "type": DIR, "cap": "absent",
                     "factor": a["target"], "why": f"target removed, pure={a['pure']}",
                     "query": a.get("ablated", "")[:80]})

    # ---- the review rows: every factor stated outright.
    iced = json.load(open(ROOT / "data/iced.json"))
    for r in iced:
        rows.append({"src": "review_rows", "type": MFT, "cap": "plain", "factor": "all",
                     "why": "every factor stated in the query", "query": r["user_query"][:80]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", action="store_true", help="list every case with its labels")
    a = ap.parse_args()
    rows = collect()

    print(f"{len(rows)} cases across {len(set(r['src'] for r in rows))} files\n")
    grid = defaultdict(int)
    for r in rows:
        grid[(r["cap"], r["type"])] += 1

    caps = [c for c in CAPABILITIES if any(grid[(c, t)] for t in (MFT, INV, DIR))]
    caps += sorted({r["cap"] for r in rows} - set(CAPABILITIES))
    print(f"{'capability':20} {'MFT':>6} {'INV':>6} {'DIR':>6}    what it tests")
    print("-" * 96)
    for c in caps:
        cells = [grid[(c, t)] for t in (MFT, INV, DIR)]
        marks = "  ".join(f"{n:>4}" if n else "   ." for n in cells)
        print(f"{c:20} {marks}    {CAPABILITIES.get(c, '(unmatched — needs a rule)')}")
    print("-" * 96)
    tot = [sum(grid[(c, t)] for c in caps) for t in (MFT, INV, DIR)]
    print(f"{'TOTAL':20} " + "  ".join(f"{n:>4}" for n in tot))

    empty = [(c, t) for c in caps for t in (MFT, INV, DIR) if not grid[(c, t)]]
    print(f"\nEMPTY CELLS: {len(empty)} of {len(caps)*3}")
    for c, t in empty:
        print(f"   {c:20} {t}")

    unmatched = [r for r in rows if r["cap"] == "UNMATCHED"]
    if unmatched:
        print(f"\nUNMATCHED `why` strings ({len(unmatched)}) — the clustering rules need extending:")
        for r in unmatched:
            print(f"   {r['src']:16} {r['why']}")

    print("\nby source:")
    for s, n in Counter(r["src"] for r in rows).most_common():
        ts = Counter(r["type"] for r in rows if r["src"] == s)
        print(f"   {s:16} {n:>4}   {dict(ts)}")

    if a.cases:
        print("\n" + "=" * 96)
        for r in sorted(rows, key=lambda x: (x["cap"], x["type"])):
            print(f"  {r['cap']:18} {r['type']}  {r['src']:15} {r['why'][:64]}")


if __name__ == "__main__":
    main()
