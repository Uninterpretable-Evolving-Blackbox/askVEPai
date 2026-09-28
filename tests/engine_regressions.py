#!/usr/bin/env python3
"""Regression cases for the engine defects found in the 2026-09-27 audit (docs/AUDIT_2026-09-27.md §4).

Each fix is general (whole-word organism matching, Ensembl's per-file species class, taxon-based
species keys, every build named); the cases below are the audit's reproductions, kept so the defect
cannot return. No model: the classifier is stubbed or the network call is intercepted.

  python3 tests/engine_regressions.py
"""
import contextlib, io, json, os, subprocess, sys, urllib.request
from pathlib import Path

os.environ.setdefault("PYTHONHASHSEED", "0")
ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va  # noqa: E402

OPTIONS = va.load_knowledge_base()
OPTIONS = OPTIONS[0] if isinstance(OPTIONS, tuple) else OPTIONS
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def run(tup, query, level="standard", context=None):
    """stdout and return value of run_recommend with the classifier stubbed to `tup`."""
    saved = []
    real_infer, real_save = va.infer_factors, va.save_result
    va.infer_factors = lambda *a, **k: None if tup is None else dict(tup)
    va.save_result = lambda *a, **k: saved.append(a)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = va.run_recommend(None, "stub", OPTIONS, [], query, level=level, clarify="state",
                                  context=context)
    finally:
        va.infer_factors, va.save_result = real_infer, real_save
    return buf.getvalue(), rc, saved


def tup(species, size=("small",), goal=("clinical-interpretation",), region=("coding",), organism=None):
    t = {"species": species, "origin": "germline", "variant_size_class": list(size),
         "region_focus": list(region), "analysis_goal": list(goal), "_request_type": "configure"}
    if organism:
        t["_organism"] = organism
    return t


def recommended(out):
    """The lines under RECOMMENDED, all passes."""
    rec, on = [], False
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("RECOMMENDED"):
            on = True
            continue
        if on and (not s or s.startswith(("OPTIONAL", "ALREADY ON", "="))):
            on = False
        if on:
            rec.append(s)
    return rec


print("E1  a failed classifier call is an error, not a configuration")
out, rc, saved = run(None, "Germline exome, which variants are pathogenic?")
check("run_recommend returns 1", rc == 1, rc)
check("no configuration printed", "YOUR VEP CONFIGURATION" not in out)
check("the failure is explained", "Could not read the scenario" in out)
check("nothing saved", not saved)
p = subprocess.run([sys.executable, "vep_assistant.py", "Germline exome, which variants are pathogenic?"],
                   cwd=DEMO, capture_output=True, text=True, timeout=120,
                   env=dict(os.environ, OLLAMA_BASE_URL="http://127.0.0.1:9/v1", NO_PROXY="127.0.0.1"))
check("CLI exits 1 when Ollama is unreachable", p.returncode == 1, p.returncode)

print("\nK4  seed and temperature reach the model call")
captured = {}


def fake_urlopen(req, timeout=None):
    captured["body"] = json.loads(req.data)
    raise OSError("intercepted")


real_urlopen = urllib.request.urlopen
urllib.request.urlopen = fake_urlopen
try:
    va.infer_factors(None, "gemma4:26b", "Germline SNVs", seed=43, temperature=0.8)
finally:
    urllib.request.urlopen = real_urlopen
opts = captured.get("body", {}).get("options", {})
check("native call sends seed 43, temperature 0.8", opts.get("seed") == 43 and opts.get("temperature") == 0.8, opts)
check("the failure reason is kept", "intercepted" in (va.LAST_CLASSIFIER_ERROR or ""), va.LAST_CLASSIFIER_ERROR)

print("\nE2  organism names match on whole words")
expect = {
    "guinea-pig": "cavia_porcellus", "guinea pig": "cavia_porcellus", "sea bass": None,
    "grass carp": None, "cassowary": None, "spiny dogfish": None, "turkey vulture": None,
    "horseshoe crab": None, "crab eating macaque": "macaca_fascicularis",
    "Cricetulus griseus": "cricetulus_griseus", "Heterocephalus glaber": "heterocephalus_glaber",
    "Cyprinus carpio": "cyprinus_carpio", "naked mole rat": "heterocephalus_glaber",
    "muscovy duck": "cairina_moschata_domestica", "domestic pig": "sus_scrofa", "sharksucker": "echeneis_naucrates",
    "dingo": "canis_lupus_dingo", "dog": "canis_lupus_familiaris", "cattle": "bos_taurus",
    "pig": "sus_scrofa", "human": "homo_sapiens",
}
for name, want in expect.items():
    got = va.resolve_model_organism(name)
    ok = (got is None) if want is None else (got is not None and va.species_key(got) == va.species_key(want))
    check(f"{name!r} -> {want}", ok, got)
