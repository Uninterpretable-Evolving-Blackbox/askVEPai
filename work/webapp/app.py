#!/usr/bin/env python3
"""Ask VEPai — minimalistic local web UI over the existing VEP assistant pipeline.

This is a PRESENTATION LAYER only. It imports and reuses the exact inference
functions from ``vep_ai_demo/vep_assistant.py`` (retrieval, prompt assembly,
streaming, the free-text parser, and the deterministic constraint checker) so the
browser shows the *same* behaviour as the CLI — no logic is forked or re-implemented
here (per the project's experiment-discipline rule).

Run:
    python work/webapp/app.py                  # http://localhost:5050
    VEP_MODEL=gemma4:26b python work/webapp/app.py

It honours the same OLLAMA_BASE_URL / VEP_MODEL env vars as the CLI, and serves the
58-option catalogue with its example corpus.
"""

import json
import re
import sys
import threading
import urllib.request
from pathlib import Path

from flask import Flask, Response, request, render_template, jsonify

# --- Wire in the existing pipeline -----------------------------------------
WEBAPP_DIR = Path(__file__).resolve().parent
ROOT = WEBAPP_DIR.parent.parent                 # repo root (GSoC_WORK)
DEMO_DIR = ROOT / "vep_ai_demo"
sys.path.insert(0, str(DEMO_DIR))

import vep_assistant as va                       # noqa: E402  (path set above)
from openai import OpenAI                         # noqa: E402

import os                                         # noqa: E402

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("VEP_MODEL", "gemma4:26b")

client = OpenAI(base_url=BASE_URL, api_key="ollama")

# Serialise generation: the semantic model + embedding caches in vep_assistant are
# module-level globals, and we only ever have one local user. One inference at a time
# keeps those caches race-free and avoids hammering Ollama.
INFER_LOCK = threading.Lock()

# --- Knowledge base (loaded once, reused) ------------------------------------
# One catalogue: the 58-option build the priority table is generated for. The old 26-option demo KB
# was retired — it predated the catalogue rebuild, so running against it silently switched the
# importance tiers off (five of its ids, including the transcript-database choice, are not in the
# table). There is nothing to switch between any more.
KB_DEFS = {
    "expanded": {
        "label": "Catalogue",
        "options": ROOT / "work" / "vep_options_expanded.json",
        "examples": ROOT / "work" / "preliminary_examples" / "simulated_gold_examples.json",
    },
}
_KB_CACHE: dict[str, tuple[list, list]] = {}


def get_kb(kb: str):
    """Load (and cache) a (vep_options, examples) pair. Each KB keeps a stable list
    identity so vep_assistant's embedding caches stay valid across requests."""
    kb = kb if kb in KB_DEFS else "expanded"
    if kb not in _KB_CACHE:
        d = KB_DEFS[kb]
        with open(d["options"]) as f:
            options = json.load(f)
        with open(d["examples"]) as f:
            examples = json.load(f)
        _KB_CACHE[kb] = (options, examples)
    return _KB_CACHE[kb]


def kb_available(kb: str) -> bool:
    d = KB_DEFS[kb]
    return d["options"].exists() and d["examples"].exists()


# --- Ollama model discovery -------------------------------------------------
def list_models() -> list[str]:
    tags_url = BASE_URL.rsplit("/v1", 1)[0] + "/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=3) as r:
            data = json.load(r)
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []


