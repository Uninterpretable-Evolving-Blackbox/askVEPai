#!/usr/bin/env python3
"""VEP AI Assistant: recommends which options to tick on the Ensembl VEP web form for a scenario.

An LLM classifier reads the query into five factors plus organism; a deterministic resolver prices
options from the priority table; a checker applies species, assembly, conflict and dependency gates.
  python vep_assistant.py ["query"] [--explain] [--minimal|--full] [--cli] [--no-ask|--quiet]
  python vep_assistant.py explain-result "why..."   # explain a VEP output annotation
Run with --help for every flag.
"""

import json
import os
import re
import sys
import time
import datetime
from pathlib import Path

# The openai SDK is imported lazily in main(): harnesses import this module without it.

BASE_DIR = Path(__file__).parent


# --- Knowledge base loading ---

def _kb_path(env_var, work_relative, demo_filename):
    """Path to a knowledge-base file: the env var if set, else the `work/` copy, else the demo-local copy.

    The demo-local fallback lets `vep_ai_demo/` run without `work/` beside it."""
    if env_var and os.environ.get(env_var):
        return Path(os.environ[env_var])
    canonical = BASE_DIR.parent / work_relative
    return canonical if canonical.exists() else BASE_DIR / demo_filename


def load_knowledge_base():
    """Return (vep_options, training_examples); VEP_OPTIONS_FILE / VEP_EXAMPLES_FILE override the paths."""
    options_path = _kb_path("VEP_OPTIONS_FILE", "work/vep_options_expanded.json", "vep_options.json")
    # Only --two-pass reads the examples, so a missing file gives an empty list.
    examples_path = Path(os.environ.get("VEP_EXAMPLES_FILE", BASE_DIR / "legacy" / "training_examples.json"))

    # Raise rather than exit: harnesses call this. main() catches and prints.
    if not options_path.exists():
        raise FileNotFoundError(f"VEP options file not found at {options_path}")

    with open(options_path) as f:
        vep_options = json.load(f)
    training_examples = []
    if examples_path.exists():
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


# --- The factor scheme (the generation pipeline imports this) ---
# A scenario is a set of factor values (research/taxonomy_proposal.md §3). It lives in the engine
# because work/generation imports vep_ai_demo, never the reverse. The scheme and priority table are
# provisional config files, not yet mentor-validated.

def load_factors():
    """Return factors.json: values, kinds, hard gates, exclusions, conditional rules."""
    path = _kb_path("VEP_FACTORS_FILE", "work/generation/generation_config/factors.json", "factors.json")
    with open(path) as f:
        return json.load(f)


# --- The importance table ---
# `priority_by_factor.json` is authored by hand: one block per option, factor -> value -> priority.
# Rationale and mentor quotes are in work/generation/generation_config/priority_by_factor_NOTES.md.
# Only the species gate is computed, at load, from each option's `species` list.

# Two tiers; `critical` is not in the scheme.
RANK = {"recommended": 2, "optional": 1, "not_applicable": 0}


def validate_priority_table(table, factors_cfg=None):
    """Return problems in `priority_by_factor.json` as readable strings; [] when clean.

    Catches unknown factors, values and labels. `verify_pipeline.py` asserts []; the engine only warns."""
    problems = []
    if factors_cfg is None:
        try:
            factors_cfg = load_factors()
        except Exception:
            factors_cfg = None
    known = {f: set(spec.get("values", [])) for f, spec in (factors_cfg or {}).get("factors", {}).items()}
    for oid, block in (table.get("priorities") or {}).items():
        if not isinstance(block, dict):
            problems.append(f"{oid}: expected an object of factor -> value -> priority, got {type(block).__name__}")
            continue
        for factor, valmap in block.items():
            if factor.startswith("_"):
                continue
            if known and factor not in known:
                problems.append(f"{oid}: unknown factor {factor!r} (expected one of {', '.join(sorted(known))})")
                continue
            if not isinstance(valmap, dict):
                problems.append(f"{oid}.{factor}: expected an object of value -> priority")
                continue
            for value, label in valmap.items():
                if known and value not in known.get(factor, set()):
                    problems.append(f"{oid}.{factor}: unknown value {value!r} "
                                    f"(expected one of {', '.join(sorted(known[factor]))})")
                if label not in RANK:
                    problems.append(f"{oid}.{factor}.{value}: unknown priority {label!r} "
                                    f"(expected one of {', '.join(RANK)})")
    return problems


_PRIORITY_TABLE_WARNED = False


def load_priority_by_factor(vep_options=None):
    """Load `priority_by_factor.json` (required) and stamp species.non-human from each option's `species`."""
    global _PRIORITY_TABLE_WARNED
    path = _kb_path("VEP_PRIORITY_FACTOR_FILE",
                    "work/generation/generation_config/priority_by_factor.json",
                    "priority_by_factor.json")
    if not path.exists():
        raise FileNotFoundError(f"priority table not found at {path} (it is authored, not derived)")
    with open(path) as f:
        table = json.load(f)
    if vep_options is None:
        opts_path = _kb_path("VEP_OPTIONS_FILE", "work/vep_options_expanded.json", "vep_options.json")
        with open(opts_path) as f:
            vep_options = json.load(f)
    problems = validate_priority_table(table)
    if problems and not _PRIORITY_TABLE_WARNED:
        _PRIORITY_TABLE_WARNED = True
        print("\n  Note: problems in priority_by_factor.json -- these entries are IGNORED:")
        for pr in problems[:8]:
            print(f"    - {pr}")
        if len(problems) > 8:
            print(f"    ... and {len(problems) - 8} more")
        print()
    # Species gate: human-only, or a two-species set that includes human, is not_applicable for
    # non-human. Plugins are skipped; the checker uses their species lists (Ensembl plugin_config.txt).
    priorities = table.setdefault("priorities", {})
    for o in vep_options:
        if option_source(o) == "plugin":
            continue
        if _gates_nonhuman(o.get("species", "all")):
            priorities.setdefault(o["id"], {}).setdefault("species", {})["non-human"] = "not_applicable"
    return table


# --- Display vocabulary ---
# The user sees two buckets, RECOMMENDED and ADD-ON (mentors, 2026-08-07). The names are Nakib's:
# "default" would suggest the option applies automatically. The CLI, web payload and review export
# all read this one map.
DISPLAY_TIER = {"recommended": "recommended", "optional": "add-on"}


# Form defaults that are on only for a human run. `af`, `pubmed`, `tsl`, `appris` and `mane` are
# rendered only under the Homo_sapiens guard in InputForm.pm (lines 574-612, 674/684/694). `clinvar`
# rides on `check_existing`, which renders for any species with variation data, but ClinVar data is
# human-only. Every other `web_default_on` control renders for all species (InputForm.pm, 2026-09-14).
_HUMAN_ONLY_FORM_DEFAULTS = frozenset({"appris", "tsl", "mane", "af", "clinvar", "pubmed"})


def _form_default_on(oid, vep_options, species):
    """True when the web form ships this option ticked for this species.

    Form defaults are assumed on and not recommended (mentor instruction, 2026-09-13)."""
    opt = next((o for o in vep_options if o["id"] == oid), None)
    if not opt or not opt.get("web_default_on"):
        return False
    # `species` is the factor value ("human") or an Ensembl production name ("homo_sapiens...").
    is_human = species in (None, "human", "unknown") or str(species).lower().startswith("homo_sapiens")
    if oid in _HUMAN_ONLY_FORM_DEFAULTS and not is_human:
        return False
    return True


def display_tier(priority):
    """Return the user-facing bucket for a priority label; labels with no bucket come back unchanged."""
    return DISPLAY_TIER.get(priority, priority)


# Hard-gate factors (`hard_gate` in factors.json) remove an option outright when they mark it
# not_applicable. `region_focus` is one so a purely regulatory query gets no missense predictors
# (constraints_dossier.md:123). This amends taxonomy_proposal §3 and awaits mentor sign-off.

def _factor_scheme():
    """Return (values, multi-select factors, hard-gate factors) from factors.json, which is required."""
    try:
        spec = load_factors()["factors"]
    except Exception as e:
        raise RuntimeError("factors.json is required and could not be read: %s" % e) from e
    values = {f: list(s["values"]) for f, s in spec.items()}
    multi = tuple(f for f, s in spec.items() if s.get("select") == "multi")
    gates = tuple(f for f, s in spec.items() if s.get("hard_gate"))
    return values, multi, gates


FACTOR_VALUES, MULTI_FACTORS, HARD_GATE_FACTORS = _factor_scheme()

# Options whose value is not a bare boolean (everything else -> True when enabled).
VALUE_DEFAULTS = {"sift": "b", "polyphen": "b", "check_existing": "yes"}


def strongest(labels):
    """Return the strongest label (recommended > optional), or None; other labels are ignored."""
    best, best_rank = None, 0
    for p in labels:
        r = RANK.get(p, 0)
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
    """Compact, deterministic label for a tuple (for ids / filenames), in FACTOR_VALUES order."""
    parts = []
    for f in FACTOR_VALUES:
        v = factor_tuple.get(f)
        parts.append("+".join(v) if isinstance(v, list) else str(v))
    return "__".join(parts).replace("-", "").replace("_", "")


# --- One VEP run per variant size, when the callset holds both ---
# CADD's form control picks one annotation file (SNVs and InDels / SNVs / InDels / CADD-SV), so one run
# cannot cover short and structural variants (Likhitha). The labels are the catalogue's
# `web_form_values`, read off the live form. The factor stays multi-select; the output is split into
# one configuration per size at render time.
SIZE_FACTOR = "variant_size_class"
SIZE_PASS_LABELS = {"small": "short variants (SNVs and indels)",
                    "structural-CNV": "structural variants and CNVs"}


def size_passes(factor_tuple):
    """Return [(size_value, label, factor tuple)], one entry per VEP run the scenario needs.

    With both sizes active, each tuple is a copy with the size pinned to one value."""
    if not factor_tuple:
        return [(None, "", factor_tuple)]
    sizes = [v for v in active_values(factor_tuple).get(SIZE_FACTOR, []) if v]
    if len(sizes) < 2:
        one = sizes[0] if sizes else None
        return [(one, SIZE_PASS_LABELS.get(one, ""), factor_tuple)]
    ordered = ([s for s in SIZE_PASS_LABELS if s in sizes]
               + [s for s in sizes if s not in SIZE_PASS_LABELS])
    out = []
    for v in ordered:
        pinned = dict(factor_tuple)
        pinned[SIZE_FACTOR] = [v] if isinstance(factor_tuple.get(SIZE_FACTOR), list) else v
        out.append((v, SIZE_PASS_LABELS.get(v, v), pinned))
    return out


def size_dependent_choice(oid, size_value, vep_options, assembly=None):
    """Return (form value for this pass, reason it is unavailable) for a control with `web_form_values`.

    A reason is given only when a stated assembly rules the value out (CADD-SV is GRCh38-only)."""
    if not size_value:
        return None, None
    opt = next((o for o in vep_options if o["id"] == oid), None)
    values = (opt or {}).get("web_form_values") or []
    if not values:
        return None, None
    for v in values:
        if size_value in (v.get("covers") or []):
            need = v.get("assembly_restriction")
            if need and assembly and assembly != need:
                return v["label"], (f"its only {size_value} annotation file is {need}-only "
                                    f"and you stated {assembly}")
            return v["label"], None
    return None, f"the form offers no annotation file covering {size_value}"


def drop_unavailable_size_values(enabled, vep_options, size_value, assembly):
    """Remove from `enabled` the options this pass has no usable data file for; return [(oid, why)]."""
    gone = [(oid, reason) for oid in sorted(enabled)
            for _lab, reason in [size_dependent_choice(oid, size_value, vep_options, assembly)]
            if reason]
    for oid, _ in gone:
        enabled.discard(oid)
    return gone


# A minimal query for infer_species when the resolver runs the checker without a real query.
# Every non-human species gates the same human-only block, so 'mouse' stands for all of them.
def species_cue_query(species):
    return "human variant analysis" if species == "human" else "mouse variant analysis"


def factor_value_for(oid, species):
    """The VALUE an enabled option takes (most are boolean True)."""
    if oid == "core_type":
        return "Ensembl/GENCODE" if species == "human" else "Ensembl"
    return VALUE_DEFAULTS.get(oid, True)


def intent_priorities(factor_tuple, catalogue, pbf, factors_cfg, enable=("recommended",), trace=None):
    """Return {oid: (enabled, priority or None, gated)} from factor priorities, before the checker.

    `enable`: priority labels that switch an option on. `trace`: optional dict, filled per option with
    {"priority", "votes": [(factor, value, label)], "winner": vote or None, "gated_by": [(factor, values)]}."""
    av = active_values(factor_tuple)
    priorities = pbf["priorities"]
    cond_rules = factors_cfg.get("conditional_rules", [])

    out = {}
    for opt in catalogue:
        oid = opt["id"]
        pf = priorities.get(oid, {})
        gated = False
        # (1) Hard gates: a factor gates an option only if EVERY active value marks it not_applicable,
        # so a coding+regulatory set keeps its missense predictors.
        for hf in HARD_GATE_FACTORS:
            vals = av.get(hf, [])
            if vals and all(pf.get(hf, {}).get(v) == "not_applicable" for v in vals):
                gated = True
        if gated:
            out[oid] = (False, None, True)
            if trace is not None:
                trace[oid] = {"priority": None, "votes": [], "winner": None,
                              "gated_by": [(hf, av.get(hf, [])) for hf in HARD_GATE_FACTORS
                                           if av.get(hf) and all(pf.get(hf, {}).get(v) == "not_applicable"
                                                                 for v in av[hf])]}
            continue
        # (2) Soft ranking over all active factor values.
        labels, votes = [], []
        for f, vals in av.items():
            for v in vals:
                lab = pf.get(f, {}).get(v)
                labels.append(lab)
                if lab:
                    votes.append((f, v, lab))
        # (3) Conditional rules: joint conditions the per-value table cannot express. A rule fires when
        # every 'when' pair is active and joins the same max, so it can only raise an option. Hard-gated
        # options never reach here.
        for rule in cond_rules:
            if all(wv in av.get(wf, []) for wf, wv in rule["when"].items()):
                lab = rule["then"].get(oid)
                if lab:
                    labels.append(lab)
                    votes.append(("conditional rule",
                                  " + ".join(f"{k}={v}" for k, v in rule["when"].items()), lab))
        pr = strongest(labels)
        out[oid] = (pr in enable, pr, False)
        if trace is not None:
            winners = [t for t in votes if t[2] == pr]
            trace[oid] = {"priority": pr, "votes": votes,
                          "winner": winners[0] if winners else None, "gated_by": []}
    return out


