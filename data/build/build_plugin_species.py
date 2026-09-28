#!/usr/bin/env python3
"""Which species each VEP plugin supports, from Ensembl's own plugin config.

SOURCE: `reference/ensembl_source/vep_plugins_species_config_116.txt`, fetched 2026-09-20 from
https://raw.githubusercontent.com/Ensembl/VEP_plugins/release/116/plugin_config.txt (pointer from
Likhitha, 2026-09-16 meeting). Each plugin block carries a `species` field; a plugin with no such
field runs for every species. NOTE every plugin in that file is `available => 0` -- the web
deployment overrides it -- so it cannot say what the FORM offers. That stays with
`vep_plugins_web_config.txt`, and this script only reads the species lists.

WHAT IT WRITES: the `species` field of every plugin option in the catalogue
(`vep_ai_demo/vep_options.json`), e.g. cadd -> ["gallus_gallus", "homo_sapiens", "meleagris_gallopavo",
"sus_scrofa"], maxentscan -> ["homo_sapiens"]. A plugin with no species field in the config gets "all".
Until 2026-09-22 this went to a separate `generation_config/species_data.json` that overrode the
catalogue's own (partly wrong) plugin species. Names are collapsed to their species with the engine's
`species_key` (`gallus_gallus_GCA_000002315.5` -> `gallus_gallus`; Ensembl taxon ids decide, through
`species_of` in the species index), because the data lists are per species.

  python3 data/build/build_plugin_species.py            # dry run: the diff against the catalogue
  python3 data/build/build_plugin_species.py --write    # update the catalogue
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
import vep_assistant as va                                              # noqa: E402

CONFIG = ROOT / "reference" / "ensembl_source" / "vep_plugins_species_config_116.txt"
CATALOGUE = ROOT / "vep_ai_demo" / "vep_options.json"


def parse_config(path=CONFIG):
    """{plugin key (lowercased): [species] or None} from the perl config."""
    text = path.read_text()
    starts = [m.start() for m in re.finditer(r'"key"\s*=>', text)] + [len(text)]
    out = {}
    for a, b in zip(starts, starts[1:]):
        blk = text[a:b]
        key = re.search(r'"key"\s*=>\s*"([^"]+)"', blk)
        if not key:
            continue
        sp = re.search(r'"species"\s*=>\s*\[(.*?)\]', blk, re.S)
        out[key.group(1).lower()] = (sorted({va.species_key(x.lower())
                                             for x in re.findall(r'"([^"]+)"', sp.group(1))})
                                     if sp else None)
    return out


def map_to_options(cfg, catalogue):
    """Our option id -> species list, for catalogue entries that are plugins."""
    mapped, every_species, unmatched = {}, [], []
    for o in catalogue:
        if not (o.get("cli_flag") or "").startswith("--plugin"):
            continue
        key = (o.get("cli_flag") or "").replace("--plugin", "").strip().lower()
        species = cfg.get(key, cfg.get(o["id"].lower(), "MISSING"))
        if species == "MISSING":
            unmatched.append(o["id"])
        elif species is None:
            # No `species` field in the config: the plugin carries no species restriction. Recorded
            # explicitly, because our catalogue says "human only" for UTRAnnotator and the config does
            # not -- and an absent key would read as "we never looked".
            every_species.append(o["id"])
        else:
            mapped[o["id"]] = species
    return mapped, sorted(every_species), unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    cfg = parse_config()
    catalogue = json.loads(CATALOGUE.read_text())
    mapped, every_species, unmatched = map_to_options(cfg, catalogue)
    by_id = {o["id"]: o for o in catalogue}

    print(f"{len(cfg)} plugins in the config · {len(mapped)} of our plugin options get a species list "
          f"· {len(every_species)} have no species field, so they run for every species "
          f"({', '.join(every_species)})")
    if unmatched:
        print(f"  NOT FOUND in the config (check the cli_flag): {', '.join(unmatched)}")

    print("\nwhere our catalogue disagrees with the config:")
    target = {oid: list(sp) for oid, sp in mapped.items()} | {oid: "all" for oid in every_species}
    diffs = [oid for oid in sorted(target) if by_id[oid].get("species") != target[oid]]
    for oid in diffs:
        print(f"  {oid:18} catalogue: {by_id[oid].get('species')}  config: {target[oid]}")
    if not diffs:
        print("  none")

    if not a.write:
        print("\ndry run; pass --write to update the catalogue")
        return
    for o in catalogue:
        if o["id"] in target:
            o["species"] = target[o["id"]]
    CATALOGUE.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(diffs)} plugin species lists to {CATALOGUE.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
