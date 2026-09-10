#!/usr/bin/env python3
"""A/B the OUTPUT of two configurations through real VEP — columns AND rows.

WHY THIS EXISTS. Every metric this project publishes compares OPTION SETS. Exp 16 went one step
further and asked whether a lost option's field was populated, but it still runs only the truth
configuration and infers the fallback's output as "truth minus those fields". So the whole evaluation
measures COLUMNS and never ROWS, and the options that change which variants and which transcripts come
back at all are invisible to it:

    frequency (--check_frequency)  a PRE-FILTER: drops input variants before annotation
    pick / pick_allele / per_gene  collapse many transcript rows into one
    coding_only                    drops non-coding consequence rows
    core_type (refseq/merged/...)  changes which transcript set is annotated at all

`origin`'s entire measured cost in the re-prompting table is `frequency`, which is exactly one of
these. This harness runs BOTH configurations end to end and diffs the two result tables.

WHAT IT REPORTS, per variant class:
    ROWS     transcript_consequences / colocated_variants / regulatory_feature_consequences counts
    COLUMNS  keys populated in A but not in B, and the reverse
    FILL     per column, the fraction of transcript rows carrying a non-empty value

THE TRAP THIS HARNESS EXISTS TO AVOID. **Ensembl REST silently ignores parameters it does not
support** — it returns HTTP 200 and unchanged output. Verified on 2026-09-06 by passing
`canonical_only=1`, which is not a REST parameter at all: 200, and byte-identical row counts. So a
plain A/B diff CANNOT distinguish "this option changed nothing" from "REST cannot do this option",
and would report `check_frequency` as harmless when the truth is that it is unmeasurable here.

Every row-affecting option therefore carries a verdict established by positive control, and anything
in the IGNORED set is reported as UNMEASURABLE rather than as "no change". Re-derive the table with
--probe if a future Ensembl release changes what REST honours.

TWO FINDINGS FROM BUILDING THIS, both of which bound what it can ever report (2026-09-06, rel 116):

1. **REST returns SIFT, PolyPhen and clin_sig with NO parameters at all.** Only `mane` of those four
   actually requires its flag. So on REST, dropping `sift` from a configuration does not remove
   SIFT from the output, and a column diff of truth-vs-fallback for the clinical->basic pair shows
   `mane` alone. Exp 16 reports `clinvar`, `polyphen` and `sift` as lost on `coding_known`; that is
   its REALIZED measurement (was the field populated in the truth run), which is sound, carried into
   a "lost" label, which is not — it assumes option-removal implies field-removal, and Exp 16 never
   ran the fallback side to check. The same conclusion holds on the WEB FORM for a different reason:
   all four are `web_default_on`, so the form ships them switched on and the tool only ever says
   SWITCH THESE ON. An option the user already has is not lost by our failing to recommend it.

2. **The only row-affecting option our recommender ever VARIES is `frequency`, and REST ignores it.**
   Over all 108 factor tuples, `core_type` is recommended in 108/108 (so it cancels in every diff)
   and `frequency` in 9/108. No tuple pair differs on any other row option. `frequency` is
   `origin`'s entire measured cost in the re-prompting table, and it is a pre-filter REST will not
   apply. So the row machinery below is correct and proven by --probe, and on real configurations it
   has exactly one thing to measure and cannot measure it here. **Measuring `origin`'s true output
   cost requires a local VEP install or the web form.** That is a precise, bounded statement of what
   Stage 7 is actually for.

  python work/harness/run_vep_ab.py --pair clinical-interpretation:basic-consequence
  python work/harness/run_vep_ab.py --a-factors species=human,... --b-factors species=human,...
  python work/harness/run_vep_ab.py --probe          # re-derive the honoured/ignored table
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402
# Reuse rather than restate: the option->param map and the variant panel are already established and
# already carry their own provenance. Duplicating them here would let the two drift.
from run_vep_rest import REST_PARAM, COLUMN_VERDICT, PANEL, SPECIES_PANEL, fetch_release   # noqa: E402

REST = "https://rest.ensembl.org"

# ROW-AFFECTING OPTIONS: the ones a column diff cannot see. `verdict` was established empirically on
# 2026-09-06 against Ensembl 116 by running each param against a variant chosen so that an honoured
# param MUST visibly change the output (the positive control). Re-derive with --probe.
#
#   HONOURED  REST applies it and the row counts move
#   IGNORED   REST returns 200 and changes nothing -> effect is UNMEASURABLE here, not absent
ROW_PARAM = {
    "pick":        ("pick",        None,          "HONOURED", "24 -> 1 transcript rows"),
    "pick_allele": ("pick_allele", None,          "HONOURED", "24 -> 1 transcript rows"),
    "per_gene":    ("per_gene",    None,          "HONOURED", "24 -> 2 transcript rows"),
    "core_type":   ("refseq",      "gencode_basic", "HONOURED", "24 -> 2 (refseq) / 16 (gencode_basic) / 26 (merged)"),
    "coding_only": ("coding_only", None,          "IGNORED",  "3 of 24 rows are non-coding; all 24 still returned"),
    "most_severe": ("most_severe", None,          "IGNORED",  "identical keys and structure; a text-output flag"),
    "summary":     ("summary",     None,          "IGNORED",  "no change"),
    "frequency":   ("check_frequency", None,      "IGNORED",  "rs1800795 is common (MAF~0.4) and survives exclude-common"),
}

GOALS = ("basic-consequence", "clinical-interpretation", "population-frequency")
BASE_FACTORS = {"species": "human", "origin": "germline",
                "variant_size_class": ["small"], "region_focus": ["coding"]}


def fetch(species, endpoint, ident, params):
    q = urllib.parse.urlencode({**params, "content-type": "application/json"})
    url = f"{REST}/vep/{species}/{endpoint}/{urllib.parse.quote(ident)}?{q}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=90) as r:
                return json.loads(r.read().decode()), None
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:150]
            # 429 is rate limiting and is worth waiting out; everything else is a real answer.
            if e.code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            return None, f"HTTP {e.code}: {body}"
        except Exception as e:                                   # noqa: BLE001
            if attempt < 2:
                time.sleep(2)
                continue
            return None, f"{type(e).__name__}: {e}"
    return None, "exhausted retries"


def blocks(payload, kind):
    """The list of records of one kind, across every variant in the payload."""
    out = []
    for rec in payload or []:
        out += rec.get(kind, []) or []
    return out


def row_shape(payload):
    return {k: len(blocks(payload, k)) for k in
            ("transcript_consequences", "colocated_variants", "regulatory_feature_consequences")} | {
        "variant_records": len(payload or [])}


def row_ids(payload):
    """The IDENTITY of every row, not just how many there are.

    row_shape counts. Two configurations can return the same NUMBER of rows and not the same rows --
    `core_type` swaps the transcript set outright (RefSeq vs Ensembl/GENCODE vs merged), so a
    same-size, entirely different set reports as "ROWS identical" under a count comparison. That is
    the one claim a count cannot support, and "the guess costs nothing" depends on it.

    Keyed on the stable identifier per block type; falls back to a sorted repr so an unkeyed row
    still participates rather than silently collapsing with its siblings.
    """
    out = {}
    for kind, key in (("transcript_consequences", "transcript_id"),
                      ("colocated_variants", "id"),
                      ("regulatory_feature_consequences", "regulatory_feature_id")):
        ids = []
        for b in blocks(payload, kind):
            if not isinstance(b, dict):
                continue
            ids.append(str(b.get(key) or sorted(b.items(), key=lambda kv: kv[0])))
        out[kind] = ids
    return out


def populated_keys(payload):
    """Every key carrying a non-empty value anywhere in the payload, with where it was seen."""
    seen = {}
    for rec in payload or []:
        groups = [("record", [rec])]
        for kind in ("transcript_consequences", "colocated_variants",
                     "regulatory_feature_consequences"):
            groups.append((kind, rec.get(kind, []) or []))
        for where, items in groups:
            for b in items:
                if not isinstance(b, dict):
                    continue
                for k, v in b.items():
                    if v not in (None, "", [], {}):
                        seen.setdefault(k, where)
    return seen


def fill_rates(payload):
    """Per key on transcript_consequences: fraction of rows carrying a non-empty value."""
    tcs = blocks(payload, "transcript_consequences")
    if not tcs:
        return {}, 0
    keys = {k for t in tcs for k in t}
    return {k: sum(1 for t in tcs if t.get(k) not in (None, "", [], {})) / len(tcs)
            for k in keys}, len(tcs)


def params_for(recommended):
    """Split a recommended set into what REST can show, what it ignores, and what it never exposes."""
    params, column_ok, row_ok, ignored, unexposed = {}, [], [], [], []
    for oid in recommended:
        if oid in ROW_PARAM:
            p, alt, verdict, _why = ROW_PARAM[oid]
            if verdict == "HONOURED":
                params[p] = 1
                row_ok.append(oid)
            else:
                ignored.append(oid)
        elif oid in REST_PARAM:
            # COLUMN_VERDICT is the positive control for the column half, exactly as ROW_PARAM's
            # verdict is for the row half. An option REST returns with no parameter at all cannot
            # show up in a diff, so counting it as measurable would report "no loss" for something
            # this harness simply cannot see. Send the parameter anyway (harmless, and keeps the two
            # sides identical apart from the options under test), but do not claim it was measured.
            p, _fields = REST_PARAM[oid]
            params[p] = 1
            if COLUMN_VERDICT.get(oid) == "HONOURED":
                column_ok.append(oid)
            else:
                ignored.append(oid)
        else:
            unexposed.append(oid)
    return params, sorted(column_ok), sorted(row_ok), sorted(ignored), sorted(unexposed)


def fetch_cohort(species, panel, params):
    """The whole PANEL as ONE callset — the shape a real user submits.

    Every per-class number in this harness annotates a single variant, but the tool's target is a
    variant SET, and enable-F1's defence rests on sets. REST batches by input type, so a mixed panel
    is two POSTs (hgvs notations + rsIDs) whose records are concatenated; the option parameters ride
    in the same body and are identical for both sides apart from the options under test."""
    hgvs = [ident for ep, ident, _w in panel.values() if ep == "hgvs"]
    ids = [ident for ep, ident, _w in panel.values() if ep == "id"]
    out = []
    for endpoint, key, vals in (("hgvs", "hgvs_notations", hgvs), ("id", "ids", ids)):
        if not vals:
            continue
        req = urllib.request.Request(
            f"{REST}/vep/{species}/{endpoint}?content-type=application/json",
            data=json.dumps({key: vals, **params}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        got = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    got = json.loads(r.read().decode())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                return None, f"POST {endpoint}: HTTP {e.code}: {e.read().decode()[:120]}"
            except Exception as e:                               # noqa: BLE001
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None, f"POST {endpoint}: {type(e).__name__}: {e}"
        out += got or []
        time.sleep(0.4)
    return out, None


def rec_keys(rec):
    """Populated keys of ONE variant record, all block kinds."""
    return set(populated_keys([rec]))


def diff_cohort(species, pa, pb, label_a, label_b, measurable):
    payload_a, err_a = fetch_cohort(species, PANEL, pa)
    payload_b, err_b = fetch_cohort(species, PANEL, pb)
    if err_a or err_b:
        print(f"  COHORT ERROR  A={err_a or 'ok'}  B={err_b or 'ok'}")
        return None
    sa, sb = row_shape(payload_a), row_shape(payload_b)
    ia, ib = row_ids(payload_a), row_ids(payload_b)
    ka, kb = set(populated_keys(payload_a)), set(populated_keys(payload_b))
    lost, gained = sorted(ka - kb), sorted(kb - ka)
    print(f"\n  COHORT — all {len(payload_a)} panel variants as one callset")
    moved = {k: (sa[k], sb[k]) for k in sa if sa[k] != sb[k]}
    for k, (x, y) in moved.items():
        print(f"    ROWS     {k:30} {label_a}={x} {label_b}={y}  delta {y - x:+d}")
    if not moved:
        print(f"    ROWS     identical ({sa['transcript_consequences']} transcript rows both sides)")
    print(f"    COLUMNS in the whole result file: {label_a}={len(ka)}  {label_b}={len(kb)}")
    print(f"    lost in {label_b}: {len(lost)} — {', '.join(lost)}")
    if gained:
        print(f"    gained in {label_b}: {', '.join(gained)}")
    # The hypothesis under test: the per-variant 2-19 spread collapses at cohort scale because a
    # callset realizes nearly every class. Per-record losses restate the spread on the same payload.
    b_by_input = {r.get("input") or r.get("id"): r for r in payload_b}
    per = []
    for r in payload_a:
        key = r.get("input") or r.get("id")
        if key in b_by_input:
            per.append(len(rec_keys(r) - rec_keys(b_by_input[key])))
    if per:
        print(f"    per-variant columns lost: min {min(per)}  mean {sum(per)/len(per):.1f}  "
              f"max {max(per)}   -> cohort-level {len(lost)}")
    return {"cohort_rows_a": sa, "cohort_rows_b": sb, "columns_lost": lost,
            "columns_gained": gained, "per_variant_lost": per,
            "n_variants": len(payload_a), "measurable_options": measurable}


def resolve(factors, catalogue):
    resolved = va.resolve_for_query(factors, catalogue) or {}
    return sorted(o for o, (e, _p, _g) in resolved.items() if e)


def probe():
    """Re-derive the HONOURED/IGNORED table. The positive control is the whole point: an honoured
    param MUST move the numbers on the chosen variant, or the test proves nothing."""
    V = "ENST00000366667.4:c.803C>T"
    base, err = fetch("human", "hgvs", V, {})
    if err:
        sys.exit(f"probe baseline failed: {err}")
    b = row_shape(base)["transcript_consequences"]
    print(f"baseline transcript_consequences = {b}  (variant {V})")
    print("a param that changes nothing here is IGNORED, not harmless — REST 200s on unknown params\n")
    for oid, (p, alt, recorded, why) in sorted(ROW_PARAM.items()):
        time.sleep(0.5)
        payload, err = fetch("human", "hgvs", V, {p: 1})
        if err:
            print(f"  {oid:14} {p:16} ERROR {err}")
            continue
        n = row_shape(payload)["transcript_consequences"]
        now = "HONOURED" if n != b else "IGNORED"
        flag = "" if now == recorded else f"   <-- CHANGED, table says {recorded}"
        print(f"  {oid:14} {p:16} {n:3d} rows  {now:9}{flag}")
    print("\n  control: canonical_only is not a REST parameter at all")
    time.sleep(0.5)
    payload, _ = fetch("human", "hgvs", V, {"canonical_only": 1})
    n = row_shape(payload)["transcript_consequences"] if payload else -1
    print(f"  {'canonical_only':14} {'(not a param)':16} {n:3d} rows  "
          f"{'IGNORED — proves 200 does not mean supported' if n == b else 'UNEXPECTED'}")


def diff_one(species, cls, entry, pa, pb, label_a, label_b):
    endpoint, ident, what = entry
    payload_a, err_a = fetch(species, endpoint, ident, pa)
    time.sleep(0.4)
    payload_b, err_b = fetch(species, endpoint, ident, pb)
    time.sleep(0.4)
    if err_a or err_b:
        print(f"\n  {cls:18} ERROR  A={err_a or 'ok'}  B={err_b or 'ok'}")
        return None

    sa, sb = row_shape(payload_a), row_shape(payload_b)
    ia, ib = row_ids(payload_a), row_ids(payload_b)
    ka, kb = populated_keys(payload_a), populated_keys(payload_b)
    fa, na = fill_rates(payload_a)
    fb, nb = fill_rates(payload_b)

    print(f"\n  {cls}  ({what})")
    moved = {k: (sa[k], sb[k]) for k in sa if sa[k] != sb[k]}
    # IDENTITY, not size. A same-count swap is the failure a count comparison cannot see.
    swapped = {}
    for kind in ia:
        only_a, only_b = sorted(set(ia[kind]) - set(ib[kind])), sorted(set(ib[kind]) - set(ia[kind]))
        if only_a or only_b:
            swapped[kind] = {"only_a": only_a, "only_b": only_b}
    if moved:
        for k, (x, y) in moved.items():
            print(f"    ROWS     {k:34} {label_a}={x:<4} {label_b}={y:<4}  delta {y - x:+d}")
    if swapped:
        for kind, d in swapped.items():
            print(f"    ROWS-ID  {kind:30} only in {label_a}: {len(d['only_a'])}   "
                  f"only in {label_b}: {len(d['only_b'])}")
            for r in d["only_a"][:3]:
                print(f"               - {label_a} only: {r[:60]}")
            for r in d["only_b"][:3]:
                print(f"               - {label_b} only: {r[:60]}")
    if not moved and not swapped:
        print(f"    ROWS     identical  ({sa['transcript_consequences']} transcript rows, "
              f"SAME rows on both sides — checked by id, not count)")
    elif not moved and swapped:
        print(f"    ROWS     same COUNT but DIFFERENT rows — a swap a count check would have missed")

    lost = sorted(set(ka) - set(kb))
    gained = sorted(set(kb) - set(ka))
    if lost:
        print(f"    COLUMNS  lost in {label_b}:   {', '.join(f'{k}[{ka[k]}]' for k in lost)}")
    if gained:
        print(f"    COLUMNS  gained in {label_b}: {', '.join(f'{k}[{kb[k]}]' for k in gained)}")
    if not lost and not gained:
        print("    COLUMNS  identical key sets")

    shifted = {k: (fa[k], fb[k]) for k in set(fa) & set(fb) if abs(fa[k] - fb[k]) > 0.001}
    if shifted:
        for k, (x, y) in sorted(shifted.items()):
            print(f"    FILL     {k:34} {x:.0%} -> {y:.0%}   (of {na} vs {nb} transcript rows)")
    return {"class": cls, "rows_a": sa, "rows_b": sb, "rows_swapped": swapped,
            "columns_lost": lost, "columns_gained": gained,
            "fill_shift": {k: list(v) for k, v in shifted.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", help="truth:fallback analysis goals, e.g. "
                                   "clinical-interpretation:basic-consequence")
    ap.add_argument("--a-factors", help="species=human,origin=germline,...")
    ap.add_argument("--b-factors")
    ap.add_argument("--species", default="human")
    ap.add_argument("--probe", action="store_true", help="re-derive the honoured/ignored table")
    ap.add_argument("--cohort", action="store_true",
                    help="also run the whole panel as ONE callset per side — the shape a user "
                         "actually submits — and report per-variant vs cohort-level column loss")
    ap.add_argument("--json", help="write the structured diff here")
    args = ap.parse_args()

    if args.probe:
        probe()
        return

    catalogue, _ = va.load_knowledge_base()

    def parse(s):
        ft = {}
        for part in s.split(","):
            k, v = part.split("=", 1)
            ft[k] = v.split("+") if k in va.MULTI_FACTORS else v
        return ft

    if args.pair:
        truth, fallback = args.pair.split(":", 1)
        for g in (truth, fallback):
            if g not in GOALS:
                sys.exit(f"unknown analysis_goal {g!r}; one of {GOALS}")
        fa = BASE_FACTORS | {"analysis_goal": [truth]}
        fb = BASE_FACTORS | {"analysis_goal": [fallback]}
        label_a, label_b = "truth", "fallback"
        header = f"{truth}  ->  {fallback}"
    elif args.a_factors and args.b_factors:
        fa, fb = parse(args.a_factors), parse(args.b_factors)
        label_a, label_b = "A", "B"
        header = f"{args.a_factors}  ->  {args.b_factors}"
    else:
        ap.error("give --pair, or both --a-factors and --b-factors, or --probe")

    rec_a, rec_b = resolve(fa, catalogue), resolve(fb, catalogue)
    pa, col_a, row_a, ign_a, unexp_a = params_for(rec_a)
    pb, col_b, row_b, ign_b, unexp_b = params_for(rec_b)

    try:
        rel, _ = fetch_release()
    except Exception:                                            # noqa: BLE001
        rel = "unknown"

    print(f"A/B OUTPUT DIFF   {header}")
    print(f"Ensembl REST release {rel}, species {args.species}\n")
    print(f"  {label_a}: {len(rec_a):2d} recommended   {label_b}: {len(rec_b):2d} recommended")
    lost_opts = sorted(set(rec_a) - set(rec_b))
    print(f"  options {label_b} loses: {', '.join(lost_opts) if lost_opts else 'none'}")

    # The honest accounting, stated before any result: what this run can and cannot see.
    unmeasurable = sorted(set(ign_a) | set(ign_b))
    never = sorted(set(unexp_a) | set(unexp_b))
    print(f"\n  measurable here : {len(set(col_a) | set(col_b))} column options, "
          f"{len(set(row_a) | set(row_b))} row options")
    if unmeasurable:
        print(f"  UNMEASURABLE    : {', '.join(unmeasurable)}")
        for oid in unmeasurable:
            if oid in ROW_PARAM:
                print(f"                    {oid} -> REST ignores {ROW_PARAM[oid][0]} "
                      f"({ROW_PARAM[oid][3]})")
            else:
                why = COLUMN_VERDICT.get(oid, "IGNORED")
                reason = ("REST returns it with no parameter at all, so a diff cannot see it"
                          if why == "RETURNED_BY_DEFAULT" else
                          "REST accepts the parameter and changes nothing")
                print(f"                    {oid} -> {why}: {reason}")
    if never:
        print(f"  not exposed     : {len(never)} options — {', '.join(never[:8])}"
              f"{' …' if len(never) > 8 else ''}")

    results = []
    # PANEL was human-only until 2026-09-10: every mouse probe 400'd on the human variants and
    # main() still exited 0, so an all-errors run looked exactly like a clean diff. Pick the panel
    # for the species being run, and refuse to report if nothing could be measured.
    panel = SPECIES_PANEL.get(args.species, PANEL)
    for cls, entry in panel.items():
        r = diff_one(args.species, cls, entry, pa, pb, label_a, label_b)
        if r:
            results.append(r)

    cohort = None
    if args.cohort:
        cohort = diff_cohort(args.species, pa, pb, label_a, label_b,
                             sorted(set(col_a) | set(col_b)))

    if not results:
        sys.exit(f"NOTHING MEASURED: every probe failed for species={args.species!r}. "
                 f"Exiting non-zero rather than reporting a clean diff of nothing.")

    print("\n  Read the ROWS lines first: they are what an option-set metric and Exp 16 both miss.")
    if unmeasurable:
        print("  An UNMEASURABLE option is NOT a null result — REST cannot apply it, so its effect on")
        print("  the output file is unknown and needs a local VEP install or the web form.")

    if args.json:
        out = {"ensembl_release": rel, "header": header, "species": args.species,
               "cohort": cohort,
               "recommended_a": rec_a, "recommended_b": rec_b, "options_lost": lost_opts,
               "unmeasurable": unmeasurable, "not_exposed": never, "panel": results}
        Path(args.json).write_text(json.dumps(out, indent=1))
        print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
