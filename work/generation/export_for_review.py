#!/usr/bin/env python3
"""Stage 6 — mentor review-queue export + provenance log.

Emits a human-scannable review queue (CSV + JSON) and appends one append-only provenance record per
row. NOTHING here is approved gold — `review_status` starts "pending"; the mentor adjudicates. Uses the
tiered Core/Add-ons view (reused tier_options/format_tiered_config) so the enabled set is readable.

  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/generation/export_for_review.py --in candidates/iced.json --outdir candidates/review
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import genlib


def kb_hash():
    h = hashlib.sha256()
    with open(os.environ["VEP_OPTIONS_FILE"], "rb") as f:
        h.update(f.read())
    return "sha256:" + h.hexdigest()[:16]


def _rel(p):
    """Path relative to the repo root for display, or the raw path if it isn't under it."""
    p = Path(p)
    try:
        return p.relative_to(genlib.ROOT)
    except ValueError:
        return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--outdir", default=str(genlib.GEN_DIR / "candidates" / "review"))
    args = ap.parse_args()

    va = genlib.load_va()
    catalogue = genlib.load_catalogue()
    rows = json.load(open(args.inp))
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    khash = kb_hash()

    review = []
    prov_path = genlib.GEN_DIR / "provenance.jsonl"
    with open(prov_path, "a") as prov:
        for r in rows:
            opts = r["recommended_options"]
            enabled = [k for k, v in opts.items() if v.get("enabled")]
            fl = r["factor_labels"]
            gates = r.get("_gates", {})
            ice = r.get("_ice", {})
            qg = r.get("_query_gen", {})

            # Split by IMPORTANCE, not by native-vs-plugin. This used to call va.tier_options(), which
            # splits on cli_flag ("--plugin" => add-on) — a FACTUAL split that was the stand-in while no
            # priorities existed. It is the wrong axis for review: it answers "is this a plugin?", not
            # "must I have this?". The reviewer's own spec asks for generated options "including mandatory
            # and optional", so the sheet has to show the priority tiers.
            by_prio = {"critical": [], "recommended": []}
            for oid in sorted(enabled):
                by_prio.setdefault(opts[oid].get("priority", "recommended"), []).append(oid)

            review.append({
                "id": r["id"],
                "species": fl["species"], "origin": fl["origin"], "size": fl["variant_size_class"],
                "region": "+".join(fl["region_focus"]), "goal": "+".join(fl["analysis_goal"]),
                "query": r.get("user_query"),
                "n_enabled": len(enabled),
                # --- the config, by importance ---
                "critical": "; ".join(by_prio.get("critical", [])),
                "recommended": "; ".join(by_prio.get("recommended", [])),
                "optional_addons": "; ".join(sorted(r.get("add_on_options", {}))),
                # (no explicit disables: the checker owns everything OFF at runtime — see resolve_config)
                # --- the factual native/plugin split, kept but named for what it actually is ---
                "plugins_used": "; ".join(va.tier_options(enabled, catalogue)["addons"]),
                # --- diagnostics ---
                "ice_critical_recall": ice.get("critical_recall"),
                "deterministic_pass": gates.get("deterministic_pass"),
                "flags": "; ".join(gates.get("flags", [])),
                "config_source": r.get("_resolver", {}).get("config_source"),
                # --- columns for the reviewer to fill in ---
                "review_status": "pending",
                "critical_ok": "",       # are the `critical` options right — too many? too few?
                "optional_ok": "",       # do the add-ons belong, and is anything missing?
                "query_ok": "",          # does the query actually describe this scenario?
                "notes": "",
            })

            prov.write(json.dumps({
                "id": r["id"],
                "factor_labels": fl,
                "query_axes_cell": qg.get("query_axes_cell"),
                "teacher_model": qg.get("teacher_model"),
                "teacher_seed": qg.get("seed"),
                "resolver_config_source": r.get("_resolver", {}).get("config_source"),
                "kb_hash": khash,
                "checker_clean": gates.get("checks", {}).get("checker_clean"),
                "ice_critical_recall": ice.get("critical_recall"),
                "ice_student": ice.get("student"),
                "deterministic_pass": gates.get("deterministic_pass"),
                "flags": gates.get("flags", []),
                "review_status": "pending",
            }) + "\n")

    # CSV
    csv_path = outdir / "review_queue.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(review[0].keys()))
        w.writeheader()
        w.writerows(review)
    # JSON (full annotated rows, for programmatic use)
    (outdir / "review_queue.json").write_text(json.dumps(rows, indent=2))
    # readable per-row tiered view
    lines = []
    for r in rows:
        opts = r["recommended_options"]
        fl = r["factor_labels"]
        lines.append("=" * 80)
        lines.append(f"{r['id']}   [{'; '.join(r['_gates'].get('flags', [])) or 'no flags'}]")
        lines.append(f"  {fl['species']} / {fl['origin']} / {fl['variant_size_class']} / "
                     f"{'+'.join(fl['region_focus'])} / {'+'.join(fl['analysis_goal'])}")
        lines.append(f"Q: {r.get('user_query')}")
        for tier in ("critical", "recommended"):
            ids = sorted(o for o, v in opts.items() if v.get("enabled") and v.get("priority") == tier)
            lines.append(f"  {tier.upper():12s} ({len(ids)}): {', '.join(ids) or '-'}")
        add = sorted(r.get("add_on_options", {}))
        lines.append(f"  {'OPTIONAL':12s} ({len(add)}): {', '.join(add) or '-'}")
    (outdir / "review_view.txt").write_text("\n".join(lines))

    print(f"Review queue -> {_rel(csv_path)}")
    print(f"  {len(review)} rows, {sum(1 for x in review if x['deterministic_pass'])} pass deterministic gates")
    print(f"  provenance appended -> {_rel(prov_path)}")
    print(f"  readable view -> {_rel(outdir / 'review_view.txt')}")
    print("\nREMINDER: these are PENDING candidates on a PROVISIONAL config — not approved gold.")


if __name__ == "__main__":
    main()
