#!/usr/bin/env python3
"""Generate the species index from Ensembl itself, for use as a HINT to the classifier.

WHY A HINT AND NOT AN ANSWER. `infer_species()` is a first-match-wins keyword scan whose result
OVERRIDES the model (vep_assistant.py:951). That inverts the division of labour: the regex has no
judgement, so it reads "going down this rabbit hole" as rabbit, "used as a guinea pig" as pig, and
"not a mouse study" as mouse -- and the model, which gets all three right, never gets a say.

Reversed here. The scan reports EVERY name it matched, the classifier is shown those matches and
told they may be idioms, gene symbols, software tools or place names, and the model decides. The
regex supplies recall over 356 species; the model supplies precision.

That also makes the full list safe to add. Under first-match-wins, adding `hedgehog` breaks every
Sonic Hedgehog query and adding `turkey` breaks every cohort from Turkey. As a rejectable hint they
cost nothing.

  python3 data/build/build_species_index.py --out vep_ai_demo/species_index.json
  python3 data/build/build_species_index.py --add-derived vep_ai_demo/species_index.json   # no download
  python3 data/build/build_species_index.py --add-species-of vep_ai_demo/species_index.json

DERIVED NAMES (2026-09-28). Ensembl names some genomes by strain or sex (`heterocephalus_glaber_female`,
`cricetulus_griseus_chok1gshd`) and some common names carry a tag ("muscovy Duck (domestic type)"), so
the plain names a person writes ("heterocephalus glaber", "muscovy duck") matched nothing: 10 of the 14
misses of `organism_754_names.py` were the model naming the species right and the lookup failing. Two
kinds of name are added, each marked `derived` with its reason:
  - the plain scientific name (genus species) of every species that has no genome under it, pointing to
    the species' first genome in alphabetical order. The engine compares data lists by species
    (`species_of`, below), and the genomes grouped here share one, so the genome chosen does not change
    what is offered. Left out: "canis lupus", the wolf, which Ensembl has no genome for; the dog and the
    dingo sit under it.
  - a common name with its bracketed tag removed, when what is left is a plain name ("muscovy duck").
Ensembl's own names are untouched. `--add-derived` adds them to an existing index without downloading:
a fresh download does not reproduce the index, because when several genomes share a common name the last
one in Ensembl's reply wins, and that order changes between requests.

SPECIES, NOT STRAIN (2026-09-28). Ensembl's data lists name species; the index lists 356 genomes, many
of them strains or breeds of one species (28 pig breeds, 13 mouse strains). Cutting a production name to
its first two words grouped them, and got one case wrong: canis_lupus_dingo and canis_lupus_familiaris
both became canis_lupus, so a dingo was offered dog SIFT and dog frequency data. `species_of` groups
genomes by Ensembl's own `taxon_id` instead (dingo 286419, dog 9615); a group's key is its reference
genome, else the words all its genomes share, else its shortest name. The engine's `species_key` reads it.
`--add-species-of` adds it to an existing index and leaves every name entry as it is.
"""
import argparse, json, re, urllib.request
from collections import defaultdict
from pathlib import Path

REST = "https://rest.ensembl.org/info/species?content-type=application/json"
# Names that also mean something else in genomics prose. Kept in the index, but marked, so the
# prompt can tell the model which matches deserve extra suspicion.
KNOWN_TRAPS = {
    "hedgehog": "the Sonic/Indian/Desert Hedgehog (SHH) gene family and signalling pathway",
    "turkey": "the country",
    "rabbit": "the idiom 'rabbit hole'",
    "guinea pig": "the idiom for a test subject",
    "platypus": "the variant caller",
    "salmon": "the RNA-seq quantification tool",
    "cat": "the CAT catalase gene",
    "dog": "the DOG1 (ANO1) gene",
    "duck": "'duck typing'",
    "drill": "'drill down'",
    "mole": "a skin lesion, and the chemistry unit",
}


# Plain scientific names not added, with the reason.
NOT_DERIVED = {"canis lupus": "the wolf; Ensembl has only the dog and the dingo under this key"}


