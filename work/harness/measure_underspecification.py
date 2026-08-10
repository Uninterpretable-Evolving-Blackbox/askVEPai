#!/usr/bin/env python3
"""How often does a real VEP question leave a factor open, and does it matter?

This replaces a measurement that turned out to be unsound. The old one ran on twenty hand-transcribed
questions; checking them against their sources showed none of the nine flagged `verbatim` actually was,
and five had VEP command lines removed — which makes a question look more under-specified than the user's
real one. The edits ran in the direction that supported the conclusion.

Three things are done differently here.

  VERBATIM      the text is whatever `fetch_real_queries.py` stored from the API, hash-checked. Nothing
                is retyped, trimmed or reflowed, including command lines that name VEP flags.

  TWO READERS   "the question does not state it" and "the classifier missed it" are different claims and
                the old measurement could not tell them apart. Two different models read each question;
                a factor counts as STATED only if both recover it and agree. Disagreement is its own
                category rather than being silently folded into one side.

  CONSEQUENCE   the headline is not "did the text mention it" — a linguistic judgement, and where the
                bias got in last time — but "would supplying it change the configuration". For each open
                factor, every candidate value is forced in turn and the resulting option sets compared.
                A factor whose answer changes nothing did not need stating, whatever the words did.

KNOWN LIMIT, stated rather than buried: a GitHub issue is not the same speech act as a question typed
into a recommender. People opening issues often already know which flag they want, and paste it. That is
why framing is reported as a stratum instead of being edited away.

  python work/harness/measure_underspecification.py [--limit N]
"""
import argparse
import itertools
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "generation"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import genlib                                                            # noqa: E402
import vep_assistant as va                                              # noqa: E402
from openai import OpenAI                                               # noqa: E402

STORE = ROOT / "work" / "preliminary_examples" / "real_queries_fetched.json"
READERS = ("gemma4:26b", "gemma4:e4b")
MATERIAL = 3          # options changed before a factor counts as worth having

# Fixed and stated up front, so the same rule is applied to every item and can be disagreed with.
IN_SCOPE_PROMPT = (
    "You are triaging issues from the Ensembl VEP trackers.\n\n"
    "Answer YES only if the text is a person describing their own variant-annotation situation and "
    "asking how to configure or run VEP for it.\n"
    "Answer NO for bug reports, installation or crash problems, feature requests, release notes, "
    "questions about interpreting an output column, and anything not about choosing VEP settings.\n\n"
    "Reply with exactly: YES <short reason>  or  NO <short reason>.\n\nText:\n"
)


def in_scope(client, text):
    r = client.chat.completions.create(
        model=READERS[0], temperature=0.0, seed=42,
        messages=[{"role": "system", "content": IN_SCOPE_PROMPT + text[:6000]},
                  {"role": "user", "content": "Classify it."}])
    out = (r.choices[0].message.content or "").strip()
    return out.upper().startswith("YES"), out[:120]


def read_factors(client, model, text):
    return va.infer_factors(client, model, text[:6000], apply_defaults=False)


def stated(a, b, f):
    """A factor counts as stated only when BOTH readers recover it and agree."""
    if not a or not b:
        return None
    va_, vb = a.get(f), b.get(f)
    empty = (lambda v: not v) if f in va.MULTI_FACTORS else (lambda v: v in (None, "unstated"))
    if empty(va_) or empty(vb):
        return False
    if f in va.MULTI_FACTORS:
        return sorted(va_) == sorted(vb)
    return va_ == vb


def genuinely_open(row):
    """The factors this question really leaves open: material, and not merely a reader disagreement.

    THE CORRECTION. `stated()` returns False when the two readers BOTH recover a factor but disagree
    about its value, which lumps disagreement in with absence — and telling those apart is the entire
    reason there are two readers. A question where both models found the fact and read it differently
    is evidence about our classifier, not about the user's prose, and counting it as "the user did not
    say" inflates exactly the number this file exists to report. It moves the headline from 7/8 to 4/8.

    Kept as a separate function rather than folded into `stated()` so both figures stay visible: the
    disagreement rate is worth reporting in its own right, and hiding it would trade one silent
    conflation for another."""
    return [f for f in row["material"] if f not in row["disagreed"]]


