#!/usr/bin/env python3
"""Shared helpers for the gold-example generation pipeline (work/generation/).

This module REUSES the demo's deterministic pipeline (vep_assistant) — it never reimplements
the checker, species logic, parser, or embedder. It defaults the KB env vars to the EXPANDED
58-option catalogue + the simulated corpus so every reused function operates on the right KB.
Never mix with the demo KB (different ids — see work/id_migration.json).

Nothing here is mentor-validated: the factor scheme + priorities are PROVISIONAL config files
under generation_config/. Swap those files on sign-off; the code does not change.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
WORK = GEN_DIR.parent
ROOT = WORK.parent
DEMO = ROOT / "vep_ai_demo"
CONFIG_DIR = GEN_DIR / "generation_config"

# Point the reused load_knowledge_base()/checker at the expanded catalogue + simulated corpus.
os.environ.setdefault("VEP_OPTIONS_FILE", str(WORK / "vep_options_expanded.json"))
os.environ.setdefault(
    "VEP_EXAMPLES_FILE",
    str(WORK / "preliminary_examples" / "simulated_gold_examples.json"),
)
# Same pattern for the factor scheme: the demo ships its own copy so it stays standalone-publishable,
# and the pipeline overrides to the canonical config under generation_config/ — which is the file the
# mentor swaps on sign-off (no code change). Mirrors VEP_OPTIONS_FILE exactly.
os.environ.setdefault("VEP_FACTORS_FILE", str(CONFIG_DIR / "factors.json"))
os.environ.setdefault("VEP_PRIORITY_FACTOR_FILE", str(CONFIG_DIR / "priority_by_factor.json"))

_VA_CACHE = None


def load_va():
    """Import the demo's vep_assistant by path (the single source of truth for the checker AND, since
    the factor-core move, for the factor scheme itself). Cached: every caller shares one module
    instance, and this module re-exports the factor core from it at import time. Caching is safe
    because vep_assistant reads every env var inside functions, never at import."""
    global _VA_CACHE
    if _VA_CACHE is None:
        spec = importlib.util.spec_from_file_location("vep_assistant", DEMO / "vep_assistant.py")
        va = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(va)
        _VA_CACHE = va
    return _VA_CACHE


def load_evaluate():
    """Import the demo's evaluate module (call_llm etc.). It imports vep_assistant, so DEMO must be on path."""
    if str(DEMO) not in sys.path:
        sys.path.insert(0, str(DEMO))
    import evaluate as ev  # noqa: E402
    return ev


def _load_json(p):
    with open(p) as f:
        return json.load(f)


def load_catalogue():
    return _load_json(os.environ["VEP_OPTIONS_FILE"])


def load_corpus():
    """The in-context example corpus (simulated gold today; swap via VEP_EXAMPLES_FILE)."""
    return _load_json(os.environ["VEP_EXAMPLES_FILE"])


def load_query_axes():
    return _load_json(CONFIG_DIR / "query_axes.json")


# ---------------------------------------------------------------------------
# Factor core — RE-EXPORTED from the demo engine, not defined here
# ---------------------------------------------------------------------------
# The factor scheme, the priority algebra (taxonomy_proposal.md §5), the config->tiers resolver and
# the query->factors classifier all live in vep_ai_demo/vep_assistant.py now. They used to be defined
# HERE and consumed only by the pipeline, which meant the shipped prose recommender ran on the older
# single-label use-case scheme while the pipeline ran on factors — two taxonomies in one project,
# free to drift. The dependency arrow only ever runs work/generation -> vep_ai_demo (the demo must
# stay standalone-publishable), so the shared core belongs in the engine and is re-exported here.
#
# These names are kept so every existing caller (resolve_config, sample_factors, verify_pipeline,
# seed_priorities, the harness) keeps working unchanged.
_VA = load_va()

PRIORITY_ORDER = _VA.PRIORITY_ORDER
HARD_GATE_FACTORS = _VA.HARD_GATE_FACTORS
VALUE_DEFAULTS = _VA.VALUE_DEFAULTS
strongest = _VA.strongest
active_values = _VA.active_values
species_cue_query = _VA.species_cue_query
factor_slug = _VA.factor_slug
factor_value_for = _VA.factor_value_for
intent_priorities = _VA.intent_priorities
load_factors = _VA.load_factors
load_priority_by_factor = _VA.load_priority_by_factor


