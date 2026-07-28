#!/usr/bin/env python3
"""Stage 4 — automated candidate gates.

Deterministic gates (MUST pass) run first, then an optional LLM-as-judge that only FLAGS for review
(never silently drops — see the generation proposal §7).

Deterministic gates (all reuse existing code, no reimplementation):
  1. valid ids      — every recommended_options key is a real catalogue id
  2. checker-clean  — check_and_fix_violations on the REAL query makes ZERO structural changes
                      (the validate_examples.py bar; the resolver already repaired the config)
  3. species match  — infer_species(query) agrees with the species factor (the hard safety gate), and a
                      somatic row never enables frequency ('frequency', not 'filter_common' — factors.json)
  4. dedup          — BGE-small cosine < 0.92 AND ROUGE-L < 0.7 vs other queries in the same factor cell

LLM pass (flags only; never drops — proposal §7.2):
  - factor round-trip — a checker model reads ONLY the query and classifies all 5 factors; mismatches vs the
    true tuple (contradiction / partial / unrecoverable) are flagged. Replaces the old keyword check
    (keywords can't handle varied/implicit phrasing). Prefer a checker model != the Stage-3 teacher.
  - judge — specificity / coherence / solvability (is-a-config-recommendation, not a how-to).

  VEP_OPTIONS_FILE=work/vep_options_expanded.json \
  python work/generation/filter_candidates.py --in candidates/queried.json --out candidates/filtered.json \
         [--no-judge] [--judge-model gemma4:26b] [--factor-model gemma4:12b]
"""
import argparse
import json
import os

import genlib

DEDUP_COSINE = 0.92
DEDUP_ROUGE = 0.70


def _cell_key(row):
    fl = row["factor_labels"]
    return (fl["species"], fl["origin"], fl["variant_size_class"])


def deterministic_gates(rows, va, catalogue, corpus):
    cat_ids = {o["id"] for o in catalogue}
    # embeddings for dedup (reuse the demo's BGE-small model)
    from sentence_transformers.util import cos_sim
    model = va._get_semantic_model()
    queries = [r.get("user_query") or "" for r in rows]
    embs = model.encode(queries)

    for i, row in enumerate(rows):
        opts = row["recommended_options"]
        q = row.get("user_query") or ""
        checks, flags = {}, []

        # 1. valid ids
        unknown = [k for k in opts if k not in cat_ids]
        checks["valid_ids"] = not unknown

        # 2. checker-clean on the REAL query
        en = {k for k, v in opts.items() if v.get("enabled")}
        dis = {k for k, v in opts.items() if not v.get("enabled")}
        viol = va.check_and_fix_violations(set(en), set(dis), catalogue, corpus, q)
        changes = [v for v in viol if v.get("option_disabled") or v.get("option_enabled")]
        checks["checker_clean"] = not changes

        # 3. factor consistency (DETERMINISTIC part). species is the hard safety gate (infer_species) and
        # somatic must not enable frequency. Full query<->factor faithfulness across all 5 factors is the
        # SEMANTIC llm_factor_recovery pass (below, flag-only) -- not keyword matching.
        sp = va.infer_species(q)
        want_human = row["factor_labels"]["species"] == "human"
        species_ok = (sp in ("human", "unknown")) if want_human else (sp not in ("human", "unknown"))
        somatic_ok = not (row["factor_labels"]["origin"] == "somatic" and "frequency" in en)
        checks["factor_match"] = bool(species_ok and somatic_ok)

        # 4. dedup within the same factor cell (vs other candidate rows + the corpus is skipped for smoke)
        dup_of = None
        for j, other in enumerate(rows):
            if j == i or _cell_key(other) != _cell_key(row):
                continue
            cos = float(cos_sim(embs[i], embs[j])[0][0])
            rl = genlib.rouge_l(q, other.get("user_query") or "")
            if cos >= DEDUP_COSINE and rl >= DEDUP_ROUGE:
                dup_of = other["id"]
                break
        checks["not_duplicate"] = dup_of is None

        if unknown:
            flags.append(f"unknown_ids:{unknown}")
        if changes:
            flags.append("checker_would_change:" + ",".join(
                f"{v['type']}:{v.get('option_disabled') or v.get('option_enabled')}" for v in changes))
        if not species_ok:
            flags.append(f"species_mismatch:query_infers_{sp}_want_{row['factor_labels']['species']}")
        if not somatic_ok:
            flags.append("somatic_enables_frequency")
        if dup_of:
            flags.append(f"duplicate_of:{dup_of}")
        # Surface arbitrary conflict-tiebreaks from Stage 2 as a REVIEW flag (not a gate failure): the
        # config is checker-clean, but the checker picked which option to drop by a coin-flip, so a human
        # should confirm it rather than have a gold row silently encode it.
        for ac in row.get("_resolver", {}).get("arbitrary_conflicts", []):
            flags.append(f"conflict_arbitrary:dropped_{ac['disabled']}_kept_{ac['kept']}")
        # Surface factor values the catalogue cannot satisfy for this tuple (e.g. non-human +
        # population-frequency: gnomAD/1000G are human-only, so the config carries no frequency data while
        # the query still asks for it). Not a gate failure — the config is correct given the catalogue and
        # the query is faithful to its factors; the SCENARIO is the thing that does not hold together, and
        # only a human can decide whether to add a catalogue entry or stop sampling the combination.
        for uf in row.get("_resolver", {}).get("unsatisfiable_factors", []):
            flags.append(f"unsatisfiable_factor:{uf['factor']}={uf['value']}")
        # The query must not name its own answer (see genlib.TOOL_NAMES). Flag, don't drop: the row's
        # CONFIG is still correct and the query is still fluent — it is the wrong *kind* of query for a
        # scenario->config example. Recorded on the row so ice_screen can refuse to score it, because a
        # query naming its critical options makes ICE measure reading, not inference.
        leaked = genlib.query_names_tool(q)
        row["_query_leaks_tools"] = leaked
        if leaked:
            flags.append(f"query_names_tool:{','.join(leaked)}")

        row["_gates"] = {
            "deterministic_pass": all(checks.values()),
            "checks": checks,
            "flags": flags,
        }
    return rows


