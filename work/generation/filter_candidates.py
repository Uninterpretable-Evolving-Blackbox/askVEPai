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


def llm_factor_recovery(rows, ev, model):
    """Stage-4 SEMANTIC query<->factor round-trip (replaces the removed keyword check). A checker model reads
    ONLY the query and classifies the five factors; we compare to the true tuple and FLAG mismatches for
    review (never auto-drop -- judge discipline). Deterministic: temp 0, fixed seed, concurrency 1 (Metal/MoE
    rule). Prefer a `model` DIFFERENT from the Stage-3 teacher (cross-check > self-check)."""
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    for row in rows:
        q = row.get("user_query") or ""
        raw = ev.call_llm(client, model, genlib.FACTOR_CLASSIFIER_PROMPT + q,
                          "Return the JSON classification.", temperature=0.0, seed=42)
        recovered = genlib.parse_factor_classification(raw)
        if recovered is None:                       # checker model returned unparseable output
            row["_gates"]["factor_recovery"] = None
            row["_gates"].setdefault("flags", []).append("factor_check_unparseable")
        else:
            per_factor, fflags = genlib.compare_factors(recovered, row["factor_labels"])
            row["_gates"]["factor_recovery"] = per_factor
            row["_gates"].setdefault("flags", []).extend(fflags)
        row["_gates"]["factor_checker_model"] = model
    return rows


JUDGE_PROMPT = (
    "You are screening a candidate question for a VEP-configuration dataset. Answer ONLY with a JSON "
    "object: {\"specificity\": bool, \"coherence\": bool, \"solvability\": bool, \"note\": \"...\"}.\n"
    "- specificity: does it state species, assay and variant type well enough to choose settings?\n"
    "- coherence: is it a single coherent scenario (not unrelated requests bolted together)?\n"
    "- solvability: is it asking to RECOMMEND a configuration (not a how-to/troubleshooting ticket)?\n\n"
    "Question:\n"
)


def llm_judge(rows, ev, model):
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    for row in rows:
        q = row.get("user_query") or ""
        raw = ev.call_llm(client, model, JUDGE_PROMPT + q, "Return the JSON verdict.",
                          temperature=0.0, seed=42)
        verdict, jflags = None, []
        try:
            start, end = raw.find("{"), raw.rfind("}")
            verdict = json.loads(raw[start:end + 1])
            for key in ("specificity", "coherence", "solvability"):
                if not verdict.get(key):
                    jflags.append(f"judge_{key}_fail")
        except Exception:
            jflags.append("judge_unparseable")
        row["_gates"]["judge"] = verdict
        row["_gates"]["flags"].extend(jflags)
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