def rouge_l(a, b):
    """Word-level ROUGE-L (LCS-based F1) between two strings — pure Python, no dependency.
    Used for near-duplicate query detection within a factor cell (Self-Instruct-style filter)."""
    at, bt = a.lower().split(), b.lower().split()
    if not at or not bt:
        return 0.0
    prev = [0] * (len(bt) + 1)
    for i in range(1, len(at) + 1):
        cur = [0] * (len(bt) + 1)
        for j in range(1, len(bt) + 1):
            cur[j] = prev[j - 1] + 1 if at[i - 1] == bt[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    lcs = prev[-1]
    prec, rec = lcs / len(bt), lcs / len(at)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


# ---------------------------------------------------------------------------
# Query-faithfulness: does the generated query EXPRESS the factors its config encodes? (SEMANTIC / LLM)
# ---------------------------------------------------------------------------
# Stage 3 writes the NL query; a query can silently omit origin/size/region/goal while its config was built
# for them (an under-specified gold pair -- also why a low ICE was ambiguous: bad config vs bad query). We
# verify this SEMANTICALLY: a checker model reads ONLY the query and classifies each factor; we compare to
# the true tuple. (Keyword matching was removed -- it can't handle the varied/implicit phrasing that is the
# whole point of Stage 3, and some 'signals' were tool/DB names the query is told NOT to contain.) This is
# an Alberti-style round-trip: generate X from Y, recover Y from X, keep if recovered. Prefer a checker
# model DIFFERENT from the Stage-3 teacher (cross-check > self-check); run it deterministically (temp 0,
# fixed seed, concurrency 1). Judge discipline (proposal §7.2): it only FLAGS for review, never auto-drops
# -- the hard species gate stays deterministic (infer_species) in Stage 4.

# Re-exported from the engine (see the factor-core block above); the private aliases are kept
# because compare_factors() below and existing callers reference them by these names.
_FACTOR_VALUES = _VA.FACTOR_VALUES
_MULTI_FACTORS = _VA.MULTI_FACTORS

# --- Tool-name leak detection -----------------------------------------------------------------------
# Stage 3 forbids the teacher from naming VEP options ("Do NOT name VEP options, flags, plugins, or column
# names", generate_queries.py). That rule is load-bearing: the whole point of reverse generation is that the
# student must INFER the config from the biology. If the query says "cross-referenced with MANE Select
# transcripts", the student can read the answer off the question, and ICE — which decides whether a row is
# good — then measures reading comprehension instead of inference. Some queries do name a resource (e.g.
# MANE) unprompted, because it is genuinely how clinicians talk; that is realistic but off-spec — a query
# that names its own answer is a different task (the `names_options` framing), not scenario->config.
#
# ONLY unambiguous tool/resource names belong here. Words that are BOTH an option id and ordinary biology
# vocabulary (regulatory, protein, variant, frequency, phenotypes, domains, canonical, distance, summary)
# are deliberately excluded — a query about regulatory regions must be free to say "regulatory".
TOOL_NAMES = [
    "MANE", "SIFT", "PolyPhen", "CADD", "REVEL", "AlphaMissense", "ClinPred", "dbNSFP",
    "SpliceAI", "MaxEntScan", "dbscSNV", "gnomAD", "ClinVar", "1000 Genomes", "1000G",
    "LOEUF", "Mastermind", "Geno2MP", "UTRAnnotator", "Enformer", "APPRIS", "CCDS",
    "UniProt", "RefSeq", "GENCODE", "COSMIC", "dbSNP", "Paralogues", "DosageSensitivity",
    "HGVS", "TSL",
]
_TOOL_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in TOOL_NAMES) + r")\b", re.IGNORECASE)


def query_names_tool(query):
    """Tool/resource names the query gives away, deduped and in canonical casing. Empty = clean."""
    hits = {m.group(1).lower() for m in _TOOL_RE.finditer(query or "")}
    canon = {t.lower(): t for t in TOOL_NAMES}
    return sorted({canon[h] for h in hits})


# The classifier prompt and its parser now live in the engine too, so the SHIPPED recommender and the
# pipeline's Stage-4 round-trip infer factors with exactly the same prompt (they cannot diverge).
FACTOR_CLASSIFIER_PROMPT = _VA.FACTOR_CLASSIFIER_PROMPT
parse_factor_classification = _VA.parse_factor_classification


def compare_factors(recovered, factor_tuple):
    """Compare the checker's recovered factors to the true tuple -> (per_factor, flags). FLAG-ONLY (never
    fails a row): query-faithfulness is a review signal; the deterministic species gate is the hard net.
    per_factor[factor] in {match, match_plus_extra, partial, unknown, contradict}."""
    per_factor, flags = {}, []
    for f in _FACTOR_VALUES:
        rec = recovered.get(f)
        if f in _MULTI_FACTORS:
            want, got = set(factor_tuple[f]), set(rec or [])
            missing, extra = want - got, got - want
            if f == "analysis_goal":
                missing -= {"basic-consequence"}           # baseline goal is always implicitly satisfied
            st = ("match" if not missing and not extra else "match_plus_extra" if not missing
                  else "unknown" if missing == want else "partial")
        else:
            want = factor_tuple[f]
            st = "match" if rec == want else "unknown" if rec in (None, "unstated") else "contradict"
        per_factor[f] = st
        if st == "contradict":
            flags.append(f"factor_contradict:{f}(query_reads_as_{recovered.get(f)})")
        elif st in ("unknown", "partial"):
            flags.append(f"factor_unrecoverable:{f}({st})")
    return per_factor, flags
