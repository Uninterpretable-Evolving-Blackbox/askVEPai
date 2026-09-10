#!/usr/bin/env python3
"""Score the controlled ablations SEPARATELY PER OUTPUT TIER, and print the table §2 publishes.

WHY THIS EXISTS. The published table counted options as one undifferentiated set, so losing `clinvar`
— which the user sees switched ON — scored the same as no longer being OFFERED `nmd`, which they would
have had to opt into. Those are not the same harm, and the tool's whole output is built on the
distinction. This scores the two buckets the user actually sees:

  RECOMMENDED  the options the tool switches on           -> losing one costs a finding
  ADD-ONS      the options it offers, off by default      -> losing one costs an option they never saw

It also corrects a claim the old scoring could not see. "region_focus and variant_size_class lose
NOTHING" was true only of the RECOMMENDED bucket; both drop a fraction of an add-on per query. The
headline stands — no recommended option is ever lost — but "loses nothing" was too strong.

Deterministic: no model, no GPU. The ablations were built once by `ablate_queries.py`; this only
re-resolves them through the current priority table, so it re-prints from the code rather than from a
saved number, and moves when the table moves.

  /opt/anaconda3/bin/python3 work/harness/score_ablations.py [--markdown]
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

ABL = ROOT / "work" / "preliminary_examples" / "ablated_queries.json"
ORDER = ("region_focus", "variant_size_class", "origin", "analysis_goal", "species")
GUESS = {"region_focus": "guessed *both*", "variant_size_class": "guessed *both*",
         "origin": "guessed *somatic*", "analysis_goal": "asked; *basic-consequence* on skip",
         "species": "guessed *human*"}


def buckets(factor_tuple, catalogue):
    """(RECOMMENDED set, ADD-ONS set) — the two things the user is actually shown."""
    res = va.resolve_for_query(factor_tuple, catalogue) or {}
    on = {o for o, (e, _p, _g) in res.items() if e}
    offered = {o for o, (e, p, _g) in res.items() if not e and p == "optional"}
    return on, offered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true", help="emit the table as markdown for the proposal")
    ap.add_argument("--single-select-check", action="store_true",
                    help="print the reprompting_proposal §3 comparison: variant_size_class filled "
                         "EMPTY (single-select's only option, since neither single value is safe) "
                         "vs guessed *both*. Regenerates the §3 table from the live priority table.")
    ap.add_argument("--file", default=None,
                    help="score a different ablation file (e.g. the _rerun set) instead of the "
                         "committed primary; the primary stays the number of record until adopted")
    args = ap.parse_args()

    catalogue, _ = va.load_knowledge_base()
    rows = [r for r in json.load(open(args.file or ABL)) if r["pure"]]

    if args.single_select_check:
        vs = [r for r in rows if r["target"] == "variant_size_class"]
        print(f"\n§3 arm — variant_size_class on {len(vs)} pure ablations, RECOMMENDED tier\n")
        print(f"  {'policy':24} {'REC lost':>9} {'REC gained':>11} {'queries losing a REC':>21}")
        for label, fill in (("empty (single-select)", []),
                            ("both (shipped)", ["small", "structural-CNV"])):
            rl = rg = q = 0
            for r in vs:
                t_on, _ = buckets(r["truth"], catalogue)
                ra = dict(r["read_after"]); ra["variant_size_class"] = list(fill)
                o_on, _ = buckets(ra, catalogue)
                rl += len(t_on - o_on); rg += len(o_on - t_on); q += bool(t_on - o_on)
            n = len(vs)
            print(f"  {label:24} {rl/n:>9.2f} {rg/n:>11.2f} {q:>18}/{n}")
        return

    S = collections.defaultdict(collections.Counter)
    for r in rows:
        t_on, t_off = buckets(r["truth"], catalogue)
        # The gap is filled with the default UNDER TEST, then compared against the truth. This is why
        # the table cannot be used to CHOOSE a default -- it presupposes one. It validates, it does not
        # select. See ONBOARDING.md §5.
        filled, _asm = va.resolve_underspecified(dict(r["read_after"]), catalogue, mode="assume",
                                                 user_query=r["ablated"], assembly=None)
        o_on, o_off = buckets(filled, catalogue)
        s = S[r["target"]]
        s["n"] += 1
        s["rec_lost"] += len(t_on - o_on)
        s["rec_gained"] += len(o_on - t_on)
        s["add_lost"] += len(t_off - o_off)
        s["add_gained"] += len(o_off - t_off)
        if t_on - o_on:
            s["q_rec_lost"] += 1
        if not (t_on ^ o_on) and not (t_off ^ o_off):
            s["exact"] += 1

    if args.markdown:
        print("| fact deleted | n | RECOMMENDED lost | RECOMMENDED gained | ADD-ONS lost | "
              "ADD-ONS gained | rows losing a recommended option |")
        print("|---|---|---|---|---|---|---|")
        for t in ORDER:
            s = S[t]
            n = s["n"]
            if n == 0:
                print(f"| `{t}` — {GUESS[t]} | 0 | — | — | — | — | this file carries no {t} ablations |")
                continue
            hi = "**" if s["rec_lost"] == 0 else ""
            print(f"| `{t}` — {GUESS[t]} | {n} | {hi}{s['rec_lost']/n:.2f}{hi} | "
                  f"{s['rec_gained']/n:.2f} | {s['add_lost']/n:.2f} | {s['add_gained']/n:.2f} | "
                  f"{hi}{s['q_rec_lost']}/{n}{hi} |")
        return

    print("\nWhat silence costs, split by the bucket the user sees "
          f"({sum(S[t]['n'] for t in ORDER)} clean ablations)\n")
    print(f"  {'fact deleted':<20} {'n':>3} | {'REC lost':>9} {'REC gain':>9} | "
          f"{'ADD lost':>9} {'ADD gain':>9} | {'rows losing a REC':>18} | {'exact':>7}")
    print("  " + "-" * 100)
    for t in ORDER:
        s = S[t]
        n = s["n"]
        if n == 0:
            print(f"  {t:<20}   0 | (no ablations for this factor in this file)")
            continue
        print(f"  {t:<20} {n:>3} | {s['rec_lost']/n:>9.2f} {s['rec_gained']/n:>9.2f} | "
              f"{s['add_lost']/n:>9.2f} {s['add_gained']/n:>9.2f} | "
              f"{s['q_rec_lost']:>8}/{n:<9} | {s['exact']:>3}/{n}")
    print("\n  RECOMMENDED = switched on. Losing one costs the user a finding.")
    print("  ADD-ONS     = offered, off by default. Losing one costs an option they never saw offered.")
    print("\n  Read the RECOMMENDED-lost column first: it is the only one that costs anything a user")
    print("  would notice as missing. `region_focus` and `variant_size_class` are 0.00 there, which is")
    print("  what makes them safe to guess; `analysis_goal` is the only factor that loses on BOTH")
    print("  tiers while gaining nothing, which is why it is asked about rather than guessed.")


if __name__ == "__main__":
    main()
