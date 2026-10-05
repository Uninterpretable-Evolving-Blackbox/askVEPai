#!/usr/bin/env python3
"""Does the classifier name the ORGANISM correctly, and does the name agree with the binary factor?

WHY. Since 2026-09-20 the classifier returns an `organism` field beside the binary `species` factor,
and the data lookups (SIFT, frequency files, per-plugin species lists) are keyed on it. Nothing has
ever measured that field: every earlier species measurement scored human vs non-human only, where the
name does not matter. This does, and it also counts how often the name and the binary answer disagree
("Taeniopygia guttata ... species: human" was seen by hand on 2026-09-20).

CASES, since 2026-09-26: every non-human name in Ensembl's own index (`vep_ai_demo/species_index.json`),
754 names for 270 species (Ensembl's genomes grouped by taxon, as the engine groups them): scientific names, common names, breeds and strains, and names with an assembly or
hybrid tag. The index labels each name with what makes it hard to read, and results are reported per label:

    binomial        Nothobranchius furzeri          scientific name, unambiguous
    common          nine-banded armadillo           English name, several words
    english_word    turkey, salmon, cattle          the name is also an ordinary word
    strain          Rambouillet sheep               a breed or strain in front of the species
    trap            dog, drill, duck, guinea pig    the index flags these as commonly false hits
    tagged          muscovy duck (domestic type)    an assembly or hybrid tag in the name

THE 121 SAMPLE (`--sample-121`). One name per species, 30 per kind
(binomial, common, english_word, strain) plus the traps, tagged names left out: 30 per kind, so a clean
sweep bounds that kind's error rate below ~10% (rule of three, 3/30). The trap group has only 8 names in
the whole index; it is reported separately and its n is stated, because 8 bounds nothing useful (~31%).
Its results are in evidence/legacy_decisions/species_data/results/, where
species_options_scan_vs_model.py replays them.

TWO VERSIONS of every case, because naming is only hard when there is something to confuse it with:

    plain   the organism is the only one named
    decoy   a second organism is named as something else ("my supervisor works on {decoy}, but the
            samples are {organism}") -- the answer must still be the sample's organism

The other four factors are stated plainly in every query, as in `factors_150_tricky_cases.py`.

SCORED
  name        the resolved organism is the same species as the index's genome for that name
              (`va.species_key`: genomes of one Ensembl taxon, e.g. a breed or strain, are one
              species, because the data lists are per species)

CASE LIST FIXED. Cases are grouped (one per species in the sample) and decoys drawn with the first
two words of the production name (`_case_key`), not with `va.species_key`, so the questions asked do
not move when the engine's species grouping changes. Only the expected answer follows it.
  binary      the `species` factor, human / non-human
  disagree    the name resolves to a non-human species while the binary factor says human, or vice
              versa -- the two halves of the same reading contradicting each other

  python3 evidence/current_evidence/organism_754_names.py --export                  # cases only, no model
  NO_PROXY=localhost,127.0.0.1 python3 evidence/current_evidence/organism_754_names.py [--reader reasoning_on|reasoning_off] [--sample-121]
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "vep_ai_demo" / "vep_options.json"))
import vep_assistant as va                                              # noqa: E402

KINDS = ("binomial", "common", "english_word", "strain")
PER_KIND = 30

# The four non-target factors, stated plainly. Same idea as factors_150_tricky_cases's background: they are there so
# the query is a real scenario, and they are cycled so no single wording dominates.
BACKGROUND = [
    ("germline SNVs and small indels", "in coding exons", "I just need the consequence types."),
    ("somatic point mutations", "in promoters and enhancers", "I want to know which are pathogenic."),
    ("inherited structural variants", "in coding regions", "I just need the basic consequences."),
    ("acquired somatic CNVs", "in regulatory regions", "I want to know which are pathogenic."),
]
OPENERS = ["We have", "I'm working with", "Our lab just got back", "I've got a VCF of", "We called"]
DECOY_FRAMES = [
    "My supervisor works on {decoy}, but the samples are {organism}.",
    "The variants were first reported in {decoy}; ours are from {organism}.",
    "We followed a protocol written for {decoy}, and the samples are {organism}.",
    "Not a {decoy} study: the samples are {organism}.",
]
# A one-word species name needs an article to read like a sentence: "The samples are ass." is not
# something anyone writes, and answering "unstated" to it is defensible rather than wrong. Multi-word
# names take the plain frames.
PLAIN_FRAMES = [
    "The samples are from {organism}.",
    "These are {organism} samples.",
    "The data are from {organism}.",
]
PLAIN_FRAMES_ONE_WORD = [
    "The samples are from a {organism}.",
    "These samples come from a {organism}.",
    "The data are from a {organism}.",
]
DECOY_FRAMES_ONE_WORD = [
    "My supervisor works on {decoy}, but the samples are from a {organism}.",
    "The variants were first reported in {decoy}; ours are from a {organism}.",
    "We followed a protocol written for {decoy}, and the samples are from a {organism}.",
    "Not a {decoy} study: the samples are from a {organism}.",
]


def article(frame, name):
    """a -> an before a vowel, so the sentence reads naturally."""
    return frame.replace("a {organism}", "an {organism}") if name[:1] in "aeiou" else frame


# Index entries that carry an assembly or a hybrid tag ("gadus morhua (celtic sea) - gca_010882105.1")
# are real Ensembl names but nobody types them, so they are excluded: this measures reading a name out
# of a sentence, not parsing an accession. 174 of the 243 strain-level names survive the filter.
UNNATURAL = re.compile(r"[()]|gc[af]_?\d|\bv\d+\b| - |hybrid", re.IGNORECASE)


def load_index():
    """Ensembl's own names. Names the index derives for lookup (marked `derived`) are not test cases."""
    p = ROOT / "vep_ai_demo" / "species_index.json"
    return {n: v for n, v in json.loads(p.read_text())["names"].items() if not v.get("derived")}


