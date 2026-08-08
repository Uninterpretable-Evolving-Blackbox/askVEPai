#!/usr/bin/env python3
"""Stage 6 — mentor review-queue export + provenance log.

Emits a human-scannable review queue (CSV + JSON) and appends one append-only provenance record per
row. NOTHING here is approved gold — `review_status` starts "pending"; the mentor adjudicates.

TWO buckets, RECOMMENDED and ADD-ONS (agreed 2026-08-07). The engine keeps `critical` internally —
restore_missing_critical, --minimal and critical-recall are all defined on it — but the reviewer is
not asked to adjudicate a distinction that never reached the configuration.

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
            #
            # TWO buckets since 2026-08-07 (Likhitha + Nakib): `critical` and `recommended` are one
            # RECOMMENDED column, `optional` is ADD-ONS. Nothing about the CONFIGURATION changes —
            # `recommended_options` was always `critical ∪ recommended`, so the same 391 options across
            # these 31 rows are enabled either way. Only the column they are printed in changes.
            #
            # Worth knowing before applying round-1 comments: about 12 of the reviewer's edits are
            # critical↔recommended moves, which are no-ops here. What survives is anything crossing the
            # recommended/add-on line.
            #
            # Filed by PRIORITY rather than by "is it enabled", so an enabled `optional` — which the
            # resolver does not currently produce, but nothing stops it from producing — lands in
            # ADD-ONS where it belongs instead of being quietly promoted by the merge.
            recommended = [oid for oid in sorted(enabled)
                           if opts[oid].get("priority", "recommended") != "optional"]
            enabled_addons = [oid for oid in sorted(enabled)
                              if opts[oid].get("priority") == "optional"]

            review.append({
                "id": r["id"],
                "species": fl["species"], "origin": fl["origin"], "size": fl["variant_size_class"],
                "region": "+".join(fl["region_focus"]), "goal": "+".join(fl["analysis_goal"]),
                "query": r.get("user_query"),
                "n_enabled": len(enabled),
                # --- the config, in the two buckets the reviewer sees ---
                "recommended": "; ".join(recommended),
                "addons": "; ".join(sorted(set(r.get("add_on_options", {})) | set(enabled_addons))),
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
                "recommended_ok": "",    # are the recommended options right — too many? too few?
                "addons_ok": "",         # do the add-ons belong, and is anything missing?
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
        rec = sorted(o for o, v in opts.items()
                     if v.get("enabled") and v.get("priority", "recommended") != "optional")
        add = sorted(set(r.get("add_on_options", {}))
                     | {o for o, v in opts.items() if v.get("enabled") and v.get("priority") == "optional"})
        lines.append(f"  {'RECOMMENDED':12s} ({len(rec)}): {', '.join(rec) or '-'}")
        lines.append(f"  {'ADD-ONS':12s} ({len(add)}): {', '.join(add) or '-'}")
    (outdir / "review_view.txt").write_text("\n".join(lines))

    print(f"Review queue -> {_rel(csv_path)}")
    print(f"  {len(review)} rows, {sum(1 for x in review if x['deterministic_pass'])} pass deterministic gates")
    print(f"  provenance appended -> {_rel(prov_path)}")
    print(f"  readable view -> {_rel(outdir / 'review_view.txt')}")
    print("\nREMINDER: these are PENDING candidates on a PROVISIONAL config — not approved gold.")


if __name__ == "__main__":
    main()
