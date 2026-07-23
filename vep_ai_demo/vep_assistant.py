#!/usr/bin/env python3
"""VEP AI Assistant — recommends Ensembl VEP configuration based on your analysis scenario.

Supports three modes:
  python vep_assistant.py                        # interactive recommendation
  python vep_assistant.py --explain "query"      # recommendation + decision trace
  python vep_assistant.py explain-result "why..." # explain a VEP output annotation

How much configuration you get back (default = standard):
  --minimal   only the options that are essential for your scenario
  --full      also switch on every add-on the scenario justifies
"""

import json
import os
import re
import sys
import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai SDK not installed. Run: pip install openai")
    sys.exit(1)

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Knowledge base loading
# ---------------------------------------------------------------------------

def load_knowledge_base():
    """Load VEP options and training examples from JSON files.

    Honours VEP_OPTIONS_FILE / VEP_EXAMPLES_FILE env vars so the same code can
    run on the demo KB (default) or the expanded catalogue + bootstrap set.
    """
    options_path = Path(os.environ.get("VEP_OPTIONS_FILE", BASE_DIR / "vep_options.json"))
    examples_path = Path(os.environ.get("VEP_EXAMPLES_FILE", BASE_DIR / "training_examples.json"))

    if not options_path.exists():
        print(f"Error: VEP options file not found at {options_path}")
        sys.exit(1)
    if not examples_path.exists():
        print(f"Error: Training examples file not found at {examples_path}")
        sys.exit(1)

    with open(options_path) as f:
        vep_options = json.load(f)
    with open(examples_path) as f:
        training_examples = json.load(f)

    return vep_options, training_examples


def load_consequences():
    """Load VEP consequence term definitions."""
    path = BASE_DIR / "vep_consequences.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# The FACTOR SCHEME (single source of truth — the generation pipeline imports this)
# ---------------------------------------------------------------------------
# A "use case" is a SET of factor values, not one category. The older single-label scheme
# (rare_disease_germline / somatic_cancer / ...) mixes axes — a mouse somatic SV is somatic AND
# structural AND non-human at once — so it mislabels the scenario and picks the wrong priorities.
# See research/taxonomy_proposal.md §3.
#
# This block lives HERE, in the engine, deliberately. Both entry paths need it (the prose
# recommender and the deterministic factor resolver), and the dependency arrow runs
# work/generation -> vep_ai_demo, never the reverse (the demo must stay standalone/publishable).
# Defining it once here is what stops the two paths from drifting apart.
#
# NOTHING here is mentor-validated: the scheme and the priority table are PROVISIONAL config
# files. On sign-off, swap the JSON — the code does not change.

def load_factors():
    """The factor scheme (values, kinds, hard gates, exclusions, conditional rules)."""
    path = Path(os.environ.get("VEP_FACTORS_FILE", BASE_DIR / "factors.json"))
    with open(path) as f:
        return json.load(f)


def load_priority_by_factor():
    """The PROVISIONAL importance table, keyed option -> factor -> value -> priority."""
    path = Path(os.environ.get("VEP_PRIORITY_FACTOR_FILE", BASE_DIR / "priority_by_factor.json"))
    with open(path) as f:
        return json.load(f)


PRIORITY_ORDER = {"critical": 3, "recommended": 2, "optional": 1}

# Factors that can REMOVE an option outright when they mark it not_applicable.
#
# `region_focus` was added on documentary evidence, and it AMENDS taxonomy_proposal §3, which calls it
# "purely soft". The docs disagree with the proposal: the catalogue rates the missense predictors (and
# mane/protein/nmd) `regulatory_noncoding: not_applicable` — 9 of 10 predictors, CADD the sole exception —
# and constraints_dossier.md:123 prescribes exactly this: "Model as a soft dependency (recommender gate,
# not a CLI requirement): apply only to missense/coding variants." Without the gate, composition is
# max-only, so `analysis_goal=clinical` would hand missense predictors to a purely regulatory query.
# FLAG FOR THE MENTOR: this is a proposed amendment to §3, not something §3 already licenses.
HARD_GATE_FACTORS = ("species", "variant_size_class", "region_focus")

FACTOR_VALUES = {
    "species": ["human", "non-human"],
    "origin": ["germline", "somatic"],
    "variant_size_class": ["small", "structural-CNV"],
    "region_focus": ["coding", "regulatory-noncoding"],                                   # multi-select
    "analysis_goal": ["basic-consequence", "clinical-interpretation", "population-frequency"],  # multi-select
}
MULTI_FACTORS = ("region_focus", "analysis_goal")

# Options whose value is not a bare boolean (everything else -> True when enabled).
VALUE_DEFAULTS = {"sift": "b", "polyphen": "b", "check_existing": "yes"}


def strongest(labels):
    """Strongest soft priority among labels (critical>recommended>optional), ignoring
    not_applicable/None. Returns the label str or None if none apply."""
    best, best_rank = None, 0
    for p in labels:
        r = PRIORITY_ORDER.get(p, 0)
        if r > best_rank:
            best, best_rank = p, r
    return best


def active_values(factor_tuple):
    """Normalise a factor tuple to {factor: [values]} (single-select -> 1-element list)."""
    out = {}
    for f, v in factor_tuple.items():
        if f.startswith("_"):
            continue
        out[f] = v if isinstance(v, list) else [v]
    return out


def factor_slug(factor_tuple):
    """Compact, deterministic label for a tuple (for ids / filenames)."""
    parts = [
        factor_tuple["species"],
        factor_tuple["origin"],
        factor_tuple["variant_size_class"],
        "+".join(factor_tuple["region_focus"]),
        "+".join(factor_tuple["analysis_goal"]),
    ]
    return "__".join(parts).replace("-", "").replace("_", "")


# Canonical non-human cue: the resolver runs the checker BEFORE the real query exists, so it
# feeds infer_species a minimal species cue. Any non-human species gates the same human-only
# block, so 'mouse' is a fair representative.
def species_cue_query(species):
    return "human variant analysis" if species == "human" else "mouse variant analysis"


def factor_value_for(oid, species):
    """The VALUE an enabled option takes (most are boolean True)."""
    if oid == "core_type":
        return "Ensembl/GENCODE" if species == "human" else "Ensembl"
    return VALUE_DEFAULTS.get(oid, True)


def intent_priorities(factor_tuple, catalogue, pbf, factors_cfg, enable=("critical", "recommended")):
    """Pre-checker intent: {oid: (enabled_bool, priority_or_None, gated_bool)} from factor priorities.

    `enable` is the set of priority labels that switch an option ON — default critical+recommended
    (taxonomy_proposal §5). Pass ('critical',) for a tighter, higher-precision config."""
    av = active_values(factor_tuple)
    priorities = pbf["priorities"]
    cond_rules = factors_cfg.get("conditional_rules", [])
    somatic_na = set()
    for f, spec in factors_cfg["factors"].items():
        for rule in spec.get("hard_rules", []):
            if factor_tuple.get(f) == rule["when_value"]:
                somatic_na.update(rule["not_applicable"])

    out = {}
    for opt in catalogue:
        oid = opt["id"]
        pf = priorities.get(oid, {})
        gated = False
        # (1) hard gates — a factor gates an option only if EVERY one of its ACTIVE values marks the
        # option not_applicable. For the single-select factors (species, variant_size_class) that is
        # identical to the previous "any active value" rule, since there is exactly one active value.
        # It matters for the multi-select `region_focus`: a coding+regulatory variant set HAS a coding
        # component, so a missense predictor still applies and must not be gated away just because a
        # regulatory component is also present. "any" would have dropped it; "all" keeps it.
        for hf in HARD_GATE_FACTORS:
            vals = av.get(hf, [])
            if vals and all(pf.get(hf, {}).get(v) == "not_applicable" for v in vals):
                gated = True
        if oid in somatic_na:
            gated = True
        if gated:
            out[oid] = (False, None, True)
            continue
        # (2) soft ranking over ALL active factor values
        labels = []
        for f, vals in av.items():
            for v in vals:
                labels.append(pf.get(f, {}).get(v))
        # (3) conditional rules — JOINT conditions the per-value table cannot express. The priority table
        # is keyed one factor value at a time and composes by max, so every value votes alone; there is no
        # slot for "non-human AND clinical together imply MaxEntScan". A rule fires only when EVERY 'when'
        # pair is active, and contributes its label to the same max — so it can only RAISE an option, never
        # lower one. It also cannot resurrect a hard-gated option: gating `continue`s above this.
        for rule in cond_rules:
            if all(wv in av.get(wf, []) for wf, wv in rule["when"].items()):
                lab = rule["then"].get(oid)
                if lab:
                    labels.append(lab)
        pr = strongest(labels)
        out[oid] = (pr in enable, pr, False)
    return out