def add_derived_names(index, species_of=None):
    """Add the plain scientific names and untagged common names described above; return how many.

    With `species_of`, a plain name points to a genome of the species it names when there is one: Ensembl
    files "cyprinus carpio" (taxon 7962: German mirror, Hebao red, Huanghe) apart from the subspecies
    cyprinus_carpio_carpio (taxon 630221), which is first in alphabetical order."""
    species_of = species_of or {}
    for k in [k for k, m in index.items() if m.get("derived")]:
        del index[k]
    by_key = {}
    for m in index.values():
        by_key.setdefault("_".join(m["species"].split("_")[:2]), set()).add(m["species"])
    added = {}
    for key, genomes in sorted(by_key.items()):
        name = key.replace("_", " ")
        if name not in index and name not in NOT_DERIVED:
            own = sorted(g for g in genomes if species_of.get(g) == key)
            added[name] = {"species": (own or sorted(genomes))[0], "binomial": True, "english_word": False,
                           "trap": None, "derived": "plain scientific name; Ensembl genomes: "
                                                    + ", ".join(sorted(genomes))}
    for n, m in list(index.items()):
        base = re.sub(r"\s*\([^)]*\)", "", n).strip()
        if base != n and " - " not in base and base not in index and base not in added:
            added[base] = {"species": m["species"], "binomial": False, "english_word": False,
                           "trap": None, "derived": f"Ensembl's \"{n}\" without its bracketed tag"}
    names = set(index) | set(added)
    for n, m in added.items():
        first = n.split()[0]
        m["shadowed_by"] = first if (" " in n and first in names and first != n) else None
    index.update(added)
    return len(added)


def species_of_map(species):
    """{production name: species key}, grouping Ensembl's genomes by taxon_id (see the docstring)."""
    by_taxon = defaultdict(list)
    for s in species:
        by_taxon[s["taxon_id"]].append(s)
    out = {}
    for members in by_taxon.values():
        names = sorted(m["name"] for m in members)
        refs = [m["name"] for m in members if (m.get("strain") or "").lower().startswith("reference")]
        if len(refs) == 1:
            key = refs[0]
        else:
            common = []
            for parts in zip(*(n.split("_") for n in names)):
                if len(set(parts)) != 1:
                    break
                common.append(parts[0])
            key = "_".join(common) if len(common) >= 2 else min(names, key=lambda n: (len(n), n))
        for n in names:
            out[n] = key
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--add-derived", metavar="INDEX", help="add the derived names to an existing index file")
    ap.add_argument("--add-species-of", metavar="INDEX",
                    help="add the taxon-based species_of map to an existing index file; names untouched")
    args = ap.parse_args()
    if args.add_species_of:
        with urllib.request.urlopen(REST, timeout=90) as r:
            species = json.load(r)["species"]
        path = Path(args.add_species_of)
        data = json.loads(path.read_text())
        data["species_of"] = species_of_map(species)
        missing = {m["species"] for m in data["names"].values()} - set(data["species_of"])
        if missing:
            raise SystemExit(f"index genomes Ensembl no longer lists: {sorted(missing)[:5]}; rebuild with --out")
        path.write_text(json.dumps(data, indent=1, sort_keys=True))
        moved = sum(1 for k, v in data["species_of"].items() if k != v)
        print(f"  species_of: {len(data['species_of'])} genomes, {moved} map to another genome's key; wrote {path}")
        return
    if args.add_derived:
        path = Path(args.add_derived)
        data = json.loads(path.read_text())
        n = add_derived_names(data["names"], data.get("species_of"))
        data["_n_names"] = len(data["names"])
        path.write_text(json.dumps(data, indent=1, sort_keys=True))
        print(f"  {n} derived names; {data['_n_names']} names in {path}")
        return
    if not args.out:
        ap.error("--out, --add-derived or --add-species-of is required")
    with urllib.request.urlopen(REST, timeout=90) as r:
        species = json.load(r)["species"]
    try:
        english = {w.strip().lower() for w in open("/usr/share/dict/words")}
    except FileNotFoundError:
        english = set()

    index, names_seen = {}, set()
    for s in species:
        canon = s["name"]                                  # e.g. salmo_salar
        cands = {canon.replace("_", " ")}                  # the binomial: unambiguous
        for k in ("common_name", "display_name"):
            v = (s.get(k) or "").strip().lower()
            if v:
                cands.add(v)
        for c in cands:
            c = re.sub(r"\s+", " ", c).strip().lower()
            if not c or len(c) < 3:
                continue
            names_seen.add(c)
            index[c] = {"species": canon,
                        "binomial": " " in canon.replace("_", " ") and c == canon.replace("_", " "),
                        "english_word": c in english,
                        "trap": KNOWN_TRAPS.get(c)}
    # shadowing: a multi-word name whose first token is itself a name ("guinea pig" -> "pig")
    for c, meta in index.items():
        first = c.split()[0]
        meta["shadowed_by"] = first if (" " in c and first in names_seen and first != c) else None

    species_of = species_of_map(species)
    add_derived_names(index, species_of)
    out = {"_source": REST, "_n_species": len(species), "_n_names": len(index),
           "_note": "Matches are HINTS for the classifier, never an answer. See the module docstring.",
           "names": index, "species_of": species_of}
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    n_tr = sum(1 for m in index.values() if m["trap"])
    n_en = sum(1 for m in index.values() if m["english_word"])
    n_sh = sum(1 for m in index.values() if m["shadowed_by"])
    print(f"  {len(species)} species -> {len(index)} searchable names")
    print(f"    english words: {n_en}   shadowed: {n_sh}   known traps: {n_tr}")
    print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
