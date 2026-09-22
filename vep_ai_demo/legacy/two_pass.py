"""LEGACY -- the stage-B draft path. Not on the default path; loaded only by --two-pass or a legacy harness.

Moved verbatim out of vep_assistant.py on 2026-09-22. Until 2026-09-14 the tool made TWO model calls:
the factor classifier, then a "draft recommender" that was shown retrieved examples and asked to write
the configuration as prose, which this module then parsed (`✓/✗ [source: id]` markers), audited and
handed to the checker. Exp 20 measured that the checker rebuilt the same RECOMMENDED set whatever the
draft said (31/31), so the draft call was dropped and single-pass became the default.

What is here: example retrieval (keyword and embedding), the draft prompt builder, the marker parser and
its citation audit, the override report, and the structured-JSON assembler that had one stage-B caller.
The engine keeps eight one-line shims with these names so the harnesses and the web app that still
import them keep working; each shim loads this module on first use.

HOW IT BINDS. The functions are byte-identical to when they lived in the engine, so they refer to
engine names (RANK, load_species_data, _first_sentence, ...) unqualified. `_bind` copies the engine's
namespace in once, at load, so nothing here had to be rewritten -- and nothing here is imported by the
engine at startup.
"""


def _bind(engine_namespace):
    """Make every public and private name of the engine available here, unqualified.

    Takes the engine's `globals()` dict rather than a module object, because the generation pipeline
    loads the engine from its file path without registering it in sys.modules."""
    # Names this module defines itself are NOT overwritten: the engine carries one-line shims with the
    # same names that call back into here, and copying those in would make each function call itself.
    here = globals()
    here.update({k: v for k, v in engine_namespace.items()
                 if not k.startswith("__") and k not in here})


def build_option_aliases(vep_options):
    """Build a map of alias → option_id for fuzzy matching.

    Indexes each option by its id, display name and CLI flag(s), plus a hand-curated
    list of synonyms an LLM tends to emit (polyphen2, splice_ai, 1000genomes, ...).
    The map is the lookup table behind _match_option / the prose fallback parser.
    """
    # alias -> {option_ids claiming it}. Collected as CLAIMS, not assignments, so that an alias claimed by
    # more than one option can be dropped as ambiguous instead of silently resolving by insertion order.
    claims = {}

    def claim(alias, oid):
        alias = (alias or "").strip().lstrip("-").lower()
        if len(alias) > 2:      # 1-2 chars is too short to disambiguate
            claims.setdefault(alias, set()).add(oid)

    for opt in vep_options:
        oid = opt["id"]
        claim(opt["name"], oid)
        # CLI flags. Take only ACTUAL FLAG tokens (`--foo`), plus the plugin/custom NAME that follows
        # `--plugin`/`--custom`.
        #
        # IMPORTANT: take only ACTUAL flag tokens, not every substring of the cli_flag. Splitting the whole
        # cli_flag string on [/,\s]+ and indexing every token >2 chars produces wrong configurations. For `--plugin CADD,snv=/path/to/
        # SNVs.tsv.gz` that harvests `plugin`, `path`, `snv=`, `SNVs.tsv.gz`... — and `plugin` is the flag
        # KEYWORD, claimed by all 19 plugin options in the expanded catalogue. Last-write-wins left
        # `plugin` pointing at one arbitrary plugin, and because _match_option prefers the LONGEST
        # matching alias, a model citing `[source: plugin_cadd]` matched the 6-char `plugin` ahead of the
        # 4-char `cadd` and resolved to that arbitrary option — so a model citing `[source: plugin_cadd]`
        # would enable an arbitrary plugin (MaxEntScan on the demo KB, mutfunc on the expanded one) rather
        # than CADD, presented as authoritative with no warning. Any `plugin_<name>` where <name> is <= 6 chars hit this (cadd, revel, eve,
        # loeuf, sift...). Value syntax (`[b|p|s]`, claimed by sift+polyphen) had the same shape.
        flag_str = opt.get("cli_flag") or ""
        for tok in re.findall(r"--([A-Za-z0-9_]+)", flag_str):
            if tok.lower() not in _FLAG_KEYWORDS:
                claim(tok, oid)
        m = re.search(r"--(?:plugin|custom)\s+([A-Za-z0-9_]+)", flag_str)
        if m:
            claim(m.group(1), oid)
    # common extra aliases.
    # CAVEAT (demo-era targets): several values below are DEMO ids absent from the expanded 58-option
    # catalogue ('gnomad'->'gnomad_af' [now af_gnomade/af_gnomadg], 'mane'->'mane_select' [now 'mane'],
    # '1kg'->'af_1kg'). Layer 3 below fixes an extra whose KEY collides with a real id, but an extra
    # whose VALUE is a dead id still resolves to that dead id, which then silently falls out of every
    # catalogue lookup (rank 0 / all-species). Latent because the model cites real ids from the prompt.
    extras = {
        "polyphen2": "polyphen", "polyphen-2": "polyphen",
        "splice_ai": "spliceai", "splice ai": "spliceai",
        "alpha_missense": "alphamissense", "alpha missense": "alphamissense",
        "gnomad": "gnomad_af", "gnomad_freq": "gnomad_af",
        "gnomad_sv_freq": "gnomad_sv",
        "1000genomes": "af_1kg", "1000_genomes": "af_1kg", "1kg": "af_1kg",
        "af_1kg": "af_1kg",
        "maxentscan": "maxentscan", "max_ent_scan": "maxentscan",
        "mane": "mane_select",
        "gene_pheno": "gene_phenotype", "phenotype": "gene_phenotype",
        "existing": "check_existing", "check existing": "check_existing",
        "clinvar_structural": "clinvar_sv",
        "gnomad_structural": "gnomad_sv",
    }
    for alias, oid in extras.items():
        claim(alias, oid)

    # AMBIGUOUS aliases are DROPPED, not resolved by insertion order. An alias two options both claim
    # cannot identify either of them, and guessing one is how `plugin` came to mean `mutfunc`. Losing an
    # ambiguous alias only costs a fuzzy near-miss; keeping it costs a confidently wrong option.
    aliases = {a: next(iter(oids)) for a, oids in claims.items() if len(oids) == 1}
    # Real catalogue ids are EXACT and authoritative: they always win, over an extra (for the expanded
    # catalogue 'mane' is a real id, so it must map to 'mane', not 'mane_select') and over the ambiguity
    # filter above (e.g. `check_existing` is claimed by both `check_existing` and `clinvar`, whose flag is
    # "--check_existing (derived)", but it is also a real id, so it must resolve to itself).
    for opt in vep_options:
        aliases[opt["id"].lower()] = opt["id"]
    # FIX (phantom ids): drop any alias whose TARGET isn't a real catalogue id. The demo-era extras above
    # point at ids absent from the expanded catalogue (gnomad->gnomad_af, phenotype->gene_phenotype,
    # mane->mane_select); without this filter a model citing [source: gnomad] resolves to the dead
    # 'gnomad_af', which then leaks into `enabled` (confirmed in the 26b logs) and falls out of every
    # catalogue lookup. Filtering against the loaded catalogue keeps valid synonyms, drops dead targets —
    # and since valid_ids in extract_recommendations derives from these values, it fixes that too.
    real_ids = {opt["id"] for opt in vep_options}
    aliases = {alias: oid for alias, oid in aliases.items() if oid in real_ids}
    return aliases