check("a list-valued organism is not a name", va.resolve_model_organism(["mouse", "rat"]) is None)
for q, want in {"We have a guinea-pig colony with germline SNVs": None,
                "naked mole-rat exomes": "heterocephalus_glaber", "pig herd SNVs": "sus_scrofa"}.items():
    got = va.resolve_species_name(q)
    ok = (got is None or va.species_key(got) == "cavia_porcellus") if want is None else \
        (got is not None and va.species_key(got) == want)
    check(f"name scan {q!r} -> {want or 'not pig'}", ok, got)

# Every index name, with hyphens swapped for spaces and back, and with its first word dropped: the
# lookup may return the right species or nothing, never another species (unless the variant is itself
# another species' name, e.g. 'guinea pig' minus 'guinea' is 'pig', 'kangaroo rat' minus 'kangaroo' is 'rat').
idx = va.load_species_index()
exact = {va._name_words(k): v["species"] for k, v in idx.items()}
wrong = []
for k, v in idx.items():
    words = k.split()
    for var in {k, k.replace(" ", "-"), k.replace("-", " "), " ".join(words[1:])} - {""}:
        got = va.resolve_model_organism(var)
        if got is None or va.species_key(got) == va.species_key(v["species"]):
            continue
        other = exact.get(va._name_words(var)) or va._WORD_TO_PRODUCTION.get(va._name_words(var))
        if other and va.species_key(other) == va.species_key(got):
            continue
        wrong.append((var, v["species"], got))
check(f"no index-name variant resolves to another species ({len(idx)} names)", not wrong, wrong[:5])

print("\nE3  the CADD file choice follows Ensembl's per-file species class")
out, _, _ = run(tup("non-human", organism="sus_scrofa"), "pig herd")
check("pig SNVs: CADD SNVs annotation file", "CADD drop-down: CADD SNVs annotation file" in out)
check("pig SNVs: no human-only SNV+InDel file", "CADD SNVs and InDels annotation file" not in out)
out, _, _ = run(tup("non-human", size=("structural-CNV",), organism="sus_scrofa"), "pig herd")
check("pig SVs: CADD dropped with a reason", "Dropped cadd on this pass" in out
      and not any("CADD" in r for r in recommended(out)))
out, _, _ = run(tup("human"), "germline exome on GRCh38")
check("human SNVs keep the default file", "CADD drop-down: CADD SNVs and InDels annotation file" in out)

print("\nE4  a text naming both human builds is not read as the first one")
check("'lifted over from hg19 to GRCh38' -> no build read", va.infer_assembly("lifted over from hg19 to GRCh38") is None)
check("'GRCh37' -> GRCh37", va.infer_assembly("variants on GRCh37") == "GRCh37")
check("'hg38' -> GRCh38", va.infer_assembly("an hg38 VCF") == "GRCh38")
check("mouse build ignored", va.infer_assembly("GRCm39 and GRCh38") == "GRCh38")
both, _, _ = run(tup("human"), "calls lifted over from hg19 to GRCh38")
g38, _, _ = run(tup("human"), "calls on GRCh38")
cfg = lambda t: t[t.index("YOUR VEP CONFIGURATION"):]
check("both builds named: GRCh38 configuration", cfg(both) == cfg(g38))
check("both builds named: disclosed", "your text names both GRCh37 and GRCh38" in both)
check("the build used is printed", "- assembly: GRCh38" in g38)

print("\nE5  species keys follow Ensembl's taxon, not the first two words")
check("dingo and dog are different species", va.species_key("canis_lupus_dingo") != va.species_key("canis_lupus_familiaris"))
check("a dog breed is dog", va.species_key("canis_lupus_familiarisboxer") == va.species_key("canis_lupus_familiaris"))
check("dingo is not offered dog SIFT", not va.offer_available("sift", OPTIONS, "canis_lupus_dingo"))
check("a boxer is offered dog SIFT", va.offer_available("sift", OPTIONS, "canis_lupus_familiarisboxer"))
check("plugin-list assembly names map to the index", va.species_key("gallus_gallus_GCA_000002315.5") == "gallus_gallus")
out, _, _ = run(tup("non-human", goal=("population-frequency",), organism="canis_lupus_dingo"), "dingo")
check("dingo gets no dog frequency data", not any("Population frequency data" in r for r in recommended(out)))

print("\nE6  --full does not put back an option the pass has no data file for")
out, _, _ = run(tup("human", size=("structural-CNV",)), "germline SVs on GRCh37", level="full")
check("GRCh37 SV --full: no CADD", not any("CADD" in r for r in recommended(out)))
check("GRCh37 SV --full: removals labelled by cause", "not on this assembly:" in out
      and "removed on a conflict" not in out)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