# --- SSE helpers ------------------------------------------------------------
def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stream_tokens(model, system_prompt, user_message):
    """Stream the LLM reply as ('content'|'reasoning', text) tuples.

    Same Ollama call as va.stream_response (same max_tokens, streaming). The ONLY
    addition over the CLI is that we also surface the 'reasoning' channel that
    thinking models (e.g. gemma4:26b) emit: those models stream their chain-of-thought
    into delta.reasoning / reasoning_content and leave delta.content EMPTY until the
    think finishes — so a content-only reader (the CLI / evaluate.py) shows nothing for
    the whole think and looks frozen. We forward reasoning purely for live feedback;
    only 'content' is fed to the parser/checker, so scored behaviour stays identical
    to evaluate.py (which reads content only)."""
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=4096,
        stream=True,
    )
    for chunk in stream:
        d = chunk.choices[0].delta
        # Thinking channel — attribute name varies by Ollama/OpenAI-SDK version, so
        # check both typed attrs and the SDK's model_extra passthrough.
        r = getattr(d, "reasoning", None) or getattr(d, "reasoning_content", None)
        if not r:
            extra = getattr(d, "model_extra", None) or {}
            r = extra.get("reasoning") or extra.get("reasoning_content")
        if r:
            yield ("reasoning", r)
        if d.content:
            yield ("content", d.content)


# --- Structured views of the decision trace (reuse va scoring functions) ----
def build_trace(query, vep_options, training_examples, retrieval, resolved=None):
    """Structured form of va.print_decision_trace. Returns the retrieval ranking,
    the per-option priority map, and (semantic only) option relevance — computed
    with the SAME functions the CLI/eval use, so the numbers are identical.

    `resolved` is intent_priorities() for this scenario's factors; when given, the priority map is
    keyed to the factors (matching the recommendation) instead of the legacy per-use-case column."""
    trace = {
        "retrieval_mode": retrieval,
        "examples": [],
        "options_relevance": [],
        "priority_map": [],
        "use_case": "unknown",
    }

    if retrieval == "semantic":
        from sentence_transformers.util import cos_sim

        model = va._get_semantic_model()
        corpus = va._get_corpus_embeddings(training_examples)
        q_emb = model.encode([query])
        sims = cos_sim(q_emb, corpus)[0]
        scored = sorted(
            ((float(sims[i]), training_examples[i]) for i in range(len(training_examples))),
            key=lambda x: -x[0],
        )
        for rank, (s, ex) in enumerate(scored, 1):
            trace["examples"].append({
                "rank": rank, "id": ex["id"],
                "use_case": ex["use_case_category"],
                "score": round(s, 4), "selected": rank <= 2,
            })
        opt_embs = va._get_options_embeddings(vep_options)
        opt_sims = cos_sim(q_emb, opt_embs)[0]
        opt_scored = sorted(
            ((float(opt_sims[i]), vep_options[i]) for i in range(len(vep_options))),
            key=lambda x: -x[0],
        )
        for rank, (s, opt) in enumerate(opt_scored, 1):
            trace["options_relevance"].append({
                "rank": rank, "id": opt["id"],
                "score": round(s, 4), "included": rank <= 10,
            })
        top_uc = scored[0][1]["use_case_category"] if scored else "unknown"
    else:
        # keyword AND all share keyword scoring for ranking/use-case detection (va._detect_use_case
        # only special-cases "semantic", so this stays consistent). The only difference: in "all" mode
        # EVERY example is placed in the prompt, so all are marked selected.
        all_mode = retrieval == "all"
        q_words = set(query.lower().split())
        scored = []
        for ex in training_examples:
            ex_text = f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}".lower()
            matched = q_words & set(ex_text.split())
            scored.append((len(matched), sorted(matched), ex))
        scored.sort(key=lambda x: -x[0])
        for rank, (n, matched, ex) in enumerate(scored, 1):
            trace["examples"].append({
                "rank": rank, "id": ex["id"],
                "use_case": ex["use_case_category"],
                "score": n, "matched_words": matched[:10],
                "selected": True if all_mode else rank <= 2,
            })
        top_uc = scored[0][2]["use_case_category"] if scored else "unknown"

    trace["use_case"] = top_uc

    # The priority map shows every catalogue option with the priority that applies to THIS scenario.
    # When the factors resolved, use them (the same source as the recommendation's tiers) so the two
    # panels agree; otherwise fall back to the legacy per-use-case column. Either way, SORT by
    # importance — critical first — rather than leaving the catalogue's arbitrary order, so the map
    # reads top-to-bottom as "what matters most".
    RANK = {"critical": 0, "recommended": 1, "optional": 2}
    rows = []
    for opt in vep_options:
        if resolved is not None:
            _, priority, gated = resolved.get(opt["id"], (False, None, False))
            priority = "not_applicable" if gated else (priority or "—")
        else:
            priority = opt.get("priority_by_use_case", {}).get(top_uc, "n/a")
        rows.append({
            "id": opt["id"],
            "priority": priority,
            "species": opt.get("species_restriction", "all species"),
        })
    rows.sort(key=lambda r: (RANK.get(r["priority"], 3), r["id"]))
    trace["priority_map"] = rows
    return trace


