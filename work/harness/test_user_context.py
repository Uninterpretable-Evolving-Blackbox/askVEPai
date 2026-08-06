#!/usr/bin/env python3
"""Systematic test for user-supplied context — the fields that let someone state a fact outright
instead of having a model infer it from prose.

WHY THESE TESTS AND NOT OTHERS. The feature's whole claim is "what you tell us wins". That is one
contract with four ways to break it, and each section below attacks one:

  1  OVERRIDE      a stated value must beat the classifier, including when the query says the opposite.
                   The failure mode is a field that looks accepted and changes nothing — which is worse
                   than no field, because the user believes they have been heard.
  2  ABSENCE       an untouched field must leave behaviour exactly as it was. This is what makes the
                   feature safe to ship: everyone who ignores it is unaffected.
  3  EXHAUSTIVE    every combination of the fields must resolve to a checker-clean configuration. The
                   fields are independent, so the space is small enough to enumerate rather than sample,
                   and enumerating is the only way to catch a combination nobody thought of.
  4  CONSEQUENCE   the two cases where being wrong actually costs the user something: a somatic sample
                   must never get the common-variant filter (it discards real findings), and a GRCh37
                   run must never get MANE (there is no data behind it, and VEP's own form does not
                   protect you). Both must hold from the field ALONE, with the query silent.

Deterministic: no GPU, no model. Section 5 optionally checks the end-to-end path with --llm.

  VEP_OPTIONS_FILE=work/vep_options_expanded.json python work/harness/test_user_context.py [--llm]
"""
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
sys.path.insert(0, str(ROOT / "work" / "generation"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import genlib                                                          # noqa: E402
import vep_assistant as va                                             # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


CAT = genlib.load_catalogue()
FC = genlib.load_factors()
PBF = genlib.load_priority_by_factor()
CORPUS = genlib.load_corpus()


def resolve(tup, assembly=None, query="variant analysis"):
    """Factor tuple -> the option set actually emitted, checker included."""
    ip = genlib.intent_priorities(tup, CAT, PBF, FC)
    en = {o for o, (e, _, _) in ip.items() if e}
    dis = set()
    for _ in range(6):
        v = va.check_and_fix_violations(en, dis, CAT, CORPUS, query, assembly_override=assembly)
        if not [x for x in v if x.get("option_disabled") or x.get("option_enabled")]:
            break
    return en


def main():
    print("\n== 1. A stated value beats the classifier ==")
    # The classifier's reading is deliberately the OPPOSITE of the context in every case, so a field
    # that is merely merged rather than authoritative fails here.
    read = {"species": "human", "origin": "germline", "variant_size_class": "small",
            "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
    for field, opposite in [("species", "non-human"), ("origin", "somatic"),
                            ("variant_size_class", "structural-CNV")]:
        rec, _, ov = va.apply_user_context(read, {field: opposite})
        check(f"{field}: stated value wins over the classifier",
              rec[field] == opposite and field in ov, f"got {rec[field]!r}")
    rec, asm, ov = va.apply_user_context(read, {"assembly": "GRCh37"})
    check("assembly: carried through even though it is not a factor", asm == "GRCh37" and "assembly" in ov)

    print("\n== 2. An untouched field changes nothing ==")
    for ctx, label in [({}, "no context at all"),
                       ({"species": None, "origin": "", "variant_size_class": "infer"}, "blank/infer values")]:
        rec, asm, ov = va.apply_user_context(read, ctx)
        check(f"{label}: record unchanged, nothing reported as overridden",
              rec == read and asm is None and ov == [], f"overridden={ov}")
    rec, _, _ = va.apply_user_context(read, {"origin": "nonsense", "species": "martian"})
    check("a value outside the scheme is ignored, not written through",
          rec["origin"] == "germline" and rec["species"] == "human")

    print("\n== 3. Every combination resolves to a checker-clean config ==")
    fields = [("species", va.FACTOR_VALUES["species"]),
              ("origin", va.FACTOR_VALUES["origin"]),
              ("variant_size_class", va.FACTOR_VALUES["variant_size_class"]),
              ("assembly", [None, "GRCh37", "GRCh38"])]
    bad = []
    for combo in itertools.product(*[v for _, v in fields]):
        ctx = dict(zip([f for f, _ in fields], combo))
        rec, asm, _ = va.apply_user_context(read, ctx)
        en = resolve(rec, assembly=asm)
        # re-running the checker must be a no-op: the emitted set is already its own output
        again = va.check_and_fix_violations(set(en), set(), CAT, CORPUS, "variant analysis",
                                            assembly_override=asm)
        if [x for x in again if x.get("option_disabled") or x.get("option_enabled")] or not en:
            bad.append(ctx)
    check(f"all {len(list(itertools.product(*[v for _, v in fields])))} field combinations are stable",
          not bad, str(bad[:3]))

    print("\n== 4. The two cases where being wrong costs the user ==")
    # (a) somatic + the common-variant filter. Stated on the field, with a query that says nothing.
    rec, asm, _ = va.apply_user_context(
        {"species": "human", "origin": "germline", "variant_size_class": "small",
         "region_focus": ["coding"], "analysis_goal": ["population-frequency"]}, {"origin": "somatic"})
    en = resolve(rec, assembly=asm, query="variant analysis")
    check("stating 'somatic' keeps the common-variant filter off, from the field alone",
          "frequency" not in en, f"frequency present: {'frequency' in en}")
    # (b) assembly. This is the capability that did not exist: gating used to need the QUERY to name a
    # build, so a user on GRCh37 who never typed 'GRCh37' got MANE with no data behind it.
    base = {"species": "human", "origin": "germline", "variant_size_class": "small",
            "region_focus": ["coding"], "analysis_goal": ["clinical-interpretation"]}
    en37 = resolve(base, assembly="GRCh37", query="variant analysis")
    en38 = resolve(base, assembly="GRCh38", query="variant analysis")
    ennone = resolve(base, assembly=None, query="variant analysis")
    check("GRCh37 drops MANE (GRCh38-only) without the query mentioning a build", "mane" not in en37)
    check("GRCh38 keeps MANE", "mane" in en38)
    check("GRCh37 drops EVE (GRCh38-only)", "eve" not in en37)
    check("saying nothing leaves both in place (fail-open, unchanged behaviour)",
          "mane" in ennone, "assembly gating must not fire when nobody said anything")

    # The bug this guards: restore_missing_critical re-adds anything the factor table rates critical,
    # and its internal re-check used to run WITHOUT the assembly, so it handed MANE straight back to a
    # GRCh37 run one step after the gate removed it. Every layer that can put an option back has to see
    # the same context as the layer that took it out.
    for asm, want in (("GRCh37", False), ("GRCh38", True)):
        r = genlib.intent_priorities(base, CAT, PBF, FC)
        en = {o for o, (e, _, _) in r.items() if e}
        dis = set()
        va.check_and_fix_violations(en, dis, CAT, CORPUS, "variant analysis", assembly_override=asm)
        va.restore_missing_critical(en, dis, r, CAT, CORPUS, "variant analysis", assembly_override=asm)
        check(f"{asm}: restore_missing_critical does not undo the assembly gate",
              ("mane" in en) == want, f"mane present={'mane' in en}, expected {want}")

    if "--llm" in sys.argv:
        print("\n== 5. End to end: the field beats the words in the query ==")
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        q = "somatic variants from a mouse tumour sample"
        rec = va.infer_factors(client, "gemma4:26b", q, apply_defaults=False)
        check("classifier reads the query as non-human/somatic",
              rec["species"] == "non-human" and rec["origin"] == "somatic", str(rec))
        forced, _, ov = va.apply_user_context(rec, {"species": "human", "origin": "germline"})
        check("stating human+germline overrides a query that plainly says mouse tumour",
              forced["species"] == "human" and forced["origin"] == "germline", str(ov))

    print(f"\n{'=' * 62}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED: " + "; ".join(FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