def report(rows):
    """Print the headline figures. Split out so a saved run can be re-scored without the readers."""
    n = len(rows)
    if not n:
        print("  no rows to score")
        return
    open_by_row = [genuinely_open(r) for r in rows]
    hit = sum(1 for c in open_by_row if c)
    raw = sum(1 for r in rows if r["n_material"])
    print(f"\n{'='*74}")
    print(f"  questions leaving >=1 factor genuinely open AND material : {hit}/{n}  ({hit/n:.0%})")
    print(f"  which factor                                            : "
          f"{dict(Counter(f for c in open_by_row for f in c)) or 'none'}")
    print(f"  mean such factors per question                          : "
          f"{sum(len(c) for c in open_by_row)/n:.2f}")
    print(f"\n  counting reader disagreement as unstated would give     : {raw}/{n}  "
          f"({raw/n:.0%})  <- NOT the headline; see genuinely_open()")
    print(f"  material only because the readers disagreed              : "
          f"{dict(Counter(f for r in rows for f in r['material'] if f in r['disagreed'])) or 'none'}")
    print(f"  open but changes <{MATERIAL} options (not worth asking)  : "
          f"{dict(Counter(f for r in rows for f in r['immaterial'])) or 'none'}")
    print(f"  the two readers disagreed on                            : "
          f"{dict(Counter(f for r in rows for f in r['disagreed'])) or 'none'}")
    for label, sel in (("pastes VEP flags", True), ("prose only", False)):
        s = [(r, c) for r, c in zip(rows, open_by_row) if r["pastes_flags"] is sel]
        if s:
            print(f"  [{label:16s}] {sum(1 for _, c in s if c)}/{len(s)} affected")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rescore", action="store_true",
                    help="re-print the headlines from the saved run, without calling either reader. "
                         "This is what makes the corrected figures checkable: the readings are already "
                         "on disk, so the scoring rule can be argued with for free.")
    args = ap.parse_args()
    if args.rescore:
        saved = STORE.with_name("underspecification_measurement.json")
        report(json.load(open(saved))["rows"])
        print(f"\n  re-scored from {saved.relative_to(ROOT)} — no model was run")
        return
    items = json.load(open(STORE))
    if args.limit:
        items = items[:args.limit]
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    cat = genlib.load_catalogue(); pbf = genlib.load_priority_by_factor(); fc = genlib.load_factors()
    SCORED = ("origin", "variant_size_class", "region_focus", "analysis_goal")

    print(f"Triaging {len(items)} fetched issues against the fixed in-scope rule.\n")
    kept, triage = [], []
    for it in items:
        ok, why = in_scope(client, it["body"])
        triage.append({"url": it["url"], "in_scope": ok, "reason": why})
        print(f"  [{'IN ' if ok else 'out'}] #{it['number']:<5} {why[:88]}")
        if ok:
            kept.append(it)
    print(f"\n  in scope: {len(kept)}/{len(items)}  ({len(kept)/max(1,len(items)):.0%})")
    if not kept:
        return

    print(f"\nReading each with two models ({READERS[0]} and {READERS[1]}).\n")
    rows = []
    for it in kept:
        a = read_factors(client, READERS[0], it["body"])
        b = read_factors(client, READERS[1], it["body"])
        base = dict(a or {})
        if not base.get("analysis_goal"):
            base["analysis_goal"] = ["basic-consequence"]
        open_material, open_immaterial, disagreed = [], [], []
        for f in SCORED:
            st = stated(a, b, f)
            if st is True:
                continue
            if st is None:
                continue
            # does answering it change anything?
            cfgs = []
            for v in fc["factors"][f]["values"]:
                t = dict(base); t[f] = [v] if f in va.MULTI_FACTORS else v
                ip = genlib.intent_priorities(t, cat, pbf, fc)
                cfgs.append({o for o, (e, _, _) in ip.items() if e})
            delta = max((len(x ^ y) for x, y in itertools.combinations(cfgs, 2)), default=0)
            same = (a or {}).get(f) == (b or {}).get(f)
            (open_material if delta >= MATERIAL else open_immaterial).append((f, delta))
            if not same:
                disagreed.append(f)
        rows.append({"url": it["url"], "n_material": len(open_material),
                     "material": [f for f, _ in open_material],
                     "immaterial": [f for f, _ in open_immaterial], "disagreed": disagreed,
                     "pastes_flags": "--" in it["body"]})
        print(f"  #{it['number']:<5} open&material={[f for f,_ in open_material] or '-'}"
              f"  open-but-inert={[f for f,_ in open_immaterial] or '-'}"
              f"  readers-disagreed={disagreed or '-'}")

    report(rows)
    out = STORE.with_name("underspecification_measurement.json")
    json.dump({"triage": triage, "rows": rows, "readers": READERS, "material_threshold": MATERIAL},
              open(out, "w"), indent=1)
    print(f"\n  -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