def build_result(enabled, disabled, violations, vep_options, use_case, resolved=None):
    """Structured authoritative config (the post-checker 'dispose' step), plus the
    VEP web-form section mapping.

    When `resolved` is given (intent_priorities for this scenario's factors) each option carries the
    priority that applies HERE, and the payload gains the same essential/recommended/add-on grouping
    the CLI prints. Without it the per-option priority falls back to the legacy use-case column, which
    is the same for every query and is what this UI showed before factors existed."""
    by_id = {o["id"]: o for o in vep_options}

    def detail(oid):
        o = by_id.get(oid, {})
        if resolved:
            _, priority, _ = resolved.get(oid, (False, None, None))
            priority = priority or "unpriced here"
        else:
            priority = o.get("priority_by_use_case", {}).get(use_case, "n/a")
        return {
            "id": oid,
            "name": o.get("name", oid),
            "cli_flag": va.display_flag(o.get("cli_flag", "")),
            "section": o.get("web_form_section", "") or "other",
            "subsection": o.get("web_form_subsection", ""),
            "species": o.get("species_restriction", "all species"),
            "priority": priority,
            "when_to_use": (o.get("when_to_use", "") or "")[:240],
            "source_type": o.get("source_type", ""),
        }

    enabled_d = [detail(o) for o in sorted(enabled)]
    disabled_d = [detail(o) for o in sorted(disabled)]
    # Reuse the engine's flag builder rather than joining cli_flag strings: it drops the
    # value-placeholder syntax ("--sift [b|p|s]" -> "--sift b"), emits each flag once, and returns
    # radiolist options like core_type separately instead of pasting all four alternatives inline.
    flag_list, choices = va.cli_flags_for(sorted(enabled), vep_options)
    command = ("vep --input_file <in.vcf> --output_file <out.txt> --cache "
               + " ".join(flag_list)).strip()

    sections: dict[str, list] = {}
    for d in enabled_d:
        sections.setdefault(d["section"], []).append(d)

    out = {
        "enabled": enabled_d,
        "disabled": disabled_d,
        "violations": violations,
        "command": command,
        "command_choices": [{"id": oid, "alternatives": alts} for oid, alts in choices],
        "use_case": use_case,
        "sections": sections,
    }
    if resolved:
        out["tiers"] = va.tier_by_importance(enabled, resolved)
    return out


# Matches a recommendation line's verdict marker. The model is prompted to emit one
# ✓/✗ line per option, each ending with a [source: option_id] citation (the provenance
# tag the interpretability layer relies on). NB: a ✓/✗ may follow bullets/bold, so we
# scan the whole line rather than only its first char (mirrors extract_recommendations).
_MARK_RE = re.compile(r"[✓✅✗✘❌]")
_SRC_RE = re.compile(r"\[source:\s*([A-Za-z0-9_]+)")


