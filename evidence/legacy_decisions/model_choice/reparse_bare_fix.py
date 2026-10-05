#!/usr/bin/env python3
"""Re-parse every logged run with the fixed alias table, to quantify the `bare` correction.

WHY: build_option_aliases used to harvest junk tokens out of each option's cli_flag string — most
damagingly the flag KEYWORD `plugin`, claimed by all 19 plugin options in the expanded catalogue. The
prose fallback parser (Phase 2, used when the model emits no `[source:]` tags) scans for alias words at a
word boundary, so any response containing the ordinary English word "plugin" enabled an arbitrary plugin
option. 38 of 60 bare responses contain it.

The KB conditions never touched that path (Phase 0 parses their exact `[source: id]` tags), so this is
expected to move `bare` ONLY. That is exactly what this script checks: it re-parses the saved response
text with the current code and prints mean±SD per condition per run, so the corrected numbers can replace
the published ones. Valid because the prompt and the model outputs are unchanged — only parsing changed
(the same argument rescore_offline.py makes).

  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json \
  VEP_EXAMPLES_FILE=vep_ai_demo/legacy/training_examples.json \
  python evidence/legacy_decisions/model_choice/reparse_bare_fix.py
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va       # noqa: E402

LOGS = [
    ("Exp 4/7  26b (3 seeds)", "evidence/local_runs/results_fixedparser/raw/gemma4_26b.jsonl"),
    ("Exp 10   e4b (5 seeds)", "evidence/legacy_decisions/model_choice/results/raw/gemma4_e4b.jsonl"),
    ("Exp 10   12b (5 seeds)", "evidence/legacy_decisions/model_choice/results/raw/gemma4_12b.jsonl"),
    ("Exp 10   26b (5 seeds)", "evidence/legacy_decisions/model_choice/results/raw/gemma4_26b.jsonl"),
    ("Exp 11   26b (5 seeds)", "evidence/local_runs/results_noex/raw/gemma4_26b.jsonl"),
]
CONDS = ["bare", "noex", "keyword", "all", "semantic"]


def f1(pred, gold):
    if not gold:
        return None
    ov = len(pred & gold)
    p = ov / len(pred) if pred else None
    r = ov / len(gold)
    if p is None:
        return None
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    options, _ = va.load_knowledge_base()
    aliases = va.build_option_aliases(options)
    print(f"catalogue={len(options)} options  aliases={len(aliases)}  "
          f"'plugin' alias -> {aliases.get('plugin', 'DROPPED (fixed)')}\n")
    print(f"{'run':24s} {'cond':9s} {'OLD (logged)':>14s} {'NEW (re-parsed)':>16s} {'delta':>7s}")
    print("-" * 76)
    for label, rel in LOGS:
        path = ROOT / rel
        if not path.exists():
            print(f"{label:24s} (missing: {rel})")
            continue
        rows = [json.loads(l) for l in open(path)]
        old_by, new_by = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
        for r in rows:
            cond, run = r.get("condition"), r.get("run", 0)
            gold = set(r.get("gt_enabled") or [])
            if not gold:
                continue
            old = f1(set(r.get("enabled") or []), gold)          # as logged, old parser
            new_en, _ = va.extract_recommendations(r.get("response") or "", aliases)
            new = f1(set(new_en), gold)                          # re-parsed, fixed parser
            if old is not None:
                old_by[cond][run].append(old)
            if new is not None:
                new_by[cond][run].append(new)
        for cond in CONDS:
            if cond not in new_by:
                continue
            def agg(d):
                per_run = [statistics.mean(v) for v in d[cond].values() if v]
                if not per_run:
                    return None, 0.0
                return statistics.mean(per_run), (statistics.stdev(per_run) if len(per_run) > 1 else 0.0)
            om, osd = agg(old_by)
            nm, nsd = agg(new_by)
            delta = f"{(nm - om) * 100:+.0f}%" if (om is not None and nm is not None) else "-"
            mark = "  <-- MOVED" if (om is not None and nm is not None and abs(nm - om) > 0.015) else ""
            print(f"{label:24s} {cond:9s} {om * 100:11.0f}%±{osd * 100:<2.0f} "
                  f"{nm * 100:13.0f}%±{nsd * 100:<2.0f} {delta:>7s}{mark}")
        print()


if __name__ == "__main__":
    main()