# --- Query -> factors (the inference half; the resolver above is the config half) -------------------
# A checker/reader model classifies the five factors from the query text ALONE. Deliberately
# LLM-based, not keyword-based: keyword matching cannot handle the varied/implicit phrasing real
# questions use, and it returns "unstated" rather than guessing so an absent factor is visible
# instead of silently defaulted. Run it deterministically (temp 0, fixed seed, concurrency 1 —
# temp=0 is NOT deterministic under concurrency on the Metal/MoE stack).

FACTOR_CLASSIFIER_PROMPT = (
    "You read a researcher's natural-language question about annotating genetic variants and identify ONLY "
    "what the question actually states or clearly implies about the analysis. Do NOT guess; if the question "
    "does not indicate a characteristic, use \"unstated\" (or [] for a list).\n\n"
    "Reply with ONLY this JSON object, no prose:\n"
    "{\n"
    '  "species": "human" | "non-human" | "unstated",\n'
    '  "origin": "germline" | "somatic" | "unstated",\n'
    '  "variant_size_class": "small" | "structural-CNV" | "unstated",\n'
    '  "region_focus": array with any of ["coding","regulatory-noncoding"],\n'
    '  "analysis_goal": array with any of ["basic-consequence","clinical-interpretation","population-frequency"]\n'
    "}\n\n"
    "Guidance (judge by meaning, not keywords):\n"
    "- origin: germline = inherited / constitutional / rare-disease / healthy cohort; somatic = tumour / cancer.\n"
    "- variant_size_class: small = SNVs / indels / point changes; structural-CNV = large deletions / duplications / CNVs / SVs.\n"
    "- region_focus: coding = protein-coding / missense / exonic; regulatory-noncoding = enhancer / promoter / intronic / intergenic.\n"
    "- analysis_goal: basic-consequence = just a quick consequence call; clinical-interpretation = pathogenicity / "
    "disease significance; population-frequency = allele frequencies. Use basic-consequence only when no richer goal is indicated.\n\n"
    "Output raw JSON only — no markdown, no code fences, no explanation.\n\n"
    "Question:\n"
)


def parse_factor_classification(raw):
    """Parse the checker model's JSON into {factor: value|'unstated' | [values]}. Tolerant of surrounding
    prose / code fences. Returns None on a genuine parse failure so the caller can flag it as a CHECKER
    problem (not 5 phantom 'unknown' factors)."""
    out = {f: ([] if f in MULTI_FACTORS else "unstated") for f in FACTOR_VALUES}
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[s:e + 1])
        if not isinstance(obj, dict):
            return None
    except Exception:
        return None
    for f in FACTOR_VALUES:
        v = obj.get(f)
        if f in MULTI_FACTORS:
            out[f] = [x for x in v if x in FACTOR_VALUES[f]] if isinstance(v, list) else []
        else:
            out[f] = v if v in FACTOR_VALUES[f] else "unstated"
    return out


def infer_factors(client, model, user_query):
    """Classify a free-text query into a factor tuple, or None if the classifier fails.

    SPECIES is taken from infer_species(), not from the classifier: species is the hard safety gate
    and the deterministic keyword layer is fail-closed by design, so it stays the authority. An
    unconfirmed species reads as 'human' here, matching what the checker already does (keep the
    human-only options and warn) — the checker still runs its own species pass regardless.

    'unstated' is preserved for the other single-select factors rather than guessed: it contributes no
    priority and triggers no hard gate, so an unstated factor simply exerts no influence. The one
    default applied is analysis_goal -> basic-consequence when nothing richer is indicated, which is
    the agreed baseline goal.

    Deterministic (temperature 0, fixed seed) — but note temp=0 is NOT reproducible under concurrency
    on a Metal/MoE stack, so a reproducible run needs concurrency 1.

    Runs on VEP_FACTOR_MODEL if set, otherwise on the SAME model as the recommendation. Defaulting to
    a second, smaller model would be faster — this is a ~60-token fixed-schema classification, so the
    big model buys nothing — but it would silently require a second download: a user who pulled only
    the quickstart model would get a failed classification, no factors, and no indication why. One
    pulled model has to be enough. Set VEP_FACTOR_MODEL=gemma4:e4b (or 12b) to get the speed back."""
    model = os.environ.get("VEP_FACTOR_MODEL") or model
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": FACTOR_CLASSIFIER_PROMPT + (user_query or "")},
                {"role": "user", "content": "Return the JSON classification."},
            ],
            temperature=0.0,
            seed=42,
        )
        raw = resp.choices[0].message.content or ""
    except Exception:
        return None

    rec = parse_factor_classification(raw)
    if rec is None:
        return None

    rec["species"] = "non-human" if infer_species(user_query) not in ("human", "unknown") else "human"
    if not rec.get("analysis_goal"):
        rec["analysis_goal"] = ["basic-consequence"]
    return rec