def compute_citation_stats(response_text, vep_options):
    """Citation coverage: of the model's recommendation lines, how many carry a
    [source: id] tag, and how many of those ids resolve to a REAL catalogue option.

    This is the interpretability/provenance signal — every ✓/✗ line should trace back
    to a knowledge-base entry. Resolution mirrors extract_recommendations Phase 0
    EXACTLY (exact id, else fuzzy va._match_option) so 'resolved' equals what the parser/
    checker actually accept — not a stricter check that would over-report phantoms (e.g.
    'CADD'→'cadd'). A citation that still doesn't resolve is a 'phantom' (invented or
    mis-named source)."""
    real_ids = {o["id"] for o in vep_options}
    aliases = va.build_option_aliases(vep_options)
    rec_lines = cited = resolved = 0
    items = []
    for raw in response_text.splitlines():
        if not _MARK_RE.search(raw):
            continue
        rec_lines += 1
        m = _SRC_RE.search(raw)
        if not m:
            items.append({"id": None, "resolved_to": None, "valid": False})
            continue
        cited += 1
        oid = m.group(1)
        rid = oid if oid in real_ids else va._match_option(oid, aliases)
        valid = rid is not None
        if valid:
            resolved += 1
        items.append({
            "id": oid,
            "resolved_to": rid if (valid and rid != oid) else None,
            "valid": valid,
        })
    return {
        "rec_lines": rec_lines,
        "cited": cited,
        "resolved": resolved,
        "phantom": cited - resolved,
        "rate": round(100 * cited / rec_lines) if rec_lines else None,
        "resolve_rate": round(100 * resolved / rec_lines) if rec_lines else None,
        "items": items,
    }


# --- Flask app --------------------------------------------------------------
app = Flask(__name__, template_folder=str(WEBAPP_DIR / "templates"))
# Pick up index.html edits without a server restart (dev convenience).
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/meta")
def api_meta():
    kbs = []
    for key, d in KB_DEFS.items():
        avail = kb_available(key)
        info = {"key": key, "label": d["label"], "available": avail,
                "n_options": None, "n_examples": None}
        if avail:
            opts, exs = get_kb(key)
            info["n_options"] = len(opts)
            info["n_examples"] = len(exs)
        kbs.append(info)
    models = list_models()
    default_model = DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else DEFAULT_MODEL)
    return jsonify({
        "kbs": kbs,
        "models": models,
        "default_model": default_model,
        "ollama_reachable": bool(models),
    })


