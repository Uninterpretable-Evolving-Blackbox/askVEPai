#!/usr/bin/env python3
"""Precompute every factor combination -> resolved config, for the interactive playground.

The factor input space is tiny and finite: 2 species x 2 origin x 2 size x 3 region-subsets x 7
goal-subsets = 168 combinations. Because the resolver is deterministic and LLM-free, we can resolve ALL
of them once, ahead of time, and hand the browser a lookup table. Then flipping a factor in the UI is an
O(1) dictionary read — zero compute, no server, no GPU, works offline. That is the "optimised performance"
design: move all the work to build time.

  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json python pipeline/build_playground_data.py
      -> writes pipeline/candidates/playground_data.json
"""
import itertools
import json

import genlib
import resolve_config as rc


def subsets(vals):
    out = []
    for r in range(1, len(vals) + 1):
        out += [sorted(c) for c in itertools.combinations(vals, r)]
    return out


def tuple_key(t):
    return "|".join([t["species"], t["origin"], t["variant_size_class"],
                     ",".join(sorted(t["region_focus"])), ",".join(sorted(t["analysis_goal"]))])


def drivers(oid, factor_tuple, pbf):
    av = genlib.active_values(factor_tuple)
    pf = pbf["priorities"].get(oid, {})
    return [{"factor": f, "value": v, "priority": pf[f][v]}
            for f in av for v in av[f] if f in pf and v in pf[f]]


def main():
    catalogue = genlib.load_catalogue()
    pbf = genlib.load_priority_by_factor()
    factors_cfg = genlib.load_factors()
    va = genlib.load_va()
    corpus = genlib.load_corpus()
    by_id = {o["id"]: o for o in catalogue}
    F = factors_cfg["factors"]

    # a compact reused command builder mirroring vep_assistant.cli_flags_for (kept dependency-free here)
    def flags_for(enabled):
        import re
        out, seen = [], set()
        for oid in sorted(enabled):
            f = (by_id.get(oid, {}).get("cli_flag") or "").strip()
            if not f.startswith("--"):
                continue
            head = f.split("(+", 1)[0].strip() if "(+" in f else f
            alts = re.findall(r"--[A-Za-z0-9_]+", head)
            if len(alts) > 1 and re.search(r"\s*[|/]\s*", head):
                continue  # menu — skip from the paste-able command
            f = head
            if "derived" in f or "no flag" in f:
                continue
            m = re.search(r"\[[^\]]*\|[^\]]*\]", f)
            if m:
                dflt = {"sift": "b", "polyphen": "b"}.get(oid)
                f = re.sub(r"\s*\[[^\]]*\]", f" {dflt}" if dflt else "", f).strip()
            if "(" in f:
                f = f.split("(", 1)[0].strip()
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

    # Normalise: store each option's static metadata ONCE in `options`, and per-config store only the
    # dynamic bits (which options, their priority, and the factor drivers). This keeps the embedded payload
    # small enough to inline in a single self-contained page.
    options_meta = {o["id"]: {"name": o.get("name", o["id"]),
                              "flag": o.get("cli_flag", ""),
                              "section": o.get("web_form_section", ""),
                              "category": o.get("category", ""),
                              "desc": (o.get("description") or "")[:240]}
                    for o in catalogue}

    data = {}
    for sp in F["species"]["values"]:
        for og in F["origin"]["values"]:
            for sz in F["variant_size_class"]["values"]:
                for rg in subsets(F["region_focus"]["values"]):
                    for gl in subsets(F["analysis_goal"]["values"]):
                        t = {"species": sp, "origin": og, "variant_size_class": sz,
                             "region_focus": rg, "analysis_goal": gl}
                        row = rc.resolve_row(t, catalogue, pbf, factors_cfg, va, corpus)
                        intent = rc.intent_priorities(t, catalogue, pbf, factors_cfg)
                        rec = row["recommended_options"]
                        core = [{"id": oid, "priority": c.get("priority", "recommended"),
                                 "drivers": drivers(oid, t, pbf)}
                                for oid, c in rec.items() if c.get("enabled")]
                        add_ons = [{"id": oid, "drivers": drivers(oid, t, pbf)}
                                   for oid in sorted(row.get("add_on_options", {}))]
                        disabled = [{"id": oid, "note": c.get("note", "")}
                                    for oid, c in rec.items() if not c.get("enabled")]
                        gated = sorted(oid for oid, (_e, _p, g) in intent.items() if g)
                        core.sort(key=lambda x: ({"recommended": 1}.get(x["priority"], 2),
                                                 x["id"]))
                        data[tuple_key(t)] = {
                            "core": core, "add_ons": add_ons, "disabled": disabled, "gated": gated,
                            "unsatisfiable": row["_resolver"].get("unsatisfiable_factors", []),
                            "command": flags_for([c["id"] for c in core]),
                        }

    out = {
        "meta": {
            "status": pbf.get("_status", ""),
            "kb_options": len(catalogue),
            "n_combinations": len(data),
            "factors": {f: {"values": spec["values"], "select": spec.get("select", "single"),
                            "gate": f in genlib.HARD_GATE_FACTORS}
                        for f, spec in F.items()},
            "predictor_tiers": pbf.get("_authoring", {}).get("predictor_tiers", {}),
        },
        "options": options_meta,
        "configs": data,
    }
    out_path = genlib.GEN_DIR / "candidates" / "playground_data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out, separators=(",", ":"))
    with open(out_path, "w") as f:
        f.write(payload)
    print(f"Wrote {out_path.relative_to(genlib.ROOT)}  ({len(data)} combinations, "
          f"{out_path.stat().st_size // 1024} KB)")

    # Assemble the self-contained, offline HTML by injecting the data into the template. The result opens
    # with a double-click — no server, no GPU, instant. Regenerate whenever the priority table changes.
    tmpl_path = genlib.GEN_DIR / "playground_template.html"
    if tmpl_path.exists():
        html = tmpl_path.read_text().replace("__DATA__", payload)
        html_path = genlib.GEN_DIR / "playground.html"
        html_path.write_text(html)
        print(f"Wrote {html_path.relative_to(genlib.ROOT)}  "
              f"(self-contained, {html_path.stat().st_size // 1024} KB — open in any browser)")


if __name__ == "__main__":
    main()