def kind_of(name, v):
    if v.get("trap"):
        return "trap"
    if v.get("english_word"):
        return "english_word"
    if len(v["species"].split("_")) > 2:
        return "strain"
    return "binomial" if v.get("binomial") else "common"


def _case_key(production_name):
    """Genus and species words of a production name; draws the cases and decoys (see CASE LIST FIXED)."""
    return "_".join(production_name.split("_")[:2])


def build(seed=20260920):
    rng = random.Random(seed)
    idx = load_index()
    by_kind = defaultdict(list)
    for name, v in idx.items():
        if v["species"] == "homo_sapiens" or UNNATURAL.search(name):
            continue                                   # the binary factor covers human; this is naming
        by_kind[kind_of(name, v)].append((name, v))
    cases, used_species = [], set()
    for kind in KINDS + ("trap",):
        pool = sorted(by_kind[kind])
        rng.shuffle(pool)
        picked = []
        for name, v in pool:
            sp = _case_key(v["species"])
            if sp in used_species:                     # one case per species, so a species cannot
                continue                               # carry the result of two kinds at once
            used_species.add(sp)
            picked.append((name, v))
            if len(picked) == (len(pool) if kind == "trap" else PER_KIND):
                break
        for i, (name, v) in enumerate(picked):
            size_origin, region, goal = BACKGROUND[i % len(BACKGROUND)]
            opener = OPENERS[i % len(OPENERS)]
            bg = f"{opener} {size_origin} {region}. {goal}"
            one_word = " " not in name
            pf = PLAIN_FRAMES_ONE_WORD if one_word else PLAIN_FRAMES
            df = DECOY_FRAMES_ONE_WORD if one_word else DECOY_FRAMES
            decoy = rng.choice([n for n, w in pool if _case_key(w["species"]) != _case_key(v["species"])])
            cases.append({
                "id": f"{kind[:4]}-{i + 1}",
                "kind": kind,
                "name": name,
                "expected_species": va.species_key(v["species"]),
                "plain_query": f"{article(pf[i % len(pf)], name).format(organism=name)} {bg}",
                "decoy_query": f"{article(df[i % len(df)], name).format(decoy=decoy, organism=name)} {bg}",
                "decoy": decoy,
            })
    return cases


def build_all(seed=20260920):
    """Every non-human name in the index, one case per name (added 2026-09-23, David: check all of them).

    Names UNNATURAL filters out of the sample (assembly or hybrid tags) are kept here as kind "tagged",
    reported separately. A species appears once per name it has, so common species weigh more."""
    rng = random.Random(seed)
    idx = load_index()
    natural = [(n, v) for n, v in sorted(idx.items())
               if v["species"] != "homo_sapiens" and not UNNATURAL.search(n)]
    cases, count = [], Counter()
    for name, v in sorted(idx.items()):
        if v["species"] == "homo_sapiens":
            continue
        kind = "tagged" if UNNATURAL.search(name) else kind_of(name, v)
        i = count[kind]
        count[kind] += 1
        size_origin, region, goal = BACKGROUND[i % len(BACKGROUND)]
        bg = f"{OPENERS[i % len(OPENERS)]} {size_origin} {region}. {goal}"
        one_word = " " not in name
        pf = PLAIN_FRAMES_ONE_WORD if one_word else PLAIN_FRAMES
        df = DECOY_FRAMES_ONE_WORD if one_word else DECOY_FRAMES
        decoy = rng.choice([n for n, w in natural if _case_key(w["species"]) != _case_key(v["species"])])
        cases.append({
            "id": f"{kind[:4]}-{i + 1}",
            "kind": kind,
            "name": name,
            "expected_species": va.species_key(v["species"]),
            "plain_query": f"{article(pf[i % len(pf)], name).format(organism=name)} {bg}",
            "decoy_query": f"{article(df[i % len(df)], name).format(decoy=decoy, organism=name)} {bg}",
            "decoy": decoy,
        })
    return cases