def describe_factors(factor_tuple):
    """One-line-per-factor rendering of a tuple, for the prompt and the user-facing trace."""
    if not factor_tuple:
        return ""
    out = []
    for f in FACTOR_VALUES:
        v = factor_tuple.get(f)
        shown = ", ".join(v) if isinstance(v, list) else v
        out.append(f"- {f}: {shown or 'unstated'}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Fuzzy option extraction from free-text LLM output
# ---------------------------------------------------------------------------

# Flag keywords that name the MECHANISM, not the option: every plugin's cli_flag starts `--plugin`, every
# custom dataset's `--custom`. They identify nothing on their own and must never become aliases.
_FLAG_KEYWORDS = {"plugin", "custom"}


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


def audit_source_citations(text, option_aliases):
    """Deterministically audit the `[source: id]` ids the model cited, BEFORE we present an answer.

    The parser is deliberately forgiving: an id it cannot resolve is skipped (extract_recommendations_
    detailed), and a near-miss is fuzzy-resolved by _match_option. Both are silent, and silence is the
    problem — a model citing a source that does not exist is exactly the signal a provenance-traced tool
    exists to surface. This does not change any decision; it reports what the parser did, so the caller
    can show it.

    Returns {"exact": [id], "coerced": [(cited, resolved)], "unknown": [cited], "n_tagged": int}
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
            "n_tagged": len(exact) + len(coerced) + len(unknown)}


def format_citation_audit(audit, kb_size):
    """Render the citation audit for the user. Empty string when the model cited cleanly."""
    if not audit["coerced"] and not audit["unknown"] and audit["n_tagged"]:
        return ""
    out = []
    if not audit["n_tagged"]:
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


# ---------------------------------------------------------------------------
# Scope gate — did the model decline to produce a configuration at all?
# ---------------------------------------------------------------------------
# When the user asks something that is not a VEP-configuration request, the model correctly declines.
# Everything downstream, though, assumes a configuration WAS proposed: the citation audit reports "no
# [source:] tags", the prose fallback keyword-scrapes option names out of the refusal text, and the
# checker then "corrects" that phantom config and warns about an unspecified species. All three warnings
# are true statements about a configuration that does not exist, and they bury the one thing the user
# needs to read — that the question was out of scope.
#
# So: detect the decline and skip the whole config pipeline. Primary signal is an explicit marker the
# prompt asks for (deterministic, no guessing). The secondary net catches models that decline without
# it, and is deliberately CONSERVATIVE — it fires only when the model produced neither citations nor
# ✓/✗ markers AND the prose reads as a scope refusal. Anything else keeps the existing format warning,
# because silently dropping that warning would hide a real failure (a weak model that rambled).

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
    """True when the model declined to configure VEP, so there is NO configuration to audit or check.

    Order: (1) the explicit marker the prompt asks for; (2) a conservative fallback — no citations AND
    no ✓/✗ markers AND refusal phrasing. Returns False whenever the model made any attempt at the
    output contract, so a genuine format failure still raises its warning."""
    if not text:
        return False
    if text.lstrip().upper().startswith(OUT_OF_SCOPE_PREFIX):
        return True
    if audit and audit.get("n_tagged"):
        return False                                   # it cited the KB -> it attempted a config
    if re.search(r"(?m)^\s*[✓✗]", text):
        return False                                   # it used the recommendation markers
    return bool(_REFUSAL_RE.search(text))


def extract_recommendations_detailed(text, option_aliases):
    """Parse LLM output into ORDERED per-option records, the structured-output source of truth.

    Same three-tier strategy and EXACT same enable/disable decisions as
    extract_recommendations (which is now derived from this), but additionally captures the
    per-option fields the prompted format carries — confidence, the model's priority tag, the
    `Reason:` line, and any value — so the deterministic JSON assembler (build_recommendation_json)
    can emit schema-valid output WITHOUT the model ever producing JSON (Exp 8 showed it can't).

    Returns a list of dicts: {option_id, action ('enable'|'disable'), confidence, priority,
    reason, value}. confidence/priority/reason/value are None outside Phase 0 (the bare-run
    fallbacks carry only an action). De-duplicated by (option_id, action), first occurrence wins,
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

    def _add(oid, action, confidence=None, priority=None, reason=None, value=None):
        key = (oid, action)
        if key in seen:
            return
        seen.add(key)
        records.append({"option_id": oid, "action": action, "confidence": confidence,
                        "priority": priority, "reason": reason, "value": value})

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
        _add(oid, action, confidence, priority, reason)
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


# ---------------------------------------------------------------------------
# Post-hoc constraint checker (runs AFTER LLM output, BEFORE display)
# ---------------------------------------------------------------------------

# Priority ranking for conflict resolution (higher number = higher priority)
_PRIORITY_RANK = {
    "critical": 4,
    "recommended": 3,
    "optional": 2,
    "not_applicable": 1,
}

# Restrictiveness ranking: when priorities are equal, disable the MORE restrictive
# option first (most_severe is most restrictive because it suppresses annotations)
_RESTRICTIVENESS = {
    "most_severe": 3,
    "pick": 2,
    "per_gene": 1,
}

# Keyword → species mapping for species inference
_SPECIES_KEYWORDS = {
    "mouse": "mouse",
    "mice": "mouse",           # plural — word-boundary matching means "mice" != "mouse"
    "murine": "mouse",         # common adjective ("murine model")
    "mus musculus": "mouse",
    "grcm": "mouse",
    "grcm38": "mouse",
    "grcm39": "mouse",
    "zebrafish": "zebrafish",
    "danio": "zebrafish",
    "danio rerio": "zebrafish",
    "drosophila": "drosophila",
    "fruit fly": "drosophila",
    "d. melanogaster": "drosophila",
    "c. elegans": "c_elegans",
    "caenorhabditis": "c_elegans",
    "rat": "rat",
    "rats": "rat",
    "rattus": "rat",
    "chicken": "chicken",
    "chickens": "chicken",
    "gallus": "chicken",
    "pig": "pig",
    "pigs": "pig",
    "porcine": "pig",
    "sus scrofa": "pig",
    "dog": "dog",
    "dogs": "dog",
    "canine": "dog",
    "canis": "dog",
    "non-human": "non_human",
    "non human": "non_human",
    "arabidopsis": "arabidopsis",
    "rice": "rice",
    "oryza": "rice",
    # extra common organisms (reduces the fail-open surface — still enumeration-limited)
    "cow": "cow", "cows": "cow", "cattle": "cow", "bovine": "cow", "bos taurus": "cow",
    "sheep": "sheep", "ovine": "sheep", "ovis": "sheep",
    "horse": "horse", "horses": "horse", "equine": "horse", "equus": "horse",
    "yeast": "yeast", "saccharomyces": "yeast",
    "rabbit": "rabbit", "rabbits": "rabbit",
}

# Positive HUMAN signals — so 'human' is EARNED, not a silent default (fail-closed design). With no
# non-human keyword AND no human signal, infer_species returns 'unknown' and the checker withholds
# human-only options. Non-human organisms are matched FIRST, so 'mouse tumour' -> 'mouse', not 'human'.
_HUMAN_SIGNALS = [
    "human", "homo sapiens", "h. sapiens", "patient", "clinical", "clinician",
    "proband", "mendelian", "rare disease", "rare-disease", "diagnos",
    "germline", "somatic", "tumour", "tumor", "cancer", "oncolog", "carcinoma",
    "gnomad", "clinvar", "cosmic", "acmg", "omim", "hgmd",
    "grch37", "grch38", "hg19", "hg38",
]


def infer_species(user_query: str) -> str:
    """Detect species from the user query → a non-human species name, 'human', or 'unknown'.

    FAIL-CLOSED design (this is a safety layer): 'human' is returned only when POSITIVELY indicated, not
    as a silent default. Order: (1) an explicit non-human organism (_SPECIES_KEYWORDS) wins — so
    'mouse tumour' -> 'mouse'; (2) else a positive human signal (_HUMAN_SIGNALS) -> 'human'; (3) else
    'unknown' — the species check then FLAGS the unconfirmed species and keeps human-only options
    (stripping on 'unknown' would wrongly break the many human queries that never say "human"; see
    check_and_fix_violations). Word boundaries avoid false positives ('rat' in 'generated').

    RESIDUAL LIMITATIONS (keyword matching, not language understanding — the proper fix is structured
    output, where species/assembly are explicit model-filled fields): still NEGATION-BLIND ('not a mouse
    study' -> 'mouse'); still SINGLE-GUESS / first-match-by-dict-order, can't represent 'both'; and an
    UNLISTED non-human organism described with a human-context word (e.g. 'feline cancer') can still
    resolve to 'human' via _HUMAN_SIGNALS — narrower than the old blanket default, but not eliminated.
    """
    q = user_query.lower()
    for keyword, species in _SPECIES_KEYWORDS.items():      # (1) explicit non-human organism wins
        if re.search(r"\b" + re.escape(keyword) + r"\b", q):
            return species
    for sig in _HUMAN_SIGNALS:                              # (2) positive human signal
        if sig in q:
            return "human"
    return "unknown"                                        # (3) fail closed: caller withholds human-only


def _get_priority_rank(option_id: str, use_case: str, vep_options: list) -> int:
    """Look up the numeric priority rank for an option in a given use case."""
    for opt in vep_options:
        if opt["id"] == option_id:
            priority = opt.get("priority_by_use_case", {}).get(use_case, "not_applicable")
            return _PRIORITY_RANK.get(priority, 0)
    return 0


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


# Non-human species names that can appear in a multi-species restriction ('human + mouse only').
_OTHER_SPECIES = {"mouse", "rat", "pig", "dog", "zebrafish", "chicken", "cow", "sheep",
                  "horse", "yeast", "rabbit", "drosophila", "arabidopsis", "rice"}


def _is_human_only(restriction: str) -> bool:
    """True if a species_restriction string denotes a HUMAN-ONLY option (vs all-species or multi-species).

    Reads an OPTION's `species_restriction` metadata — NOT the user query (that's infer_species).
    Human-only iff it mentions 'human', is not an 'all species' restriction, and names NO other species.
    This keys on actual SPECIES NAMES, which correctly handles the real catalogue vocabulary:
      'human only', 'human only (GRCh37+GRCh38)', 'human only (GRCh37 and GRCh38)'  -> True
          (the '+' / 'and' there are ASSEMBLIES, not species)
      'human + mouse only', 'human + pig only'                                       -> False (multi-species)
      'all species', 'species with SIFT data'                                        -> False
    Fixes the earlier literal-'human and' test, which wrongly flagged 'human + mouse only' as human-only
    and stripped e.g. `ccds` for a mouse query (caught by the demo-path smoke).
    """
    r = (restriction or "all species").lower()
    if "human" not in r or "all" in r:
        return False
    return not any(re.search(r"\b" + re.escape(s) + r"\b", r) for s in _OTHER_SPECIES)


# Every recognised spelling of a HUMAN build -> its canonical name. Keys are lower-cased and
# separator-stripped, so GRCh38 / grch38 / GRCH38 / "GRCh 38" / GRCh-38 / hg38 all resolve to GRCh38.
# NOTE deliberately NOT fuzzy/typo-tolerant: GRCh37 and GRCh38 differ by a single character, so an
# edit-distance match could not tell a typo of one from a correct spelling of the other — and a wrong
# build call drops the OTHER build's options (the opposite of a missed gate). Exact spellings only.
_ASSEMBLY_ALIASES = {
    "grch37": "GRCh37", "hg19": "GRCh37",
    "grch38": "GRCh38", "hg38": "GRCh38",
}


def infer_assembly(query):
    """The human assembly the query names ('GRCh37'/'GRCh38'), or None if it doesn't say.

    Fail-open by design, mirroring infer_species: most queries never name an assembly, so assuming one
    would strip options from the majority to protect a minority. Case- and separator-insensitive.
    """
    m = _ASSEMBLY_RE.search(query or "")
    if not m:
        return None
    token = re.sub(r"[\s_-]", "", m.group(1).lower())   # 'GRCh 38' / 'GRCh-38' -> 'grch38'
    return _ASSEMBLY_ALIASES.get(token)                 # non-human builds (GRCm39...) -> None


def _assembly_restriction(restriction):
    """Human assemblies an option's data exists for, or None if it isn't assembly-restricted.

      'human only (GRCh38)'         -> {'GRCh38'}
      'human only (GRCh37+GRCh38)'  -> {'GRCh37','GRCh38'}   (unrestricted in practice)
      'human only' / 'all species'  -> None
    """
    return set(re.findall(r"GRCh3[78]", restriction or "")) or None


def check_and_fix_violations(enabled: set, disabled: set, vep_options: list,
                             training_examples: list,
                             user_query: str,
                             retrieval_mode: str = "keyword") -> list[dict]:
    """Check enabled options for constraint violations and auto-correct them.

    Loads conflict rules, species restrictions and dependencies from
    vep_options.json. For conflicts, disables the option with lower priority for
    the detected use case (more restrictive option loses on ties). For
    dependencies, auto-enables a required option, unless that option is itself a
    species violation, in which case the dependent option is disabled instead.

    Returns a list of violation dicts with keys:
        type: 'conflict', 'species' or 'dependency'
        option_disabled / option_enabled: the option that was changed
        option_kept: (conflicts only) the option that was kept
        reason: human-readable explanation

    SIDE EFFECT: mutates the passed-in `enabled` / `disabled` sets in place (discard/add) — that IS how
    the corrected set reaches the caller, but it's an undocumented mutation a future caller might not expect.
    """
    violations = []
    # Order matters: species first (may remove options before they can conflict),
    # then conflicts, then dependencies (auto-enable may re-introduce options).
    species = infer_species(user_query)
    use_case = _detect_use_case(enabled, vep_options, training_examples,
                                user_query, retrieval_mode=retrieval_mode)

    # Build lookup maps (single pass over the catalogue; mutated sets stay small)
    conflicts_map = {}
    species_map = {}
    depends_map = {}
    for opt in vep_options:                      # (description_map removed — it was built but never used)
        conflicts_map[opt["id"]] = set(opt.get("conflicts_with", []))
        species_map[opt["id"]] = opt.get("species_restriction", "all species")
        depends_map[opt["id"]] = list(opt.get("depends_on", []))

    # --- Species violations ---
    # Human-only annotation sources (CADD/PolyPhen/ClinVar/gnomAD...) are meaningless for a non-human
    # query, so move them enabled -> disabled. This is the "harm=0" guarantee: the checker, not the LLM.
    # POSTURE (evidence-tuned): strip human-only options only for a POSITIVELY-identified non-human
    # species. For 'unknown' we FLAG rather than strip — a hard fail-closed (stripping on unknown) would
    # wrongly withhold gnomAD/ClinVar/regulatory from the many human queries that never say "human"
    # (GWAS / cohort / WGS / CNV ... — 8/20 gold queries classify 'unknown'), which is worse than the
    # original silent fail-open. So: confirmed non-human -> repair; unspecified -> surface the assumption.
    # (Full fix = structured output: an explicit species/assembly field the user fills.)
    if species == "unknown":
        violations.append({
            "type": "species",
            "reason": ("species not specified in the query — ASSUMING HUMAN and keeping human-only options "
                       "(CADD/gnomAD/ClinVar...). If this is a non-human sample, disable them."),
        })
    elif species != "human":          # positively-identified non-human -> withhold human-only options
        for oid in list(enabled):
            if _is_human_only(species_map.get(oid, "all species")):
                violations.append({
                    "type": "species",
                    "option_disabled": oid,
                    "reason": f"'{oid}' is restricted to {species_map[oid]} but your query specifies {species}",
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Assembly violations ---
    # Some human sources exist for only ONE build: MANE and EVE are GRCh38-only, Geno2MP is GRCh37-only.
    # The web form does NOT protect the user here — it shows those checkboxes for any human assembly
    # (e.g. InputForm.pm:694-702 gates `mane` on species alone) — so a GRCh37 query can tick MANE and get
    # an empty column. The restriction was documented only in when_not_to_use prose ("MANE is human GRCh38
    # only"), which no code reads; it now lives in species_restriction where this can enforce it.
    # Same fail-open posture as species: gate ONLY when the query actually names a build. Runs after the
    # species pass, so non-human rows have already lost these options anyway.
    assembly = infer_assembly(user_query)
    if assembly:
        for oid in list(enabled):
            allowed = _assembly_restriction(species_map.get(oid, "all species"))
            if allowed and assembly not in allowed:
                violations.append({
                    "type": "assembly",
                    "option_disabled": oid,
                    "reason": (f"'{oid}' has data for {'/'.join(sorted(allowed))} only, but your query "
                               f"specifies {assembly}"),
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Conflict violations ---
    # Pairwise scan of enabled options; checked_pairs dedupes the (a,b)/(b,a) symmetry.
    checked_pairs = set()
    for oid_a in list(enabled):
        if oid_a not in enabled:          # FIX: may have been disabled by an earlier pair this pass
            continue
        for oid_b in list(enabled):
            if oid_a not in enabled:          # FIX: oid_a may have lost an EARLIER pair in THIS inner
                break                         # loop — stop, or we'd judge oid_b against a dead oid_a and
                                              # wrongly disable a valid oid_b on a conflict that's moot
            if oid_b not in enabled or oid_a == oid_b:   # FIX: skip already-disabled options / self
                continue
            pair = tuple(sorted([oid_a, oid_b]))
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)

            if oid_b in conflicts_map.get(oid_a, set()) or oid_a in conflicts_map.get(oid_b, set()):
                # Decide which to disable: lower priority loses
                rank_a = _get_priority_rank(oid_a, use_case, vep_options)
                rank_b = _get_priority_rank(oid_b, use_case, vep_options)

                # Tie-break ladder: (1) use-case priority — the option that matters
                # more for this use case wins; (2) restrictiveness — drop the option
                # that suppresses more output (most_severe > pick > per_gene); (3)
                # alphabetical, purely so the result is deterministic.
                if rank_a != rank_b:
                    loser = oid_a if rank_a < rank_b else oid_b
                    winner = oid_b if loser == oid_a else oid_a
                else:
                    # Equal priority: disable the more restrictive option
                    rest_a = _RESTRICTIVENESS.get(oid_a, 0)
                    rest_b = _RESTRICTIVENESS.get(oid_b, 0)
                    if rest_a != rest_b:
                        loser = oid_a if rest_a > rest_b else oid_b
                        winner = oid_b if loser == oid_a else oid_a
                    else:
                        # Fallback: disable the first alphabetically
                        loser, winner = sorted([oid_a, oid_b])

                # Find the conflict reason from whichever side declared it
                if loser in conflicts_map.get(winner, set()):
                    decl = winner
                else:
                    decl = loser
                conflict_note = (
                    f"--{decl} conflicts with --{loser}" if decl != loser
                    else f"--{loser} conflicts with --{winner}"
                )

                violations.append({
                    "type": "conflict",
                    "option_disabled": loser,
                    "option_kept": winner,
                    "reason": (
                        f"'{loser}' and '{winner}' cannot both be enabled "
                        f"({conflict_note}). Disabled: {loser}"
                    ),
                })
                enabled.discard(loser)
                disabled.add(loser)

    # --- Dependency violations ---
    # If an enabled option requires another option, ensure the dependency is on.
    # Auto-enable the dependency, unless enabling it would itself break a species
    # restriction (e.g. a human-only dependency for a mouse query), in which case
    # the dependent option cannot be satisfied and is disabled instead. The loop
    # re-scans so transitive dependencies (A->B->C) are fully resolved.
    # CAVEAT (ordering gap): this runs AFTER conflict resolution, and a newly auto-enabled dependency is
    # NOT re-checked for conflicts -- so the checker can itself introduce an unresolved conflict that
    # ships unflagged. A fix re-runs the conflict pass after dependencies (or interleaves the two).
    changed = True
    while changed:
        changed = False
        for oid in list(enabled):
            for dep in depends_map.get(oid, []):
                if dep in enabled:
                    continue
                if species not in ("human", "unknown") and _is_human_only(species_map.get(dep, "all species")):
                    violations.append({
                        "type": "dependency",
                        "option_disabled": oid,
                        "reason": (
                            f"'{oid}' requires '{dep}', which is restricted to "
                            f"{species_map.get(dep)} but your query specifies {species}. "
                            f"Disabled: {oid}"
                        ),
                    })
                    enabled.discard(oid)
                    disabled.add(oid)
                else:
                    violations.append({
                        "type": "dependency",
                        "option_enabled": dep,
                        "reason": f"'{oid}' requires '{dep}'; auto-enabled '{dep}'",
                    })
                    enabled.add(dep)
                    disabled.discard(dep)
                changed = True
                break          # restart the scan: the set just changed under us
            if changed:
                break

    return violations


def format_violation_warnings(violations: list[dict]) -> str:
    """Format constraint violations into a clearly readable warning block.

    Returns an empty string if there are no violations.
    """
    if not violations:
        return ""

    lines = [
        "",
        "⚠️  CONSTRAINT VIOLATIONS DETECTED AND CORRECTED:",
    ]
    for v in violations:
        tag = v["type"].upper()
        lines.append(f"  - {tag}: {v['reason']}")
    lines.append("")
    return "\n".join(lines)


# An option whose cli_flag lists SEVERAL flags ("--refseq | --merged | --gencode_basic") is a menu, not a
# flag: the user must pick one. Detected by >1 "--" separated by | or /, so a single flag carrying a path
# ("--plugin MaxEntScan,/path/to/x") or a value placeholder ("--sift [b|p|s]") is NOT mistaken for a menu.
_FLAG_ALT_SPLIT = re.compile(r"\s*[|/]\s*")


def cli_flags_for(enabled, vep_options):
    """Runnable, de-duplicated CLI flags for an enabled set → (flags, choices).

    `choices` are (option_id, [alternatives]) for menu-style cli_flags, which must be offered rather than
    pasted into a command. Both command builders share this, because they had drifted into two different
    broken rules:
      * format_corrected_config joined every raw cli_flag with no filtering at all, so the printed command
        contained "--check_existing --check_existing" (both `clinvar` and `check_existing` carry that flag)
        and the literal menu "--gencode_basic / --refseq / --merged".
      * build_recommendation_json filtered on `"|" not in f`, which on the expanded catalogue silently
        DROPPED --sift/--polyphen from the command, because their flag is "--sift [b|p|s]" — a value
        placeholder, not a menu.
    """
    flag_by_id = {o["id"]: (o.get("cli_flag") or "") for o in vep_options}
    flags, choices, seen = [], [], set()
    for oid in sorted(enabled):
        f = flag_by_id.get(oid, "").strip()
        if not f.startswith("--"):
            continue
        # A flag with SUB-PARAMETERS, "--check_frequency (+ --freq_pop/--freq_freq/...)": the parenthetical
        # lists parameters used ALONGSIDE the main flag, not alternatives to it. Emit only the leading
        # flag (the sub-params need user-supplied values anyway); do NOT present them as a pick-one menu.
        # Detected by the "(+" additional-params marker, checked before the menu rule below.
        head = f.split("(+", 1)[0].strip() if "(+" in f else f
        alts = re.findall(r"--[A-Za-z0-9_]+", head)
        # A MENU of several flags -> the user must pick one. Checked BEFORE the derived/no-flag skip
        # below, because core_type's flag is "--refseq | --merged | --gencode_basic | --gencode_primary
        # (no flag for core)": it contains "no flag" (describing its DEFAULT) while still being a real
        # choice, so skipping on that substring first dropped the transcript database from the command
        # entirely — silently, which is the same class of bug as the rest of this function.
        if len(alts) > 1 and _FLAG_ALT_SPLIT.search(head):
            choices.append((oid, alts))
            continue
        f = head   # drop any "(+ ...)" sub-parameter annotation from the emitted flag
        # Not a standalone flag: derived options ride on another option's flag (clinvar -> check_existing).
        if "derived" in f or "no flag" in f:
            continue
        # VALUE PLACEHOLDER, not a runnable value: sift/polyphen carry "--sift [b|p|s]", meaning "pick one
        # of b|p|s". Pasting "[b|p|s]" verbatim makes the command un-runnable (a model's
        # config can produce `--sift [b|p|s]`). Substitute the option's documented default from
        # _SET_VALUE_DEFAULTS; if we have no default, drop the bracket group rather than emit garbage.
        if re.search(r"\[[^\]]*\|[^\]]*\]", f):
            default = _SET_VALUE_DEFAULTS.get(oid)
            f = re.sub(r"\s*\[[^\]]*\]", f" {default}" if default else "", f).strip()
        # DESCRIPTIVE PARENTHETICAL, not runnable syntax: gnomad_sv's flag is
        # "--custom (gnomAD_SV VCF, type=exact, overlap_cutoff 80/90/100/exact)" — the parenthetical
        # describes what data file to supply, it is not command syntax. Pasting it verbatim is unrunnable;
        # emit just the flag (the user fills the file per the "fill in values/paths" note on the command).
        if "(" in f:
            f = f.split("(", 1)[0].strip()
        if f not in seen:            # de-dup: two options can legitimately share one flag
            seen.add(f)
            flags.append(f)
    return flags, choices


_PRIORITY_MISMATCH_WARNED = False


def priority_table_covers(vep_options, table):
    """Ids in this catalogue that the priority table prices for no factor at all.

    The table is generated FROM a catalogue, so a catalogue it wasn't generated from can share most
    ids and still be wrong. The 26-option demo KB against the 58-option table is exactly that: 21 ids
    match, but `transcript_set`, `mane_select`, `gnomad_af`, `gene_phenotype` and `clinvar_sv` are
    absent, and the first of those is the "always choose a transcript database" baseline that is
    critical in every scenario. Resolving anyway produced a plausible-looking ESSENTIAL list with the
    single most important option quietly missing — worse than showing no tiers at all. So this is an
    exact-subset check, not a fuzzy one."""
    return {o["id"] for o in vep_options} - set(table.get("priorities", {}))


def resolve_for_query(factor_tuple, vep_options):
    """`intent_priorities()` for a factor tuple, or None if the tuple or the config is unusable.

    One place for the try/except so the prompt builder and the output formatter can never disagree
    about what this scenario's priorities are."""
    global _PRIORITY_MISMATCH_WARNED
    if not factor_tuple:
        return None
    try:
        table = load_priority_by_factor()
        missing = priority_table_covers(vep_options, table)
        if missing:
            if not _PRIORITY_MISMATCH_WARNED:
                _PRIORITY_MISMATCH_WARNED = True
                print(f"\n  Note: the priority table does not cover {len(missing)} option(s) in this "
                      f"catalogue ({', '.join(sorted(missing)[:4])}"
                      f"{', …' if len(missing) > 4 else ''}), so importance tiers are switched off for "
                      f"this run.\n  They are generated together — point VEP_OPTIONS_FILE and "
                      f"VEP_PRIORITY_FACTOR_FILE at a matching pair to turn them back on.\n")
            return None
        return intent_priorities(factor_tuple, vep_options, table, load_factors())
    except Exception:
        return None                              # config missing/unreadable -> caller falls back


def tier_by_importance(enabled, resolved):
    """Split the corrected option set by the priority the FACTOR table gives it for THIS scenario.

    This is the essential-vs-optional view. It is a different axis from :func:`tier_options`, which
    splits on native-flag vs plugin (i.e. does it need downloaded data files) — an infrastructure
    question, not a clinical one. An option can be a plugin AND essential (AlphaMissense), or native
    AND an add-on (`--uniprot`).

    Returns five lists:
      essential / recommended / addons_on — ENABLED options, grouped by tier.
      unpriced        — enabled, but the table prices them for no factor here (output/compute controls).
      addons_offered  — rated `optional` for this scenario and NOT enabled: the "offered, off by
                        default" set. Hard-gated options are never offered.

    DISPLAY ONLY: it regroups the corrected set, it never changes which options are enabled, so the
    checker and every scored metric are untouched."""
    out = {"essential": [], "recommended": [], "addons_on": [], "unpriced": [], "addons_offered": []}
    for oid in sorted(enabled):
        _, priority, _ = resolved.get(oid, (False, None, False))
        if priority == "critical":
            out["essential"].append(oid)
        elif priority == "recommended":
            out["recommended"].append(oid)
        elif priority == "optional":
            out["addons_on"].append(oid)
        else:
            out["unpriced"].append(oid)
    for oid, (_, priority, gated) in sorted(resolved.items()):
        if priority == "optional" and not gated and oid not in enabled:
            out["addons_offered"].append(oid)
    return out


CONFIG_LEVELS = ("minimal", "standard", "full")


def apply_config_level(enabled, disabled, resolved, level, vep_options, training_examples,
                       user_query, retrieval_mode="keyword"):
    """Narrow or widen the corrected set to the depth the user asked for. Mutates `enabled`.

      minimal  — keep only what the factor table calls `critical` here. For someone who wants the
                 smallest runnable configuration and will add to it themselves.
      standard — leave it as recommended (the default).
      full     — additionally switch on every add-on the table rates `optional` and does not gate,
                 for someone who wants everything the scenario can justify.

    Re-running the checker afterwards is what makes either edit safe: narrowing can strip an option
    that a surviving one depends on (ClinVar needs check_existing), and the dependency pass puts it
    back; widening can introduce a conflict, and the conflict pass resolves it. So the result is a
    runnable configuration at every level, not just a filtered list.

    Returns the set of ids removed by narrowing (empty otherwise), for reporting."""
    if level == "minimal":
        keep = {oid for oid in enabled if resolved.get(oid, (False, None, False))[1] == "critical"}
        removed = set(enabled) - keep
        enabled.clear()
        enabled.update(keep)
    elif level == "full":
        removed = set()
        enabled.update(oid for oid, (_, priority, gated) in resolved.items()
                       if priority == "optional" and not gated)
    else:
        return set()
    check_and_fix_violations(enabled, disabled, vep_options, training_examples, user_query,
                             retrieval_mode=retrieval_mode)
    return removed - set(enabled)          # a dep the re-check restored was not really removed


def format_corrected_config(enabled, disabled, vep_options, violations, resolved=None):
    """Render the authoritative post-checker configuration — the 'dispose' step, not just a warning.

    check_and_fix_violations has already REPAIRED the option set in place (removed species/conflict
    violations, auto-enabled dependencies); `enabled` here is that corrected set. We don't rewrite the
    model's streamed draft prose above (editing free text / the generated command in place is fragile —
    that's the structured-output job), so this block is the conflict-free, species-correct configuration
    the user should actually apply, and it SUPERSEDES the draft wherever they differ.
    """
    flag_by_id = {o["id"]: o.get("cli_flag", "") for o in vep_options}
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    on = sorted(enabled)
    lines = ["", "=" * 60,
             "  CORRECTED CONFIGURATION (after constraint check — authoritative)"]
    if violations:
        lines.append("  (the checker changed the draft above; apply THIS set)")
    lines.append("=" * 60)
    if resolved:
        # Essential-vs-optional view: group the SAME corrected set by this scenario's priorities.
        tiers = tier_by_importance(enabled, resolved)
        for key, title, mark in (
            ("essential",   "ESSENTIAL — must-have for this scenario", "✓"),
            ("recommended", "RECOMMENDED — standard defaults for this scenario", "✓"),
            ("addons_on",   "ADD-ONS (enabled) — optional extras this run turned on", "+"),
            ("unpriced",    "OTHER (enabled) — the factor table ranks these for no factor here", "✓"),
        ):
            if not tiers[key]:
                continue
            lines.append(f"{title}  [{len(tiers[key])}]")
            lines.extend(f"  {mark} {name_by_id.get(oid, oid)} [{oid}] {flag_by_id.get(oid, '')}".rstrip()
                         for oid in tiers[key])
        if not on:
            lines.append("ENABLE: (none)")
        if tiers["addons_offered"]:
            lines.append("")
            lines.append("AVAILABLE ADD-ONS — NOT enabled; turn on if they help  "
                         f"[{len(tiers['addons_offered'])}]")
            lines.extend(f"  · {name_by_id.get(oid, oid)} [{oid}] {flag_by_id.get(oid, '')}".rstrip()
                         for oid in tiers["addons_offered"])
        lines.append("")
        lines.append("  Tiers come from the PROVISIONAL factor priority table — VEP itself ranks nothing.")
    else:
        lines.append("ENABLE:")
        for oid in on:
            lines.append(f"  ✓ {name_by_id.get(oid, oid)} [{oid}] {flag_by_id.get(oid, '')}".rstrip())
        if not on:
            lines.append("  (none)")
    flag_list, choices = cli_flags_for(on, vep_options)
    lines.append("")
    lines.append("Corrected VEP command (use THIS, not the draft command above — fill in values/paths):")
    lines.append(f"  vep --input_file <in.vcf> --output_file <out.txt> --cache "
                 f"{' '.join(flag_list)}".rstrip())
    for oid, alts in choices:
        lines.append(f"  # {name_by_id.get(oid, oid)} [{oid}] — choose ONE: {' | '.join(alts)}")
    lines.append("=" * 60)
    return "\n".join(lines)


# --- Structured-output assembler (deterministic ✓/✗ → schema-valid JSON) ---------------------
# Exp 8 showed the local model cannot reliably emit JSON, but it reliably emits the
# `✓/✗ [source: id]` format. So OUR code assembles the schema-valid JSON from the parsed records +
# the checker's corrected set + KB factual fields — valid by construction, the LLM never emits JSON.
# Target contract: work/output_schema/vep_recommendation.schema.json (+ SCHEMA_DESIGN.md mapping table).

# The 'Restrict results' dropdown: these catalogue ids are mutually-exclusive VALUES of one control
# whose HTML name is `summary` (InputForm.pm). web_form_field='summary', value=<the id>.
_RESTRICT_RESULTS_IDS = {"pick", "pick_allele", "per_gene", "summary", "most_severe"}

# Native non-checkbox controls (dropdown / radiolist / string): action='set_value' with this default
# value (the InputForm.pm web default) unless the model specified one. `core_type` handled separately.
_SET_VALUE_DEFAULTS = {
    "sift": "b", "polyphen": "b", "check_existing": "yes", "shift_3prime": "shift_3prime",
    "distance": "1000", "buffer_size": "5000", "frequency": "common",
}

# Species-scoped controls whose HTML name is suffixed with the resolved species at runtime.
_SPECIES_SCOPED_IDS = {"regulatory", "cell_type"}

# infer_species() word -> InputForm species form-name suffix (for `regulatory_<Species>` etc.).
_SPECIES_FORM_NAME = {
    "human": "Homo_sapiens", "mouse": "Mus_musculus", "rat": "Rattus_norvegicus",
    "zebrafish": "Danio_rerio", "pig": "Sus_scrofa", "dog": "Canis_lupus_familiaris",
    "chicken": "Gallus_gallus", "cow": "Bos_taurus",
}

_ASSEMBLY_RE = re.compile(r"\b(GRCh[\s_-]?3[78]|hg38|hg19|GRCm39|GRCm38|GRCz11|Rnor_6\.0|mRatBN7\.2)\b",
                          re.IGNORECASE)


def _web_form_target(option: dict, species_form: str, model_value=None):
    """Map a catalogue option to its (web_form_field, action, value) for click-to-apply.

    Implements the SCHEMA_DESIGN.md field-name table deterministically from the option's id +
    source_type + cli_flag. `species_form` is the resolved InputForm species suffix (e.g.
    'Homo_sapiens'); `model_value` is an optional value the model emitted (rarely present).
    """
    oid = option["id"]
    src = option.get("source_type", "native")
    flag = option.get("cli_flag", "") or ""

    if oid in _RESTRICT_RESULTS_IDS:                       # one dropdown, name='summary'
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


def _first_sentence(text: str, limit: int = 240) -> str:
    """First sentence (or a bounded prefix) of a description — a non-empty reason fallback."""
    text = (text or "").strip()
    if not text:
        return ""
    head = text.split(". ")[0].strip()
    return (head if head.endswith(".") else head + ".")[:limit]


def build_recommendation_json(query, response_text, vep_options, training_examples,
                              option_aliases=None, retrieval_mode="keyword",
                              model=None, kb_version=None, run_checker=True):
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
    use_case = _detect_use_case(enabled, vep_options, training_examples, query, retrieval_mode)

    violations = []
    if run_checker:
        # Mutates enabled/disabled in place into the corrected, authoritative set.
        violations = check_and_fix_violations(enabled, disabled, vep_options, training_examples,
                                              query, retrieval_mode=retrieval_mode)

    species_out = "human" if species == "unknown" else species
    species_form = _SPECIES_FORM_NAME.get(species_out, species_out.replace(" ", "_").title())

    def _rec(oid, action_kind):
        opt = by_id[oid]
        field, action, value = _web_form_target(opt, species_form, value_by_id.get(oid))
        if action_kind == "disable":                      # ensure-OFF entry
            action, value = "disable", None
        priority = opt.get("priority_by_use_case", {}).get(use_case, "not_applicable")
        reason = reason_by_id.get(oid) or _first_sentence(opt.get("description", "")) or opt.get("name", oid)
        return {
            "option_id": oid,
            "web_form_section": opt.get("web_form_section", "advanced"),
            "web_form_subsection": opt.get("web_form_subsection"),
            "web_form_field": field,
            "action": action,
            "value": value,
            "cli_flag": opt.get("cli_flag", ""),
            "priority": priority if priority in ("critical", "recommended", "optional", "not_applicable") else "not_applicable",
            "confidence": get_confidence(oid, use_case, vep_options),
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

    am = _ASSEMBLY_RE.search(query or "")
    assembly = am.group(1) if am else None

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

    This is the source-grounded discriminator (the `cli_flag` itself), NOT the provisional
    `priority_by_use_case` judgement — so it is safe to drive output tiers off it today.
    """
    f = cli_flag or ""
    return "--plugin" in f or "--custom" in f


def tier_options(enabled, vep_options):
    """Split an enabled option set into two deterministic, separable output tiers:

      - ``core``   — native VEP flags: available from the core install, no extra data, fast.
      - ``addons`` — plugins / custom files (``--plugin`` / ``--custom``): need downloaded data
                     files and add runtime, so a user may want to opt in to them explicitly.

    The split is FACTUAL (keyed on ``cli_flag`` via :func:`is_plugin_flag`), so it is reliable now —
    unlike an essential-vs-optional split, which would depend on the still-uncalibrated
    ``priority_by_use_case`` labels. Returns ``{"core": [...ids], "addons": [...ids]}`` (each sorted).
    """
    flag_by_id = {o["id"]: o.get("cli_flag", "") for o in vep_options}
    core, addons = [], []
    for oid in sorted(enabled):
        (addons if is_plugin_flag(flag_by_id.get(oid, "")) else core).append(oid)
    return {"core": core, "addons": addons}


def format_tiered_config(enabled, vep_options):
    """Render the enabled set grouped into Core (native) vs Add-ons (plugins/custom).

    DISPLAY LAYER ONLY — does not change which options are enabled (so it has no effect on the
    checker or the scored metrics); it only makes the recommended set separable for the user.
    """
    tiers = tier_options(enabled, vep_options)
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    flag_by_id = {o["id"]: o.get("cli_flag", "") for o in vep_options}
    lines = []
    lines.append(f"CORE — native VEP options (no extra data files, fast)  [{len(tiers['core'])}]")
    for oid in tiers["core"]:
        lines.append(f"  \u2713 {name_by_id.get(oid, oid)} [{oid}] {flag_by_id.get(oid, '')}".rstrip())
    if not tiers["core"]:
        lines.append("  (none)")
    lines.append(f"ADD-ONS — plugins / custom data (need downloaded files + extra runtime)  [{len(tiers['addons'])}]")
    for oid in tiers["addons"]:
        lines.append(f"  + {name_by_id.get(oid, oid)} [{oid}] {flag_by_id.get(oid, '')}".rstrip())
    if not tiers["addons"]:
        lines.append("  (none)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt building — compression + retrieval
# ---------------------------------------------------------------------------

def compress_options(vep_options, resolved=None):
    """Convert verbose JSON options into a compact text reference.

    `resolved` is the output of intent_priorities() for THIS query's factor tuple. When supplied,
    each option carries the single priority that applies to this scenario ("critical" / "recommended"
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
            priorities = ", ".join(f"{k}={v}" for k, v in opt.get("priority_by_use_case", {}).items())
        conflicts = ", ".join(opt.get("conflicts_with", [])) or "none"
        depends = ", ".join(opt.get("depends_on", [])) or "none"
        # NOTE: when_to_use / when_not_to_use are deliberately NOT shown here — they feed semantic
        # retrieval embeddings (_get_options_embeddings) but the model never sees them in this block;
        # only description[:120] + species + priorities + conflicts/depends are. (Attribution implication:
        # the Exp 6 'description' ablation effectively removes description[:120] + the priority labels,
        # NOT when_to_use/when_not_to_use.) .get guards a catalogue entry missing a key (else KeyError).
        lines.append(
            f"- **{opt['id']}** (`{opt.get('cli_flag', '')}`): {opt.get('description', '')[:120]}. "
            f"Species: {opt.get('species_restriction', 'all species')}. "
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
        texts = [
            f"{opt['description']} {opt.get('when_to_use', '')} {opt.get('when_not_to_use', '')}"
            for opt in vep_options
        ]
        _options_embeddings = model.encode(texts)
    return _options_embeddings


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
        f"Use case: {ex['use_case_category']}\n"
        f"Options:\n" + "\n".join(opts) + "\n"
        f"Rationale: {ex['justification'][:200]}..."
    )


def get_confidence(option_id, use_case, vep_options):
    """Derive confidence level from priority_by_use_case metadata."""
    for opt in vep_options:
        if opt["id"] == option_id:
            priority = opt.get("priority_by_use_case", {}).get(use_case, "")
            if priority == "critical":
                return "high"
            elif priority == "recommended":
                return "medium"
            elif priority in ("optional", "not_applicable"):
                return "low"
    return "low"


def build_system_prompt(vep_options, training_examples, user_query="",
                        retrieval_mode="keyword", examples_override=None, factor_tuple=None):
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
    resolved = resolve_for_query(factor_tuple, vep_options)

    relevant_options = None
    if examples_override is not None:
        scored_examples = [(0, ex) for ex in examples_override]
        if retrieval_mode == "semantic" and user_query:
            scored_options = retrieve_options_semantic(vep_options, user_query, top_k=10)
            relevant_options = [opt for _, opt in scored_options]
            options_text = compress_options(relevant_options, resolved)
        else:
            options_text = compress_options(vep_options, resolved)
    elif retrieval_mode == "all":
        # Include ALL training examples, no retrieval filtering
        options_text = compress_options(vep_options, resolved)
        scored_examples = [(0, ex) for ex in training_examples]
    elif retrieval_mode == "semantic" and user_query:
        # Use semantic retrieval for both options and examples
        scored_options = retrieve_options_semantic(vep_options, user_query, top_k=10)
        relevant_options = [opt for _, opt in scored_options]
        options_text = compress_options(relevant_options, resolved)
        scored_examples = retrieve_examples_semantic(
            training_examples, user_query, vep_options
        )
    else:
        options_text = compress_options(vep_options, resolved)
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
`critical` and `recommended` options. Offer `optional` ones as add-ons only if they genuinely help,
and never enable anything marked NOT APPLICABLE.
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


def build_explain_result_prompt(consequences):
    """Build system prompt for the VEP output explainer mode."""
    consequence_text = []
    for term, info in consequences.items():
        impact = f" (impact: {info['impact']})" if info.get("impact") else ""
        consequence_text.append(f"- **{term}**{impact}: {info['explanation']}")
    consequence_block = "\n".join(consequence_text)

    return f"""You are a VEP Output Explainer. You help users understand VEP annotation results.

## VEP Consequence Terms Reference
{consequence_block}

## Your Role
When a user asks about a VEP output, annotation, or consequence term:
1. Identify which consequence term(s) are relevant.
2. Explain what the annotation means in plain language.
3. Explain WHY VEP assigned that consequence (the biological mechanism).
4. Suggest what the user should check next (e.g., splicing predictors, frequency data).

Cite the consequence term definitions above. Be specific and educational.
Keep answers concise but thorough. Use the [term: X] format to cite consequence terms."""


# ---------------------------------------------------------------------------
# Decision trace (Layer 1 + 2: retrieval transparency + provenance)
# ---------------------------------------------------------------------------

def print_decision_trace(user_query, vep_options, training_examples,
                         retrieval_mode="keyword"):
    """Print the retrieval and reasoning trace for --explain mode."""
    print("=" * 60)
    print(f"  DECISION TRACE (--explain mode, retrieval={retrieval_mode})")
    print("=" * 60)

    # Layer 1: Retrieval transparency
    print("\n--- Layer 1: Retrieved Knowledge Base Entries ---")
    print(f"Query: \"{user_query}\"\n")

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
    else:
        # Keyword mode
        query_words = set(user_query.lower().split())
        all_scored = []
        for ex in training_examples:
            ex_text = f"{ex['user_query']} {ex['use_case_category']} {ex.get('justification', '')}".lower()
            ex_words = set(ex_text.split())
            overlap = query_words & ex_words
            all_scored.append((len(overlap), overlap, ex))
        all_scored.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, matched_words, ex) in enumerate(all_scored, 1):
            marker = " ← SELECTED" if rank <= 2 else ""
            print(f"  #{rank} [{ex['id']}] score={score}{marker}")
            print(f"      Use case: {ex['use_case_category']}")
            if matched_words:
                print(f"      Matched words: {', '.join(sorted(matched_words)[:10])}")
            print()

    # Layer 2: Option provenance preview
    print("--- Layer 2: Option Confidence Map ---")
    if retrieval_mode == "semantic":
        top_category = all_scored[0][1]["use_case_category"] if all_scored else "unknown"
    else:
        top_category = all_scored[0][2]["use_case_category"] if all_scored else "unknown"
    print(f"Detected use case (from top match): {top_category}\n")

    for opt in vep_options:
        conf = get_confidence(opt["id"], top_category, vep_options)
        priority = opt.get("priority_by_use_case", {}).get(top_category, "n/a")
        species = opt.get("species_restriction", "all")
        bar = {"high": "███", "medium": "██░", "low": "█░░"}.get(conf, "░░░")
        print(f"  {bar} {opt['id']:20s} priority={priority:15s} species={species}")

    print()
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Result saving
# ---------------------------------------------------------------------------

def save_result(query, response, mode="recommend", warnings=""):
    """Save the recommendation to the results directory as markdown.

    Args:
        query: The user's original query.
        response: The LLM response text.
        mode: 'recommend' or 'explain'.
        warnings: Optional constraint violation warnings to append.
    """
    # FIX: honour VEP_RESULTS_DIR (like evaluate.py) so demo + benchmark write to the same place;
    # microsecond timestamp so two runs in the same second don't silently overwrite each other.
    results_dir = Path(os.environ.get("VEP_RESULTS_DIR", BASE_DIR / "results"))
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = results_dir / f"vep_{mode}_{timestamp}.md"

    try:
        with open(filename, "w") as f:
            f.write(f"# VEP {'Recommendation' if mode == 'recommend' else 'Output Explanation'}\n\n")
            f.write(f"**Date:** {datetime.datetime.now().isoformat()}\n\n")
            f.write(f"## User Query\n{query}\n\n")
            f.write(f"## {'Recommendation' if mode == 'recommend' else 'Explanation'}\n{response}\n")
            if warnings:
                f.write(f"\n## Constraint Check\n{warnings}\n")
        print(f"\nResult saved to: {filename}")
    except OSError as e:
        print(f"\nWarning: Could not save result to {filename}: {e}")


# ---------------------------------------------------------------------------
# LLM streaming
# ---------------------------------------------------------------------------

def stream_response(client, model, system_prompt, user_message):
    """Call the LLM with streaming and return full response text.

    CAVEAT: sets no temperature (Ollama's default applies -> the demo path is nondeterministic and at a
    different temperature than evaluate.py's, so demo behaviour != benchmarked behaviour), and
    max_tokens=4096 is hardcoded -> a long all-examples prompt + long answer can hit the cap, truncating
    output and leaving partial ✓ lines the parser under-reads.
    """
    response_text = ""
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=4096,
        stream=True,
        # Keep the model resident between calls. The latency benchmark found the big TTFT spikes (up to
        # ~40s) were Ollama EVICTING the 15GB model and reloading it, not prefill — and that the fixed
        # system prompt prefix is cache-able (TTFT dropped to ~0.2s on a warm cache). keep_alive=-1 pins
        # the model in memory so the second query onward pays neither reload nor (cached) prefill.
        extra_body={"keep_alive": -1},
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            response_text += delta
    print()
    return response_text


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def run_recommend(client, model, vep_options, training_examples, user_query,
                   explain=False, skip_check=False, retrieval_mode="keyword", level="standard"):
    """Run the recommendation mode (default).

    Args:
        skip_check: If True, skip the post-hoc constraint checker.
        retrieval_mode: "keyword" or "semantic".
        level: "minimal" (essentials only), "standard" (default), or "full" (add every add-on).
    """
    if explain:
        print_decision_trace(user_query, vep_options, training_examples,
                             retrieval_mode=retrieval_mode)

    # Classify the query into factor values FIRST, so the option block can carry the priority that
    # applies to this scenario rather than the flat table of legacy use-case labels. A classifier
    # failure is non-fatal: factor_tuple stays None and the prompt falls back to the old block.
    factor_tuple = infer_factors(client, model, user_query)
    if factor_tuple:
        print("Detected scenario:")
        print(describe_factors(factor_tuple))
        print()

    system_prompt = build_system_prompt(vep_options, training_examples, user_query,
                                        retrieval_mode=retrieval_mode,
                                        factor_tuple=factor_tuple)
    print("Analysing your scenario...\n")

    try:
        response_text = stream_response(client, model, system_prompt, user_query)
    except Exception as e:
        print(f"\nError communicating with Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        print(f"And the model is pulled: ollama pull {model}")
        sys.exit(1)

    # --- Post-hoc constraint check + REPAIR ---
    # check_and_fix_violations repairs the option set IN PLACE (drops species/conflict violations,
    # auto-enables dependencies); we then surface that corrected set as the AUTHORITATIVE configuration
    # (format_corrected_config), not merely a warning — so the checker actually "disposes". NOTE: the
    # model's streamed draft prose above is left raw (rewriting free prose / its generated command in
    # place is fragile), so the corrected block SUPERSEDES the draft. Regenerating the whole deliverable
    # from the corrected set is the structured-output migration's job.
    warnings = ""
    if not skip_check:
        option_aliases = build_option_aliases(vep_options)
        # Audit what the model CITED before we act on it: ids that don't exist are dropped, near-misses
        # are fuzzy-resolved, and both used to happen silently. A silent guess is how `[source: plugin_cadd]`
        # became MaxEntScan in a live demo, so the guess is now stated out loud.
        audit = audit_source_citations(response_text, option_aliases)

        # The model declined the request: there is no configuration, so there is nothing to audit,
        # repair or display. Running the rest would keyword-scrape a phantom config out of the refusal
        # text and then warn about ITS species and format — three true-but-irrelevant alarms attached
        # to something the model never proposed.
        if is_out_of_scope_response(response_text, audit):
            save_result(user_query, response_text, mode="recommend", warnings="")
            return

        audit_report = format_citation_audit(audit, len(vep_options))
        if audit_report:
            print(audit_report)
        enabled, disabled = extract_recommendations(response_text, option_aliases)
        violations = check_and_fix_violations(
            enabled, disabled, vep_options, training_examples, user_query,
            retrieval_mode=retrieval_mode,
        )
        warnings = format_violation_warnings(violations)
        if warnings:
            print(warnings)
        resolved = resolve_for_query(factor_tuple, vep_options)
        if resolved and level != "standard":
            removed = apply_config_level(enabled, disabled, resolved, level, vep_options,
                                         training_examples, user_query,
                                         retrieval_mode=retrieval_mode)
            note = (f"  ({len(removed)} non-essential options dropped; dependencies kept)"
                    if level == "minimal" else "  (every applicable add-on switched on)")
            print(f"\nCONFIG LEVEL: {level}\n{note}")
        elif level != "standard":
            print(f"\nCONFIG LEVEL: {level} requested, but the scenario's factors could not be "
                  f"resolved — showing the standard set.")
        corrected = format_corrected_config(enabled, disabled, vep_options, violations,
                                            resolved=resolved)
        print(corrected)
        warnings = "\n".join(x for x in (audit_report, warnings, corrected) if x)

    save_result(user_query, response_text, mode="recommend", warnings=warnings)


def run_explain_result(client, model, user_query):
    """Run the VEP output explainer mode."""
    consequences = load_consequences()
    if not consequences:
        print("Error: vep_consequences.json not found.")
        sys.exit(1)

    system_prompt = build_explain_result_prompt(consequences)
    print("Explaining VEP output...\n")

    try:
        response_text = stream_response(client, model, system_prompt, user_query)
    except Exception as e:
        print(f"\nError communicating with Ollama: {e}")
        sys.exit(1)

    save_result(user_query, response_text, mode="explain")


def main():
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # Default to the model this system is actually built and benchmarked on. It was qwen2.5:3b, chosen
    # when the demo just needed something small — but 3B cannot hold the `✓/✗ ... [source: id]` output
    # contract the whole pipeline depends on. It frequently emits no [source:] tags at all, which drops the
    # parser into its prose fallback (built for the no-KB experimental condition), and that fallback
    # inverts the model: "✗ polyphen: ON" parses as ENABLE. Exp 1/10 measure 3B at 31-39% enable-F1, the
    # worst of every model tested, vs 84% for gemma4:26b. Shipping it as the default made the demo's first
    # impression the system's worst configuration.
    model = os.environ.get("VEP_MODEL", "gemma4:26b")
    client = OpenAI(base_url=base_url, api_key="ollama")

    args = sys.argv[1:]

    # --- Mode: explain-result ---
    if args and args[0] == "explain-result":
        query = " ".join(args[1:]).strip()
        if not query:
            print("Usage: python vep_assistant.py explain-result \"Why is my variant splice_donor_variant?\"")
            sys.exit(1)
        run_explain_result(client, model, query)
        return

    # --- Mode: recommend (with optional --explain, --no-check, --semantic) ---
    explain = "--explain" in args
    skip_check = "--no-check" in args
    semantic = "--semantic" in args
    retrieval_mode = "semantic" if semantic else "keyword"
    # How much configuration the user wants back. --minimal for the smallest runnable set,
    # --full to switch on every add-on the scenario justifies; neither given = the standard set.
    level = "minimal" if "--minimal" in args else "full" if "--full" in args else "standard"
    remaining = [a for a in args
                 if a not in ("--explain", "--no-check", "--semantic", "--minimal", "--full")]

    vep_options, training_examples = load_knowledge_base()

    if remaining:
        user_query = " ".join(remaining)
    else:
        print("=" * 60)
        print("  VEP AI Assistant (local LLM via Ollama)")
        print("  Describe your analysis scenario to get VEP recommendations")
        print("  Tip: use --explain for full decision trace, --semantic for embedding retrieval")
        print("=" * 60)
        print()
        user_query = input("Your scenario: ").strip()
        if not user_query:
            print("No query provided. Exiting.")
            sys.exit(0)

    print()
    run_recommend(client, model, vep_options, training_examples, user_query,
                  explain=explain, skip_check=skip_check,
                  retrieval_mode=retrieval_mode, level=level)


if __name__ == "__main__":
    main()