def _match_option(text, aliases):
    """Try to match a text fragment to an option id.

    Uses direct matching first, then substring matching with a minimum
    length of 4 characters to avoid false positives from short fragments.
    """
    text = text.strip().lower().replace("-", "_").replace(" ", "_")
    # direct
    if text in aliases:
        return aliases[text]
    # strip leading dashes (cli flags)
    stripped = text.lstrip("_")
    if stripped in aliases:
        return aliases[stripped]
    # substring match — require both sides >= 4 chars to reduce false positives.
    # Longest alias first so the most specific match wins (e.g. 'gnomad_sv' before 'gnomad').
    if len(text) >= 4:
        for alias, oid in sorted(aliases.items(), key=lambda x: -len(x[0])):
            if len(alias) >= 4 and (alias in text or text in alias):
                return oid
    return None


# The audit describes a DRAFT the model wrote. Under the single-pass default there is none, so the
# "did not follow the output format" warning fired on every --explain run and told the user not to
# trust a configuration the resolver had built. It is now gated on the draft having said anything.
def audit_source_citations(text, option_aliases):
    """Deterministically audit the `[source: id]` ids the model cited, BEFORE we present an answer.

    The parser is deliberately forgiving: an id it cannot resolve is skipped (extract_recommendations_
    detailed), and a near-miss is fuzzy-resolved by _match_option. Both are silent, and silence is the
    problem — a model citing a source that does not exist is exactly the signal a provenance-traced tool
    exists to surface. This does not change any decision; it reports what the parser did, so the caller
    can show it.

    Returns {"exact": [id], "coerced": [(cited, resolved)], "unknown": [cited], "n_tagged": int,
    "n_lines": int}
      exact    — cited a real catalogue id
      coerced  — cited something else that fuzzily resolved to a real id (we GUESSED; say so)
      unknown  — cited something that resolves to nothing (dropped from the config entirely)
    """
    real_ids = set(option_aliases.values())
    real_ci = {r.lower(): r for r in real_ids}     # case-insensitive: the model capitalises freely
    exact, coerced, unknown = [], [], []
    # `[source:` is matched case-insensitively — a model writing "[Source: cadd]" (capital S) must not
    # collapse n_tagged to 0 and trip the "did not follow the format" alarm over one letter.
    for line in text.splitlines():
        m = re.search(r"\[source:\s*([A-Za-z0-9_]+)", line, re.IGNORECASE)
        if not m:
            continue
        cited = m.group(1)
        # A correctly-named id in the wrong case (e.g. "CADD" for `cadd`) is EXACT, not a guess — don't
        # cry wolf on a correct citation.
        if cited in real_ids or cited.lower() in real_ci:
            exact.append(real_ci.get(cited.lower(), cited))
            continue
        resolved = _match_option(cited, option_aliases)
        (coerced.append((cited, resolved)) if resolved else unknown.append(cited))
    return {"exact": exact, "coerced": coerced, "unknown": unknown,
            # How much draft text there was at all. Zero under the single-pass default, which is how
            # format_citation_audit tells "the model ignored the format" from "there was no draft".
            "n_lines": len([ln for ln in (text or "").splitlines() if ln.strip()]),
            "n_tagged": len(exact) + len(coerced) + len(unknown)}


def format_citation_audit(audit, kb_size):
    """Render the citation audit for the user. Empty string when the model cited cleanly."""
    if not audit.get("n_lines"):
        return ""                                    # no draft at all: the single-pass default
    if not audit["coerced"] and not audit["unknown"] and audit["n_tagged"]:
        return ""
    out = []
    if not audit["n_tagged"] and audit.get("n_lines"):
        # No [source:] tags at all: the model ignored the required output format. The parser will fall
        # back to scanning prose (Phases 1-2), which is built for the no-KB experimental condition and
        # guesses from wording — it cannot be trusted to carry a real recommendation. Say so rather than
        # present a config assembled by keyword-spotting.
        out.append("\n⚠️  THE MODEL DID NOT FOLLOW THE REQUIRED OUTPUT FORMAT")
        out.append("   It cited no [source: option_id] tags, so the configuration below was recovered by")
        out.append("   scanning its prose for option names — a fallback that guesses, and regularly gets")
        out.append("   enable/disable backwards. Do not trust it. Use a stronger model (gemma4:26b is the")
        out.append(f"   one this system is built and benchmarked on; the KB has {kb_size} options).")
        return "\n".join(out) + "\n"
    out.append("\n⚠️  CITATION AUDIT")
    for cited, resolved in audit["coerced"]:
        out.append(f"   GUESSED: the model cited '{cited}', which is not a catalogue id. Read as "
                   f"'{resolved}' (closest match). Confirm this is what you wanted.")
    for cited in audit["unknown"]:
        out.append(f"   DROPPED: the model cited '{cited}', which is not a VEP option in this knowledge "
                   f"base and matches nothing. It has been removed from the configuration.")
    return "\n".join(out) + "\n"


def format_marker_overrides(records, vep_options):
    """Report the ✓ lines whose own priority/reason overruled the tick. Empty when there were none.

    Sibling of format_citation_audit: the parser made a call the user did not watch it make, so it
    says so rather than quietly shipping a different configuration from the one the draft drew."""
    flipped = [r for r in records if r.get("marker_override")]
    if not flipped:
        return ""
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    out = ["", "⚠️  TICKS OVERRULED"]
    for r in flipped:
        nm = f"'{name_by_id.get(r['option_id'], r['option_id'])}' [{r['option_id']}]"
        if r["marker_override"] == "gate":
            # Do NOT quote the Reason here: in the observed case it argued FOR the option, and
            # printing it under "switched OFF" would read as the justification for the flip.
            out.append(f"   OFF: the model ticked {nm}, but the priority table rates it not "
                       f"applicable for this scenario, and its own line said so. Read as OFF.")
        else:
            why = (r["reason"] or "marked not applicable").rstrip(".")
            out.append(f"   OFF: the model ticked {nm} and then wrote \"{why}\". Read as OFF.")
    return "\n".join(out) + "\n"