# --- Query -> factors ---
# An LLM classifies the factors from the query text alone and answers "unstated" rather than guess.
# Run it at temperature 0, fixed seed, concurrency 1: temp 0 is not deterministic under concurrency
# on the Metal/MoE stack.

def _schema_lines():
    """Return the JSON schema lines of the classifier prompt, generated from factors.json."""
    out = []
    for f, vals in FACTOR_VALUES.items():
        if f in MULTI_FACTORS:
            out.append(f'  "{f}": array with any of [' + ",".join(f'"{v}"' for v in vals) + ']')
        else:
            out.append(f'  "{f}": ' + " | ".join(f'"{v}"' for v in vals) + ' | "unstated"')
    return ",\n".join(out) + "\n"


FACTOR_CLASSIFIER_PROMPT_V1 = (
    "You read a researcher's natural-language question about annotating genetic variants and identify ONLY "
    "what the question actually states or clearly implies about the analysis. Do NOT guess; if the question "
    "does not indicate a characteristic, use \"unstated\" (or [] for a list).\n\n"
    "Reply with ONLY this JSON object, no prose:\n"
    "{\n"
    # First: _schema_lines() leaves no trailing comma on its last line.
    "  \"request_type\": \"configure\" | \"not-vep\" | \"vep-support\",\n"
    + _schema_lines() +
    "}\n\n"
    "Guidance (judge by meaning, not keywords):\n"
    "- request_type: what the user is asking FOR. configure = they want to know which VEP options to "
    "switch on for their data. not-vep = small talk, or a topic unrelated to variant annotation. "
    "vep-support = a VEP question that is not about choosing options: an error or bug, output that "
    "looks wrong, how to install or run it, or what a column means. This assistant only recommends "
    "options, so not-vep and vep-support are both out of scope. When request_type is not "
    "\"configure\", still fill in any factor the text does state.\n"
    "- origin: germline = inherited / constitutional / rare-disease / healthy cohort; somatic = tumour / cancer.\n"
    "- variant_size_class: small = SNVs / indels / point changes; structural-CNV = large deletions / duplications / CNVs / SVs.\n"
    "- region_focus: coding = protein-coding / missense / exonic; regulatory-noncoding = enhancer / promoter / intronic / intergenic.\n"
    "- analysis_goal: basic-consequence = just a quick consequence call; clinical-interpretation = "
    "pathogenicity / disease significance — a named disease, a patient, a diagnosis, or 'pathogenic' / "
    "'clinical' all indicate this; population-frequency = allele frequencies. Use basic-consequence "
    "only when the question really is just 'what are these variants', with no clinical or disease "
    "framing.\n\n"
    "Output raw JSON only — no markdown, no code fences, no explanation.\n\n"
    "Question:\n"
)


# V2, the default. The role opening makes a question about the user's own variants a configure
# request; its last sentence stops that from filling analysis_goal or origin. The query goes in the
# user message (`classifier_messages`). V1 is selected with VEP_CLASSIFIER_PROMPT=v1.
FACTOR_CLASSIFIER_PROMPT_V2 = (
    "You are the first step of Ask VEPai, a tool that recommends settings for the Ensembl Variant Effect "
    "Predictor (VEP) web form. Most messages come from a researcher who wants to annotate their own "
    "genetic variants. When they ask a question about their variants -- \"are any of these pathogenic?\", "
    "\"how common are these?\" -- they are asking which VEP settings will get them that answer, so that is "
    "a configure request. You do not answer the question itself. Being a configure request says nothing "
    "about the factors: if the message never says what they want from the annotation, analysis_goal is "
    "[]; if it never says germline or somatic, origin is \"unstated\".\n\n"
    "Your job: identify ONLY what the researcher's message actually states or clearly implies about the "
    "analysis. Do NOT guess; if the message does not indicate a characteristic, use \"unstated\" (or [] "
    "for a list). The message is in the user turn.\n\n"
    "Reply with ONLY this JSON object, no prose:\n"
    "{\n"
    # First: _schema_lines() leaves no trailing comma on its last line.
    "  \"request_type\": \"configure\" | \"not-vep\" | \"vep-support\",\n"
    + _schema_lines() +
    ",  \"organism\": the organism named in the message, as written (\"pig\", \"Sus scrofa\", \"zebra finch\"), "
    "or \"unstated\"\n"
    "}\n\n"
    "Guidance (judge by meaning, not keywords):\n"
    "- organism: copy the organism the DATA is from, if the message names one. It is only a name: the "
    "tool looks up what Ensembl has for it. Leave it \"unstated\" when no organism is named, or when the "
    "organism mentioned is not what was sequenced.\n"
    "- request_type: what the user is asking FOR. configure = they want to know which VEP options to "
    "switch on for their data. not-vep = small talk, or a topic unrelated to variant annotation. "
    "vep-support = a VEP question that is not about choosing options: an error or bug, output that "
    "looks wrong, how to install or run it, or what a column means. This assistant only recommends "
    "options, so not-vep and vep-support are both out of scope. When request_type is not "
    "\"configure\", still fill in any factor the text does state.\n"
    "- origin: germline = inherited / constitutional / rare-disease / healthy cohort; somatic = tumour / cancer.\n"
    "- variant_size_class: small = SNVs / indels / point changes; structural-CNV = large deletions / duplications / CNVs / SVs.\n"
    "- region_focus: coding = protein-coding / missense / exonic; regulatory-noncoding = enhancer / promoter / intronic / intergenic.\n"
    "- analysis_goal: basic-consequence = just a quick consequence call; clinical-interpretation = "
    "pathogenicity / disease significance — a named disease, a patient, a diagnosis, or 'pathogenic' / "
    "'clinical' all indicate this; population-frequency = allele frequencies. Use basic-consequence "
    "only when the question really is just 'what are these variants', with no clinical or disease "
    "framing.\n\n"
    "Output raw JSON only — no markdown, no code fences, no explanation.\n"
)


def _classifier_prompt_version():
    return "v1" if (os.environ.get("VEP_CLASSIFIER_PROMPT") or "").strip().lower() == "v1" else "v2"


# The name callers import. Under v2 it is instructions only; under v1 the query is appended to it.
FACTOR_CLASSIFIER_PROMPT = FACTOR_CLASSIFIER_PROMPT_V1 if _classifier_prompt_version() == "v1" else FACTOR_CLASSIFIER_PROMPT_V2


def classifier_messages(user_query, hint=""):
    """Return the classifier's chat messages; the CLI and harnesses both use this.

    v2: instructions in system, query plus species hint in user. v1: query appended to the system prompt."""
    q = user_query or ""
    if _classifier_prompt_version() == "v1":
        return [{"role": "system", "content": FACTOR_CLASSIFIER_PROMPT_V1 + q + hint},
                {"role": "user", "content": "Return the JSON classification."}]
    return [{"role": "system", "content": FACTOR_CLASSIFIER_PROMPT_V2},
            {"role": "user", "content": q + hint}]


def parse_factor_classification(raw):
    """Parse the classifier's JSON into {factor: value | 'unstated' | [values]}, plus _request_type, _organism.

    Tolerates surrounding prose and code fences. Returns None when no JSON object can be parsed."""
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
    # Scope: the factors alone cannot tell "hi" from "annotate my VCF", so the classifier judges it.
    # Unrecognised or absent defaults to "configure".
    rt = obj.get("request_type")
    out["_request_type"] = rt if rt in ("configure", "not-vep", "vep-support") else "configure"
    # Organism: the data lists (SIFT, frequency files, plugin species) are per species. The name is
    # checked against Ensembl's index, so an invented one resolves to None. V1 has no organism field.
    out["_organism"] = resolve_model_organism(obj.get("organism"))
    return out


# How long Ollama keeps the model loaded after a call. The default -1 (forever) keeps reloads out of
# eval timings; on a shared machine set VEP_KEEP_ALIVE=5m, or 0 to unload at once.
def _keep_alive():
    """Return VEP_KEEP_ALIVE as an int if numeric, else the duration string; -1 when unset.

    Ollama rejects a numeric string such as "-1" (HTTP 400), so numbers are sent as int."""
    v = os.environ.get("VEP_KEEP_ALIVE")
    if v is None:
        return -1
    try:
        return int(v)
    except ValueError:
        return v


KEEP_ALIVE = _keep_alive()