# How many times to ask the checker model before calling a query unrecoverable, and how much of a failed
# response to keep for diagnosis.
FACTOR_ATTEMPTS = 3
RAW_KEEP_CHARS = 600


def llm_factor_recovery(rows, ev, model, attempts=FACTOR_ATTEMPTS):
    """Stage-4 SEMANTIC query<->factor round-trip (replaces the removed keyword check). A checker model reads
    ONLY the query and classifies the five factors; we compare to the true tuple and FLAG mismatches for
    review (never auto-drop -- judge discipline). Deterministic: temp 0, fixed seed, concurrency 1 (Metal/MoE
    rule). Prefer a `model` DIFFERENT from the Stage-3 teacher (cross-check > self-check).

    NO FLAG WHEN THE CHECK ITSELF FAILS. This used to append `factor_check_unparseable` to the row's
    `flags`, which put a failure of OUR tooling into the column a reviewer reads for findings about HER
    data, next to genuine signals like `factor_unrecoverable`. There is no action a reviewer can take on
    "the checker crashed", and the first thing the mentor asked was what it meant; the honest answer,
    "nothing about your rows", is the proof it did not belong there.

    The one real bit of information — this row was never actually checked, which is not the same as
    checked-and-clean — is preserved where it already lived: `factor_recovery` stays None, the raw
    evidence is attached, and the count is reported in the run summary. Visible to us, not to her.

    RETRY + RAW CAPTURE. `ev.call_llm` now retries and raises on a genuinely empty completion, so the
    common failure (the model streams nothing) is handled at the call boundary for every stage at once.
    The loop here covers the DIFFERENT failure of a non-empty response that will not parse. Attempt 1
    keeps seed 42 so a first-try success is bit-identical to every number already logged; later attempts
    vary the seed, because re-asking with the same seed would only ever work by accident of the very
    flakiness it is compensating for.

    The raw text of every failed attempt is kept. Discarding it was the real bug: it let "the model is
    too weak for the schema" stand as the working theory for a week, when the captured evidence turned
    out to be a zero-length response, which no parser could have salvaged.
    """
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    n_retried, n_failed = 0, 0
    for row in rows:
        q = row.get("user_query") or ""
        recovered, raws, used_attempt = None, [], None
        for k in range(attempts):
            seed = 42 if k == 0 else 42 + k * 1000
            try:
                raw = ev.call_llm(client, model, genlib.FACTOR_CLASSIFIER_PROMPT + q,
                                  "Return the JSON classification.", temperature=0.0, seed=seed)
            except Exception as e:                  # noqa: BLE001 - empty/transport = one bad attempt
                raw = f"<call failed: {type(e).__name__}: {e}>"
            raws.append({"attempt": k + 1, "seed": seed, "raw": (raw or "")[:RAW_KEEP_CHARS]})
            recovered = genlib.parse_factor_classification(raw)
            if recovered is not None:
                used_attempt = k + 1
                break

        row["_gates"]["factor_checker_model"] = model
        row["_gates"]["factor_attempts_used"] = used_attempt or attempts
        if recovered is None:                       # the check could not run — a TOOLING failure, no flag
            n_failed += 1
            row["_gates"]["factor_recovery"] = None
            row["_gates"]["factor_check_failed"] = True        # machine-readable "not verified"
            row["_gates"]["factor_raw_failures"] = raws        # the evidence, kept for diagnosis
        else:
            if used_attempt > 1:
                n_retried += 1
                row["_gates"]["factor_raw_failures"] = raws[:-1]
            per_factor, fflags = genlib.compare_factors(recovered, row["factor_labels"])
            row["_gates"]["factor_recovery"] = per_factor
            row["_gates"].setdefault("flags", []).extend(fflags)
    print(f"  factor round-trip: {len(rows)} rows, {n_retried} needed a retry, "
          f"{n_failed} could not be checked after {attempts} attempts (tooling, not a row finding)")
    if n_failed:
        print(f"    -> {n_failed} row(s) carry factor_check_failed=true and were NOT factor-verified")
    return rows