def score(r, expected):
    """One answer scored: the organism the tool resolves, the human/non-human answer, and whether they clash."""
    name_ok = va.species_key(r["resolved"] or "") == expected
    binary_ok = r["species"] == "non-human"
    disagree = bool(r["resolved"]) and ((r["resolved"] != "homo_sapiens") != (r["species"] == "non-human"))
    return dict(r, name_ok=name_ok, binary_ok=binary_ok, disagree=disagree)


def summarise(rows, title):
    """Print the per-kind table; return (per_kind, total)."""
    n = len(rows)
    print(f"\n=== {title} ===")
    print(f"  {'kind':14} {'n':>3}  {'name plain':>11} {'name decoy':>11} {'binary plain':>13} "
          f"{'binary decoy':>13} {'name+binary disagree':>21}")
    summary = {}
    for k in KINDS + ("trap", "tagged"):
        sel = [r for r in rows if r["kind"] == k]
        if not sel:
            continue
        s = {f"name_{v}": sum(r["result"][v]["name_ok"] for r in sel) for v in ("plain", "decoy")}
        s.update({f"binary_{v}": sum(r["result"][v]["binary_ok"] for r in sel) for v in ("plain", "decoy")})
        s["disagree"] = sum(r["result"][v]["disagree"] for r in sel for v in ("plain", "decoy"))
        s["n"] = len(sel)
        summary[k] = s
        print(f"  {k:14} {len(sel):>3}  {s['name_plain']:>8}/{len(sel)} {s['name_decoy']:>8}/{len(sel)} "
              f"{s['binary_plain']:>10}/{len(sel)} {s['binary_decoy']:>10}/{len(sel)} {s['disagree']:>15}/{2 * len(sel)}")
    tot = {k: sum(s[k] for s in summary.values()) for k in ("name_plain", "name_decoy", "binary_plain",
                                                            "binary_decoy", "disagree", "n")}
    print(f"  {'TOTAL':14} {tot['n']:>3}  {tot['name_plain']:>8}/{n} {tot['name_decoy']:>8}/{n} "
          f"{tot['binary_plain']:>10}/{n} {tot['binary_decoy']:>10}/{n} {tot['disagree']:>15}/{2 * n}")

    return summary, tot


def rescore(path):
    """Re-resolve the saved `said` answers against today's species index; rewrite the file.

    The model's answers are not re-run: the organism a user gets is `resolve_model_organism(said)`, so a
    change to the index changes the score without a model call. A lookup that changes keeps its old
    value in `resolved_at_run`; an expected species that changes (the engine's species grouping) keeps
    its old value in `expected_at_run`."""
    d = json.load(open(path))
    idx = load_index()
    changed = 0
    for r in d["rows"]:
        expected = va.species_key(idx[r["name"]]["species"])
        if expected != r["expected_species"]:
            r.setdefault("expected_at_run", r["expected_species"])
            r["expected_species"] = expected
        for v in ("plain", "decoy"):
            x = r["result"][v]
            new = va.resolve_model_organism(x["said"])
            if new != x["resolved"]:
                x.setdefault("resolved_at_run", x["resolved"])
                changed += 1
            r["result"][v] = score(dict(x, resolved=new), r["expected_species"])
    d["per_kind"], d["total"] = summarise(d["rows"], f"re-scored {Path(path).name} against today's species index")
    d["rescored"] = {"date": time.strftime("%Y-%m-%d"), "index_names": len(va.load_species_index()),
                     "lookups_changed": changed}
    json.dump(d, open(path, "w"), indent=2)
    print(f"  {changed} lookups changed; wrote {path}")


def safe_read(model, q, think, timings):
    """native_read, retried once; a call that still fails is recorded with its error, not fatal."""
    for attempt in (1, 2):
        try:
            return native_read(model, q, think, timings)
        except Exception as e:                                          # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
    return {"said": None, "resolved": None, "species": None, "error": err}


