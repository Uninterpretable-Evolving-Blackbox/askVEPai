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

  python3 work/harness/build/build_species_index.py --out work/generation/generation_config/species_index.json
"""
import argparse, json, re, urllib.request
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
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

    out = {"_source": REST, "_n_species": len(species), "_n_names": len(index),
           "_note": "Matches are HINTS for the classifier, never an answer. See the module docstring.",
           "names": index}
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    n_tr = sum(1 for m in index.values() if m["trap"])
    n_en = sum(1 for m in index.values() if m["english_word"])
    n_sh = sum(1 for m in index.values() if m["shadowed_by"])
    print(f"  {len(species)} species -> {len(index)} searchable names")
    print(f"    english words: {n_en}   shadowed: {n_sh}   known traps: {n_tr}")
    print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
