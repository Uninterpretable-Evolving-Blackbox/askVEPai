#!/usr/bin/env python3
"""Does every option the tool shows exist for the organism the user named? No model, seconds.

WHY. The existing species checks are binary: verify_pipeline asserts that non-human rows never enable
a human-only option. Ensembl's plugin lists (VEP_plugins release/116 plugin_config.txt) name species
one by one: CADD for pig, chicken and turkey; mutfunc for yeast; IntAct for seven species. A binary
check cannot see "offered IntAct to a pig". This walks the shipped resolution chain for every
organism in the 356-species index and every factor tuple, and checks what the user is shown against
each option's `species` list.

CHAIN, as run_recommend runs it per size pass: resolve_for_query -> check_and_fix_violations ->
restore_missing_recommended -> tier_by_importance. The organism is given as the classifier's
`organism` would give it (production name), species factor non-human; humans run with no organism.

SHOWN = recommended (switched on) + add-ons switched on + add-ons offered. An option is ALLOWED when
its `species` is "all" or lists the organism (compared with species_key, so strains fold to the
species as the checker folds them).

  python3 tests/species_by_organism.py [--json out.json]
"""
import argparse, itertools, json, os, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402

MULTI = ("variant_size_class", "region_focus", "analysis_goal")


def tuples(factors, species):
    vals = {k: v["values"] if isinstance(v, dict) else v for k, v in factors["factors"].items()}
    vals = {k: [x["id"] if isinstance(x, dict) else x for x in v] for k, v in vals.items()}
    def subsets(xs):
        return [list(c) for r in range(1, len(xs) + 1) for c in itertools.combinations(xs, r)]
    for o, s, r, g in itertools.product(vals["origin"], subsets(vals["variant_size_class"]),
                                        subsets(vals["region_focus"]), subsets(vals["analysis_goal"])):
        yield {"species": species, "origin": o, "variant_size_class": s, "region_focus": r,
               "analysis_goal": g}


def shown(tup, cat, organism):
    """{pass_label: {'recommended': [...], 'addons': [...]}} for one tuple and organism."""
    out = {}
    species = tup["species"]
    for size_value, label, pass_tuple in va.size_passes(tup):
        resolved = va.resolve_for_query(pass_tuple, cat)
        en, dis = set(), set()
        viol = va.check_and_fix_violations(en, dis, cat, "", species_override=species,
                                           resolved=resolved, organism=organism)
        va.restore_missing_recommended(en, dis, resolved, cat, "", species_override=species,
                                       violations_out=viol, organism=organism)
        va.drop_unavailable_size_values(en, cat, size_value, None)
        t = va.tier_by_importance(en, resolved)
        # What format_corrected_config prints: add-ons pass offer_available (added 2026-09-23).
        shown_as = organism or "human"
        offered = [o for o in t["addons_offered"] if va.offer_available(o, cat, shown_as)]
        out[label] = {"on": sorted(set(t["recommended"]) | set(t["unpriced"]) | set(t["addons_on"])),
                      "offered": sorted(offered)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    cat = va.load_vep_options() if hasattr(va, "load_vep_options") else json.load(open(os.environ["VEP_OPTIONS_FILE"]))
    factors = va.load_factors()
    sp = {o["id"]: o.get("species", "all") for o in cat}
    restricted = {oid: {va.species_key(x) for x in s} for oid, s in sp.items() if s != "all"}
    index = json.load(open(ROOT / "vep_ai_demo/species_index.json"))["names"]
    organisms = sorted({v["species"] for v in index.values()} - {"homo_sapiens"})
    named = sorted({x for s in restricted.values() for x in s} - {"homo_sapiens"})
    print(f"{len(cat)} options, {len(restricted)} species-restricted; {len(organisms)} non-human organisms "
          f"in the index, {len(named)} named by at least one option's list")

    leaks = {"on": Counter(), "offered": Counter()}       # option -> (organism, tuple) count
    by_org = defaultdict(lambda: {"on": set(), "offered": set()})
    cells = {"on": 0, "offered": 0}
    n_calls = 0
    non_tuples = list(tuples(factors, "non-human"))
    for org in organisms:
        k = va.species_key(org)
        for tup in non_tuples:
            n_calls += 1
            for _label, s in shown(tup, cat, org).items():
                for where in ("on", "offered"):
                    for oid in s[where]:
                        cells[where] += 1
                        if oid in restricted and k not in restricted[oid]:
                            leaks[where][oid] += 1
                            by_org[org][where].add(oid)
    # Human: nothing restricted to other species only should appear (sanity), and nothing human is lost.
    human_bad = Counter()
    for tup in tuples(factors, "human"):
        for _label, s in shown(tup, cat, None).items():
            for oid in s["on"] + s["offered"]:
                if oid in restricted and "homo_sapiens" not in restricted[oid]:
                    human_bad[oid] += 1

    print(f"\n{n_calls} (organism x non-human tuple) resolutions, {len(non_tuples)} tuples each")
    for where, title in (("on", "SWITCHED ON (recommended / add-on on)"), ("offered", "ADD-ONS OFFERED")):
        tot = sum(leaks[where].values())
        print(f"\n{title}: {tot} option-instances not on the option's species list, of {cells[where]} shown")
        for oid, n in leaks[where].most_common():
            print(f"  {oid:22} {n:6}   list: {', '.join(sorted(restricted[oid]))[:90]}")
    orgs_hit = [o for o in organisms if by_org[o]["offered"] or by_org[o]["on"]]
    print(f"\norganisms shown at least one option they are not listed for: {len(orgs_hit)}/{len(organisms)}")
    for org in ("sus_scrofa", "mus_musculus", "gallus_gallus", "saccharomyces_cerevisiae", "danio_rerio",
                "bos_taurus", "canis_lupus_familiaris"):
        if org in by_org:
            print(f"  {org:26} on: {sorted(by_org[org]['on']) or '-'}   offered: {sorted(by_org[org]['offered']) or '-'}")
    print(f"\nhuman tuples: {sum(human_bad.values())} shown options whose list lacks homo_sapiens "
          f"{dict(human_bad) or ''}")
    if a.json:
        Path(a.json).write_text(json.dumps({
            "n_options": len(cat), "n_restricted": len(restricted), "n_organisms": len(organisms),
            "n_tuples_nonhuman": len(non_tuples), "cells": cells,
            "leaks": {w: dict(c) for w, c in leaks.items()},
            "by_organism": {o: {w: sorted(v) for w, v in d.items()} for o, d in by_org.items()},
            "human_bad": dict(human_bad)}, indent=1))
        print(f"wrote {a.json}")


if __name__ == "__main__":
    main()