# The judge screens for the intrinsic criteria of Iskander et al. (EMNLP 2024) §4.1. It FLAGS ONLY; a
# failure never drops a row.
#
# WHY THIS PROMPT IS FEW-SHOT AND EXPLICITLY DEFAULTED TO TRUE. The zero-shot one-liner it replaces failed
# 13/31 rows on solvability and 4/31 on specificity, and inspection of the flagged queries shows almost all
# of them are good rows. Both failures were artifacts of the query-axes design, i.e. the judge was
# penalising exactly the diversity Stage 3 is built to produce:
#
#   * SOLVABILITY. The old wording asked whether the query "is asking to RECOMMEND a configuration". But
#     query_axes.json has a `premise: implicit` category, so many queries legitimately state the analysis
#     rather than ask a question ("I am analyzing somatic SNVs and indels from a mouse tumor WES to quickly
#     identify high-impact protein-coding variants"). That names species, origin, size, region and goal —
#     it is a model row — yet it contains no literal request, so the judge answered "no". The criterion was
#     measuring sentence mood, not solvability.
#   * SPECIFICITY. query_axes.json also has a `terminology: lay` category, so a query may say "small
#     spelling changes" for SNVs or "the parts of the genome that make proteins" for coding regions. Same
#     information, non-expert vocabulary — and the judge read the vocabulary as vagueness.
#
# So the criteria are restated to judge INFORMATION CONTENT rather than phrasing, the default is stated as
# true, and the three worked examples are chosen to cover precisely these two traps plus one genuine
# failure. Solvability is narrowed to the one thing it was meant to catch: a troubleshooting ticket about a
# run that already happened, which is out of scope per the assistant's own scope gate.
JUDGE_PROMPT = (
    "You are screening a candidate question for a VEP-configuration dataset. VEP (Variant Effect Predictor) "
    "annotates genetic variants; the dataset teaches an assistant to turn a described analysis into a VEP "
    "configuration.\n\n"
    "Answer ONLY with a JSON object: "
    "{\"specificity\": bool, \"coherence\": bool, \"solvability\": bool, \"note\": \"...\"}.\n\n"
    "Judge the INFORMATION the question carries, not how it is phrased. Each criterion defaults to true — "
    "answer false only when the question clearly fails it.\n\n"
    "- specificity: can a VEP expert tell enough about the species, sample type and variant type to choose "
    "settings? Everyday wording counts: 'small spelling changes in the DNA' is as specific as 'SNVs and "
    "indels', and 'the parts of the genome that make proteins' is as specific as 'coding regions'. False "
    "only if a fact needed to choose settings is genuinely absent, not merely worded plainly.\n"
    "- coherence: is this one scenario, rather than unrelated requests bolted together? False only if it "
    "describes two analyses that have nothing to do with each other.\n"
    "- solvability: could an expert answer it by recommending a configuration? A question does NOT have to "
    "literally ask for one — describing the analysis is enough, and most entries are written that way on "
    "purpose. False ONLY if it is a troubleshooting or how-to ticket about a run that already happened: an "
    "error message, an installation or cache problem, a question about why existing output looks wrong.\n\n"
    "Examples:\n\n"
    "Question: I am analyzing somatic SNVs and indels from a mouse tumor exome to quickly identify "
    "high-impact protein-coding variants.\n"
    "{\"specificity\": true, \"coherence\": true, \"solvability\": true, \"note\": \"states species, "
    "somatic origin, variant size and coding focus; describes the analysis rather than asking, which is "
    "fine\"}\n\n"
    "Question: We have some small spelling changes in the DNA from a study of mice and want to work out "
    "which ones in the parts of the genome that make proteins are likely to cause disease.\n"
    "{\"specificity\": true, \"coherence\": true, \"solvability\": true, \"note\": \"lay wording, but "
    "species, variant type, region and clinical goal are all present\"}\n\n"
    "Question: My VEP run keeps dying with 'ERROR: Could not find cache directory' after I upgraded. How "
    "do I point it at the right cache?\n"
    "{\"specificity\": false, \"coherence\": true, \"solvability\": false, \"note\": \"troubleshooting an "
    "existing run; names no variant data and asks for a fix, not a configuration\"}\n\n"
    "Question:\n"
)


