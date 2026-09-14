#!/usr/bin/env python3
"""Which species actually have the data an option needs -- from Ensembl's own sources, not ours.

WHY. `species` is a binary factor (human / non-human) and the mentors are reviewing that scheme, so
it stays binary. But the form's DATA is not uniform across non-human: Ensembl computes SIFT for
eleven non-human species and PolyPhen for none; the form renders CCDS for mouse and variant synonyms
for pig; custom population-frequency files exist for chicken, dog, goat and sheep. A cattle query and a
zebra-finch query are both "non-human" and should not get the same predictors. This is the same shape
as assembly -- data that exists for some inputs and not others -- and it rides alongside the factor as
a lookup, exactly as assembly does (ONBOARDING §2).

SOURCES, all saved under research/ensembl_docs_116/ or ensembl_source/:
  SIFT species      the sentence on Ensembl's "Pathogenicity predictions" page:
                    "SIFT predictions are also available for cat, chicken, cow, dog, goat, horse, mouse,
                    pig, rat, sheep and zebrafish." PolyPhen-2 is stated as human only.
  form gating       InputForm.pm `_stt_<Species>` classes: ccds = Homo_sapiens + Mus_musculus;
                    var_synonyms = Homo_sapiens + Sus_scrofa.
  frequency files   vep_custom_web_config.json, one entry per species x assembly.
Names are resolved to Ensembl production names through the 356-species index.

  python3 work/harness/build_species_data.py
"""
import json, re, html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "work" / "research" / "ensembl_docs_116"
OUT = ROOT / "work" / "generation" / "generation_config" / "species_data.json"
idx = json.load(open(ROOT / "work/generation/generation_config/species_index.json"))["names"]

SYN = {"cow": ["cow", "cattle", "bos taurus"], "pig": ["pig", "sus scrofa"], "dog": ["dog", "canis lupus familiaris"],
       "chicken": ["chicken", "gallus gallus"], "cat": ["cat", "felis catus"], "horse": ["horse", "equus caballus"],
       "mouse": ["mouse", "mus musculus"], "rat": ["rat", "rattus norvegicus"], "sheep": ["sheep", "ovis aries"],
       "goat": ["goat", "capra hircus"], "zebrafish": ["zebrafish", "danio rerio"], "human": ["human", "homo sapiens"]}


def production(word):
    for n in SYN.get(word, [word]):
        if n in idx:
            return idx[n]["species"]
    raise SystemExit(f"cannot resolve '{word}' to a production name")


t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", open(DOCS / "protein_function.html", errors="replace").read())))
m = re.search(r"SIFT predictions are also available for ([^.]+)\.", t)
sift_words = [w.strip() for w in re.split(r",| and ", m.group(1)) if w.strip()]
# SIFT is computed per SPECIES and Ensembl's own table lists the strains under it (Dog - Boxer,
# Sheep - Texel), so each resolved name is expanded to every production name sharing its
# genus_species prefix. The engine's gate compares the same prefix (`species_key`).
all_prod = sorted({v["species"] for v in idx.values()})
def key(name): return "_".join(name.split("_")[:2])
bases = {key(production("human"))} | {key(production(w)) for w in sift_words}
sift = sorted(p for p in all_prod if key(p) in bases)

customs = json.load(open(ROOT / "work/ensembl_source/vep_custom_web_config.json"))
customs = customs if isinstance(customs, list) else (customs.get("customs") or list(customs.values())[0])
freq = {}
for c in customs:
    sp = c.get("species"); 
    if not sp or sp == "homo_sapiens":
        continue
    freq.setdefault(sp, []).append({"assembly": c.get("assembly"), "name": c.get("name") or c.get("label") or c.get("id"),
                                    "section": c.get("section")})

data = {
    "_sources": {
        "sift": "research/ensembl_docs_116/protein_function.html: '" + m.group(0) + "'",
        "polyphen": "same page: 'For human variants ... we use SIFT and PolyPhen-2'",
        "ccds": "ensembl_source/VEP/InputForm.pm:401 field_class '_stt_Homo_sapiens _stt_Mus_musculus'",
        "var_synonyms": "ensembl_source/VEP/InputForm.pm:472 class '_stt_Homo_sapiens _stt_Sus_scrofa'",
        "frequency_files": "ensembl_source/vep_custom_web_config.json (release/115 snapshot), non-human entries",
    },
    "_built": "2026-09-15 by work/harness/build_species_data.py",
    "sift": sift,
    "polyphen": [production("human")],
    "ccds": sorted({production("human"), production("mouse")}),
    "var_synonyms": sorted({production("human"), production("pig")}),
    "frequency_files": dict(sorted(freq.items())),
}
OUT.write_text(json.dumps(data, indent=1) + "\n")
print(f"wrote {OUT}")
print(" sift:", len(data["sift"]), data["sift"])
print(" frequency files:", {k: len(v) for k, v in data["frequency_files"].items()})