@app.route("/api/recommend")
def api_recommend():
    query = (request.args.get("query") or "").strip()
    kb = request.args.get("kb", "expanded")
    retrieval = request.args.get("retrieval", "all")
    do_check = request.args.get("check", "1") == "1"
    explain = request.args.get("explain", "1") == "1"
    model = request.args.get("model") or DEFAULT_MODEL
    context = {"species": request.args.get("species"), "origin": request.args.get("origin"),
               "variant_size_class": request.args.get("size"),
               "assembly": request.args.get("assembly")}
    if retrieval not in ("keyword", "semantic", "all"):
        retrieval = "keyword"

    def gen():
        if not query:
            yield sse("error", {"message": "Empty scenario."})
            return
        with INFER_LOCK:
            yield sse("status", {"message": "Retrieving knowledge base…"})
            try:
                vep_options, training_examples = get_kb(kb)
            except Exception as e:
                yield sse("error", {"message": f"Could not load KB '{kb}': {e}"})
                return

            # Classify the scenario into factor values first, exactly as the CLI does, so the option
            # block AND the decision trace's priority map carry the priority that applies to THIS
            # scenario rather than the flat legacy use-case table. A classifier failure is non-fatal —
            # factor_tuple stays None and everything falls back to the pre-factor path.
            yield sse("status", {"message": "Reading the scenario…"})
            factor_tuple = va.infer_factors(client, model, query)
            # Whatever the user stated on the "About your data" bar replaces what the classifier read.
            # These are facts about their sample, not judgements: asking a model to infer them from prose
            # is where every measured misclassification came from, and assembly cannot be inferred at all.
            factor_tuple, assembly, overridden = va.apply_user_context(factor_tuple, context)
            if overridden:
                yield sse("status", {"message": "Using what you specified for: "
                                                + ", ".join(overridden)})
            resolved = va.resolve_for_query(factor_tuple, vep_options)

            try:
                trace = build_trace(query, vep_options, training_examples, retrieval, resolved)
            except Exception as e:
                yield sse("error", {"message": f"Retrieval/embedding failed: {e}. "
                                               "Semantic mode needs sentence-transformers."})
                return

            use_case = trace["use_case"]
            species = va.infer_species(query)
            selected = [e for e in trace["examples"] if e["selected"]]
            yield sse("meta", {
                "use_case": use_case,
                "species": species,
                "model": model,
                "kb": kb,
                "kb_label": KB_DEFS.get(kb, {}).get("label", kb),
                "retrieval": retrieval,
                "n_options": len(vep_options),
                "n_examples": len(training_examples),
                "selected_examples": selected,
            })
            if explain:
                yield sse("trace", trace)

            if factor_tuple:
                yield sse("factors", {"factors": factor_tuple,
                                      "text": va.describe_factors(factor_tuple)})

            yield sse("status", {"message": f"Querying {model}…"})
            system_prompt = va.build_system_prompt(
                vep_options, training_examples, query, retrieval_mode=retrieval,
                factor_tuple=factor_tuple,
            )
            chunks = []
            try:
                for kind, delta in stream_tokens(model, system_prompt, query):
                    if kind == "content":
                        chunks.append(delta)
                        yield sse("token", {"text": delta})
                    else:
                        yield sse("reasoning", {"text": delta})
            except Exception as e:
                yield sse("error", {"message": f"Ollama error: {e}. Is the model pulled and the "
                                               f"server running? (model={model})"})
                return
            response_text = "".join(chunks)

            yield sse("citations", compute_citation_stats(response_text, vep_options))

            if do_check:
                yield sse("status", {"message": "Running constraint checker…"})
                aliases = va.build_option_aliases(vep_options)
                enabled, disabled = va.extract_recommendations(response_text, aliases)
                violations = va.check_and_fix_violations(
                    enabled, disabled, vep_options, training_examples, query,
                    retrieval_mode=retrieval, assembly_override=assembly,
                )
                result = build_result(enabled, disabled, violations, vep_options, use_case,
                                      resolved=resolved)
                yield sse("result", result)

                # Persist identically to the CLI (provenance), reusing va helpers.
                warn = va.format_violation_warnings(violations)
                corrected = va.format_corrected_config(
                    enabled, disabled, vep_options, violations, resolved=resolved,
                )
                warnings = (warn + "\n" + corrected) if warn else corrected
            else:
                warnings = ""

            try:
                va.save_result(query, response_text, mode="recommend", warnings=warnings)
            except Exception:
                pass
            yield sse("done", {"checked": do_check})

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no",
                             "Connection": "keep-alive"})


@app.route("/api/explain_result")
def api_explain_result():
    query = (request.args.get("query") or "").strip()
    model = request.args.get("model") or DEFAULT_MODEL

    def gen():
        if not query:
            yield sse("error", {"message": "Empty question."})
            return
        with INFER_LOCK:
            consequences = va.load_consequences()
            if not consequences:
                yield sse("error", {"message": "vep_consequences.json not found."})
                return
            yield sse("meta", {"mode": "explain_result", "model": model,
                               "n_terms": len(consequences)})
            yield sse("status", {"message": f"Querying {model}…"})
            system_prompt = va.build_explain_result_prompt(consequences)
            chunks = []
            try:
                for kind, delta in stream_tokens(model, system_prompt, query):
                    if kind == "content":
                        chunks.append(delta)
                        yield sse("token", {"text": delta})
                    else:
                        yield sse("reasoning", {"text": delta})
            except Exception as e:
                yield sse("error", {"message": f"Ollama error: {e}"})
                return
            try:
                va.save_result(query, "".join(chunks), mode="explain")
            except Exception:
                pass
            yield sse("done", {})

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no",
                             "Connection": "keep-alive"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    print(f"Ask VEPai web UI  →  http://localhost:{port}")
    print(f"  Ollama: {BASE_URL}   default model: {DEFAULT_MODEL}")
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