def native_read(model, q, think, timings):
    body = {"model": model, "stream": False, "keep_alive": va.KEEP_ALIVE, "think": think,
            "messages": va.classifier_messages(q),
            "options": {"temperature": 0.0, "seed": 42, "num_predict": va._CLASSIFY_MAX_TOKENS}}
    req = urllib.request.Request(va._native_chat_url(), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    msg = d.get("message") or {}
    timings.append({"seconds": round(time.perf_counter() - t0, 3), "eval_count": d.get("eval_count"),
                    "done_reason": d.get("done_reason")})
    raw = json.loads((msg.get("content") or "{}")[(msg.get("content") or "{}").find("{"):
                                                  (msg.get("content") or "{}").rfind("}") + 1] or "{}")
    rec = va.parse_factor_classification(msg.get("content") or "") or {}
    return {"said": raw.get("organism"), "resolved": rec.get("_organism"), "species": rec.get("species")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--reader", choices=("reasoning_on", "reasoning_off"), default="reasoning_on",
                    help="reasoning_on = the tool's setting; reasoning_off = the same call with reasoning off")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--rescore", metavar="RESULTS_JSON", nargs="+",
                    help="re-resolve saved answers against today's species index, no model call")
    ap.add_argument("--sample-121", action="store_true",
                    help="the earlier 121-organism sample instead of every name (754); written beside "
                         "species_options_scan_vs_model.py, which replays it")
    a = ap.parse_args()
    if a.rescore:
        for path in a.rescore:
            rescore(path)
        return

    cases = build() if a.sample_121 else build_all()
    stem = "organism_121_names" if a.sample_121 else "organism_754_names"
    out_dir = ROOT / ("evidence/legacy_decisions/species_data/results" if a.sample_121
                      else "evidence/current_evidence/results")
    a.json = a.json or str(out_dir / f"{stem}_{a.reader}.json")
    csv_path = out_dir / f"{stem}_list.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "kind", "organism as written", "expected species", "decoy", "plain query", "decoy query"])
        for c in cases:
            w.writerow([c["id"], c["kind"], c["name"], c["expected_species"], c["decoy"],
                        c["plain_query"], c["decoy_query"]])
    print(f"{len(cases)} organisms x 2 versions = {2 * len(cases)} queries -> {csv_path.relative_to(ROOT)}")
    print("  per kind: " + ", ".join(f"{k} {sum(1 for c in cases if c['kind'] == k)}"
                                     for k in KINDS + ("trap", "tagged")))
    if a.export:
        return

    run = cases[: a.limit] if a.limit else cases
    timings = []
    jobs = [(i, v) for i in range(len(run)) for v in ("plain", "decoy")]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(lambda j: (j, safe_read(a.model, run[j[0]][f"{j[1]}_query"],
                                                    a.reader == "reasoning_on", timings)), jobs))
    got = {j: r for j, r in out}

    rows = []
    for i, c in enumerate(run):
        res = {v: score(got[(i, v)], c["expected_species"]) for v in ("plain", "decoy")}
        rows.append(dict(c, result=res))
        marks = "".join(("N" if res[v]["name_ok"] else "n") + ("B" if res[v]["binary_ok"] else "b")
                        for v in ("plain", "decoy"))
        bad = "" if marks == "NBNB" else f"   said plain={res['plain']['said']!r} decoy={res['decoy']['said']!r}"
        print(f"  {c['id']:10} {c['kind']:13} {c['name'][:28]:30} {marks}{bad}", flush=True)

    summary, tot = summarise(rows, f"organism naming: {len(rows)} organisms x 2, {a.model}, reader {a.reader}")
    errors = sum(1 for r in rows for v in ("plain", "decoy") if r["result"][v].get("error"))
    print(f"\n  calls that failed twice (scored wrong): {errors}")
    if not timings:
        sys.exit("no model call succeeded: " + next(r["result"][v]["error"] for r in rows
                                                   for v in ("plain", "decoy") if r["result"][v].get("error")))
    secs = sorted(t["seconds"] for t in timings)
    print(f"\n  per-call time under {a.workers} parallel requests: median {secs[len(secs) // 2]} s")
    print(f"  cases where the name was wrong but the binary answer right: "
          f"{sum(1 for r in rows for v in ('plain', 'decoy') if not r['result'][v]['name_ok'] and r['result'][v]['binary_ok'])}")
    json.dump({"model": a.model, "reader": a.reader, "prompt": va._classifier_prompt_version(),
               "per_kind": summary, "total": tot, "rows": rows}, open(a.json, "w"), indent=2)
    print(f"  wrote {a.json}")


if __name__ == "__main__":
    main()
