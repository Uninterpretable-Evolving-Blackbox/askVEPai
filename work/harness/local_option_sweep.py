#!/usr/bin/env python3
"""What every catalogue option does to a real VEP result, one option at a time, locally.

WHY THIS AND NOT `run_vep_ab.py`. That harness diffs two whole resolved CONFIGURATIONS over Ensembl
REST. REST returns five options whether asked or not (`sift`, `polyphen`, `clinvar`, `biotype`,
`symbol`) and silently ignores the four that delete rows (`frequency`, `coding_only`, `most_severe`,
`summary`), so it can never measure the options that matter most. The local install can.

THE BASELINE IS THE WEB FORM'S DEFAULT, NOT VEP'S. 16 of the 65 options are already ticked when the
form loads, so "what does this option add" is only meaningful on top of what the user already has.
An option that is ON by default is measured by REMOVING it; everything else by ADDING it.

THE INPUT IS ENSEMBL'S OWN EXAMPLE VCF, shipped with ensembl-vep (173 human variants, GRCh38).
Deliberately not a set we chose: an input we picked is an input we have to defend.

READ THE FAILURES AS DATA. Every plugin needs its own annotation file and none are installed here,
so `--plugin X` failing is "not measurable on this machine", NOT "this option does nothing". Same
distinction `run_vep_ab.py` draws between IGNORED and no-change.

  python3 work/harness/local_option_sweep.py
  python3 work/harness/local_option_sweep.py --only coding_only,pick,frequency
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

VEP_LOCAL = ROOT / "tools_local" / "vep_local"
VEP_BIN = VEP_LOCAL / "ensembl-vep" / "vep"
CACHE = VEP_LOCAL / "cache"
EXAMPLE = VEP_LOCAL / "ensembl-vep" / "examples" / "homo_sapiens_GRCh38.vcf"

# ENV.sh derives its own directory from $0, which is whatever script sources it, so the paths are
# set here directly rather than by sourcing it.
PERL5LIB = ":".join(str(VEP_LOCAL / p) for p in (
    "Bio-DB-HTS/blib/lib", "Bio-DB-HTS/blib/arch", "bioperl-live", "ensembl/modules",
    "ensembl-variation/modules", "ensembl-funcgen/modules", "ensembl-io/modules",
    "ensembl-vep/modules"))

# The 16 form defaults as CLI flags. core_type=core, buffer_size=5000 and distance=5000 are VEP's
# own defaults too, so they need no flag to be present.
FORM_DEFAULT = ["--af", "--appris", "--biotype", "--check_existing", "--mane", "--polyphen", "b",
                "--pubmed", "--regulatory", "--sift", "b", "--symbol", "--transcript_version",
                "--tsl"]

# How to exercise each option. A value means "the flag plus its argument". None means the option
# cannot be expressed as a single flag and is handled by an explicit arm below.
ADD_FLAG = {
    "af_1kg": ["--af_1kg"], "af_gnomade": ["--af_gnomade"], "af_gnomadg": ["--af_gnomadg"],
    "canonical": ["--canonical"], "ccds": ["--ccds"], "cell_type": ["--cell_type"],
    "coding_only": ["--coding_only"], "domains": ["--domains"], "failed": ["--failed", "1"],
    "hgvs": ["--hgvs"], "mirna": ["--mirna"], "most_severe": ["--most_severe"],
    "numbers": ["--numbers"], "per_gene": ["--per_gene"], "pick": ["--pick"],
    "pick_allele": ["--pick_allele"], "protein": ["--protein"],
    "shift_3prime": ["--shift_3prime", "1"], "summary": ["--summary"], "uniprot": ["--uniprot"],
    "var_synonyms": ["--var_synonyms"],
    "frequency": ["--check_frequency", "--freq_filter", "exclude", "--freq_gt_lt", "gt",
                  "--freq_freq", "0.01", "--freq_pop", "1KG_ALL"],
}
# ON by default -> measured by REMOVING the flag from the baseline.
REMOVE_FLAG = {
    "af": ["--af"], "appris": ["--appris"], "biotype": ["--biotype"],
    "check_existing": ["--check_existing"], "clinvar": ["--check_existing"], "mane": ["--mane"],
    "polyphen": ["--polyphen", "b"], "pubmed": ["--pubmed"], "regulatory": ["--regulatory"],
    "sift": ["--sift", "b"], "symbol": ["--symbol"],
    "transcript_version": ["--transcript_version"], "tsl": ["--tsl"],
}
# Options that are a VALUE, not a switch: each value is its own arm.
VALUE_ARMS = {
    "core_type": {"refseq": ["--refseq"], "merged": ["--merged"],
                  "gencode_basic": ["--gencode_basic"]},
    "distance": {"0": ["--distance", "0"], "50000": ["--distance", "50000"]},
    "buffer_size": {"100": ["--buffer_size", "100"]},
    "sift_value": {"p_only": ["--sift", "p"], "s_only": ["--sift", "s"]},
    "frequency_pop": {"AF": ["--check_frequency", "--freq_filter", "exclude", "--freq_gt_lt", "gt",
                             "--freq_freq", "0.01", "--freq_pop", "AF"],
                      "gnomADe": ["--check_frequency", "--freq_filter", "exclude", "--freq_gt_lt",
                                  "gt", "--freq_freq", "0.01", "--freq_pop", "gnomADe"]},
}


def run(out_dir, name, extra, drop=()):
    args = [a for a in FORM_DEFAULT if a not in drop] if drop else list(FORM_DEFAULT)
    # A flag with an argument leaves its value stranded when the flag is dropped; rebuild pairwise.
    if drop:
        args, skip = [], 0
        for i, a in enumerate(FORM_DEFAULT):
            if skip:
                skip = 0
                continue
            if a in drop:
                if i + 1 < len(FORM_DEFAULT) and not FORM_DEFAULT[i + 1].startswith("--"):
                    skip = 1
                continue
            args.append(a)
    tsv = out_dir / f"{name}.tsv"
    cmd = ([str(VEP_BIN), "--offline", "--cache", "--dir_cache", str(CACHE), "--assembly", "GRCh38",
            "--input_file", str(EXAMPLE), "--format", "vcf", "--tab", "--force_overwrite",
            "--no_stats", "--output_file", str(tsv)] + args + list(extra))
    env = dict(os.environ, PERL5LIB=PERL5LIB)
    p = subprocess.run(["perl"] + cmd, capture_output=True, text=True, env=env)
    if not tsv.exists() or tsv.stat().st_size == 0:
        err = next((l for l in (p.stdout + p.stderr).splitlines() if "ERROR" in l), "no output")
        return {"arm": name, "ok": False, "error": err.strip()[:160]}
    rows = [l for l in tsv.read_text().splitlines() if not l.startswith("#")]
    hdr = next((l for l in tsv.read_text().splitlines() if l.startswith("#Uploaded")), "")
    return {"arm": name, "ok": True, "rows": len(rows),
            "variants": len({r.split("\t")[0] for r in rows}),
            "cols": len(hdr.split("\t")), "columns": hdr.lstrip("#").split("\t")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated option ids")
    ap.add_argument("--out", default=str(ROOT / "work/results/local_option_sweep_2026-09-10"))
    args = ap.parse_args()
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    catalogue, _ = va.load_knowledge_base()
    ids = {o["id"] for o in catalogue}
    keep = set(args.only.split(",")) if args.only else None

    base = run(out_dir, "_baseline", [])
    if not base["ok"]:
        sys.exit(f"baseline failed: {base['error']}")
    print(f"baseline (16 form defaults): {base['variants']} variants, {base['rows']} rows, "
          f"{base['cols']} columns\n")
    bcols = set(base["columns"])
    results = {"_baseline": base, "arms": {}}

    def report(oid, r, kind):
        if not r["ok"]:
            print(f"  {oid:22} {kind:8} FAILED  {r['error'][:70]}")
        else:
            gained = sorted(set(r["columns"]) - bcols)
            lost = sorted(bcols - set(r["columns"]))
            dv, dr = r["variants"] - base["variants"], r["rows"] - base["rows"]
            r.update({"d_variants": dv, "d_rows": dr, "cols_gained": gained, "cols_lost": lost})
            flag = "  <-- REMOVES" if (dv or dr) else ""
            print(f"  {oid:22} {kind:8} var {dv:+4d}  rows {dr:+6d}  "
                  f"col +{len(gained)} -{len(lost)}{flag}")
        results["arms"][r["arm"]] = r

    print("--- options OFF by default: added on top of the form's defaults ---")
    for oid in sorted(ADD_FLAG):
        if oid not in ids or (keep and oid not in keep):
            continue
        report(oid, run(out_dir, oid, ADD_FLAG[oid]), "add")

    print("\n--- options ON by default: removed from the form's defaults ---")
    for oid in sorted(REMOVE_FLAG):
        if oid not in ids or (keep and oid not in keep):
            continue
        report(oid, run(out_dir, f"no_{oid}", [], drop=REMOVE_FLAG[oid]), "remove")

    print("\n--- options that are a VALUE, not a switch: one arm per value ---")
    for oid, arms in VALUE_ARMS.items():
        if keep and oid not in keep:
            continue
        for val, extra in arms.items():
            report(f"{oid}={val}", run(out_dir, f"{oid}_{val}", extra), "value")

    print("\n--- plugins: none are installed here, so a failure means NOT MEASURABLE ---")
    for o in sorted(catalogue, key=lambda x: x["id"]):
        if o.get("source_type") == "native" or (keep and o["id"] not in keep):
            continue
        flag = o.get("cli_flag", "")
        if not flag.startswith("--plugin"):
            print(f"  {o['id']:22} {'skip':8} not a plain plugin flag: {flag[:50]}")
            continue
        report(o["id"], run(out_dir, o["id"], ["--plugin", flag.split()[-1]]), "plugin")

    (out_dir / "sweep.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {out_dir}/sweep.json")


if __name__ == "__main__":
    main()
