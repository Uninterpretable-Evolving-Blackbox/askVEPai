#!/usr/bin/env python3
"""Try the assume/ask behaviour the way a user would meet it.

By default this shows what a user sees and nothing else: the question (if there is one), then the
configuration, then one closing note saying what the question did not state and what was assumed
instead. The reasoning is deliberately at the END and deliberately short — a user wants their answer,
not a lecture about how it was derived.

`--why` adds the audit view underneath: what the classifier read, and for every factor the text left
blank, the configuration under each candidate answer with the essential differences marked. That is
the part for checking whether "answering this changes something essential" is actually true.

  # ask, answer, get a config           (needs Ollama, one classifier call)
  python work/harness/try_reprompting.py "human tumour WGS, which variants are damaging?"

  # same, plus the audit view
  python work/harness/try_reprompting.py --why "human tumour WGS, which variants are damaging?"

  # no model: state the factors yourself, leave the rest blank
  python work/harness/try_reprompting.py --factors species=human,analysis_goal=population-frequency

Questions are asked only when stdin is a terminal, so piping or redirecting never blocks. Use
--no-ask to suppress them in a terminal too.

(There was a `--multi` flag here that simulated variant_size_class as multi-select. That change has
landed in factors.json, so the flag would now simulate the present, and it is gone. To compare the
policy against its predecessors, use `work/harness/ask_rate.py`, which prices every arm on the same
81 cases.)
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

BOLD, DIM, OFF = "\033[1m", "\033[2m", "\033[0m"


def load_options():
    with open(os.environ["VEP_OPTIONS_FILE"]) as f:
        return json.load(f)


def parse_factors(spec):
    """'species=human,analysis_goal=clinical-interpretation+population-frequency' -> a factor record.

    Anything not named comes back blank, which is the whole point: the blanks are what the mechanism
    reacts to."""
    rec = {f: ([] if f in va.MULTI_FACTORS else "unstated") for f in va.FACTOR_VALUES}
    for pair in filter(None, (p.strip() for p in (spec or "").split(","))):
        if "=" not in pair:
            sys.exit(f"bad factor spec {pair!r}, expected name=value")
        f, v = (x.strip() for x in pair.split("=", 1))
        if f not in va.FACTOR_VALUES:
            sys.exit(f"unknown factor {f!r}; known: {', '.join(va.FACTOR_VALUES)}")
        if v in ("", "unstated"):
            continue
        vals = [x for x in v.split("+") if x]
        bad = [x for x in vals if x not in va.FACTOR_VALUES[f]]
        if bad:
            sys.exit(f"{f}: {bad} not in {va.FACTOR_VALUES[f]}")
        rec[f] = vals if f in va.MULTI_FACTORS else vals[0]
    return rec


def shown(v):
    return ", ".join(v) if isinstance(v, list) else str(v)


def is_blank(rec, f):
    v = rec.get(f)
    return (not v) if f in va.MULTI_FACTORS else (v in (None, "unstated"))


def enabled_under(tup, opts):
    resolved = va.resolve_for_query(tup, opts)
    if not resolved:
        return None, None
    return {o for o, (e, _, _) in resolved.items() if e}, resolved


def audit(rec, filled, assumptions, questions, opts):
    """The view for arguing with the rule, not for using the tool. Off unless --why."""
    print(f"\n{DIM}{'─' * 70}{OFF}")
    print(f"{BOLD}WHY{OFF}   {DIM}(--why){OFF}")
    print(f"\n  read from the text:")
    for f in va.FACTOR_VALUES:
        print(f"    {f:20s} {'—  blank' if is_blank(rec, f) else shown(rec[f])}")

    asked_names = [f for f, _, _ in questions]
    assumed_names = [f for f, _, _ in assumptions]
    blank_in_text = [f for f in va.FACTOR_VALUES if f != "species" and is_blank(rec, f)]
    if not blank_in_text:
        print("\n  the text answered everything; nothing to decide")
        return

    print(f"\n  for each blank factor, the configuration under every candidate answer:")
    for f in blank_in_text:
        values = va.FACTOR_VALUES[f]
        sets, crit = {}, []
        for v in values:
            t = dict(filled)
            t[f] = [v] if f in va.MULTI_FACTORS else v
            en, res = enabled_under(t, opts)
            sets[v] = en or set()
            if res:
                crit.append({o for o, (e, p, _) in res.items() if e and p == "critical"})
        differ = sorted({o for x in values for y in values for o in (sets[x] ^ sets[y])})
        essential = sorted(set().union(*[a ^ b for i, a in enumerate(crit)
                                         for b in crit[i + 1:]])) if len(crit) > 1 else []
        verdict = ("ASKED" if f in asked_names
                   else f"assumed {shown(filled.get(f))}" if f in assumed_names
                   else "left open")
        print(f"\n    {BOLD}{f}{OFF}  →  {verdict}")
        for v in values:
            print(f"      {v:22s} {len(sets[v]):2d} options on")
        if not differ:
            print(f"      {DIM}identical either way, so the answer cannot matter{OFF}")
            continue
        print(f"      differs on {len(differ)}: {', '.join(differ)}")
        print(f"      essential: {', '.join(essential) if essential else DIM + 'none — this is why it is not asked' + OFF}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", help="the scenario text (needs Ollama)")
    ap.add_argument("--factors", help="skip the classifier: name=value,name=value")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--why", action="store_true", help="show the audit view underneath")
    ap.add_argument("--no-ask", action="store_true", help="report questions instead of asking them")
    a = ap.parse_args()
    if not a.query and not a.factors:
        ap.error("give a query, or --factors to skip the model")

    opts = load_options()

    if a.factors:
        rec = parse_factors(a.factors)
    else:
        from openai import OpenAI
        client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                        api_key="ollama")
        rec = va.infer_factors(client, a.model, a.query, apply_defaults=False)
        if rec is None:
            sys.exit("the classifier returned nothing parseable — a checker failure, not five blanks")

    filled, assumptions, questions = va.clarification_plan(rec, opts)

    # Same scope note the CLI prints. A query describing no analysis gets told what the tool is for
    # rather than being asked to choose between SNVs and CNVs.
    if va.states_nothing_about_variants(rec):
        print()
        print(va.OUT_OF_SCOPE_NOTE)

    # --- 1. the question, and nothing else. This is the first thing a user sees. ---
    # The configuration BEFORE any answer, so the closing note can say whether answering changed
    # anything. It often does not: an unstated factor fires no hard gate, which is behaviourally
    # identical to the permissive value, so answering `small` lands exactly where skipping does.
    # Being interrupted and then seeing no difference reads as the answer having been ignored.
    before, _ = enabled_under(filled, opts)
    answered = []
    for f, _why, _at_stake in questions:
        if a.no_ask:
            print(f"\n  Would ask: {va._FACTOR_PROMPTS.get(f, f)}   {DIM}(--no-ask){OFF}")
            continue
        if not sys.stdin.isatty():
            print(f"\n  Would ask: {va._FACTOR_PROMPTS.get(f, f)}   {DIM}(not a terminal, so not asking){OFF}")
            continue
        ans = va._ask_factor(f)
        if ans is None:
            print(f"  → skipped, {f} left open")
        else:
            filled[f] = ans
            answered.append((f, ans))
            print(f"  → using {shown(ans)}")

    # --- 2. the answer they came for ---
    en, resolved = enabled_under(filled, opts)
    if en is None:
        sys.exit("could not resolve a configuration from this tuple")
    tiers = va.tier_by_importance(en, resolved)
    print(f"\n{BOLD}RECOMMENDED{OFF} — switched on for this scenario  [{len(tiers['recommended'])}]")
    for oid in tiers["recommended"]:
        print(f"  ✓ {oid}")
    if tiers["addons_on"]:
        print(f"\n{BOLD}ADD-ONS (on){OFF}  [{len(tiers['addons_on'])}]")
        for oid in tiers["addons_on"]:
            print(f"  + {oid}")
    if tiers["addons_offered"]:
        print(f"\n{BOLD}ADD-ONS{OFF} — offered, off by default  [{len(tiers['addons_offered'])}]")
        print("  " + ", ".join(tiers["addons_offered"]))

    # --- 3. one short note at the end, not a lecture at the start ---
    notes = []
    for f, val, _why in assumptions:
        notes.append(f"{f} = {shown(val)}")
    still_open = [f for f in va.FACTOR_VALUES
                  if f != "species" and is_blank(filled, f)]
    if notes or still_open or answered:
        print()
        if notes:
            print(f"  {DIM}Your question didn't say {', '.join(f for f, _, _ in assumptions)}. "
                  f"Assumed {'; '.join(notes)}. Say otherwise in your question to change it.{OFF}")
        if answered and before is not None and before == en:
            print(f"  {DIM}Your answer matched what would have happened anyway, so the "
                  f"configuration is unchanged.{OFF}")
        if still_open:
            print(f"  {DIM}Left open: {', '.join(still_open)} — skipped, so nothing was assumed.{OFF}")

    if a.why:
        audit(rec, filled, assumptions, questions, opts)
    print()


if __name__ == "__main__":
    main()