def extract_recommendations_detailed(text, option_aliases):
    """Parse LLM output into ORDERED per-option records, the structured-output source of truth.

    Same three-tier strategy and EXACT same enable/disable decisions as
    extract_recommendations (which is now derived from this), but additionally captures the
    per-option fields the prompted format carries — confidence, the model's priority tag, the
    `Reason:` line, and any value — so the deterministic JSON assembler (build_recommendation_json)
    can emit schema-valid output WITHOUT the model ever producing JSON (Exp 8 showed it can't).

    Returns a list of dicts: {option_id, action ('enable'|'disable'), confidence, priority,
    reason, value, marker_override}. confidence/priority/reason/value are None outside Phase 0 (the
    bare-run fallbacks carry only an action). `marker_override` is None, or 'gate' / 'reason' when
    the line's ✓ was overruled — by its priority=NOT APPLICABLE echo of the resolver's gate, or by
    its own Reason text. See the rule below and format_marker_overrides. De-duplicated by (option_id, action), first occurrence wins,
    so the richest Phase-0 capture is kept and the derived sets are byte-identical to before.

      Phase 0  exact parse of the prompted `✓/✗ ... [source: option_id] confidence: X` format
               (+ the following `Reason:` line). Trustworthy; returns immediately if any found.
      Phase 1  markdown-table rows (`| option | enable |`). Phase 2  free prose (word-boundary).
    Phases 1-2 fire only when Phase 0 finds no `[source:]` tags (e.g. the bare no-KB run).
    """
    # CAVEAT: valid_ids are ALIAS TARGETS, some demo-era ids not in the real catalogue (see
    # build_option_aliases extras). The phantom-alias filter in build_recommendation_json /
    # score paths drops those; here we keep parser behaviour identical to the pre-refactor code.
    valid_ids = set(option_aliases.values())
    lines = text.splitlines()
    records = []
    seen = set()   # (option_id, action) — first wins; keeps set membership identical to the old parser

    def _add(oid, action, confidence=None, priority=None, reason=None, value=None,
             marker_override=None):
        key = (oid, action)
        if key in seen:
            return
        seen.add(key)
        records.append({"option_id": oid, "action": action, "confidence": confidence,
                        "priority": priority, "reason": reason, "value": value,
                        "marker_override": marker_override})

    # --- Phase 0: exact structured parse of the prompted format ---
    structured = False
    for i, raw_line in enumerate(lines):
        m = re.search(r"\[source:\s*([A-Za-z0-9_]+)", raw_line, re.IGNORECASE)
        if not m:
            continue
        oid = m.group(1)
        if oid not in valid_ids:
            oid = _match_option(oid, option_aliases)   # near-miss (name/flag) -> fuzzy resolve
            if not oid:
                continue
        # Marker anywhere BEFORE the [source:] tag, so bullets/numbering/bold don't hide it.
        head = raw_line[:m.start()]
        if "✓" in head or "✅" in head:
            action = "enable"
        elif "✗" in head or "✘" in head or "❌" in head:
            action = "disable"
        else:
            continue
        structured = True
        cm = re.search(r"confidence:\s*(high|medium|low)", raw_line, re.IGNORECASE)
        confidence = cm.group(1).lower() if cm else None
        pm = re.search(r"priority\s*=\s*([A-Za-z_]+)", raw_line)
        priority = pm.group(1) if pm else None
        # Reason: the following indented `Reason:` line, before the next marker/tag/blank break.
        reason = None
        for ln in lines[i + 1:]:
            rm = re.search(r"Reason:\s*(.+)", ln)
            if rm:
                reason = rm.group(1).strip() or None
                break
            stripped = ln.strip()
            if stripped == "" or "[source:" in ln or stripped[:1] in ("✓", "✗", "✅", "✘", "❌"):
                break
        # A TICK ITS OWN LINE CONTRADICTS IS NOT AN ENABLE. Observed live: the model emitted
        #     ✓ regiulatory [source: regulatory, priority=NOT APPLICABLE] confidence: high
        #       Reason: Not applicable as the focus is explicitly on coding regions.
        # and the parser read only the marker before `[source:`, so a coding-only exome run shipped
        # --regulatory carrying "Not applicable" as its justification. `most_severe` and `summary`
        # came through the same way in that run, and the two phantom enables manufactured all three
        # reported conflicts, one of which disabled HGVS and forced the restore pass to put it back.
        # Two distinct overrides, reported differently (format_marker_overrides), never silent:
        #   'gate'   — the line echoes priority=NOT APPLICABLE. That label is the resolver's hard
        #              gate restated by the model, and nothing downstream re-enforces gates, so it
        #              wins even when the Reason argues FOR the option (seen live: coding_only
        #              ticked with a pro-enable reason under priority=not_applicable).
        #   'reason' — the Reason text itself says disabled/not applicable, contradicting the tick.
        marker_override = None
        if action == "enable":
            if _NA_PRIORITY_RE.search(raw_line):
                action, marker_override = "disable", "gate"
            elif reason and _DISABLE_REASON_RE.match(reason):
                action, marker_override = "disable", "reason"
        _add(oid, action, confidence, priority, reason, marker_override=marker_override)
    if structured:
        return records   # trust the structured parse; don't run the fuzzy phases

    # --- Phases 1-2: replicate the legacy set-based fuzzy parser EXACTLY, then emit action-only
    # records from the resulting sets. Building the sets first (not records directly) preserves the
    # original "skip an option already decided in Phase 1" semantics of Phase 2 verbatim.
    enabled, disabled = set(), set()
    text_lower = text.lower()

    table_rows = re.findall(
        r"\|\s*\*{0,2}([^|]+?)\*{0,2}\s*\|\s*\*{0,2}(enable|disable|on|off|yes|no|true|false)\*{0,2}\s*\|",
        text_lower,
    )
    for opt_text, status in table_rows:
        opt_text = opt_text.strip().strip("`").strip("*")
        matched = _match_option(opt_text, option_aliases)
        if matched:
            if status in ("enable", "on", "yes", "true"):
                enabled.add(matched)
            else:
                disabled.add(matched)

    for line in text_lower.split("\n"):
        if "|" in line:
            continue
        for alias, oid in option_aliases.items():
            if oid in enabled or oid in disabled:
                continue
            if not re.search(r"\b" + re.escape(alias) + r"\b", line):
                continue
            if re.search(r"(enabl|turn.{0,3}on|\bon\b|recommend|include|add|use )", line):
                enabled.add(oid)
            elif re.search(r"(disabl|turn.{0,3}off|\boff\b|skip|omit|not.{0,6}need|unnecessary|don.t)", line):
                disabled.add(oid)

    for oid in sorted(enabled):
        _add(oid, "enable")
    for oid in sorted(disabled):
        _add(oid, "disable")
    return records


def extract_recommendations(text, option_aliases):
    """Parse LLM output to extract which options are enabled/disabled.

    Thin wrapper over extract_recommendations_detailed (the single parsing source of truth):
    derives the (enabled, disabled) id sets from the per-option records, so every existing caller
    gets byte-identical output while the structured-output path reuses the same parse. See that
    function for the three-tier strategy and the 2026-06-08 score-capping bug it fixes.
    """
    records = extract_recommendations_detailed(text, option_aliases)
    enabled = {r["option_id"] for r in records if r["action"] == "enable"}
    disabled = {r["option_id"] for r in records if r["action"] == "disable"}
    return enabled, disabled