def llm_judge(rows, ev, model):
    """Advisory intrinsic-criteria screen. Flags only; a failure never drops a row.

    Like the round-trip above, a judge that fails to RUN is not a finding about the row: `judge_unparseable`
    used to go into the reviewer's `flags` column, where it said only that our own call misbehaved. It is
    now recorded as `judge_failed` on the row and counted in the run summary, leaving `flags` for things a
    reviewer can actually adjudicate.
    """
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    n_failed = 0
    for row in rows:
        q = row.get("user_query") or ""
        verdict, jflags, failed = None, [], False
        try:
            raw = ev.call_llm(client, model, JUDGE_PROMPT + q, "Return the JSON verdict.",
                              temperature=0.0, seed=42)
            start, end = raw.find("{"), raw.rfind("}")
            verdict = json.loads(raw[start:end + 1])
            for key in ("specificity", "coherence", "solvability"):
                if not verdict.get(key):
                    jflags.append(f"judge_{key}_fail")
        except Exception:                           # noqa: BLE001 - empty completion or unparseable JSON
            failed, n_failed = True, n_failed + 1
        row["_gates"]["judge"] = verdict
        if failed:
            row["_gates"]["judge_failed"] = True
        row["_gates"].setdefault("flags", []).extend(jflags)
    print(f"  judge: {len(rows)} rows, {n_failed} could not be judged (tooling, not a row finding)")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM pass (judge + factor round-trip)")
    ap.add_argument("--judge-model", default="gemma4:26b")
    ap.add_argument("--factor-model", default=None,
                    help="checker model for the query<->factor round-trip; defaults to --judge-model. "
                         "Prefer a model DIFFERENT from the Stage-3 teacher (cross-check > self-check).")
    args = ap.parse_args()

    va = genlib.load_va()
    catalogue = genlib.load_catalogue()
    corpus = genlib.load_corpus()
    rows = json.load(open(args.inp))

    rows = deterministic_gates(rows, va, catalogue, corpus)
    if not args.no_judge:
        ev = genlib.load_evaluate()
        rows = llm_factor_recovery(rows, ev, args.factor_model or args.judge_model)
        rows = llm_judge(rows, ev, args.judge_model)

    with open(args.out, "w") as f:
        json.dump(rows, f, indent=2)

    n_pass = sum(r["_gates"]["deterministic_pass"] for r in rows)
    print(f"Gated {len(rows)} candidates -> {args.out}   ({n_pass}/{len(rows)} pass deterministic gates)\n")
    for r in rows:
        g = r["_gates"]
        tag = "PASS" if g["deterministic_pass"] else "FAIL"
        print(f"  [{tag}] {r['id'][:46]:46s} flags={g['flags'] if g['flags'] else '-'}")


if __name__ == "__main__":
    main()
