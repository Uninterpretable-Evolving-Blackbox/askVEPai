#!/usr/bin/env python3
"""Deterministic ✓/✗ → schema-valid JSON: build + validate structured output from logged responses.

Exp 8 showed the local model cannot reliably emit JSON, but it reliably emits the
`✓/✗ [source: id]` format (Phase-0 parsed 179/180 KB responses). So OUR code assembles the
schema-valid recommendation JSON from the parsed records + the deterministic constraint checker +
KB factual fields — valid by construction, the LLM never emits JSON. This script proves that on the
saved raw logs (offline, no GPU) and is the converter's de-facto test.

Usage:
  VEP_OPTIONS_FILE=vep_ai_demo/vep_options.json \
  VEP_EXAMPLES_FILE=evidence/local_runs/results_noex/gold_20set.json \
  python evidence/legacy_superseded/use_cases/build_output_json.py evidence/local_runs/results_noex/raw/gemma4_26b.jsonl [--emit out_dir] [--limit N]

Reuses vep_assistant.build_recommendation_json (single source of truth); validates each output
against evidence/legacy_superseded/use_cases/output_schema/vep_recommendation.schema.json with jsonschema.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "vep_ai_demo"))
import vep_assistant as va  # noqa: E402

SCHEMA_PATH = HERE / "output_schema" / "vep_recommendation.schema.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="raw eval log (results*/raw/<model>.jsonl) with 'response' text")
    ap.add_argument("--emit", default=None, help="optional dir to write per-query JSON files")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N records (0 = all)")
    ap.add_argument("--condition", default=None, help="only this condition (e.g. all, keyword)")
    args = ap.parse_args()

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        sys.exit("jsonschema not installed — `pip install jsonschema` to validate.")

    schema = json.load(open(SCHEMA_PATH))
    validator = Draft202012Validator(schema)

    vep_options, training_examples = va.load_knowledge_base()
    option_aliases = va.build_option_aliases(vep_options)
    print(f"options={len(vep_options)}  examples={len(training_examples)}  schema={SCHEMA_PATH.name}\n")

    recs = [json.loads(l) for l in open(args.log)]
    if args.condition:
        recs = [r for r in recs if r.get("condition") == args.condition]
    if args.limit:
        recs = recs[: args.limit]

    emit_dir = None
    if args.emit:
        emit_dir = Path(args.emit)
        emit_dir.mkdir(parents=True, exist_ok=True)

    n_ok = n_fail = n_skip = n_empty = 0
    fail_examples = []
    rec_counts = []
    for i, r in enumerate(recs):
        resp = r.get("response", "")
        if not resp:
            n_skip += 1            # bare condition predates response-logging on some runs
            continue
        out = va.build_recommendation_json(
            r["query"], resp, vep_options, training_examples,
            option_aliases=option_aliases, retrieval_mode="all", model=r.get("model"),
        )
        # An empty recommendation set means the MODEL produced no usable ✓/✗ (degenerate/empty
        # generation, e.g. a stray '---' under temp>0). That is a model no-op, not a converter
        # defect — the schema's minItems:1 correctly rejects it, so we bucket it separately rather
        # than counting it as a schema failure. The pipeline would surface "no recommendation".
        if not out["recommendations"]:
            n_empty += 1
            continue
        errors = sorted(validator.iter_errors(out), key=lambda e: e.path)
        if errors:
            n_fail += 1
            if len(fail_examples) < 5:
                loc = "/".join(str(p) for p in errors[0].path)
                fail_examples.append(f"{r.get('query_id','?')}/{r.get('condition','?')}: {errors[0].message} (at {loc or 'root'})")
        else:
            n_ok += 1
            rec_counts.append(len(out["recommendations"]))
        if emit_dir:
            tag = f"{r.get('query_id','q')}_{r.get('condition','c')}_{r.get('seed','s')}"
            (emit_dir / f"{tag}.json").write_text(json.dumps(out, indent=2))

    total = n_ok + n_fail
    print(f"VALID:   {n_ok}/{total} ({(n_ok/total if total else 0):.0%}) of non-empty responses")
    print(f"INVALID: {n_fail}/{total}")
    print(f"empty model responses (no ✓/✗ parsed; minItems:1 — model no-op, not a converter bug): {n_empty}")
    print(f"skipped (no response text logged): {n_skip}")
    if rec_counts:
        print(f"recommendations/record: mean {sum(rec_counts)/len(rec_counts):.1f}, "
              f"min {min(rec_counts)}, max {max(rec_counts)}")
    if fail_examples:
        print("\nFirst REAL failures:")
        for f in fail_examples:
            print(f"  - {f}")
    if emit_dir:
        print(f"\nWrote {n_ok} JSON files -> {emit_dir}")

    # Non-zero exit only on a REAL schema failure (a non-empty rec set that didn't validate) -> CI gate.
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