def _detect_use_case(enabled: set, vep_options: list, training_examples: list,
                     user_query: str, retrieval_mode: str = "keyword") -> str:
    """Infer the use case category from the top retrieval match.

    In semantic mode, uses embedding cosine similarity so the use case detected
    here is consistent with the retrieval used to build the prompt. Falls back to
    keyword overlap otherwise, or if the semantic model is unavailable.

    CAVEATS: `enabled` is an unused (dead) param; the keyword-overlap block below is duplicated in
    print_decision_trace and retrieve_examples_keyword (drift risk); and .split() tokenises on whitespace
    WITHOUT stripping punctuation, so 'vcf.' != 'vcf' and word overlap is slightly under-counted.
    """
    if retrieval_mode == "semantic":
        try:
            scored = retrieve_examples_semantic(
                training_examples, user_query, vep_options, top_k=1
            )
            if scored:
                return scored[0][1]["use_case_category"]
        except Exception:
            pass  # fall back to keyword matching below
    scored = []
    query_words = set(user_query.lower().split())
    for ex in training_examples:
        ex_text = f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}".lower()
        ex_words = set(ex_text.split())
        overlap = len(query_words & ex_words)
        scored.append((overlap, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]["use_case_category"] if scored else "rare_disease_germline"


def _web_form_target(option: dict, species_form: str, model_value=None):
    """Map a catalogue option to its (web_form_field, action, value) for click-to-apply.

    Implements the SCHEMA_DESIGN.md field-name table deterministically from the option's id +
    source_type + cli_flag. `species_form` is the resolved InputForm species suffix (e.g.
    'Homo_sapiens'); `model_value` is an optional value the model emitted (rarely present).
    """
    oid = option["id"]
    src = option_source(option)
    flag = option.get("cli_flag", "") or ""

    if oid in RESTRICT_RESULTS_FAMILY:                       # one dropdown, name='summary'
        return "summary", "set_value", oid
    if oid == "core_type":                                 # transcript-database radiolist
        return "core_type", "set_value", (model_value or "core")
    if oid == "clinvar":                                   # no standalone control -> via check_existing
        return "check_existing", "enable", None
    if src == "plugin":
        m = re.search(r"--plugin\s+(\w+)", flag)
        key = m.group(1) if m else oid
        field = f"plugin_{key}"
        return field, "set_value", field
    if src == "custom":
        return f"custom_{oid}", "enable", None
    if oid in _SPECIES_SCOPED_IDS:
        return f"{oid}_{species_form}", "enable", None
    if oid in _SET_VALUE_DEFAULTS:
        return oid, "set_value", (model_value or _SET_VALUE_DEFAULTS[oid])
    return oid, "enable", None                             # native checkbox


def build_recommendation_json(query, response_text, vep_options, training_examples,
                              option_aliases=None, retrieval_mode="keyword",
                              model=None, kb_version=None, run_checker=True, resolved_override=None):
    """Assemble a schema-valid recommendation JSON from a model response — deterministically.

    Pipeline reuse (no logic fork): extract_recommendations_detailed (parse) +
    check_and_fix_violations (the SAME deterministic checker that repairs the CLI/web output) +
    KB factual fields (web_form_section / cli_flag / web_form_subsection / priority). The model
    never emits JSON; this is valid by construction against
    work/output_schema/vep_recommendation.schema.json.

    The serialised `recommendations` are the POST-checker set (corrected enables, mapped to
    enable/set_value, plus any explicit/checker disables as action='disable'), so the JSON never
    contains a species- or conflict-invalid combination — matching the click-to-apply contract.

    Returns a dict (JSON-serialisable). Offline-safe: needs only a logged response + the catalogue.
    """
    from datetime import datetime, timezone

    if option_aliases is None:
        option_aliases = build_option_aliases(vep_options)

    real_ids = {o["id"] for o in vep_options}
    by_id = {o["id"]: o for o in vep_options}

    # Parse -> per-option records; drop phantom (alias-target-only) ids the checker can't reason about.
    records = [r for r in extract_recommendations_detailed(response_text, option_aliases)
               if r["option_id"] in real_ids]
    reason_by_id = {}
    value_by_id = {}
    for r in records:                                      # first occurrence wins (richest capture)
        reason_by_id.setdefault(r["option_id"], r["reason"])
        value_by_id.setdefault(r["option_id"], r["value"])

    enabled = {r["option_id"] for r in records if r["action"] == "enable"}
    disabled = {r["option_id"] for r in records if r["action"] == "disable"}

    species = infer_species(query)
    # The retired seven-category scheme, reported as `detected_use_case` below. It decides nothing:
    # `get_confidence` ignores the argument, and the checker's conflict ranking reads the factor
    # resolution. Kept only so this function's JSON keeps its shape for its one caller,
    # work/harness/build/build_output_json.py (stage B, Exp 8).
    use_case = _detect_use_case(enabled, vep_options, training_examples, query, retrieval_mode)

    # DERIVED HERE, not 40 lines further down where the command is built. The checker call below
    # passes it as assembly_override, so leaving the assignment later made every call with the
    # checker on -- the default -- raise UnboundLocalError. Introduced 2026-08-06 (8978356) when the
    # override was threaded through; nothing caught it because build_output_json.py is the only
    # caller and it had not been run since.
    am = _ASSEMBLY_RE.search(query or "")
    assembly = am.group(1) if am else None

    violations = []
    restored = []
    if run_checker:
        # Mutates enabled/disabled in place into the corrected, authoritative set. Same two steps as
        # the CLI: the checker (with THIS scenario's gates) and then restore_missing_recommended, which
        # rebuilds the RECOMMENDED set from the factor tuple. Until 2026-09-15 the second step was
        # missing here, so under the single-pass default -- an empty draft -- this serialised ZERO
        # recommendations while the CLI printed twenty-one.
        violations = check_and_fix_violations(enabled, disabled, vep_options, query, assembly_override=assembly,
                                              resolved=resolved_override)
        if resolved_override:
            restored = restore_missing_recommended(enabled, disabled, resolved_override, vep_options,
                                                   query, assembly_override=assembly, violations_out=violations)

    species_out = "human" if species == "unknown" else species
    species_form = _SPECIES_FORM_NAME.get(species_out, species_out.replace(" ", "_").title())

    def _rec(oid, action_kind):
        opt = by_id[oid]
        field, action, value = _web_form_target(opt, species_form, value_by_id.get(oid))
        if action_kind == "disable":                      # ensure-OFF entry
            action, value = "disable", None
        # Factor-scheme label for THIS tuple (recommended / optional / not_applicable). The legacy
        # seven-use-case label was retired on 2026-09-13; a frozen copy lives in harness/legacy/.
        _e, _pr, _g = (resolved_override or {}).get(oid, (False, None, None))
        priority = _pr if (_pr and not _g) else "not_applicable"
        reason = reason_by_id.get(oid) or _first_sentence(opt.get("description", "")) or opt.get("name", oid)
        return {
            "option_id": oid,
            "web_form_section": opt.get("web_form_section", "advanced"),
            "web_form_subsection": opt.get("web_form_subsection"),
            "web_form_field": field,
            "action": action,
            "value": value,
            "cli_flag": opt.get("cli_flag", ""),
            # `critical` STAYS IN THIS LIST. It was removed here on 2026-09-02 as part of deleting the
            # third tier, which was wrong: `priority` above is read from the LEGACY
            # priority_by_use_case field, a different axis that still carries 26 `critical` entries,
            # and the output schema's enum allows all four. Dropping it from the allow-list silently
            # demoted every legacy critical to `not_applicable` -- the exact failure get_confidence's
            # comment warns about, committed in the function next door.
            "priority": priority if priority in ("critical", "recommended", "optional",
                                                 "not_applicable") else "not_applicable",
            "confidence": get_confidence(oid, use_case, vep_options, resolved=resolved_override),
            "source": f"[source: {oid}]",
            "reason": reason,
        }

    recommendations = [_rec(oid, "enable") for oid in sorted(enabled)]
    recommendations += [_rec(oid, "disable") for oid in sorted(disabled) if oid in by_id]

    # constraint_check: 'passed' = no STRUCTURAL repair was needed (advisory-only notes, e.g. the
    # 'unknown species' flag, don't flip it). Each checker violation already uses the schema's keys.
    structural = [v for v in violations
                  if any(k in v for k in ("option_disabled", "option_enabled", "option_kept"))]
    viol_out = []
    for v in violations:
        item = {"type": v["type"], "reason": v["reason"]}
        for k in ("option_disabled", "option_enabled", "option_kept"):
            if k in v:
                item[k] = v[k]
        viol_out.append(item)

    # generated_command mirrors the final (post-checker) enabled set. Shares cli_flags_for() with
    # format_corrected_config so the printed command and the JSON command cannot drift apart.
    flags, choices = cli_flags_for(enabled, vep_options)
    cmd = "vep --input_file <in.vcf> --output_file <out.txt> --cache"
    if species_out:
        cmd += f" --species {species_out.lower().replace(' ', '_')}"
    if assembly:
        cmd += f" --assembly {assembly}"
    if flags:
        cmd += " " + " ".join(flags)

    out = {
        "query": query,
        "detected_use_case": use_case,
        "species": species_out,
        "assembly": assembly,
        "recommendations": recommendations,
        "constraint_check": {"passed": len(structural) == 0, "violations": viol_out},
        "generated_command": cmd,
        # Menu-style options (transcript DB, gnomAD exome-vs-genome) cannot be pasted into a command —
        # surfaced so a caller can prompt instead of emitting an unrunnable flag.
        "command_choices": [{"option_id": oid, "alternatives": alts} for oid, alts in choices],
        "metadata": {
            # ids the table restored rather than the draft proposed (all of them under single-pass)
            "restored_from_table": sorted(restored),
            "retrieval_mode": retrieval_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    if model:
        out["metadata"]["model"] = model
    if kb_version:
        out["metadata"]["kb_version"] = kb_version
    return out


def is_plugin_flag(cli_flag: str) -> bool:
    """True if an option needs an EXTERNAL data file / install (a `--plugin X` or `--custom ...` option),
    rather than a native VEP flag that works from the core cache alone.

    This is the source-grounded discriminator (the `cli_flag` itself), not a priority judgement,
    so it is safe to drive output tiers off it. (The `priority_by_use_case` field it was once
    contrasted with was retired on 2026-09-13.)
    """
    f = cli_flag or ""
    return "--plugin" in f or "--custom" in f


def tier_options(enabled, vep_options):
    """Split an enabled option set into two deterministic, separable output tiers:

      - ``core``   — native VEP flags: available from the core install, no extra data, fast.
      - ``addons`` — plugins / custom files (``--plugin`` / ``--custom``): need downloaded data
                     files and add runtime, so a user may want to opt in to them explicitly.

    The split is FACTUAL (keyed on ``cli_flag`` via :func:`is_plugin_flag`), so it is reliable —
    unlike an essential-vs-optional split, which depends on the still-unsigned priority table.
    Returns ``{"core": [...ids], "addons": [...ids]}`` (each sorted).
    """
    flag_by_id = {o["id"]: o.get("cli_flag", "") for o in vep_options}
    core, addons = [], []
    for oid in sorted(enabled):
        (addons if is_plugin_flag(flag_by_id.get(oid, "")) else core).append(oid)
    return {"core": core, "addons": addons}


DESC_CHARS = 120   # how much of each option's description the model is shown; None = all of it


_SENTINEL = object()


def _desc(opt, desc_chars):
    """The description as the model sees it. `desc_chars=None` means the whole thing."""
    d = opt.get('description', '') or ''
    n = DESC_CHARS if desc_chars is _SENTINEL else desc_chars
    return d if n is None else d[:n]


def compress_options(vep_options, resolved=None, desc_chars=_SENTINEL):
    """Convert verbose JSON options into a compact text reference.

    `resolved` is the output of intent_priorities() for THIS query's factor tuple. When supplied,
    each option carries the single priority that applies to this scenario ("recommended"
    / "optional" / "not applicable here") instead of the flat dump of all seven legacy use-case
    labels. That flat dump was the same for every query and left the model to guess which column it
    was in; showing the resolved tier is what lets it distinguish must-have from standard-default
    from add-on. Omit `resolved` to get the original behaviour (the experiment harness relies on it)."""
    lines = []
    for opt in vep_options:
        if resolved is not None:
            en, pr, gated = resolved.get(opt["id"], (False, None, False))
            priorities = ("NOT APPLICABLE for this scenario" if gated
                          else f"{pr} for this scenario" if pr
                          else "no priority for this scenario")
        else:
            priorities = "no factor resolution for this query (legacy use-case labels retired 2026-09-13)"
        conflicts = ", ".join(opt.get("conflicts_with", [])) or "none"
        depends = ", ".join(opt.get("depends_on", [])) or "none"
        # NOTE: when_to_use / when_not_to_use are deliberately NOT shown here — they feed semantic
        # retrieval embeddings (_get_options_embeddings) but the model never sees them in this block;
        # only description[:120] + species + priorities + conflicts/depends are. (Attribution implication:
        # the Exp 6 'description' ablation effectively removes description[:120] + the priority labels,
        # NOT when_to_use/when_not_to_use.) .get guards a catalogue entry missing a key (else KeyError).
        lines.append(
            # DESCRIPTION TRUNCATION. Every one of the 58 descriptions is longer than 120 characters,
            # so at the default the model has never seen a complete one — and the cut lands badly:
            # check_existing is severed at "Returns existing variant IDs (e.g. rsIDs), C", one character
            # before the word ClinVar, which is the only place the prompt would explain why `clinvar`
            # depends on it. cadd loses "coding and non-coding", the exact property that exempts it from
            # the regulatory gate. Set desc_chars=None to send the full text (~+3.5k prompt tokens;
            # prefill is not the bottleneck, generation is, so it costs little).
            f"- **{opt['id']}** (`{opt.get('cli_flag', '')}`): {_desc(opt, desc_chars)}. "
            f"Species: {species_phrase(opt)}. "
            f"Priorities: {priorities}. "
            f"Conflicts: {conflicts}. Depends: {depends}."
        )
    return "\n".join(lines)


def retrieve_examples_keyword(training_examples, user_query, top_k=2):
    """Keyword-based retrieval: score examples by word overlap with query.

    Returns list of (score, example) tuples sorted by relevance.
    """
    query_words = set(user_query.lower().split())
    scored = []
    for ex in training_examples:
        ex_text = f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}".lower()
        ex_words = set(ex_text.split())
        overlap = len(query_words & ex_words)
        scored.append((overlap, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def retrieve_examples_semantic(training_examples, user_query, vep_options=None, top_k=2):
    """Semantic retrieval: score examples by cosine similarity with query.

    Returns list of (score, example) tuples sorted by relevance.
    """
    from sentence_transformers.util import cos_sim

    model = _get_semantic_model()
    corpus_embs = _get_corpus_embeddings(training_examples)
    query_emb = model.encode([user_query])

    similarities = cos_sim(query_emb, corpus_embs)[0]
    scored = [(float(similarities[i]), training_examples[i]) for i in range(len(training_examples))]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def retrieve_options_semantic(vep_options, user_query, top_k=10):
    """Semantic retrieval for VEP options: return top-k most relevant options.

    Returns list of (score, option) tuples sorted by relevance.
    """
    from sentence_transformers.util import cos_sim

    model = _get_semantic_model()
    options_embs = _get_options_embeddings(vep_options)
    query_emb = model.encode([user_query])

    similarities = cos_sim(query_emb, options_embs)[0]
    scored = [(float(similarities[i]), vep_options[i]) for i in range(len(vep_options))]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def format_example(ex):
    """Format a training example compactly."""
    opts = []
    for name, cfg in ex["recommended_options"].items():
        status = "ON" if cfg.get("enabled") else "OFF"
        note = f' ({cfg["note"]})' if cfg.get("note") else ""
        opts.append(f"  {name}: {status}{note}")
    return (
        f"Query: {ex['user_query']}\n"
        # A corpus row is allowed to carry neither field. The 31 factor rows carry NEITHER, so
        # `ex['justification'][:200]` took the whole run down with a TypeError the moment anyone
        # pointed VEP_EXAMPLES_FILE at them -- which is the first thing you try when evaluating
        # whether the factor rows should become the corpus.
        f"Use case: {ex.get('use_case_category') or 'unspecified'}\n"
        f"Options:\n" + "\n".join(opts) + "\n"
        f"Rationale: {(ex.get('justification') or '')[:200]}..."
    )


def get_confidence(option_id, use_case, vep_options, resolved=None):
    """Confidence from THIS query's factor resolution.

        high    the table RECOMMENDS the option for this tuple
        medium  the table offers it as an add-on (`optional`)
        low     unpriced, hard-gated, or no resolution available

    Rewritten 2026-09-13. It used to read `priority_by_use_case` -- the retired seven-use-case table,
    priced against a use case guessed from the top retrieved example -- which stamped `pick` "high"
    on a rare-disease query the factor table never enables (0 of 108 tuples). A frozen copy of that
    table is in `work/harness/legacy/`; only the offline scorers still read it. `use_case` is kept in
    the signature so the thirteen call sites and the JSON schema do not move."""
    if resolved is None:
        return "low"
    _e, pri, gated = resolved.get(option_id, (False, None, None))
    if gated or pri not in ("recommended", "optional"):
        return "low"
    return "high" if pri == "recommended" else "medium"


def build_system_prompt(vep_options, training_examples, user_query="",
                        retrieval_mode="keyword", examples_override=None, factor_tuple=None,
                        desc_chars=_SENTINEL, resolved_override=None):
    """Construct a compact system prompt with retrieved examples.

    Assembles three blocks — the compressed option KB, the retrieved reference
    examples, and the strict output contract — into one system prompt. The output
    contract is what makes the `✓/✗ ... [source: option_id]` lines that Phase 0 of
    extract_recommendations parses, and the citations the interpretability layer scores.

    Args:
        retrieval_mode: "keyword" for word-overlap retrieval, "semantic" for
            embedding-based retrieval, "all" to include every training example.
            NOTE: only "semantic" hard-filters the options (top-10); "keyword"/"all" show the full
            catalogue. This top-10 semantic filter HURTS retrieval (see the experiments: do not hard-filter the
            58 options) — it is retained only as the eval's comparison condition, so `--semantic` in the
            demo runs a known-worse path and is not the recommended production setting.
        examples_override: optional pre-selected, pre-ORDERED list of example dicts to place in the
            "Reference Examples" block verbatim (order preserved). When given, the normal example
            selection (all / semantic-retrieval / keyword) is bypassed, but OPTION selection still
            follows retrieval_mode (semantic still applies its top-10 option filter). Used by the
            example-order-sensitivity experiment (work/run_order_sensitivity.py) to vary ONLY the
            order/identity of the in-context examples while holding everything else fixed.
    """
    # Resolve THIS query's factor tuple to per-option tiers, so the option block can state the one
    # priority that applies here instead of all seven legacy use-case labels at once.
    #
    # `resolved_override` lets a caller substitute an already-computed resolution. The attribution
    # harness needs it: its priority ablation removes ONE option's label and must leave every other
    # option's untouched, which cannot be expressed by changing the factor tuple or the catalogue
    # (DRIVES prices options in code, not in the catalogue). Nothing in the shipped path passes it.
    resolved = resolved_override if resolved_override is not None else resolve_for_query(
        factor_tuple, vep_options)

    relevant_options = None
    if examples_override is not None:
        scored_examples = [(0, ex) for ex in examples_override]
        if retrieval_mode == "semantic" and user_query:
            scored_options = retrieve_options_semantic(vep_options, user_query, top_k=10)
            relevant_options = [opt for _, opt in scored_options]
            options_text = compress_options(relevant_options, resolved, desc_chars)
        else:
            options_text = compress_options(vep_options, resolved, desc_chars)
    elif retrieval_mode == "all":
        # Include ALL training examples, no retrieval filtering
        options_text = compress_options(vep_options, resolved, desc_chars)
        scored_examples = [(0, ex) for ex in training_examples]
    elif retrieval_mode == "semantic" and user_query:
        # Use semantic retrieval for both options and examples
        scored_options = retrieve_options_semantic(vep_options, user_query, top_k=10)
        relevant_options = [opt for _, opt in scored_options]
        options_text = compress_options(relevant_options, resolved, desc_chars)
        scored_examples = retrieve_examples_semantic(
            training_examples, user_query, vep_options
        )
    else:
        options_text = compress_options(vep_options, resolved, desc_chars)
        if user_query:
            scored_examples = retrieve_examples_keyword(training_examples, user_query)
        else:
            scored_examples = [(0, ex) for ex in training_examples[:2]]
    examples_text = "\n\n".join(format_example(ex) for _, ex in scored_examples)

    scenario_block = ""
    if factor_tuple:
        scenario_block = f"""
## Detected Scenario
{describe_factors(factor_tuple)}

The priority shown against each option below is the one that applies to THIS scenario. Enable the
`recommended` options. Offer `optional` ones as add-ons only if they genuinely help, and never enable
anything marked NOT APPLICABLE.
"""

    num_options = len(relevant_options) if relevant_options is not None else len(vep_options)
    return f"""You are a VEP (Variant Effect Predictor) Configuration Assistant for Ensembl VEP.
Given a user's analysis scenario, recommend which VEP options to enable/disable with justifications.
{scenario_block}
## VEP Options ({num_options} shown)
{options_text}

## Reference Examples
{examples_text}

## Scope
You ONLY recommend VEP configurations for variant-analysis scenarios. If the user's message is not
such a scenario — small talk, an unrelated topic, or a VEP how-to/troubleshooting question rather than
a request to configure a run — reply with a message that BEGINS with exactly:

OUT OF SCOPE: <one or two sentences saying what this assistant does>

In that case output NOTHING else: no ✓/✗ lines, no [source:] tags, no VEP command. This marker lets the
system skip the configuration checks, which would otherwise report misleading warnings about a
configuration you never proposed.

## Output Format
Respond in three sections:
### 1. Detected Scenario
Restate the scenario as its factor values (species, origin, variant_size_class, region_focus,
analysis_goal) and say briefly what in the question indicates each.
### 2. Recommended Options
For EACH option, use this exact format (one per line):

✓ option_name [source: option_id, priority=X] confidence: high|medium|low
  Reason: explanation of why this option is enabled, citing the knowledge base entry.

✗ option_name [source: option_id] confidence: high|medium|low
  Reason: explanation of why this option is disabled.

Use ✓ for ENABLE, ✗ for DISABLE. The [source: ...] tag traces back to the knowledge base.
### 3. Generated VEP Command
```
vep --input_file <input.vcf> --output_file <output.txt> --cache [flags...]
```
Use placeholder paths for plugin data files. Also note web interface equivalents.

## Rules
- Check species restrictions: PolyPhen, CADD, AlphaMissense, REVEL, ClinVar, gnomAD are human-only.
- Flag conflicts (e.g. --most_severe incompatible with --sift, --polyphen, --hgvs, --symbol).
- Consider dataset size and runtime (--regulatory reduces buffer; plugins add time).
- Ask clarifying questions if ambiguous.
- Always include the [source: option_id, priority=X] citation for traceability.
- Be specific about WHY each option is enabled/disabled."""


# --- Moved out of vep_assistant.py on 2026-09-22: the draft call, its parse, the --explain Layer 1,
# and the embedding retrieval (--semantic, removed from the CLI on 2026-09-20). ------------------------

def draft(client, model, vep_options, training_examples, user_query, factor_tuple,
          retrieval_mode="all", think=False):
    """The retired second model call: build the draft prompt and stream the model's draft.
    Returns (response_text, reasoning_text, seconds). Moved from vep_assistant.run_recommend on
    2026-09-22; the CLI always passed retrieval_mode="all" and think=False."""
    system_prompt = build_system_prompt(vep_options, training_examples, user_query,
                                        retrieval_mode=retrieval_mode,
                                        factor_tuple=factor_tuple)
    print("Analysing your scenario...\n")

    t_recommend = time.perf_counter()
    try:
        response_text, reasoning_text = _stream_native(model, system_prompt, user_query, think)
    except Exception as e:
        print(f"\nError communicating with Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        print(f"And the model is pulled: ollama pull {model}")
        sys.exit(1)
    return response_text, reasoning_text, time.perf_counter() - t_recommend


def parse_draft(response_text, reasoning_text, vep_options, user_query):
    """Audit and parse the draft. Returns None when the model declined (the refusal is printed and saved),
    else (diagnostics, recs, enabled, disabled, audit_report, override_report). Moved from
    vep_assistant.run_recommend on 2026-09-22."""
    option_aliases = build_option_aliases(vep_options)
    # Audit what the model CITED before we act on it: ids that don't exist are dropped, near-misses
    # are fuzzy-resolved, and both used to happen silently.
    audit = audit_source_citations(response_text, option_aliases)
    if is_out_of_scope_response(response_text, audit):
        print(response_text.strip())
        print()
        save_result(user_query, response_text, mode="recommend", warnings="",
                    reasoning=reasoning_text)
        return None
    diagnostics = []
    audit_report = format_citation_audit(audit, len(vep_options))
    if audit_report:
        diagnostics.append(audit_report)
    _recs = extract_recommendations_detailed(response_text, option_aliases)
    enabled = {r["option_id"] for r in _recs if r["action"] == "enable"}
    disabled = {r["option_id"] for r in _recs if r["action"] == "disable"}
    override_report = format_marker_overrides(_recs, vep_options)
    if override_report:
        diagnostics.append(override_report)
    return diagnostics, _recs, enabled, disabled, audit_report, override_report


def print_example_retrieval(user_query, vep_options, training_examples, retrieval_mode="all"):
    """Layer 1 of the --explain trace under --two-pass: which worked examples the draft prompt carried.
    Moved verbatim from vep_assistant.print_decision_trace on 2026-09-22. No caller: run_recommend never
    passed two_pass=True to the trace, so the CLI never printed this layer."""
    two_pass = True
    if two_pass:
        print("\n--- Layer 1: Which worked examples the model saw ---")
    if two_pass and retrieval_mode == "all":
        # Nothing is selected, so there is no ranking to explain. This block used to print all 23
        # examples ordered by a stopword-inclusive word count, which implied a relevance judgement
        # that neither happened nor mattered.
        print(f"All {len(training_examples)} worked examples are sent — none is selected or ranked, "
              f"so there is no retrieval decision to explain here.\n")
    elif two_pass and retrieval_mode == "semantic":
        print("Ranked by BGE embedding cosine similarity (0-1).\n")
    else:
        # Be honest about what the number is. It used to print as `score=3`, which reads like a
        # calibrated relevance metric; it is a count of whitespace-separated words the query and the
        # example have in common, with no stopword removal, no stemming and no length normalisation —
        # so "are" and "which" count for as much as "mouse", and a longer example matches more by
        # having more words. Two examples tying at 3 is common and the tie is broken by list order.
        print("Ranked by how many words the query and the example share — a raw count, so common\n"
              "words count as much as informative ones. Experiment 1 measured selective retrieval as\n"
              "no better than using every example, so this is WHAT was picked, not what decided the\n"
              "answer.\n")

    if retrieval_mode == "semantic":
        from sentence_transformers.util import cos_sim

        model = _get_semantic_model()
        corpus_embs = _get_corpus_embeddings(training_examples)
        query_emb = model.encode([user_query])
        similarities = cos_sim(query_emb, corpus_embs)[0]

        all_scored = [
            (float(similarities[i]), training_examples[i])
            for i in range(len(training_examples))
        ]
        all_scored.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, ex) in enumerate(all_scored, 1):
            marker = " ← SELECTED" if rank <= 2 else ""
            print(f"  #{rank} [{ex['id']}] cosine_similarity={score:.4f}{marker}")
            print(f"      Use case: {ex['use_case_category']}")
            print()

        # Also show option relevance
        print("--- Layer 1b: Option Semantic Relevance ---")
        options_embs = _get_options_embeddings(vep_options)
        opt_sims = cos_sim(query_emb, options_embs)[0]
        opt_scored = [
            (float(opt_sims[i]), vep_options[i])
            for i in range(len(vep_options))
        ]
        opt_scored.sort(key=lambda x: x[0], reverse=True)
        for rank, (score, opt) in enumerate(opt_scored, 1):
            marker = " ← INCLUDED" if rank <= 10 else ""
            print(f"  #{rank} {opt['id']:20s} cosine_similarity={score:.4f}{marker}")
        print()
    elif retrieval_mode != "all":
        # Keyword mode. Skipped under "all": nothing was selected, so ranking 23 examples by a
        # stopword-inclusive word count would describe a decision that did not happen.
        query_words = set(user_query.lower().split())
        all_scored = []
        for ex in training_examples:
            ex_text = f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}".lower()
            ex_words = set(ex_text.split())
            overlap = query_words & ex_words
            all_scored.append((len(overlap), overlap, ex))
        all_scored.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, matched_words, ex) in enumerate(all_scored, 1):
            marker = "  ← SELECTED" if rank <= 2 else ""
            shared = ", ".join(sorted(matched_words)[:10]) if matched_words else "nothing"
            print(f"  #{rank} [{ex['id']}]  {score} shared word{'' if score == 1 else 's'}: "
                  f"{shared}{marker}")
            print(f"      Use case: {ex['use_case_category']}")
            print()

# ---------------------------------------------------------------------------
# Semantic retrieval (lazy-loaded, only when --semantic is used)
# ---------------------------------------------------------------------------

_semantic_model = None
_corpus_embeddings = None
_corpus_examples = None
_options_embeddings = None
_options_list = None


def _get_semantic_model():
    """Lazy-load the sentence-transformers model."""
    global _semantic_model
    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer
        _semantic_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _semantic_model


def _get_corpus_embeddings(training_examples):
    """Compute and cache corpus embeddings for training examples."""
    global _corpus_embeddings, _corpus_examples
    if _corpus_embeddings is None or _corpus_examples is not training_examples:
        model = _get_semantic_model()
        _corpus_examples = training_examples
        texts = [
            f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}"
            for ex in training_examples
        ]
        _corpus_embeddings = model.encode(texts)
    return _corpus_embeddings


def _get_options_embeddings(vep_options):
    """Compute and cache embeddings for VEP options."""
    global _options_embeddings, _options_list
    if _options_embeddings is None or _options_list is not vep_options:
        model = _get_semantic_model()
        _options_list = vep_options
        texts = [opt["description"] for opt in vep_options]
        _options_embeddings = model.encode(texts)
    return _options_embeddings


# --- Moved out of vep_assistant.py on 2026-09-22: used only by the draft path above. ----------------

import re  # these patterns are built at import, before _bind supplies the engine's names

# Every plugin's cli_flag starts `--plugin` and every custom dataset's `--custom`. These words
# identify no option on their own, so they are never aliases.
_FLAG_KEYWORDS = {"plugin", "custom"}


OUT_OF_SCOPE_PREFIX = "OUT OF SCOPE:"


_REFUSAL_RE = re.compile(
    r"(only (?:able to |designed to |here to )?(?:help|assist|answer|provide|recommend)\b[^.]{0,60}\bVEP)"
    r"|(\bI (?:can|am) only\b)"
    r"|(\b(?:outside|beyond) (?:the |my )?scope\b)"
    r"|(\bnot (?:a |an )?(?:VEP )?(?:variant|configuration|annotation)[- ]related\b)"
    r"|(\bI'?m (?:a|an) VEP\b[^.]{0,60}\bassistant\b)",
    re.IGNORECASE,
)


def is_out_of_scope_response(text, audit):
    """True when the draft declined to configure VEP, so there is no configuration to check.

    True on the OUT OF SCOPE marker, or on refusal phrasing with no citations and no ✓/✗ markers."""
    if not text:
        return False
    if text.lstrip().upper().startswith(OUT_OF_SCOPE_PREFIX):
        return True
    if audit and audit.get("n_tagged"):
        return False                                   # it cited the KB -> it attempted a config
    if re.search(r"(?m)^\s*[✓✗]", text):
        return False                                   # it used the recommendation markers
    return bool(_REFUSAL_RE.search(text))


# Signals on the same line as a ✓ that the draft means the option to be off (read by
# extract_recommendations_detailed in legacy/two_pass.py). `priority=` is the model's own text.
_NA_PRIORITY_RE = re.compile(r"priority\s*=\s*not[\s_]*applicable", re.IGNORECASE)


_DISABLE_REASON_RE = re.compile(
    r"\s*(disabled|not applicable|not needed|not relevant|not required|should not|excluded)\b",
    re.IGNORECASE)


# Controls whose HTML name takes a species suffix (`regulatory_<Species>`).
_SPECIES_SCOPED_IDS = {"regulatory", "cell_type"}


# Species word -> InputForm species suffix.
_SPECIES_FORM_NAME = {
    "human": "Homo_sapiens", "mouse": "Mus_musculus", "rat": "Rattus_norvegicus",
    "zebrafish": "Danio_rerio", "pig": "Sus_scrofa", "dog": "Canis_lupus_familiaris",
    "chicken": "Gallus_gallus", "cow": "Bos_taurus",
}


# Moved out of vep_assistant.py on 2026-09-22: only the draft passes `think`.
def _stream_native(model, system_prompt, user_message, think):
    """Stream from Ollama's native /api/chat, the only endpoint that honours `think`; return (answer, thinking).

    The OpenAI-compatible /v1 endpoint drops `think`, even via `extra_body`.
    """
    import urllib.request
    body = {
        "model": model, "stream": True, "keep_alive": KEEP_ALIVE, "think": think,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_message}],
        "options": {"num_predict": _STREAM_MAX_TOKENS},
    }
    req = urllib.request.Request(_native_chat_url(), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    answer, thinking = "", ""
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:                                  # newline-delimited JSON, one object per chunk
            raw = raw.strip()
            if not raw:
                continue
            msg = json.loads(raw).get("message", {})
            if msg.get("thinking"):
                thinking += msg["thinking"]
            if msg.get("content"):
                answer += msg["content"]
                # The draft is not printed (see stream_response); only a live counter.
                if sys.stdout.isatty():
                    print(f"\r  drafting… {len(answer) // 4} tokens", end="", flush=True)
    if sys.stdout.isatty():
        print("\r" + " " * 40 + "\r", end="", flush=True)
    return answer, thinking
