#!/usr/bin/env python3
"""Run a recommended configuration through the REAL VEP and check the output it produces.

WHY THIS EXISTS. Every number this project publishes scores the CONFIGURATION -- which options we
switched on -- and stops there. Nothing has ever checked that the resulting run answers the question.
An option can be correctly recommended and still return an empty column: gnomAD on a mouse query,
CADD-SV on GRCh37, SIFT on a species with no SIFT data. Those are the failures a user actually meets,
and option-set overlap cannot see any of them.

This closes the loop by running Ensembl's own VEP over the REST API. No install, no cache download:
the same VEP, called at `rest.ensembl.org/vep/<species>/hgvs/<variant>`.

WHAT IT CHECKS. For every option in the RECOMMENDED bucket, the catalogue implies a field that should
appear in the output. This asserts the field is actually there, and reports three outcomes per option:

    DELIVERED    recommended, and its field came back populated
    EMPTY        recommended, the run succeeded, and its field is absent or null  <- the real finding
    UNVERIFIABLE REST does not expose it (most plugins), so this harness cannot say either way

COVERAGE, MEASURED 2026-09-07 (Ensembl 116), not assumed. An earlier version of this note said REST
exposes "a handful" of plugins and that the 26 plugins largely are not checkable. That was wrong: REST
documents a parameter for 25 of the catalogue's 27 non-native options, and only `mastermind` and `go`
have none. Of 49 options with a parameter, probing each one ALONE against a variant of its own class:

    HONOURED             32   the parameter makes a field appear -> measurable here
    RETURNED_BY_DEFAULT  14   the field is there with NO parameter -> NOT measurable, and not lost
    IGNORED               3   nothing either way (gnomad_sv, paralogues, riboseqorfs)

RETURNED_BY_DEFAULT is the one that matters. REST hands back SIFT, PolyPhen, ClinVar, `regulatory` and
all four `af_*` whether or not you ask, so failing to recommend them costs a REST user nothing, and a
harness that only asks "is the field present" scores them as delivered either way.

So a clean run does NOT mean the whole configuration is sound -- it means the HONOURED part is. The web
form is still the target of record; this is the closest executable proxy.

  python work/harness/run_vep_rest.py --factors species=human,origin=germline,\\
      variant_size_class=small,region_focus=coding,analysis_goal=clinical-interpretation
  python work/harness/run_vep_rest.py --row 3          # a row from the 31-row evaluation set
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
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

REST = "https://rest.ensembl.org"
# Known missense variants with rich annotation, so an absent field means the OPTION did not deliver
# rather than the variant having nothing to report. --variant overrides.
DEFAULT_VARIANT = {"human": "ENST00000366667.4:c.803C>T",
                   "mouse": "ENSMUST00000108108.9:c.100G>A"}

# A VERDICT IS ONLY AS GOOD AS THE VARIANT IT IS TESTED ON. The single coding-missense default made
# `regulatory` report EMPTY on all 22 rows that recommend it -- not an option failure but an artifact:
# that variant overlaps no regulatory feature, so there was nothing for the option to return. The REST
# parameter is correct (rs1800795 comes back with 2 regulatory_feature_consequences).
#
# So EMPTY is only meaningful against a variant of the class the option is FOR. Each entry is
# (endpoint, identifier, what it exercises) and was confirmed live on 2026-09-04, Ensembl 116.
PANEL = {
    "coding_known":     ("hgvs", "ENST00000366667.4:c.803C>T",
                         "missense, colocated record present: predictors, HGVS, ClinVar, frequencies"),
    "coding_novel":     ("hgvs", "ENST00000366667.4:c.802G>C",
                         "missense with NO colocated record: predictors yes, frequencies no"),
    "coding_synonymous": ("hgvs", "ENST00000366667.4:c.798C>T",
                          "synonymous: colocated data yes, missense predictors have nothing to score"),
    "regulatory_utr":   ("id", "rs1800795",
                         "IL6 promoter, 2 regulatory_feature_consequences: regulatory and UTR options"),
    "intronic":         ("id", "rs12979860", "intron, no protein consequence"),
    # Added 2026-09-07 so every option is judged on a variant it is FOR. Each consequence was read back
    # from VEP rather than assumed.
    "splice_acceptor":  ("id", "rs397508256", "CFTR splice acceptor: dbscSNV, MaxEntScan, SpliceAI"),
    "stop_gained":      ("id", "rs74315329", "MYOC nonsense: NMD, OpenTargets"),
    "upstream":         ("id", "rs763110", "FASLG upstream: Enformer"),
    "mirna":            ("id", "rs2910164", "MIR146A precursor: the only class exercising `mirna`"),
    "assay_mapped":     ("id", "rs28897696", "BRCA1 missense in a MaveDB assay: MaveDB, IntAct"),
}
# Per-species panels. Only human existed until 2026-09-10; every mouse probe 400'd against the
# human variants, so the output axis could not see non-human at all -- which is the species the
# `species` default has to be measured on. Consequences read back from VEP, not assumed.
SPECIES_PANEL = {
    "mouse": {
        "coding_known": ("hgvs", "ENSMUST00000108108.9:c.100G>A",
                         "Ndufb6 missense, 18 transcript rows: predictors, HGVS"),
        "utr":          ("id", "rs27260731", "Cpxm1 3-prime UTR, 12 rows"),
        "intronic":     ("id", "rs29477109", "Kat7 intron, 8 rows"),
        "intronic_alt": ("id", "rs36723194", "Dlg2 intron, 4 rows"),
    },
}


# Which panel entry an option should be judged on. Anything unlisted is judged on the default variant.
JUDGE_ON = {
    'dbscsnv'             : 'splice_acceptor',
    'dosage_sensitivity'  : 'splice_acceptor',
    'enformer'            : 'upstream',
    'intact'              : 'assay_mapped',
    'loeuf'               : 'splice_acceptor',
    'mavedb'              : 'assay_mapped',
    'maxentscan'          : 'splice_acceptor',
    'mirna'               : 'mirna',
    'nmd'                 : 'stop_gained',
    'opentargets'         : 'stop_gained',
    'regulatory'          : 'regulatory_utr',
    'spliceai'            : 'splice_acceptor',
    'utrannotator'        : 'splice_acceptor',
}

# option id -> (REST query parameter, [fields that prove it arrived])
# Fields are looked for on the transcript consequence first, then the colocated-variant record.
# Anything absent from this map is UNVERIFIABLE: REST either does not expose it or exposes it under a
# name we have not confirmed, and guessing would turn a gap into a false pass.
REST_PARAM = {
    'af'                  : ('af', ['frequencies']),
    'af_1kg'              : ('af_1kg', ['frequencies']),
    'af_gnomade'          : ('af_gnomade', ['frequencies']),
    'af_gnomadg'          : ('af_gnomadg', ['frequencies']),
    'alphamissense'       : ('AlphaMissense', ['alphamissense']),     # plugin
    'ancestral_allele'    : ('AncestralAllele', ['aa']),     # plugin
    'appris'              : ('appris', ['appris']),
    'biotype'             : ('biotype', ['biotype']),
    'blosum62'            : ('Blosum62', ['blosum62']),     # plugin
    'cadd'                : ('CADD', ['cadd_phred', 'cadd_raw']),     # plugin
    'canonical'           : ('canonical', ['canonical']),
    'ccds'                : ('ccds', ['ccds']),
    'check_existing'      : ('check_existing', ['id']),
    'clinpred'            : ('ClinPred', ['clinpred']),     # plugin
    'clinvar'             : ('check_existing', ['clin_sig']),
    'dbnsfp'              : ('dbNSFP', ['dbNSFP_fields_required']),     # plugin
    'dbscsnv'             : ('dbscSNV', ['ada_score', 'rf_score']),     # plugin
    'domains'             : ('domains', ['domains']),
    'dosage_sensitivity'  : ('DosageSensitivity', ['phaplo', 'ptriplo']),     # plugin
    'enformer'            : ('Enformer', ['enformer_sad', 'enformer_sar']),     # plugin
    'eve'                 : ('EVE', ['popeve_eve', 'popeve_gap_frequency', 'popeve_gene']),     # plugin
    'gnomad_sv'           : ('gnomAD_SV', ['gnomad_sv']),     # plugin
    'hgvs'                : ('hgvs', ['hgvsc', 'hgvsp']),
    'intact'              : ('IntAct', ['intact']),     # plugin
    'loeuf'               : ('LOEUF', ['loeuf']),     # plugin
    'mane'                : ('mane', ['mane', 'mane_select']),
    'mavedb'              : ('MaveDB', ['mavedb']),     # plugin
    'maxentscan'          : ('MaxEntScan', ['maxentscan_alt', 'maxentscan_diff', 'maxentscan_ref']),     # plugin
    'mirna'               : ('mirna', ['mirna']),
    'mutfunc'             : ('mutfunc', ['mutfunc']),     # plugin
    'nmd'                 : ('NMD', ['nmd']),     # plugin
    'numbers'             : ('numbers', ['exon']),
    'opentargets'         : ('OpenTargets', ['opentargets']),     # plugin
    'paralogues'          : ('Paralogues', ['paralogues']),     # plugin
    'phenotypes'          : ('Phenotypes', ['phenotypes']),     # plugin
    'polyphen'            : ('PolyPhen', ['polyphen_prediction', 'polyphen_score']),
    'protein'             : ('protein', ['protein_id']),
    'pubmed'              : ('pubmed', ['pubmed']),
    'regulatory'          : ('regulatory', ['regulatory_feature_consequences']),
    'revel'               : ('REVEL', ['revel']),     # plugin
    'riboseqorfs'         : ('RiboseqORFs', ['riboseqorfs']),     # plugin
    'sift'                : ('SIFT', ['sift_prediction', 'sift_score']),
    'spliceai'            : ('SpliceAI', ['spliceai']),     # plugin
    'symbol'              : ('symbol', ['gene_symbol']),
    'transcript_version'  : ('transcript_version', ['transcript_id']),
    'tsl'                 : ('tsl', ['tsl']),
    'uniprot'             : ('uniprot', ['swissprot', 'trembl', 'uniparc']),
    'utrannotator'        : ('UTRAnnotator', ['existing_inframe_oorfs', 'existing_outofframe_oorfs', 'existing_uorfs']),     # plugin
    'var_synonyms'        : ('var_synonyms', ['var_synonyms']),
}

# COLUMN VERDICT — established 2026-09-07 against Ensembl 116 by calling each parameter ALONE on a
# variant of the class it is FOR, and diffing against that same variant with NO parameters at all.
#
#   HONOURED             the parameter makes a field appear that was not there -> a column diff SEES it
#   RETURNED_BY_DEFAULT  the field is already present with no parameter -> a column diff CANNOT see it,
#                        and not recommending the option costs a REST user nothing
#   IGNORED              nothing either way -> unsupported, or no class here exercises it
#
# WHY THIS TABLE HAS TO EXIST. REST returns HTTP 200 for parameters it does not support (proved in
# run_vep_ab.py with `canonical_only=1`, which is not a parameter at all). Without the no-parameter
# baseline, RETURNED_BY_DEFAULT and IGNORED both read as "this option changed nothing" — which is how
# Exp 16 came to report `sift`, `polyphen`, `clinvar` and all four `af_*` as LOST. REST returns every
# one of those unflagged, so dropping the option does not drop the column. Only HONOURED is measurable.
COLUMN_VERDICT = {
    'af'                  : 'RETURNED_BY_DEFAULT',
    'af_1kg'              : 'RETURNED_BY_DEFAULT',
    'af_gnomade'          : 'RETURNED_BY_DEFAULT',
    'af_gnomadg'          : 'RETURNED_BY_DEFAULT',
    'alphamissense'       : 'HONOURED',
    'ancestral_allele'    : 'HONOURED',
    'appris'              : 'HONOURED',
    'biotype'             : 'RETURNED_BY_DEFAULT',
    'blosum62'            : 'HONOURED',
    'cadd'                : 'HONOURED',
    'canonical'           : 'HONOURED',
    'ccds'                : 'HONOURED',
    'check_existing'      : 'RETURNED_BY_DEFAULT',
    'clinpred'            : 'HONOURED',
    'clinvar'             : 'RETURNED_BY_DEFAULT',
    'dbnsfp'              : 'HONOURED',
    'dbscsnv'             : 'HONOURED',
    'domains'             : 'HONOURED',
    'dosage_sensitivity'  : 'HONOURED',
    'enformer'            : 'HONOURED',
    'eve'                 : 'HONOURED',
    'gnomad_sv'           : 'IGNORED',
    'hgvs'                : 'HONOURED',
    'intact'              : 'HONOURED',
    'loeuf'               : 'HONOURED',
    'mane'                : 'HONOURED',
    'mavedb'              : 'HONOURED',
    'maxentscan'          : 'HONOURED',
    'mirna'               : 'HONOURED',
    'mutfunc'             : 'HONOURED',
    'nmd'                 : 'HONOURED',
    'numbers'             : 'HONOURED',
    'opentargets'         : 'HONOURED',
    'paralogues'          : 'IGNORED',
    'phenotypes'          : 'HONOURED',
    'polyphen'            : 'RETURNED_BY_DEFAULT',
    'protein'             : 'HONOURED',
    'pubmed'              : 'RETURNED_BY_DEFAULT',
    'regulatory'          : 'RETURNED_BY_DEFAULT',
    'revel'               : 'HONOURED',
    'riboseqorfs'         : 'IGNORED',
    'sift'                : 'RETURNED_BY_DEFAULT',
    'spliceai'            : 'HONOURED',
    'symbol'              : 'RETURNED_BY_DEFAULT',
    'transcript_version'  : 'RETURNED_BY_DEFAULT',
    'tsl'                 : 'HONOURED',
    'uniprot'             : 'HONOURED',
    'utrannotator'        : 'HONOURED',
    'var_synonyms'        : 'RETURNED_BY_DEFAULT',
}


def fetch(species, variant, params, endpoint="hgvs"):
    """One VEP call. `endpoint` is 'hgvs' or 'id' — PANEL entries carry which one they need."""
    q = urllib.parse.urlencode({**params, "content-type": "application/json"})
    url = f"{REST}/vep/{species}/{endpoint}/{urllib.parse.quote(variant)}?{q}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode()), url
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError("exhausted retries")


def fetch_release():
    q = urllib.parse.urlencode({"content-type": "application/json"})
    req = urllib.request.Request(f"{REST}/info/data?{q}",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    rels = d.get("releases") or []
    return (str(rels[0]) if rels else "unknown"), d


def present(payload, fields):
    """True if any of `fields` is present and non-empty anywhere the annotation puts it."""
    blocks = []
    for rec in payload:
        blocks.append(rec)
        blocks += rec.get("transcript_consequences", []) or []
        blocks += rec.get("colocated_variants", []) or []
        blocks += rec.get("regulatory_feature_consequences", []) or []
    for b in blocks:
        for f in fields:
            v = b.get(f)
            if v not in (None, "", [], {}):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factors", help="species=human,origin=germline,...")
    ap.add_argument("--row", type=int, help="use row N of the 31-row evaluation set instead")
    ap.add_argument("--variant", help="HGVS notation to annotate")
    ap.add_argument("--species", help="REST species name (default: human, or mouse for non-human)")
    ap.add_argument("--json", action="store_true", help="emit the raw VEP payload")
    args = ap.parse_args()

    catalogue, _ = va.load_knowledge_base()

    if args.row:
        rows = json.load(open(ROOT / "work/generation/candidates/iced.json"))
        ft = rows[args.row - 1]["factor_labels"]
        print(f"row {args.row}: {rows[args.row - 1]['user_query'][:90]}…\n")
    elif args.factors:
        ft = {}
        for part in args.factors.split(","):
            k, v = part.split("=", 1)
            ft[k] = v.split("+") if k in va.MULTI_FACTORS else v
    else:
        ap.error("give --factors or --row")

    # The factor scheme is binary (human / non-human), so the concrete organism is NOT in the tuple.
    # Defaulting non-human to mouse silently misrepresents a zebrafish or pig row; say so and let
    # --species override.
    species = args.species or ("human" if ft.get("species") == "human" else "mouse")
    if ft.get("species") != "human" and not args.species:
        print("note: factor tuple says only 'non-human'; running as mouse. --species overrides.")
    variant = args.variant or DEFAULT_VARIANT.get(species)
    if not variant:
        sys.exit(f"no default variant for {species}; pass --variant")

    resolved = va.resolve_for_query(ft, catalogue) or {}
    recommended = sorted(o for o, (e, _p, _g) in resolved.items() if e)

    # GROUP BY THE VARIANT CLASS EACH OPTION IS FOR. A single variant cannot fairly test the whole
    # catalogue: judging `regulatory` against a coding missense variant reported EMPTY on 22 rows and
    # the option was fine. One call per class, each option read only from the call it belongs to.
    by_class, not_exposed, not_measurable = {}, [], []
    for oid in recommended:
        if oid not in REST_PARAM:
            not_exposed.append(oid)
            continue
        verdict = COLUMN_VERDICT.get(oid, "IGNORED")
        if verdict != "HONOURED":
            not_measurable.append((oid, verdict))
            continue
        by_class.setdefault(JUDGE_ON.get(oid, "coding_known"), []).append(oid)

    n_meas = sum(len(v) for v in by_class.values())
    print(f"RECOMMENDED: {len(recommended)} options — {n_meas} measurable over REST, "
          f"{len(not_measurable)} not measurable, {len(not_exposed)} not exposed")

    try:
        rel, _ = fetch_release()
    except Exception:                                                     # noqa: BLE001
        rel = "unknown"

    delivered, empty, urls, seen_consequence = [], [], [], []
    for cls, oids in sorted(by_class.items()):
        endpoint, ident, what = (PANEL[cls] if not args.variant else ("hgvs", args.variant, "override"))
        params = {}
        for oid in oids:
            params[REST_PARAM[oid][0]] = 1
        time.sleep(0.3)                                # REST is rate-limited; be polite
        payload, url = fetch(species, ident, params, endpoint)
        urls.append(url)
        seen_consequence.append((cls, ident, payload[0].get("most_severe_consequence")))
        for oid in oids:
            (delivered if present(payload, REST_PARAM[oid][1]) else empty).append((oid, cls))
        if args.variant:
            break                                      # an explicit variant overrides the panel

    print(f"running VEP on {species}, {len(urls)} call(s), one per variant class\n")
    for cls, ident, csq in seen_consequence:
        print(f"    {cls:18} {ident:28} {csq}")

    print(f"\n  DELIVERED     {len(delivered):2d}  "
          f"{', '.join(f'{o}[{c}]' for o, c in delivered)}")
    if empty:
        print(f"  EMPTY         {len(empty):2d}  {', '.join(f'{o}[{c}]' for o, c in empty)}"
              "   <- recommended, judged on its OWN class, still nothing")
    if not_measurable:
        rbd = [o for o, v in not_measurable if v == "RETURNED_BY_DEFAULT"]
        ign = [o for o, v in not_measurable if v != "RETURNED_BY_DEFAULT"]
        if rbd:
            print(f"  NOT MEASURABLE {len(rbd):2d}  {', '.join(rbd)}")
            print("                     REST returns these with no parameter at all, so dropping the "
                  "option does not drop the column")
        if ign:
            print(f"  NOT MEASURABLE {len(ign):2d}  {', '.join(ign)}")
            print("                     REST accepts the parameter and changes nothing — unsupported, "
                  "or no class here exercises it")
    if not_exposed:
        print(f"  NOT EXPOSED   {len(not_exposed):2d}  {', '.join(not_exposed)}")

    print(f"\n  ensembl release: {rel}")
    if empty:
        print("\n  An EMPTY option is the failure option-set scoring cannot see: correctly "
              "recommended,\n  judged against a variant of its own class, and it still returns "
              "nothing.")
    print("\n  NOT MEASURABLE is not a null result. It means this harness cannot answer for those\n"
          "  options, and the web form or a local VEP install has to.")


if __name__ == "__main__":
    main()