def _native_chat_url():
    """Return Ollama's native /api/chat URL, derived from OLLAMA_BASE_URL."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    return base.rstrip("/").removesuffix("/v1") + "/api/chat"


# Bounds a runaway. High enough for the classifier to finish reasoning and still emit its ~60-token
# JSON; a cap spent entirely on reasoning returns empty content.
_CLASSIFY_MAX_TOKENS = 4096


def _classify_native(model, user_query, think):
    """Call the classifier on Ollama's native endpoint, which honours `think`; return the raw text."""
    import urllib.request
    body = {
        "model": model, "stream": False, "keep_alive": KEEP_ALIVE, "think": think,
        "messages": classifier_messages(user_query,
                                        format_species_hint(user_query) if _species_hint_on() else ""),
        "options": {"temperature": 0.0, "seed": 42, "num_predict": _CLASSIFY_MAX_TOKENS},
    }
    req = urllib.request.Request(_native_chat_url(), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return (json.loads(r.read()).get("message", {}) or {}).get("content") or ""


def _factor_think_setting():
    """Return the classifier's reasoning mode from VEP_FACTOR_THINK.

    unset / 1 -> True (reasoning on, native endpoint; the default, David, 2026-09-20);
    0 -> False (reasoning off, `--no-factor-think`); compat -> None (the /v1 path).
    """
    v = (os.environ.get("VEP_FACTOR_THINK") or "").strip().lower()
    if v == "compat":
        return None
    if v in ("0", "off", "false", "no"):
        return False
    return True


def infer_factors(client, model, user_query, think=False, apply_defaults=True,
                  seed=42, temperature=0.0):
    """Classify a free-text query into a factor tuple, or None if the classifier fails.

    apply_defaults=False keeps unstated factors as "unstated" so clarification_plan can disclose or
    ask about them; True fills species "human" and an empty analysis_goal ["basic-consequence"].
    think=False reads VEP_FACTOR_THINK; think=None uses the OpenAI-compatible /v1 path, which drops
    the `think` parameter. Runs on VEP_FACTOR_MODEL if set, else on `model`, so one pulled model is
    enough. temperature 0 is reproducible only at concurrency 1."""
    model = os.environ.get("VEP_FACTOR_MODEL") or model
    if think is False:                       # resolve from VEP_FACTOR_THINK
        think = _factor_think_setting()
    try:
        if think is None:                    # the /v1 compat path
            resp = client.chat.completions.create(
                model=model,
                messages=classifier_messages(user_query,
                                             format_species_hint(user_query) if _species_hint_on() else ""),
                # Parameterised so a harness can report a spread across seeds.
                temperature=temperature,
                seed=seed,
            )
            raw = resp.choices[0].message.content or ""
        else:
            raw = _classify_native(model, user_query, think)
    except Exception:
        return None

    rec = parse_factor_classification(raw)
    if rec is None:
        return None

    # SPECIES. The model's answer decides (David, 2026-09-16). Any other answer becomes "unstated",
    # so UNDERSPECIFIED_POLICY assumes human and says so; apply_defaults=True fills "human" here.
    # VEP_SPECIES_HINT=1 shows the keyword scan's matches to the model and uses the scan as fallback.
    def _species_from_rule(hint_mode):
        sp = infer_species(user_query)
        if sp not in ("human", "unknown"):
            return "non-human"                  # a named organism
        # A "human" scan result is weak evidence: 7 of the 28 _HUMAN_SIGNALS words are analysis words
        # ("somatic", "tumour", "cancer", ...). In hint mode it falls through to the disclosed
        # human assumption.
        if sp == "human" and not hint_mode:
            return "human"
        return "human" if apply_defaults else "unstated"
    said = (rec.get("species") or "").strip().lower()
    if _species_hint_on():
        rec["species"] = said if said in ("human", "non-human") else _species_from_rule(True)
    else:
        rec["species"] = said if said in ("human", "non-human") else ("human" if apply_defaults else "unstated")
    # A named non-human organism overrides the binary answer: without reasoning the model sometimes
    # names an animal and still answers "human". This only ever upgrades to non-human.
    if rec.get("_organism") and rec["_organism"] != "homo_sapiens" and rec.get("species") != "non-human":
        rec["species"] = "non-human"
    if apply_defaults and not rec.get("analysis_goal"):
        rec["analysis_goal"] = ["basic-consequence"]
    return rec


# --- Unstated factors: assume and say so, or ask ---
# An unstated factor contributes no options, so each factor has a policy. Guess where one answer is
# clearly safer; ask where none is. Evidence: research/underspecification_proposal.md.
UNDERSPECIFIED_POLICY = {
    # Human, disclosed. Withholding the human-only options from human queries that never say "human"
    # is the larger harm.
    "species": {
        "assume": "human",
        "why": "you didn't name an organism, so human is assumed and the human-only options stay "
               "available. Say the species if it isn't human",
    },
    "region_focus": {
        "assume": ["coding", "regulatory-noncoding"],
        "why": "you didn't say which regions matter, so both are covered",
    },
    # Somatic. The `somatic => frequency not_applicable` hard rule fires only on an explicit somatic,
    # so leaving origin open behaves like germline and lets the common-variant filter through.
    # `frequency` is an add-on (David, 2026-09-14), so this guess changes no enabled option on any
    # tuple; work/harness/suites/defaults_evidence.py asserts it.
    "origin": {
        "assume": "somatic",
        "why": "you didn't say germline or somatic, so the safer reading is taken — it keeps the "
               "common-variant filter off, which would otherwise discard real tumour variants. "
               "Say 'germline' if these are inherited variants",
    },
    # Both. Each single value gates away the other half of the catalogue, so assuming both only adds
    # options. Relies on the factor being multi-select (factors.json `_select_note`).
    "variant_size_class": {
        "assume": ["small", "structural-CNV"],
        "why": "you didn't say small variants or structural/CNV, so both are covered — say which if "
               "your callset is only one of them",
    },
    # Asked. No value is safe: narrow drops ClinVar and the predictors from a clinical question, broad
    # buries a quick lookup. If skipped, resolve_underspecified fills basic-consequence and says so.
    "analysis_goal": {
        "assume": None,
        "why": "you didn't say what you're after — a quick consequence call, clinical interpretation, "
               "or population frequencies; they pull in different tools",
    },
}


# --- Facts the user states on the form ---
# Species, origin and variant size are facts about the sample that the user knows. A stated value
# overrides the classifier; a blank one goes through the classifier and UNDERSPECIFIED_POLICY.
# Assembly is not a factor but belongs here: a query rarely names a build, and VEP's form shows the
# GRCh38-only MANE checkbox to every human user (InputForm.pm:694-702).
USER_CONTEXT_FIELDS = ("species", "origin", "variant_size_class", "assembly")


def apply_user_context(rec, context):
    """Overlay what the user stated on the classifier's reading. Returns (tuple, assembly, overridden).

    `context` maps USER_CONTEXT_FIELDS to values; None, "", "infer" or "unstated" leave a field to
    the classifier.
    """
    rec = dict(rec or {})
    context = context or {}
    overridden = []
    for f in USER_CONTEXT_FIELDS:
        v = context.get(f)
        if v in (None, "", "infer", "unstated"):
            continue
        if f == "assembly":
            continue                                    # not a factor; returned separately
        allowed = FACTOR_VALUES.get(f, [])
        vals = v if isinstance(v, list) else [v]
        vals = [x for x in vals if x in allowed]
        if not vals:
            continue                                    # ignore a value the scheme does not define
        rec[f] = sorted(vals) if f in MULTI_FACTORS else vals[0]
        overridden.append(f)
    # GRCh37/GRCh38 are human assemblies, so a stated build is ignored on a non-human query.
    asm = context.get("assembly")
    asm = asm if (asm in ("GRCh37", "GRCh38") and rec.get("species") != "non-human") else None
    if asm:
        overridden.append("assembly")
    return rec, asm, overridden


# Priorities that justify interrupting the user: the RECOMMENDED bucket the user sees.
# A module constant so work/harness/suites/ask_rate.py can test a wider bar.
ASK_BAR_PRIORITIES = ("recommended",)


# Values of the form's single "Restrict results" drop-down. Each collapses the output (a leaked
# per_gene cut 334 transcript rows to 19; work/results/leak_rate_README.md). The priority table
# prices none of them for any tuple, but the model can propose them. Other unpriced options only add
# columns, so the gate covers this family alone. The eval harnesses score the raw parse and never
# see this gate.
RESTRICT_RESULTS_FAMILY = ("pick", "pick_allele", "per_gene", "most_severe", "summary")


def enforce_restrict_results_gate(enabled, resolved):
    """Remove restrict-results values the priority table does not price for this scenario.

    Mutates `enabled` and returns the removed ids. No-op when `resolved` is empty; a value the table
    prices for the scenario is kept."""
    if not resolved:
        return []
    removed = []
    for oid in RESTRICT_RESULTS_FAMILY:
        if oid in enabled:
            e, pri, _g = resolved.get(oid, (False, None, None))
            if not e and pri not in ("recommended", "optional"):
                enabled.discard(oid)
                removed.append(oid)
    return sorted(removed)


def factor_must_haves_at_stake(factor, factor_tuple, vep_options):
    """Return the ask-bar options whose presence depends on how this factor is answered.

    A question is raised only when this set is non-empty. Computed per query: the same factor can
    decide an option in one scenario and nothing in another."""
    try:
        values = load_factors()["factors"][factor]["values"]
    except Exception:
        return set()
    # A multi-select factor can be answered with every value, so compare the union too: the hard gate
    # removes an option only when every active value rules it out.
    candidates = [[v] if factor in MULTI_FACTORS else v for v in values]
    if factor in MULTI_FACTORS and len(values) > 1:
        candidates.append(list(values))
    seen = []
    for v in candidates:
        t = dict(factor_tuple)
        t[factor] = v
        resolved = resolve_for_query(t, vep_options)
        if not resolved:
            continue
        seen.append({oid for oid, (en, pr, _) in resolved.items()
                     if en and pr in ASK_BAR_PRIORITIES})
    at_stake = set()
    for i, a in enumerate(seen):
        for b in seen[i + 1:]:
            at_stake |= (a ^ b)
    return at_stake


OUT_OF_SCOPE_NOTE = (
    "  This assistant recommends Ensembl VEP options for a variant-annotation run, and your question\n"
    "  did not describe one. Tell it what you are annotating — the species, whether the variants are\n"
    "  germline or somatic, small or structural, and what you want out of the annotation — and it will\n"
    "  suggest a configuration."
)

# For a question about VEP that is not a configuration request (errors, output columns, installing).
VEP_SUPPORT_NOTE = (
    "  This assistant only recommends which Ensembl VEP options to switch on for a given analysis.\n"
    "  It does not diagnose errors, explain output columns, or help with installing or running VEP.\n"
    "  For those, see the Ensembl VEP documentation and the Ensembl helpdesk. If you do want a\n"
    "  configuration, describe what you are annotating and what you need out of it."
)


def states_nothing_about_variants(rec):
    """True when the classifier read none of the four non-species factors from the query.

    Species is skipped because it is often filled by the human default rather than read from text."""
    for f in FACTOR_VALUES:
        if f == "species":
            continue
        v = (rec or {}).get(f)
        if v if f in MULTI_FACTORS else (v not in (None, "unstated")):
            return False
    return True


ASSEMBLY_ASSUMED_WHY = ("the VEP web form serves GRCh38 and directs GRCh37 users to a separate site, so GRCh38 is assumed — say GRCh37 if that is your build")


def clarification_plan(rec, vep_options, user_query=None, assembly=None):
    """Decide per unanswered factor whether to assume it or ask. Takes the apply_defaults=False reading.

    Returns (filled_tuple, assumptions, questions). An unknown human build is added to `assumptions`
    as GRCh38. The CLI and try_reprompting.py both call this, so they agree."""
    # rec is None when the classifier output did not parse.
    if not rec:
        return dict(rec or {}), [], []
    # Checked before the assumptions fill the fields it examines.
    off_topic = states_nothing_about_variants(rec)
    stated = dict(rec)                           # what the USER said, before anything was assumed
    rec = dict(rec)
    assumptions, questions = [], []
    for f in FACTOR_VALUES:
        v = rec.get(f)
        answered = bool(v) if f in MULTI_FACTORS else (v not in (None, "unstated"))
        if answered:
            continue
        policy = UNDERSPECIFIED_POLICY.get(f, {})
        if policy.get("assume") is not None:
            rec[f] = list(policy["assume"]) if f in MULTI_FACTORS else policy["assume"]
            assumptions.append((f, rec[f], policy["why"]))
        else:
            questions.append((f, policy.get("why", ""), None))
    # Keep a question only if a must-have is at stake on the tuple after assumptions.
    scored = []
    for f, why, _ in questions:
        at_stake = factor_must_haves_at_stake(f, rec, vep_options)
        if at_stake:
            scored.append((f, why, sorted(at_stake)))
    # A query naming none of the scenario factors is off topic: no questions, and the caller says
    # what the tool is for. Assumptions still apply so a configuration can be produced.
    if off_topic:
        scored = []
    else:
        # Assembly is assumed GRCh38 and disclosed (David, 2026-09-15): the form serves GRCh38, and a
        # wrong GRCh38 guess costs one add-on against four recommendations for GRCh37.
        # assembly_question decides relevance; ask_rate.py patches it.
        for _f, _why, _at_stake in assembly_question(stated, vep_options, user_query, assembly):
            assumptions.append(("assembly", "GRCh38", ASSEMBLY_ASSUMED_WHY))
    return rec, assumptions, scored


def assembly_question(stated, vep_options, user_query=None, assembly=None):
    """Return [("assembly", why, at_stake)] if the build is unknown and matters, else [].

    Empty when the text or the user names a build, the query is non-human, or nothing
    assembly-restricted is at the ask bar. Scored on the stated tuple, so options added only by our
    own assumptions (gnomAD-SV via assumed "both" sizes) cannot trigger it."""
    if (assembly or infer_assembly(user_query)) is not None:
        return []
    if stated.get("species") == "non-human":
        return []
    # An empty goal resolves to a broken configuration (about 6 options against about 13), so score
    # with the basic-consequence fallback in its place.
    scenario = dict(stated)
    if not scenario.get("analysis_goal"):
        scenario["analysis_goal"] = ["basic-consequence"]
    at_stake = assembly_at_stake(scenario, vep_options)
    if not at_stake:
        return []
    return [("assembly",
             "you didn't say which genome assembly your data is on, and these options exist for only "
             "one of them",
             sorted(at_stake))]


# Plain-English labels for the interactive question. An unlabelled value falls back to its id.
_FACTOR_VALUE_LABELS = {
    ("origin", "germline"): "germline — inherited / constitutional",
    ("origin", "somatic"): "somatic — acquired, e.g. in a tumour",
    ("variant_size_class", "small"): "small variants — SNVs and indels",
    ("variant_size_class", "structural-CNV"): "structural variants — SVs and CNVs",
    ("region_focus", "coding"): "protein-coding regions",
    ("region_focus", "regulatory-noncoding"): "regulatory / non-coding regions",
    ("analysis_goal", "basic-consequence"): "a quick consequence call — what does the variant hit?",
    ("analysis_goal", "clinical-interpretation"): "clinical interpretation — is it pathogenic?",
    ("analysis_goal", "population-frequency"): "population frequencies — how common is it?",
}

_FACTOR_PROMPTS = {
    "origin": "Are these variants germline (inherited) or somatic (tumour)?",
    "variant_size_class": "Are these small variants (SNVs/indels) or structural changes (SVs/CNVs)?",
    "region_focus": "Do you care about protein-coding regions, regulatory/non-coding, or both?",
    "analysis_goal": "What are you after — a quick consequence call, clinical interpretation, "
                     "or population frequencies?",
}


def _ask_factor(factor):
    """Ask one factor question on the terminal. Returns the chosen value, or None to leave it open.

    Enter skips. Without a tty it returns None at once, so scripts never block."""
    try:
        values = load_factors()["factors"][factor]["values"]
    except Exception:
        return None
    if not sys.stdin.isatty():
        return None
    multi = factor in MULTI_FACTORS
    print(f"\n  {_FACTOR_PROMPTS.get(factor, factor)}")
    for i, v in enumerate(values, 1):
        print(f"    {i}) {_FACTOR_VALUE_LABELS.get((factor, v), v)}")
    if multi:
        # "both" fits only two values; analysis_goal has three.
        all_label = {2: "both", 3: "all three"}.get(len(values), f"all {len(values)}")
        print(f"    {len(values) + 1}) {all_label}")
        if len(values) > 2:                    # with two values, option 3 already IS "both"
            print(f"    (or several, e.g. 1,{len(values)})")
    print("    (enter to skip — it will be left open)")
    try:
        raw = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    # Several at once, for a multi-select factor: "1,3" or "1 3".
    if multi and any(sep in raw for sep in ",  "):
        picked = [values[int(t) - 1] for t in raw.replace(",", " ").split()
                  if t.isdigit() and 1 <= int(t) <= len(values)]
        if picked:
            return sorted(set(picked))
    if raw.isdigit():
        n = int(raw)
        if multi and n == len(values) + 1:
            return list(values)
        if 1 <= n <= len(values):
            return [values[n - 1]] if multi else values[n - 1]
    # Typed text: match the value id or its label, so "clinical" and "somatic" both work.
    low = raw.lower()
    match = [v for v in values
             if v.lower().startswith(low)
             or _FACTOR_VALUE_LABELS.get((factor, v), "").lower().startswith(low)]
    if len(match) == 1:
        return [match[0]] if multi else match[0]
    return None


# --- Assembly: not a factor, resolved the same way ---
# It describes the input data, so it stays out of factors.json. MANE, EVE, gnomAD-SV and MaveDB exist
# only for GRCh38; geno2mp only for GRCh37. The checker removes what the build cannot support.
_ASSEMBLY_VALUES = ("GRCh37", "GRCh38")


def assembly_at_stake(factor_tuple, vep_options):
    """Return the assembly-restricted options at the ask bar that this scenario switches on."""
    resolved = resolve_for_query(factor_tuple, vep_options)
    if not resolved:
        return set()
    restriction = {o.get("id"): o.get("assemblies") for o in vep_options}
    at_stake = set()
    for oid, (enabled, priority, _) in resolved.items():
        if not enabled or priority not in ASK_BAR_PRIORITIES:
            continue
        allowed = _assembly_restriction(restriction.get(oid))
        if allowed and set(allowed) != set(_ASSEMBLY_VALUES):
            at_stake.add(oid)
    return at_stake


def resolve_underspecified(rec, vep_options, mode="state", user_query=None, assembly=None):
    """Fill the factors the query left open. Returns (filled_tuple, assembly).

    mode: "assume" fills silently (scripts, eval harness); "state" fills and prints what was assumed
    (default); "ask" also prompts on a tty for open questions where the answer moves a must-have.
    assembly is 'GRCh37', 'GRCh38' or None; it sits beside the tuple because it describes the data.
    """
    filled, assumptions, questions = clarification_plan(rec, vep_options, user_query, assembly)
    off_topic = states_nothing_about_variants(rec)

    # Say what the tool is for before assuming anything about a query that describes no analysis.
    if mode != "assume" and off_topic:
        print()
        print(OUT_OF_SCOPE_NOTE)

    # A build named in the text goes into the return value for the checker.
    assembly = assembly or infer_assembly(user_query)

    if mode == "ask":
        for factor, _why, _delta in questions:
            answer = _ask_factor(factor)
            if answer is None:
                continue
            filled[factor] = answer
            # Echo the answer so a mistyped choice can be caught.
            print(f"    → using {', '.join(answer) if isinstance(answer, list) else answer}")

    def still_open(q):
        if q[0] == "assembly":
            return assembly is None
        v = filled.get(q[0])
        return (not v) or v in (None, "unstated")

    questions = [q for q in questions if still_open(q)]

    # An empty analysis_goal collapses the configuration (about 6 options against about 13), so fill
    # basic-consequence and disclose it, unless the policy already assumed a goal.
    if not filled.get("analysis_goal"):
        filled["analysis_goal"] = ["basic-consequence"]
        if not any(f == "analysis_goal" for f, _, _ in assumptions):
            assumptions.append(("analysis_goal", filled["analysis_goal"],
                                "nothing was said about the goal and a configuration cannot resolve "
                                "without one, so the baseline consequence call is used — say if you "
                                "are assessing pathogenicity or need population frequencies"))
        questions = [q for q in questions if q[0] != "analysis_goal"]

    # clarification_plan recorded any assumed build; copy it into the return value.
    if assembly is None:
        assembly = next((v for f, v, _w in assumptions if f == "assembly"), None)

    if mode != "assume" and (assumptions or questions):
        print()
        for factor, value, why in assumptions:
            shown = ", ".join(value) if isinstance(value, list) else value
            # Print the value only; the reason stays in `assumptions` for --explain and the JSON
            # (David, 2026-09-15).
            print(f"  Assumed {factor} = {shown}")
        for factor, why, at_stake in questions:
            names = ", ".join(at_stake) if at_stake else "part of the configuration"
            how = "run in a terminal to be prompted" if mode == "ask" else "--ask to be prompted"
            print(f"  Left open: {why} (decides {names}; {how}).")

    # Factors filled in rather than read. The `_` prefix makes active_values and the decision trace
    # skip it, like _request_type.
    filled["_assumed"] = sorted(f for f, _v, _w in assumptions)
    return filled, assembly


def describe_factors(factor_tuple):
    """Render a factor tuple one factor per line, for the prompt and the user-facing trace."""
    if not factor_tuple:
        return ""
    out = []
    for f in FACTOR_VALUES:
        v = factor_tuple.get(f)
        shown = ", ".join(v) if isinstance(v, list) else v
        out.append(f"- {f}: {shown or 'unstated'}")
    return "\n".join(out)


# --- Option extraction from free-text draft output (used by legacy/two_pass.py) ---


# --- Scope gate for the draft (--two-pass): did the model decline to configure? ---
# A declined draft has no configuration, so the audit, prose fallback and checker are skipped.
# The fallback regex is conservative so a rambling draft still gets its format warning.


# --- Constraint checker (runs after classification, before display) ---

# Conflict tie-break when priorities are equal: the higher number loses, because it suppresses
# more output.
_RESTRICTIVENESS = {
    "most_severe": 3,
    "pick": 2,
    "per_gene": 1,
}

# Keyword -> species for infer_species. Matched on word boundaries, so plurals need their own entry.
_SPECIES_KEYWORDS = {
    "mouse": "mouse",
    "mice": "mouse",
    "murine": "mouse",
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
    "cow": "cow", "cows": "cow", "cattle": "cow", "bovine": "cow", "bos taurus": "cow",
    "sheep": "sheep", "ovine": "sheep", "ovis": "sheep",
    "horse": "horse", "horses": "horse", "equine": "horse", "equus": "horse",
    "yeast": "yeast", "saccharomyces": "yeast",
    "rabbit": "rabbit", "rabbits": "rabbit",
}

# Positive human signals for infer_species. Substring match, checked after the non-human keywords,
# so 'mouse tumour' -> 'mouse'.
_HUMAN_SIGNALS = [
    "human", "homo sapiens", "h. sapiens", "patient", "clinical", "clinician",
    "proband", "mendelian", "rare disease", "rare-disease", "diagnos",
    "germline", "somatic", "tumour", "tumor", "cancer", "oncolog", "carcinoma",
    "gnomad", "clinvar", "cosmic", "acmg", "omim", "hgmd",
    "grch37", "grch38", "hg19", "hg38",
]


_SPECIES_INDEX = None


def _species_hint_on():
    """Whether the species-index hint block is appended to the classifier prompt.

    Off unless VEP_SPECIES_HINT=1. The block fires on almost every query, never raised species
    accuracy over the bare model, and pushed analysis_goal wrong on one review row."""
    return os.environ.get("VEP_SPECIES_HINT") == "1"


def species_key(production_name):
    """Strip a production name to genus_species (`ovis_aries_texel` -> `ovis_aries`).

    Data lists are per species; the index is per strain."""
    return "_".join((production_name or "").split("_")[:2])


def load_species_index():
    """The species-name index {name: {species, trap, english_word, ...}}, cached; {} if missing.

    Built by `work/harness/build/build_species_index.py`. Callers fall back to `_SPECIES_KEYWORDS`.
    """
    global _SPECIES_INDEX
    if _SPECIES_INDEX is None:
        p = BASE_DIR.parent / "work" / "generation" / "generation_config" / "species_index.json"
        try:
            _SPECIES_INDEX = json.loads(p.read_text())["names"]
        except Exception:                                                # noqa: BLE001
            _SPECIES_INDEX = {}
    return _SPECIES_INDEX


def species_candidates(user_query: str):
    """Every index species name in the query, longest first, each with its index entry.

    Longest first keeps `guinea pig` ahead of `pig`; a name inside a longer hit is skipped.
    """
    q = (user_query or "").lower()
    idx = load_species_index()
    hits = []
    for name in sorted(idx, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", q):
            if any(name in h["name"] and name != h["name"] for h in hits):
                continue                                   # already covered by a longer match
            hits.append({"name": name, **idx[name]})
    return hits


def format_species_hint(user_query: str) -> str:
    """The species hint block for the classifier prompt; empty when nothing matched."""
    hits = species_candidates(user_query)
    if not hits:
        return ""
    lines = ["\n\nA keyword scan of the question matched these Ensembl species names:"]
    for h in hits:
        why = []
        if h.get("trap"):
            why.append(f"often means {h['trap']}")
        elif h.get("english_word"):
            why.append("also an ordinary English word")
        if h.get("shadowed_by"):
            why.append(f"contains the shorter species name '{h['shadowed_by']}'")
        lines.append(f"  - \"{h['name']}\" -> {h['species']}"
                     + (f"   ({'; '.join(why)})" if why else ""))
    lines.append(
        "These are HINTS, not the answer. A match is frequently NOT the organism: it may be a gene "
        "or pathway (Sonic Hedgehog), a software tool (Platypus, Salmon, Manta), a country (Turkey), "
        "an idiom (\"rabbit hole\", \"used as a guinea pig\") or a clinical term. Judge from the whole "
        "question and say \"human\" for human data. Reject a match that does not fit.")
    return "\n".join(lines)


_WORD_TO_PRODUCTION = {"mouse": "mus_musculus", "rat": "rattus_norvegicus", "pig": "sus_scrofa",
                       "dog": "canis_lupus_familiaris", "zebrafish": "danio_rerio", "chicken": "gallus_gallus",
                       "cow": "bos_taurus", "sheep": "ovis_aries", "horse": "equus_caballus",
                       "yeast": "saccharomyces_cerevisiae", "rabbit": "oryctolagus_cuniculus",
                       "drosophila": "drosophila_melanogaster"}


def resolve_species_name(user_query: str):
    """Name-scan the query for an organism; return its Ensembl production name or None.

    Prefers a clean index hit, then any non-trap hit, then the keyword scan. Used only for data
    lookups once the species factor is non-human."""
    hits = species_candidates(user_query) or []
    for h in hits:
        if not h.get("trap") and not h.get("english_word"):
            return h["species"]
    for h in hits:
        if not h.get("trap"):
            return h["species"]
    return _WORD_TO_PRODUCTION.get(infer_species(user_query))


def resolve_model_organism(name):
    """Validate the classifier's `organism` answer against the species index; production name or None.

    An unrecognised name returns None, so the model cannot invent a species.
    """
    n = (name or "").strip().lower()
    if not n or n in ("unstated", "unknown", "none", "n/a"):
        return None
    idx = load_species_index() or {}
    by_production = {v["species"] for v in idx.values()}

    def canonical(prod):
        """`bos_taurus_wagyu` -> `bos_taurus` when the index also has the plain species."""
        base = species_key(prod)
        return base if base != prod and base in by_production else prod

    if n in idx:
        return canonical(idx[n]["species"])
    flat = re.sub(r"[\s-]+", "_", n)
    if flat in by_production:
        return canonical(flat)
    if flat in _WORD_TO_PRODUCTION:
        return _WORD_TO_PRODUCTION[flat]
    # Partial name ("sharksucker" for `live sharksucker`): accepted only when every matching index
    # name is one species, so "pig" (pig, guinea pig) stays ambiguous and returns None.
    if len(n) >= 4:
        hits = {canonical(v["species"]) for k, v in idx.items() if n in k or k in n}
        if len(hits) == 1:
            return hits.pop()
    if n in ("human", "humans", "homo sapiens", "patient", "people"):
        return "homo_sapiens"
    return None


def infer_species(user_query: str) -> str:
    """Keyword-scan the query for species: a non-human species word, 'human', or 'unknown'.

    A non-human keyword wins, then a human signal; otherwise 'unknown', which the checker flags
    and treats as human. Negation-blind and first-match only ('not a mouse study' -> 'mouse').
    """
    q = user_query.lower()
    for keyword, species in _SPECIES_KEYWORDS.items():      # word boundaries: no 'rat' in 'generated'
        if re.search(r"\b" + re.escape(keyword) + r"\b", q):
            return species
    for sig in _HUMAN_SIGNALS:
        if sig in q:
            return "human"
    return "unknown"


def _priority_rank(option_id: str, resolved) -> int:
    """RANK of an option's priority in this scenario's factor resolution, for conflict tie-breaks.

    0 when the table does not price the option or `resolved` is None."""
    if not resolved:
        return 0
    _e, pri, _g = resolved.get(option_id, (False, None, None))
    return RANK.get(pri, 0) if pri else 0


def species_phrase(opt) -> str:
    """Display text for an option's species reach, built from its `species` and `assemblies` fields."""
    sp = opt.get("species", "all")
    if sp == "all":
        return "all species"
    if sp == ["homo_sapiens"]:
        asm = opt.get("assemblies")
        return "human only" + (f" ({'+'.join(asm)})" if asm else "")
    return ", ".join(sp) + " only"


def _is_human_only(species) -> bool:
    """True if an option's `species` field ("all" or a list of production names) is human alone.

    Multi-species lists such as ["homo_sapiens", "mus_musculus"] return False.
    """
    return species == ["homo_sapiens"]


def _gates_nonhuman(species) -> bool:
    """True if the resolver should mark an option not_applicable for a non-human scenario.

    Also gates a two-species set that includes human (`var_synonyms` = human + pig), because the
    binary factor cannot name the organism. The checker's per-species lookup lets it back."""
    return species != "all" and "homo_sapiens" in species and len(species) <= 2


# Human build spellings -> canonical name. Keys are lower-cased and separator-stripped.
# Exact spellings only: GRCh37 and GRCh38 differ by one character, and a wrong build drops the
# other build's options.
_ASSEMBLY_ALIASES = {
    "grch37": "GRCh37", "hg19": "GRCh37",
    "grch38": "GRCh38", "hg38": "GRCh38",
}


def infer_assembly(query):
    """The human assembly the query names ('GRCh37'/'GRCh38'), or None.

    None when unstated: most queries name no assembly, and assuming one would strip options.
    """
    m = _ASSEMBLY_RE.search(query or "")
    if not m:
        return None
    token = re.sub(r"[\s_-]", "", m.group(1).lower())   # 'GRCh 38' / 'GRCh-38' -> 'grch38'
    return _ASSEMBLY_ALIASES.get(token)                 # non-human builds (GRCm39...) -> None


def _assembly_restriction(assemblies):
    """An option's `assemblies` field as a set, or None if it is not assembly-restricted."""
    return set(assemblies) if assemblies else None


def check_and_fix_violations(enabled: set, disabled: set, vep_options: list,
                             user_query: str,
                             assembly_override: str = None,
                             species_override: str = None,
                             resolved: dict = None,
                             organism: str = None) -> list[dict]:
    """Apply scenario, species, assembly, conflict and dependency rules to `enabled`; return violations.

    Mutates `enabled` and `disabled` in place; that is how the corrected set reaches the caller.
    Each violation dict has `type`, `reason`, and `option_disabled`, `option_enabled` or
    `option_kept` as applicable.
    """
    violations = []
    # --- Scenario gates: an option the factor table marks not_applicable is removed. ---
    # Catches gated options added by the model or a user. Includes region_focus removing missense
    # predictors from a regulatory query (round-1 review asked for them back; open in STATUS.md).
    # `verify_pipeline` asserts this never fires on the resolver's own configuration.
    if resolved:
        for oid in sorted(enabled):
            if resolved.get(oid, (False, None, False))[2]:
                violations.append({
                    "type": "scenario",
                    "option_disabled": oid,
                    "reason": f"'{oid}' is not applicable to this scenario's factors, so it is not offered",
                })
                enabled.discard(oid)
                disabled.add(oid)

    # Order: species, assembly, conflicts, then dependencies (auto-enable may re-introduce options).
    # A stated species overrides the text, as the assembly override does below.
    species = species_override or infer_species(user_query)

    conflicts_map = {}
    species_map = {}
    species_spec = {}
    assembly_map = {}
    depends_map = {}
    plugin_ids = {o["id"] for o in vep_options if option_source(o) == "plugin"}
    for opt in vep_options:
        conflicts_map[opt["id"]] = set(opt.get("conflicts_with", []))
        species_map[opt["id"]] = species_phrase(opt)                 # message text only
        species_spec[opt["id"]] = opt.get("species", "all")          # the gates read these two
        assembly_map[opt["id"]] = opt.get("assemblies")
        depends_map[opt["id"]] = list(opt.get("depends_on", []))

    # --- Species ---
    # Confirmed non-human: remove human-only options. 'unknown': keep them and warn, because many
    # human queries never say "human".
    if species == "unknown":
        violations.append({
            "type": "species",
            "reason": ("species not specified in the query — ASSUMING HUMAN and keeping human-only options "
                       "(CADD/gnomAD/ClinVar...). If this is a non-human sample, disable them."),
        })
    elif species != "human":
        # Plugins are skipped here and judged by Ensembl's plugin_config.txt species list below.
        for oid in list(enabled):
            if oid in plugin_ids:
                continue
            if _is_human_only(species_spec.get(oid, "all")):
                violations.append({
                    "type": "species",
                    "option_disabled": oid,
                    "reason": f"'{oid}' is restricted to {species_map[oid]} but this analysis is {species}",
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Species data (non-human only) ---
    # An option with a species list (SIFT, variant synonyms, per-species frequency files, plugins) is
    # removed when the organism is not on it. Lists come from each option's `species` field; source
    # in its `provenance`. An organism the index cannot resolve counts as having no such data.
    if species not in ("human", "unknown"):
        # The classifier's validated organism if given, else the name scan.
        sp_name = organism or resolve_species_name(user_query)
        for oid in list(enabled):
            spec = species_spec.get(oid, "all")
            if spec == "all":
                continue
            if oid in plugin_ids:
                allowed = spec
                if species_key(sp_name or "") in allowed:
                    continue
                _nm = next((o.get("name", oid) for o in vep_options if o["id"] == oid), oid)
                violations.append({
                    "type": "species_data",
                    "option_disabled": oid,
                    "reason": (f"{_nm} [{oid}] is provided for {len(allowed)} species "
                               f"({', '.join(allowed)}); this analysis is "
                               f"{species_key(sp_name) if sp_name else species}, which is not among "
                               f"them (VEP_plugins release/116 plugin_config.txt)"),
                })
                enabled.discard(oid)
                disabled.add(oid)
                continue
            # Native and custom options compare per species: `ovis_aries_texel` counts as `ovis_aries`.
            have_keys = {species_key(x) for x in spec}
            if sp_name is None or species_key(sp_name) not in have_keys:
                _nm = next((o.get("name", oid) for o in vep_options if o["id"] == oid), oid)
                violations.append({
                    "type": "species_data",
                    "option_disabled": oid,
                    "reason": (f"{_nm} [{oid}] is available for {len(have_keys)} species "
                               f"({', '.join(sorted(have_keys))}); this analysis is "
                               f"{species_key(sp_name) if sp_name else species}, which is not among them"),
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Assembly ---
    # Some sources exist for one build only (MANE, EVE: GRCh38; Geno2MP: GRCh37), and the web form
    # shows them for any human assembly (InputForm.pm:694-702). Gated only when a build is known.
    assembly = assembly_override or infer_assembly(user_query)
    if assembly:
        for oid in list(enabled):
            allowed = _assembly_restriction(assembly_map.get(oid))
            if allowed and assembly not in allowed:
                violations.append({
                    "type": "assembly",
                    "option_disabled": oid,
                    "reason": (f"'{oid}' has data for {'/'.join(sorted(allowed))} only, but this "
                               f"analysis is on {assembly}"),
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Conflicts ---
    checked_pairs = set()
    for oid_a in list(enabled):
        if oid_a not in enabled:          # lost an earlier pair
            continue
        for oid_b in list(enabled):
            if oid_a not in enabled:          # oid_a just lost; its remaining conflicts are moot
                break
            if oid_b not in enabled or oid_a == oid_b:
                continue
            pair = tuple(sorted([oid_a, oid_b]))
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)

            if oid_b in conflicts_map.get(oid_a, set()) or oid_a in conflicts_map.get(oid_b, set()):
                # Loser: lower resolved priority, then more restrictive, then alphabetical.
                rank_a = _priority_rank(oid_a, resolved)
                rank_b = _priority_rank(oid_b, resolved)

                if rank_a != rank_b:
                    loser = oid_a if rank_a < rank_b else oid_b
                    winner = oid_b if loser == oid_a else oid_a
                else:
                    rest_a = _RESTRICTIVENESS.get(oid_a, 0)
                    rest_b = _RESTRICTIVENESS.get(oid_b, 0)
                    if rest_a != rest_b:
                        loser = oid_a if rest_a > rest_b else oid_b
                        winner = oid_b if loser == oid_a else oid_a
                    else:
                        loser, winner = sorted([oid_a, oid_b])

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

    # --- Dependencies ---
    # Auto-enable a required option, unless it is human-only on a non-human query; then disable the
    # dependent instead. Re-scans until stable, so A->B->C resolves.
    # Known gap: an auto-enabled dependency is not re-checked for conflicts.
    changed = True
    while changed:
        changed = False
        for oid in list(enabled):
            for dep in depends_map.get(oid, []):
                if dep in enabled:
                    continue
                if species not in ("human", "unknown") and _is_human_only(species_spec.get(dep, "all")):
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
                break          # restart the scan: the set changed
            if changed:
                break

    return violations


def format_violation_warnings(violations: list[dict], reinstated=None) -> str:
    """Format checker violations as a warning block; empty string if there are none.

    `reinstated` is the final enabled set after the restore pass. A disabled option found in it is
    marked as reinstated, so this block agrees with the restore report printed below it.
    """
    if not violations:
        return ""

    lines = [
        "",
        "⚠️  CONSTRAINT VIOLATIONS DETECTED AND CORRECTED:",
    ]
    for v in violations:
        tag = v["type"].upper()
        back = (v.get("option_disabled") and reinstated is not None
                and v["option_disabled"] in reinstated)
        note = " (reinstated below — the option it conflicted with was itself removed)" if back else ""
        lines.append(f"  - {tag}: {v['reason']}{note}")
    lines.append("")
    return "\n".join(lines)


# A cli_flag listing several flags ("--refseq | --merged | --gencode_basic") is a pick-one menu.
# Needs more than one "--" separated by | or /, so a path ("--plugin X,/path/to/x") or a value
# placeholder ("--sift [b|p|s]") does not count as a menu.
_FLAG_ALT_SPLIT = re.compile(r"\s*[|/]\s*")


def cli_flags_for(enabled, vep_options):
    """Runnable, de-duplicated CLI flags for an enabled set, as (flags, choices).

    `choices` is a list of (option_id, [alternative flags]) for menu-style cli_flags, which the
    caller offers as a choice instead of putting in the command. Shared by both command builders.
    """
    flag_by_id = {o["id"]: (o.get("cli_flag") or "") for o in vep_options}
    flags, choices, seen = [], [], set()
    for oid in sorted(enabled):
        f = flag_by_id.get(oid, "").strip()
        if not f.startswith("--"):
            continue
        # "(+ ...)" lists sub-parameters used alongside the flag ("--check_frequency (+ --freq_pop/...)").
        # They need user values and are not alternatives, so only the leading flag is kept.
        head = f.split("(+", 1)[0].strip() if "(+" in f else f
        alts = re.findall(r"--[A-Za-z0-9_]+", head)
        # Menu check runs before the "no flag" skip: core_type's flag is a real menu that also says
        # "(no flag for core)" about its default.
        if len(alts) > 1 and _FLAG_ALT_SPLIT.search(head):
            choices.append((oid, alts))
            continue
        f = head
        # Derived options ride on another option's flag (clinvar -> check_existing).
        if "derived" in f or "no flag" in f:
            continue
        # "[b|p|s]" is a value placeholder. Replace it with the default from _SET_VALUE_DEFAULTS,
        # or drop it when there is none.
        if re.search(r"\[[^\]]*\|[^\]]*\]", f):
            default = _SET_VALUE_DEFAULTS.get(oid)
            f = re.sub(r"\s*\[[^\]]*\]", f" {default}" if default else "", f).strip()
        # A remaining parenthetical describes the data file to supply (gnomad_sv's "--custom (...)").
        # Emit the bare flag; the command's "fill in values/paths" note covers the rest.
        if "(" in f:
            f = f.split("(", 1)[0].strip()
        if f not in seen:            # two options can share one flag
            seen.add(f)
            flags.append(f)
    return flags, choices


def priority_table_covers(vep_options, table):
    """Ids in this catalogue that the priority table prices for no factor at all.

    The table is generated from one catalogue. Any missing id means the pair does not match, and a
    mismatched pair can silently drop a baseline option, so the check is exact."""
    return {o["id"] for o in vep_options} - set(table.get("priorities", {}))


def resolve_for_query(factor_tuple, vep_options, trace=None):
    """`intent_priorities()` for a factor tuple, or None if the tuple or the config is unusable.

    Every caller goes through here, so all of them see the same priorities for a scenario."""
    global _PRIORITY_TABLE_WARNED
    if not factor_tuple:
        return None
    try:
        table = load_priority_by_factor(vep_options)
        missing = priority_table_covers(vep_options, table)
        if missing:
            if not _PRIORITY_TABLE_WARNED:
                _PRIORITY_TABLE_WARNED = True
                print(f"\n  Note: the priority table does not cover {len(missing)} option(s) in this "
                      f"catalogue ({', '.join(sorted(missing)[:4])}"
                      f"{', …' if len(missing) > 4 else ''}), so importance tiers are switched off for "
                      f"this run.\n  They are generated together — point VEP_OPTIONS_FILE and "
                      f"VEP_PRIORITY_FACTOR_FILE at a matching pair to turn them back on.\n")
            return None
        return intent_priorities(factor_tuple, vep_options, table, load_factors(), trace=trace)
    except Exception:
        return None                              # config missing/unreadable -> caller falls back


# Plain English for a factor value in a "because …" line.
_WHY_VALUE = {
    ("species", "human"): "the samples are human",
    ("species", "non-human"): "the samples are not human",
    ("origin", "germline"): "the variants are germline",
    ("origin", "somatic"): "the variants are somatic",
    ("variant_size_class", "small"): "these are small variants",
    ("variant_size_class", "structural-CNV"): "these are structural variants",
    ("region_focus", "coding"): "you care about coding regions",
    ("region_focus", "regulatory-noncoding"): "you care about regulatory regions",
    ("analysis_goal", "basic-consequence"): "you want a basic consequence call",
    ("analysis_goal", "clinical-interpretation"): "you want clinical interpretation",
    ("analysis_goal", "population-frequency"): "you want population frequencies",
}


_ENSEMBL_PAGE = None


def ensembl_says(oid, vep_options):
    """One line of what the Ensembl docs say the option does, for --explain; None if nothing to say.

    Reads the saved release-116 options and plugins pages in `work/research/ensembl_docs_116/`.
    Prefers the page's "Output fields" cell. With no page record it falls back to our catalogue
    description, labelled "our catalogue"."""
    global _ENSEMBL_PAGE
    if _ENSEMBL_PAGE is None:
        _ENSEMBL_PAGE = {}
        docs = BASE_DIR.parent / "work" / "research" / "ensembl_docs_116"
        # Options page records are {flag, description, output_fields}; plugins page records are
        # {id, name, blurb}. Index both shapes.
        for fn in ("vep_options_parsed.json", "vep_plugins_parsed.json"):
            try:
                for rec in json.loads((docs / fn).read_text()):
                    for key in (rec.get("flag"), rec.get("key"), rec.get("id"), rec.get("name")):
                        if key:
                            _ENSEMBL_PAGE[str(key).lstrip("-").lower()] = rec
            except Exception:                                            # noqa: BLE001
                pass
    opt = next((o for o in vep_options if o["id"] == oid), None)
    if not opt:
        return None
    flag = (opt.get("cli_flag") or "").replace("--plugin", "").strip().lstrip("-").lower()
    rec = _ENSEMBL_PAGE.get(flag) or _ENSEMBL_PAGE.get(oid.lower())
    fields = (rec or {}).get("output_fields") or ""
    if fields:
        return f"Ensembl: adds {fields}"
    page_text = _first_sentence((rec or {}).get("description") or (rec or {}).get("blurb") or "", 150)
    if page_text:
        return f"Ensembl: {page_text}"
    # Our catalogue prose is agent-written and must never be labelled as Ensembl's.
    ours = _first_sentence(opt.get("description") or "", 150)
    return f"our catalogue: {ours}" if ours else None


def why_recommended(oid, trace):
    """One plain "because …" sentence for why this option is enabled, from the resolver's trace."""
    t = (trace or {}).get(oid) or {}
    win = t.get("winner")
    if not win:
        return None
    factor, value, _label = win
    if factor == "conditional rule":
        return f"because {value}"
    other = [v for f, v, _l in t.get("votes", []) if (f, v) != (factor, value)]
    also = f" (also under {', '.join(sorted(set(other))[:2])})" if other else ""
    return "because " + _WHY_VALUE.get((factor, value), f"{factor} = {value}") + also


def tier_by_importance(enabled, resolved):
    """Group the corrected set by this scenario's factor-table priority. Display only.

    Two tiers: `recommended` and `optional` (add-ons). The name "recommended" is Nakib's: the user
    still has to switch these on. Returns a dict of four sorted lists:
      recommended     enabled, rated `recommended`
      addons_on       enabled, rated `optional`
      unpriced        enabled, priced for no factor here (output/compute controls)
      addons_offered  rated `optional`, not enabled, not hard-gated
    """
    out = {"recommended": [], "addons_on": [], "unpriced": [], "addons_offered": []}
    for oid in sorted(enabled):
        _, priority, _ = resolved.get(oid, (False, None, False))
        if priority == "recommended":
            out["recommended"].append(oid)
        elif priority == "optional":
            out["addons_on"].append(oid)
        else:
            out["unpriced"].append(oid)
    for oid, (_, priority, gated) in sorted(resolved.items()):
        if priority == "optional" and not gated and oid not in enabled:
            out["addons_offered"].append(oid)
    return out


def option_source(opt):
    """'plugin', 'custom' or 'native', read off the option's cli_flag (`--plugin X`, `--custom ...`)."""
    flag = opt.get("cli_flag") or ""
    return "plugin" if flag.startswith("--plugin") else "custom" if flag.startswith("--custom") else "native"


def display_flag(flag):
    """An option's CLI flag as shown in a listing.

    A derived option (ClinVar comes with `--check_existing`) shows "(comes with <flag>)" so the same
    flag does not appear twice."""
    if "derived" in (flag or "").lower():
        base = flag.split("(")[0].strip()
        return f"(comes with {base})" if base else "(no flag of its own)"
    return flag or ""


def apply_config_level(enabled, disabled, resolved, level, vep_options, user_query,
                       assembly_override=None, species_override=None, organism=None):
    """Narrow (--minimal) or widen (--full) the corrected set in place, then re-run the checker.

    minimal keeps only `recommended` options; standard changes nothing; full adds every ungated
    `recommended` or `optional` option. The re-check restores dependencies and resolves conflicts.
    Returns the ids removed: by narrowing, or add-ons the re-check dropped under --full."""
    if level == "minimal":
        keep = {oid for oid in enabled if resolved.get(oid, (False, None, False))[1] == "recommended"}
        removed = set(enabled) - keep
        enabled.clear()
        enabled.update(keep)
    elif level == "full":
        removed = set()
        # Add `recommended` too, so meta-predictors (REVEL, ClinPred) never ship without the
        # predictors they derive from.
        enabled.update(oid for oid, (_, priority, gated) in resolved.items()
                       if priority in ("recommended", "optional") and not gated)
        # Snapshot so add-ons the re-check removes (e.g. most_severe losing a conflict) are reported.
        before = set(enabled)
    else:
        return set()
    check_and_fix_violations(enabled, disabled, vep_options, user_query,
                             assembly_override=assembly_override,
                             species_override=species_override, resolved=resolved, organism=organism)
    if level == "full":
        return before - set(enabled)
    return removed - set(enabled)          # a dep the re-check restored was not really removed


def restore_missing_recommended(enabled, disabled, resolved, vep_options, user_query,
                                assembly_override=None, species_override=None, violations_out=None,
                                organism=None):
    """Switch on every ungated `recommended` option not yet enabled, then re-run the checker.

    Returns the ids that are still enabled after the re-check. `violations_out`, if given, receives
    the re-check's violations. On the single-pass default the set starts empty, so this re-check is
    where every gate removal happens.
    """
    if not resolved:
        return []
    missing = sorted(oid for oid, (_en, priority, gated) in resolved.items()
                     if priority == "recommended" and not gated and oid not in enabled)
    if not missing:
        return []
    enabled.update(missing)
    for oid in missing:
        disabled.discard(oid)
    # Pass the same assembly as the first check, or a gated option (MANE on GRCh37) comes back.
    v2 = check_and_fix_violations(enabled, disabled, vep_options, user_query,
                                  assembly_override=assembly_override,
                                  species_override=species_override, resolved=resolved,
                                  organism=organism)
    if violations_out is not None:
        violations_out.extend(v2)
    return [oid for oid in missing if oid in enabled]


def format_restored_recommended(restored, vep_options):
    """Report the options restore_missing_recommended added; empty string if none."""
    if not restored:
        return ""
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    lines = ["", f"RECOMMENDED OPTIONS, FROM THE PRIORITY TABLE ({len(restored)}):",
             "   The factor table recommends these for this scenario, so they were added back:"]
    lines += [f"     + {name_by_id.get(oid, oid)} [{oid}]" for oid in restored]
    lines.append("")
    return "\n".join(lines)


# CONFIG_SECTIONS id -> the label on the form's collapsible section toggle (live form, 2026-09-08).
# These are the six toggles, one level above the h2 sub-headings inside them.
_WEB_SECTION_LABELS = {
    "identifiers": "Identifiers", "variants_frequency_data": "Variants and frequency data",
    "additional_annotations": "Additional annotations", "predictions": "Predictions",
    "filters": "Filtering options", "advanced": "Advanced options"}

# Sections the form splits into boxes (Additional annotations: 7, Predictions: 3). For these the
# location also names the box.
_SPLIT_SECTIONS = frozenset({"additional_annotations", "predictions"})


def form_location(opt):
    """Where an option sits on the web form, in the form's own words.

    Source: research/ensembl_docs_116/form_layout_live.json (live release-116 form).

        MANE          -> "Additional annotations › Transcript annotation"
        HGVS          -> "Identifiers section"
        core_type     -> "top of the form, beside the input"
    """
    sec = opt.get("web_form_section") or ""
    if sec == "input":
        return "top of the form, beside the input"
    label = _WEB_SECTION_LABELS.get(sec, "")
    if not label:
        return ""
    sub = opt.get("web_form_subsection")
    if sec in _SPLIT_SECTIONS and sub:
        return f"{label} › {sub}"
    return f"{label} section"


# Form boxes whose members are interchangeable tools. Enabled members render as one line per box
# (recommend the type of tool, not one tool: Likhitha, round 2 item 11), labelled with the form's
# box name (David, 2026-09-15). Display only: the enabled set and the command are unchanged.
TYPE_GROUPED_BOXES = ("Pathogenicity predictions", "Splicing predictions")


def format_corrected_config(enabled, vep_options, violations, resolved=None,
                            reason_by_id=None, restored=(), size_value=None, assembly=None,
                            meta_notes=False, show_cli=True, species=None, show_optional=True):
    """Render the final configuration the user applies: web-form lists, then the CLI command if asked.

    `enabled` is the set already repaired by check_and_fix_violations. With `resolved`, options are
    grouped by priority; without it, a flat list is printed.
    """
    flag_by_id = {o["id"]: o.get("cli_flag", "") for o in vep_options}
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    on = sorted(enabled)
    lines = ["", "=" * 60,
             "  YOUR VEP CONFIGURATION"]
    # Count removals and restores together.
    n_fixed = len(violations) + len(restored)
    if n_fixed:
        parts = []
        if violations:
            parts.append(f"{len(violations)} removed or resolved")
        if restored:
            parts.append(f"{len(restored)} added back")
        hint = "" if meta_notes else "  --explain shows how"
        lines.append(f"  (the checker resolved {n_fixed} thing"
                     f"{'s' if n_fixed != 1 else ''}: {', '.join(parts)}){hint}")
    lines.append("=" * 60)
    if resolved:
        tiers = tier_by_importance(enabled, resolved)
        # Two sections: everything switched on (one list, matching the command), then OPTIONAL.
        core = set(tiers["recommended"]) | set(tiers["unpriced"])
        extra = set(tiers["addons_on"])
        switch_on = sorted(core | extra)
        # Options the form ships ticked move to a closing "already on" line (mentor, 2026-09-13).
        # `enabled` keeps them, so the CLI command still carries them. Species-aware.
        already_on = {oid for oid in switch_on if _form_default_on(oid, vep_options, species)}
        switch_on = [oid for oid in switch_on if oid not in already_on]
        # Web-form names and locations here; flags appear only in the CLI block (mentor, 2026-09-07).
        sect_by_id = {o["id"]: form_location(o) for o in vep_options}
        defval_by_id = {o["id"]: o.get("web_default_value") for o in vep_options}
        box_by_id = {o["id"]: o.get("web_form_subsection") for o in vep_options}
        sec_label_by_id = {o["id"]: (f"{_WEB_SECTION_LABELS[o['web_form_section']]} section"
                                     if o.get("web_form_section") in _WEB_SECTION_LABELS else "")
                           for o in vep_options}
        dep_by_id = {o["id"]: o.get("deprecated") for o in vep_options}
        unpriced = set(tiers["unpriced"])
        # An unpriced member stays on its own line so its "model-suggested" tag is shown.
        grouped_on = {oid for oid in switch_on
                      if box_by_id.get(oid) in TYPE_GROUPED_BOXES and oid not in unpriced}
        grouped_boxes = {box_by_id[oid] for oid in grouped_on}
        grouped_offered = {oid for oid in tiers["addons_offered"]
                           if box_by_id.get(oid) in grouped_boxes}
        if switch_on:
            lines.append(f"RECOMMENDED — set these on the VEP web form  [{len(switch_on)}]")
            for oid in switch_on:
                if oid in grouped_on:
                    continue
                # Tag options the table does not price here, so they do not look like table picks.
                tag = ("   (add-on)" if oid in extra else
                       "   (model-suggested)"
                       if oid in unpriced else "")
                where = f"   ({sect_by_id[oid]})" if sect_by_id.get(oid) else ""
                dep = (f"   (deprecated — {dep_by_id[oid].split(';')[0]})"
                       if dep_by_id.get(oid) else "")
                lines.append(f"  {name_by_id.get(oid, oid)}{where}{tag}{dep}")
                # A radiolist recommended at its default: tell the user to leave it.
                if oid == "core_type" and (defval_by_id.get(oid) or "core") == "core":
                    lines.append("      keep the form's default: Ensembl/GENCODE transcripts")
                if oid in ("pick", "pick_allele", "per_gene", "most_severe", "summary"):
                    lines.append(f"      set the 'Restrict results' drop-down to: {oid}")
                # The model's per-option prose (--two-pass) shows only under --explain.
                if meta_notes and (reason_by_id or {}).get(oid):
                    lines.append(f"      {reason_by_id[oid]}")
                # A drop-down whose value depends on variant size (e.g. which CADD file).
                _choice, _ = size_dependent_choice(oid, size_value, vep_options, assembly)
                if _choice:
                    lines.append(f"      drop-down: {_choice}")
            # One line per grouped box, after the single options.
            for box in TYPE_GROUPED_BOXES:
                label = box
                on_members = [oid for oid in switch_on if oid in grouped_on
                              and box_by_id.get(oid) == box]
                if not on_members:
                    continue
                off_members = [oid for oid in sorted(tiers["addons_offered"])
                               if box_by_id.get(oid) == box]
                # The line names the box, so the bracket gives only the section.
                sect = next((sec_label_by_id.get(oid) for oid in on_members
                             if sec_label_by_id.get(oid)), "")
                for_clause = (f" for {species}" if species and species != "unknown" else "")
                if assembly:
                    for_clause += f" ({assembly})"
                picked = ", ".join(name_by_id.get(o, o) for o in on_members)
                lines.append(f"  {label}: {picked}" + (f"   ({sect})" if sect else ""))
                # Under --explain, also list the unselected members; selected ones are starred.
                if meta_notes:
                    listing = ", ".join([f"{name_by_id.get(o, o)}*" for o in on_members]
                                        + [name_by_id.get(o, o) for o in off_members])
                    lines.append(f"      supported in Ensembl VEP{for_clause}: {listing}")
                    lines.append("      * recommended here — any subset works; leaving the choice "
                                 "alone keeps all of them")
                for oid in on_members:
                    _choice, _ = size_dependent_choice(oid, size_value, vep_options, assembly)
                    if _choice:
                        lines.append(f"      {name_by_id.get(oid, oid)} drop-down: {_choice}")
        else:
            lines.append("RECOMMENDED: (none)")
        offered = sorted(set(tiers["addons_offered"]) - grouped_offered)
        already_on |= {oid for oid in offered if _form_default_on(oid, vep_options, species)}
        offered = [oid for oid in offered if oid not in already_on]
        if offered and show_optional:
            lines.append("")
            lines.append(f"OPTIONAL  [{len(offered)}]")
            lines.extend((f"  {name_by_id.get(oid, oid)}"
                          + (f"   ({sect_by_id[oid]})" if sect_by_id.get(oid) else "")
                          + (f"   (deprecated — {dep_by_id[oid].split(';')[0]})"
                             if dep_by_id.get(oid) else ""))
                         for oid in offered)
        if already_on:
            lines.append("")
            lines.append(f"ALREADY ON when the form loads — leave ticked  [{len(already_on)}]")
            lines.append("  " + ", ".join(name_by_id.get(oid, oid) for oid in sorted(already_on)))
        if meta_notes:
            # --explain only (mentor, 2026-09-07).
            lines.append("")
            lines.append("  The recommended/add-on split comes from the PROVISIONAL factor priority "
                         "table — VEP itself ranks nothing.")
    else:
        lines.append("ENABLE:")
        for oid in on:
            lines.append(f"  ✓ {name_by_id.get(oid, oid)} [{oid}] "
                         f"{display_flag(flag_by_id.get(oid, ''))}".rstrip())
        if not on:
            lines.append("  (none)")
    flag_list, choices = cli_flags_for(on, vep_options)
    if not show_cli:
        # Web form only by default (mentor, 2026-09-07); --cli adds the command.
        lines.append("=" * 60)
        return "\n".join(lines)
    lines.append("")
    lines.append("CLI EQUIVALENT — the same configuration as one command (fill in values/paths):")
    lines.append(f"  vep --input_file <in.vcf> --output_file <out.txt> --cache "
                 f"{' '.join(flag_list)}".rstrip())
    for oid, alts in choices:
        lines.append(f"  # {name_by_id.get(oid, oid)} [{oid}] — choose ONE: {' | '.join(alts)}")
    lines.append("=" * 60)
    return "\n".join(lines)


# --- Web-form control values -----------------------------------------------------------------

# Default values for native non-checkbox controls (InputForm.pm web defaults). Also fills
# "[b|p|s]"-style placeholders in cli_flags_for. `core_type` is handled separately.
_SET_VALUE_DEFAULTS = {
    "sift": "b", "polyphen": "b", "check_existing": "yes", "shift_3prime": "shift_3prime",
    "distance": "1000", "buffer_size": "5000", "frequency": "common",
}


_ASSEMBLY_RE = re.compile(r"\b(GRCh[\s_-]?3[78]|hg38|hg19|GRCm39|GRCm38|GRCz11|Rnor_6\.0|mRatBN7\.2)\b",
                          re.IGNORECASE)


def _first_sentence(text: str, limit: int = 240) -> str:
    """First sentence of `text`, ending in a period, cut to `limit` characters."""
    text = (text or "").strip()
    if not text:
        return ""
    head = text.split(". ")[0].strip()
    return (head if head.endswith(".") else head + ".")[:limit]


def build_explain_result_prompt(consequences):
    """Build system prompt for the VEP output explainer mode."""
    consequence_text = []
    for term, info in consequences.items():
        if term.startswith("_"):      # metadata keys such as `_source`
            continue
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


# --- Decision trace --------------------------------------------------------

def print_decision_trace(user_query, vep_options, factor_tuple=None):
    """Print, for --explain, why each option is recommended, offered, gated or unpriced."""
    print("=" * 60)
    print("  DECISION TRACE (--explain mode)")
    print("=" * 60)
    print(f"Query: \"{user_query}\"")
    print("--- Layer 2: Why each option is where it is ---")
    if factor_tuple is None:
        print("  (needs the query's factor tuple; run without --explain-only, or pass one in)\n")
        print("=" * 60)
        return
    # `_`-prefixed keys are metadata (e.g. _request_type), not factors.
    _shown = ", ".join(f"{k}={v}" for k, v in sorted(factor_tuple.items())
                       if v and not k.startswith("_"))
    print(f"Factors read from the query: {_shown}\n")

    tr = {}
    intent_priorities(factor_tuple, vep_options, load_priority_by_factor(vep_options),
                      load_factors(), trace=tr)
    # `provenance` records each field's source; show the one for the description.
    prov = {o["id"]: (o.get("provenance") or {}).get("description", "") for o in vep_options}

    on = sorted(o for o, t in tr.items() if t["priority"] == "recommended")
    add = sorted(o for o, t in tr.items() if t["priority"] == "optional")
    gated = sorted(o for o, t in tr.items() if t["gated_by"])

    print(f"RECOMMENDED  [{len(on)}]")
    for oid in on:
        t = tr[oid]
        w = t["winner"]
        print(f"  ✓ {oid:20s} because {w[0]}={w[1]}" if w else f"  ✓ {oid:20s}")
        others = [v for v in t["votes"] if v is not w]
        if others:
            print(f"    {'':20s} also raised by "
                  + "; ".join(f"{f}={v} ({l})" for f, v, l in others))
        if prov.get(oid):
            print(f"    {'':20s} description from: {prov[oid][:88]}")

    print(f"\nADD-ONS — offered, off by default  [{len(add)}]")
    for oid in add:
        w = tr[oid]["winner"]
        print(f"  + {oid:20s} because {w[0]}={w[1]}" if w else f"  + {oid:20s}")

    print(f"\nREMOVED by a hard gate  [{len(gated)}]")
    for oid in gated:
        print(f"  ✗ {oid:20s} "
              + "; ".join(f"{f} is {'/'.join(vals)}" for f, vals in tr[oid]["gated_by"]))

    unpriced = sorted(o for o, t in tr.items()
                      if t["priority"] is None and not t["gated_by"])
    if unpriced:
        print(f"\nNO RULE PRICES THESE for this scenario  [{len(unpriced)}]")
        print("  " + ", ".join(unpriced))

    print()
    print("=" * 60)
    print()


# --- Result saving ---

def save_result(query, response, mode="recommend", warnings="", reasoning=""):
    """Write the query, response, checker warnings and model reasoning to a markdown file.

    mode is 'recommend' or 'explain'. The directory is VEP_RESULTS_DIR, else BASE_DIR/results.
    """
    # Microsecond timestamp so two runs in the same second do not overwrite each other.
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
            if reasoning:
                f.write(f"\n## Model reasoning\n\n```\n{reasoning}\n```\n")
        print(f"\nResult saved to: {filename}")
    except OSError as e:
        print(f"\nWarning: Could not save result to {filename}: {e}")


# --- LLM streaming ---

# One budget covers reasoning plus answer (measured ~1300-1700 + ~1100 tokens), with headroom because
# reasoning length varies run to run.
_STREAM_MAX_TOKENS = 8192


def _delta_reasoning(delta):
    """Return the reasoning fragment in a stream delta, across the field names different servers use."""
    for attr in ("reasoning", "reasoning_content"):
        val = getattr(delta, attr, None)
        if val:
            return val
    return None


# --- Draft path (legacy/two_pass.py) ---
# Loaded only for --two-pass, or when a harness calls a draft helper by name.
_TWO_PASS = None


def _two_pass():
    """Import legacy/two_pass.py on first use, bind it to this module's globals, and return it."""
    global _TWO_PASS
    if _TWO_PASS is None:
        import importlib
        legacy_dir = str(BASE_DIR / "legacy")
        if legacy_dir not in sys.path:
            sys.path.insert(0, legacy_dir)
        _TWO_PASS = importlib.import_module("two_pass")
        _TWO_PASS._bind(globals())            # not sys.modules: genlib loads this file by path, unregistered
    return _TWO_PASS


# Names defined in legacy/two_pass.py that harnesses still reach as `va.<name>`.
_LEGACY_NAMES = {
    "build_option_aliases", "_match_option", "format_marker_overrides", "extract_recommendations_detailed",
    "extract_recommendations", "build_recommendation_json", "tier_options", "build_system_prompt",
    "_get_semantic_model", "_get_corpus_embeddings", "_get_options_embeddings",
}


def __getattr__(name):
    if name in _LEGACY_NAMES:
        return getattr(_two_pass(), name)
    raise AttributeError(f"module 'vep_assistant' has no attribute {name!r}")


def stream_response(client, model, system_prompt, user_message):
    """Stream an LLM call; return (answer_text, reasoning_text).

    Sets no temperature, so Ollama's default applies and output is nondeterministic.
    """
    response_text, reasoning_text = "", ""
    answering = False
    _tty = sys.stdout.isatty()
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=_STREAM_MAX_TOKENS,
        stream=True,
        # Keep the model resident between calls, so a second query pays no reload.
        extra_body={"keep_alive": KEEP_ALIVE},
    )
    for chunk in stream:
        if not chunk.choices:                      # usage-only chunks carry no choices
            continue
        delta = chunk.choices[0].delta
        thought = _delta_reasoning(delta)
        if thought and not answering:
            reasoning_text += thought
            # Live counter on a terminal only: off a tty `\r` does not overwrite, so every update
            # would pile up in the output.
            if _tty:
                print(f"\r  thinking… {len(reasoning_text) // 4} tokens", end="", flush=True)
        if delta.content:
            if reasoning_text and not answering:
                print((f"\r  thought for ~{len(reasoning_text) // 4} tokens" + " " * 24) if _tty
                      else f"  (thought for ~{len(reasoning_text) // 4} tokens)")
            answering = True
            response_text += delta.content
            # The draft is not printed: it is pre-checker, so it can disagree with the final
            # configuration. A counter shows the call is alive.
            if _tty:
                print(f"\r  drafting… {len(response_text) // 4} tokens", end="", flush=True)
    if _tty and answering:
        print("\r" + " " * 40 + "\r", end="", flush=True)
    if reasoning_text and not response_text:
        # Say so: an empty answer would otherwise read as "the model recommended nothing".
        print(f"\r  the model spent its entire generation budget (~{len(reasoning_text) // 4} tokens) "
              f"reasoning and produced no answer." + " " * 8)
    print()
    return response_text, reasoning_text


# --- CLI entry points ---

_CONTEXT_FLAGS = {"--species": "species", "--origin": "origin",
                  "--size": "variant_size_class", "--assembly": "assembly"}
_CONTEXT_CHOICES = {"assembly": ["GRCh37", "GRCh38"]}


def _parse_context_flags(args):
    """Read --species/--origin/--size/--assembly from argv. Returns (context, error_or_None).

    Values are validated so a typo fails loudly instead of being silently ignored."""
    ctx = {}
    for i, a in enumerate(args):
        key = _CONTEXT_FLAGS.get(a.split("=", 1)[0])
        if not key:
            continue
        val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else "")
        allowed = _CONTEXT_CHOICES.get(key) or FACTOR_VALUES.get(key, [])
        if key == "assembly":
            # Accept the same aliases (hg19/hg38, any casing) the prose reader accepts.
            val = _ASSEMBLY_ALIASES.get(re.sub(r"[\s_-]", "", val.lower()), val)
        elif key in MULTI_FACTORS:
            # A multi-select factor takes `both`, or values joined with + or comma
            # (e.g. `small+structural-CNV` for a WGS callset).
            parts = allowed if val.lower() == "both" else re.split(r"[+,]", val)
            vals = [next((v for v in allowed if v.lower() == x.strip().lower()), x.strip())
                    for x in parts if x.strip()]
            bad = [x for x in vals if x not in allowed]
            if bad or not vals:
                return None, (f"{a.split('=')[0]} must be one or more of: {', '.join(allowed)} "
                              f"(joined with +), or 'both'"
                              + (f" (got {val!r})" if val else " (no value given)"))
            ctx[key] = vals
            continue
        else:
            val = next((v for v in allowed if v.lower() == val.lower()), val)
        if val not in allowed:
            return None, (f"{a.split('=')[0]} must be one of: {', '.join(allowed)}"
                          + (f" (got {val!r})" if val else " (no value given)"))
        ctx[key] = val
    return ctx, None


def run_recommend(client, model, vep_options, training_examples, user_query,
                  explain=False, level="standard", factor_think=False, clarify="ask", context=None,
                  show_cli=False, single_pass=True):
    """Classify the query, resolve and check the options, print the web-form configuration and save it.

    level: "minimal" (only the options you must tick), "standard" (default), or "full" (every add-on).
    `training_examples` and `single_pass=False` serve only the --two-pass draft call (legacy/two_pass.py).
    """
    # Printed first because classification is the slowest silent step; the elapsed time is the
    # progress indicator.
    print("Reading the scenario…", end="", flush=True)
    t_classify = time.perf_counter()
    factor_tuple = infer_factors(client, model, user_query, think=factor_think, apply_defaults=False)
    t_classify = time.perf_counter() - t_classify
    print(f" {t_classify:.1f}s")

    # Scope is decided by the classifier, before any defaults are assumed or questions asked.
    # A factor tuple alone cannot tell "hi" from "annotate my VCF".
    request_type = (factor_tuple or {}).get("_request_type", "configure")
    if request_type != "configure":
        print()
        print(OUT_OF_SCOPE_NOTE if request_type == "not-vep" else VEP_SUPPORT_NOTE)
        print()
        return

    # Values the user stated on the form or command line replace the classifier's reading.
    factor_tuple, assembly, overridden = apply_user_context(factor_tuple, context)
    if overridden:
        print(f"  Using what you told me for: {', '.join(overridden)}.")

    if factor_tuple:
        # `assembly` is passed in so a stated assembly is never asked for again.
        factor_tuple, assembly = resolve_underspecified(factor_tuple, vep_options, clarify,
                                                        user_query=user_query, assembly=assembly)
        print("Detected scenario:")
        print(describe_factors(factor_tuple))
        print()

    # After resolve_underspecified, so the trace explains the filled-in tuple the run actually uses.
    if explain:
        print_decision_trace(user_query, vep_options, factor_tuple=factor_tuple)

    # The default makes no draft: the checker builds the configuration from the factor table.
    # --two-pass also asks the model for a draft first (legacy/two_pass.py).
    if single_pass:
        response_text, reasoning_text, t_recommend = "", "", 0.0
    else:
        response_text, reasoning_text, t_recommend = _two_pass().draft(
            client, model, vep_options, training_examples, user_query, factor_tuple)

    if explain:
        print(f"\n[{t_classify:.1f}s reading · {t_recommend:.1f}s analysing · "
              f"{t_classify + t_recommend:.1f}s total]")

    if single_pass:
        diagnostics, _recs, enabled, disabled = [], [], set(), set()
        audit_report, override_report = "", ""
    else:
        parsed = _two_pass().parse_draft(response_text, reasoning_text, vep_options, user_query)
        if parsed is None:                       # the model declined; parse_draft printed and saved it
            return
        diagnostics, _recs, enabled, disabled, audit_report, override_report = parsed
    # Every checker call below takes `assembly_override=assembly`. Without it the checker reads the
    # build from the prose only and ignores --assembly.
    species_stated = (context or {}).get("species") or None
    # The checker gets the tuple's species (human or non-human) rather than its own keyword scan;
    # --species wins when given.
    _tuple_species = (factor_tuple or {}).get("species")
    species_for_checker = species_stated or (_tuple_species if _tuple_species in ("human", "non-human") else None)
    # The organism name, used for the species-data lookups and the already-on list.
    if species_for_checker == "human":
        species_for_display = "human"
    else:
        # Only once the tuple says non-human. The classifier's `organism` comes before the name scan,
        # which takes the first organism named ("not a mouse study ... pig herd" gives mouse).
        species_for_display = (species_stated
                               or (factor_tuple or {}).get("_organism")
                               or resolve_species_name(user_query)
                               or species_for_checker or "human")
    # The checker's species-data gate needs a production name, never the binary value.
    organism_for_checker = (species_for_display
                            if species_for_display not in ("human", "non-human") else None)
    # One VEP run per variant size: the form cannot express both sizes at once (see size_passes).
    passes = size_passes(factor_tuple)
    if len(passes) > 1:
        how = ("both variant sizes assumed"
               if "variant_size_class" in (factor_tuple or {}).get("_assumed", [])
               else "this callset has both variant sizes")
        print(f"\nTWO VEP RUNS — {how}. Run VEP once per size, with the settings below.")
    reports = []
    for _i, (size_value, pass_label, pass_tuple) in enumerate(passes, 1):
        # Each pass gets its own copies: the checker repairs the sets in place.
        p_enabled, p_disabled = set(enabled), set(disabled)
        if len(passes) > 1:
            header = f"\n{'─' * 60}\nPASS {_i} of {len(passes)} — {pass_label}\n{'─' * 60}"
            print(header)
            reports.append(header)
        # Resolved before the checker, which enforces the scenario's gates.
        why_trace = {} if explain else None
        resolved = resolve_for_query(pass_tuple, vep_options, trace=why_trace)
        violations = check_and_fix_violations(
            p_enabled, p_disabled, vep_options, user_query,
            assembly_override=assembly,
            species_override=species_for_checker, resolved=resolved,
            organism=organism_for_checker,
        )
        # Restore must-haves before the level flags, so --minimal and --full start from a complete core.
        restored = restore_missing_recommended(p_enabled, p_disabled, resolved, vep_options,
                                            user_query,
                                            assembly_override=assembly,
                                            species_override=species_for_checker,
                                            violations_out=violations,
                                            organism=organism_for_checker)
        # After the restore, so the restore cannot put a dropped option back.
        for oid, why in drop_unavailable_size_values(p_enabled, vep_options, size_value, assembly):
            line = f"  Dropped {oid} on this pass: {why}."
            print(line)
            reports.append(line)
        # Formatted after the restore so the report can name the options that came back.
        pass_warnings = format_violation_warnings(violations, reinstated=set(p_enabled))
        if pass_warnings:
            diagnostics.append(pass_warnings)
        # Species-data removals are always shown, so the user learns what is unavailable for their species.
        _sd = [v["reason"] for v in violations if v.get("type") == "species_data"]
        if _sd:
            print("\nNOT AVAILABLE FOR THIS SPECIES:")
            for _r in _sd:
                print(f"  - {_r}")
        restored_report = format_restored_recommended(restored, vep_options)
        if restored_report:
            diagnostics.append(restored_report)
        if resolved and level != "standard":
            removed = apply_config_level(p_enabled, p_disabled, resolved, level, vep_options,
                                         user_query,
                                         assembly_override=assembly,
                                         species_override=species_for_checker,
                                         organism=organism_for_checker)
            if level == "minimal":
                # --minimal keeps RECOMMENDED intact and hides the add-ons.
                note = "  (add-ons hidden; these are the options you must tick)"
            elif removed:
                note = (f"  (every applicable add-on included, except {len(removed)} the checker "
                        f"removed on a conflict: {', '.join(sorted(removed))})")
            else:
                note = "  (every applicable add-on included)"
            print(f"\nCONFIG LEVEL: {level}\n{note}")
        elif level != "standard":
            print(f"\nCONFIG LEVEL: {level} requested, but the scenario's factors could not be "
                  f"resolved — showing the standard set.")
        # Per-option reasons: the draft's prose when --two-pass produced one, else (under --explain)
        # the resolver rule that placed the option.
        _reasons = {}
        for _r in _recs:
            if _r.get("reason"):
                _reasons.setdefault(_r["option_id"], _r["reason"])
        for _oid in (why_trace or {}):
            _w = why_recommended(_oid, why_trace)
            _e = ensembl_says(_oid, vep_options) if explain else None
            if _w or _e:
                _reasons.setdefault(_oid, "\n      ".join(x for x in (_w, _e) if x))
        gated = enforce_restrict_results_gate(p_enabled, resolved)
        if gated:
            print(f"\n  (removed {', '.join(gated)}: a 'Restrict results' value the priority "
                  f"table does not price for this scenario — it would collapse the output to a "
                  f"fraction of its rows. Add it back only if that is what you want.)")
        corrected = format_corrected_config(p_enabled, vep_options, violations,
                                            resolved=resolved, reason_by_id=_reasons,
                                            restored=restored,
                                            size_value=size_value, assembly=assembly,
                                            show_cli=show_cli, meta_notes=explain,
                                            species=species_for_display,
                                            show_optional=(level != "minimal"))
        print(corrected)
        # The repair log is shown only under --explain; the saved .md always keeps it.
        if diagnostics and explain:
            print("\nHOW THIS WAS CORRECTED\n" + "-" * 60)
            for d in diagnostics:
                print(d)
        diagnostics.clear()
        # Same order as the screen: the configuration, then how it was repaired.
        reports.extend(x for x in (corrected, pass_warnings, restored_report) if x)
    # Flushes anything left if the per-pass loop never ran.
    if diagnostics and explain:
        print("\nHOW THIS WAS CORRECTED\n" + "-" * 60)
        for d in diagnostics:
            print(d)
    warnings = "\n".join(x for x in (reports + [audit_report, override_report]) if x)
    save_result(user_query, response_text, mode="recommend", warnings=warnings,
                reasoning=reasoning_text)


def run_explain_result(client, model, user_query):
    """Explain a VEP output annotation with the LLM, print the answer and save it."""
    consequences = load_consequences()
    if not consequences:
        print("Error: vep_consequences.json not found.")
        sys.exit(1)

    system_prompt = build_explain_result_prompt(consequences)
    print("Explaining VEP output...\n")

    try:
        response_text, reasoning_text = stream_response(client, model, system_prompt, user_query)
    except Exception as e:
        print(f"\nError communicating with Ollama: {e}")
        sys.exit(1)

    # stream_response does not print the answer, so print it here.
    if response_text.strip():
        print(response_text.strip())
        print()
    save_result(user_query, response_text, mode="explain", reasoning=reasoning_text)


def main():
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # gemma4:26b is the model the system is built and benchmarked on.
    model = os.environ.get("VEP_MODEL", "gemma4:26b")

    args = sys.argv[1:]

    # The openai import is deferred so --help works with nothing installed.
    def make_client(required=True):
        try:
            from openai import OpenAI
        except ImportError:
            if required:
                print("Error: openai SDK not installed. Run: pip install openai")
                sys.exit(1)
            # Only explain-result needs the SDK; the recommend path uses the native endpoint.
            return None
        return OpenAI(base_url=base_url, api_key="ollama")

    # --- Mode: explain-result ---
    if args and args[0] == "explain-result":
        query = " ".join(args[1:]).strip()
        if not query:
            print("Usage: python3 vep_assistant.py explain-result \"Why is my variant splice_donor_variant?\"")
            sys.exit(1)
        run_explain_result(make_client(), model, query)
        return

    # --- Mode: recommend ---
    known_flags = ("--explain", "--minimal", "--full",
                   "--factor-think", "--no-factor-think", "--quiet", "--assume", "--ask", "--no-ask", "--cli",
                   "--single-pass", "--two-pass") + tuple(_CONTEXT_FLAGS)
    # Removed flags exit with a reason instead of "Unknown option".
    removed_flags = {
        "--think": "removed: it set reasoning on the draft call, which the default run does not make",
        "--semantic": "removed: it chose which examples went into the draft prompt, which the default "
                      "run does not build",
        "--no-check": "removed: the checker builds the configuration, so there is nothing to skip",
    }
    _gone = [a for a in args if a in removed_flags]
    if _gone:
        for a in _gone:
            print(f"{a} {removed_flags[a]}.")
        sys.exit(2)

    # Handled before the unknown-flag check.
    if any(a in ("--help", "-h", "help") for a in args):
        print('Usage: python3 vep_assistant.py [flags] "your analysis scenario"')
        print("\nModes:")
        print("  <scenario>                    recommend a VEP web-form configuration")
        print('  explain-result "<question>"   explain a VEP output annotation')
        print("\nFlags:")
        for f, h in (("--explain", "say why each option is recommended, and how the checker resolved it"),
                     ("--minimal", "only the options you must tick; hide the optional add-ons"),
                     ("--full", "add every add-on"),
                     ("--cli", "also print the equivalent VEP command line"),
                     ("--ask", "default: ask when a missing answer would change what is recommended "
                               "(needs a terminal; otherwise the value is assumed and stated)"),
                     ("--no-ask", "never ask; state the assumed values instead"),
                     ("--quiet", "never ask and do not print the assumed values"),
                     ("--no-factor-think", "the classifier answers without reasoning first (faster, "
                                           "weaker on misleading wording)"),
                     ("--factor-think", "default: the classifier reasons before answering"),
                     ("--species / --origin / --size / --assembly", "state a fact instead of inferring it"),
                     ("--two-pass", "also make the retired draft call (legacy/two_pass.py); slower, "
                                    "same configuration")):
            print(f"  {f:<44} {h}")
        print("\nEnvironment:")
        for v, h in (("OLLAMA_BASE_URL", "Ollama server (default http://localhost:11434/v1)"),
                     ("VEP_MODEL", "model for every call (default gemma4:26b)"),
                     ("VEP_FACTOR_MODEL", "a different model for the classifier only"),
                     ("VEP_FACTOR_THINK", "0 turns the classifier's reasoning off"),
                     ("VEP_KEEP_ALIVE", "how long Ollama keeps the model loaded (default: always)"),
                     ("VEP_OPTIONS_FILE", "use another option catalogue"),
                     ("VEP_FACTORS_FILE", "use another factor scheme"),
                     ("VEP_PRIORITY_FACTOR_FILE", "use another priority table"),
                     ("VEP_RESULTS_DIR", "where each run is saved (default vep_ai_demo/results)"),
                     ("NO_PROXY=localhost,127.0.0.1", "needed behind a proxy")):
            print(f"  {v:<44} {h}")
        sys.exit(0)

    # Reject unrecognised flags so a typo is not read as part of the query.
    unknown = [a for a in args
               if a.startswith("--") and a.split("=", 1)[0] not in known_flags]
    if unknown:
        print(f"Unknown option(s): {' '.join(unknown)}")
        print(f"Available: {' '.join(known_flags)}")
        print('Usage: python3 vep_assistant.py [flags] "your analysis scenario"')
        sys.exit(2)

    # False means "unset": infer_factors resolves it through _factor_think_setting() (default on).
    # --no-factor-think pins it off via VEP_FACTOR_THINK=0.
    factor_think = True if "--factor-think" in args else (None if "--no-factor-think" in args else False)
    if factor_think is None:
        os.environ["VEP_FACTOR_THINK"] = "0"
        factor_think = False
    # --quiet only suppresses the disclosure lines; defaults are assumed either way.
    # --assume is its old name (renamed after Likhitha's question on the proposal) and still works.
    if "--assume" in args:
        print("note: --assume is now --quiet — assuming happens by default; this flag only silences "
              "the disclosure lines.")
    quiet = "--quiet" in args or "--assume" in args
    if quiet and "--ask" in args:
        print("--quiet and --ask ask for opposite things; pick one.")
        sys.exit(2)
    # Ask is the default. Off a tty `_ask_factor` returns None, so the run falls back to the
    # assumed value with its disclosure line.
    clarify = "assume" if quiet else ("state" if "--no-ask" in args else "ask")
    # Facts the user states about their data override the classifier.
    context, _ctx_err = _parse_context_flags(args)
    if _ctx_err:
        print(_ctx_err)
        sys.exit(2)
    explain = "--explain" in args
    if "--minimal" in args and "--full" in args:
        print("--minimal and --full ask for opposite things; pick one.")
        sys.exit(2)
    level = "minimal" if "--minimal" in args else "full" if "--full" in args else "standard"
    # Drop flags, and the value after a spaced context flag, so only the query text remains.
    _skip, remaining = set(), []
    for i, a in enumerate(args):
        if i in _skip:
            continue
        head = a.split("=", 1)[0]
        if head in _CONTEXT_FLAGS:
            if "=" not in a:
                _skip.add(i + 1)
            continue
        if a in known_flags:
            continue
        remaining.append(a)

    try:
        vep_options, training_examples = load_knowledge_base()
    except FileNotFoundError as e:                     # the CLI reports; the library raises
        print(f"Error: {e}")
        return 1

    if remaining:
        user_query = " ".join(remaining)
    else:
        print("=" * 60)
        print("  VEP AI Assistant (local LLM via Ollama)")
        print("  Describe your analysis scenario to get VEP recommendations")
        print("  Tip: use --explain to see why each option is recommended")
        print("=" * 60)
        print()
        try:
            user_query = input("Your scenario: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not user_query:
            print("No query provided. Exiting.")
            sys.exit(0)

    print()
    run_recommend(make_client(required=False), model, vep_options, training_examples, user_query,
                  explain=explain, level=level,
                  factor_think=factor_think, clarify=clarify, context=context,
                  show_cli="--cli" in sys.argv,
                  single_pass="--two-pass" not in sys.argv)


if __name__ == "__main__":
    try:
        # main() returns a status; propagate it so a failed run does not exit 0.
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        # Ctrl-C exits quietly with the conventional 130.
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)

