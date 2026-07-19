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


def load_va():
    """Import the demo's vep_assistant by path (the single source of truth for the checker)."""
    spec = importlib.util.spec_from_file_location("vep_assistant", DEMO / "vep_assistant.py")
    va = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(va)
    return va


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


def load_factors():
    return _load_json(CONFIG_DIR / "factors.json")


def load_priority_by_factor():
    return _load_json(CONFIG_DIR / "priority_by_factor.json")


def load_query_axes():
    return _load_json(CONFIG_DIR / "query_axes.json")


# ---------------------------------------------------------------------------
# Priority algebra (matches taxonomy_proposal.md §5)
# ---------------------------------------------------------------------------
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


# Canonical non-human cue: the resolver runs the checker BEFORE the real query exists, so it
# feeds infer_species a minimal species cue. Any non-human species gates the same human-only
# block, so 'mouse' is a fair representative. The real Stage-3 query names a real organism and
# Stage-4 verifies infer_species(real_query) is non-human.
def species_cue_query(species):
    return "human variant analysis" if species == "human" else "mouse variant analysis"


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

_FACTOR_VALUES = {
    "species": ["human", "non-human"],
    "origin": ["germline", "somatic"],
    "variant_size_class": ["small", "structural-CNV"],
    "region_focus": ["coding", "regulatory-noncoding"],                                   # multi-select
    "analysis_goal": ["basic-consequence", "clinical-interpretation", "population-frequency"],  # multi-select
}
_MULTI_FACTORS = ("region_focus", "analysis_goal")

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
    out = {f: ([] if f in _MULTI_FACTORS else "unstated") for f in _FACTOR_VALUES}
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[s:e + 1])
        if not isinstance(obj, dict):
            return None
    except Exception:
        return None
    for f in _FACTOR_VALUES:
        v = obj.get(f)
        if f in _MULTI_FACTORS:
            out[f] = [x for x in v if x in _FACTOR_VALUES[f]] if isinstance(v, list) else []
        else:
            out[f] = v if v in _FACTOR_VALUES[f] else "unstated"
    return out


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
