#!/usr/bin/env python3
"""VEP AI Assistant — recommends Ensembl VEP configuration based on your analysis scenario.

Supports three modes:
  python vep_assistant.py                        # interactive recommendation
  python vep_assistant.py --explain "query"      # recommendation + decision trace
  python vep_assistant.py explain-result "why..." # explain a VEP output annotation

How much configuration you get back (default = standard):
  --minimal   the smallest runnable set for your scenario
  --full      also switch on every add-on the scenario justifies

Reasoning. There are TWO model calls per run — a fast classifier that reads your scenario, then the
recommender that writes the configuration. Both reason before answering unless told not to, and both
default to NOT, because in each case it was measured to cost time and buy nothing:
  --think          reasoning on for the RECOMMENDER   (18.1s -> 34.9s per query, Exp 14)
  --factor-think   reasoning on for the CLASSIFIER    (0.97s -> 5.62s per query, Exp 15)

When your question doesn't say something, the tool states what it assumed rather than deciding silently:
  (default)   apply safe assumptions and say which ones
  --assume    apply them and keep quiet (scripts and batch runs)
  --ask       also prompt you about gaps where no assumption is safe
"""

import json
import os
import re
import sys
import time
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

def _kb_path(env_var, work_relative, demo_filename):
    """Resolve a knowledge-base file to ONE canonical location.

    Order: an explicit env var, then the repo's `work/` copy, then the demo-local copy.

    The point is that editing an option is a single-file change. The `work/` copy is the one that is
    curated, provenance-tracked and reviewed, so it must be the one the shipped tool reads whenever it is
    there — otherwise an edit to it silently fails to reach the CLI, which was the case until now.

    The demo-local fallback is not redundancy for its own sake: `vep_ai_demo/` is publishable on its own,
    without `work/` beside it, and has to keep working in that form. It is a fallback, never a second
    file to maintain."""
    if env_var and os.environ.get(env_var):
        return Path(os.environ[env_var])
    canonical = BASE_DIR.parent / work_relative
    return canonical if canonical.exists() else BASE_DIR / demo_filename


def load_knowledge_base():
    """Load VEP options and training examples from JSON files.

    Honours VEP_OPTIONS_FILE / VEP_EXAMPLES_FILE env vars so the same code can
    run on the demo KB (default) or the expanded catalogue + bootstrap set.
    """
    options_path = _kb_path("VEP_OPTIONS_FILE", "work/vep_options_expanded.json", "vep_options.json")
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
    path = _kb_path("VEP_FACTORS_FILE", "work/generation/generation_config/factors.json", "factors.json")
    with open(path) as f:
        return json.load(f)


# --- The importance spec, and the table DERIVED from it ---------------------------------------------
#
# This lives in the engine rather than in the generation pipeline for the same reason `intent_priorities`
# and the classifier prompt do: the shipped recommender and the pipeline must not be able to disagree
# about what a scenario's priorities are. `work/generation/seed_priorities.py` imports it back out.
#
# WHY IT IS DERIVED AND NOT A MAINTAINED FILE. The table is a pure function of this spec and the option
# catalogue, and computing all 58 options takes ~0.02 ms — there is no reason to precompute it. Keeping
# it as a generated artifact meant four copies of it existed across two trees, kept in step by hand, with
# nothing to notice when they drifted: edit the catalogue and forget to regenerate, and the shipped tool
# silently ran an older table than every measurement was taken on. Deriving it removes that class of bug
# rather than guarding against it, and reduces "how do I update an option?" to editing one file.
#
# A FILE STILL WINS IF PRESENT. That is the point of the override in load_priority_by_factor below: once
# the mentor signs off a validated table, dropping it in takes precedence over this spec, and its mere
# presence then means "a human authored this" instead of "a build step ran".
RANK = {"critical": 3, "recommended": 2, "optional": 1, "not_applicable": 0}

# Predictor tiering. READ THIS BEFORE CHANGING: **VEP itself ranks nothing.** vep_plugins_web_config.txt
# is a flat `available => 1` map with no rank field, and the web form lists "Missense pathogenicity" as one
# undifferentiated family. The core-vs-add-on split is OUR EDITORIAL JUDGEMENT, grounded in ACMG PP3/BP4 as
# refined by ClinGen SVI (Pejaver et al. 2022) — a clinical-genetics standard EXTERNAL to VEP. Cite it as
# ours; do not imply VEP prescribes it. The axis is METHOD INDEPENDENCE, read from each plugin's own
# catalogue description: a distinct predictor forms its own call, a derivative one consumes other
# predictors' scores and so double-counts them.
PREDICTOR_DISTINCT = ["sift", "polyphen", "cadd", "alphamissense", "eve"]
PREDICTOR_DERIVATIVE = ["revel", "clinpred", "dbnsfp"]
# Splice tiering uses a DIFFERENT axis, honestly labelled: maxentscan and dbscsnv are self-contained models,
# NOT derivative of SpliceAI, so method-independence does not separate them. The split is ADOPTION/RECENCY.
SPLICE_CORE = ["spliceai"]                 # human only; species-gated below
SPLICE_ADDON = ["maxentscan", "dbscsnv"]   # maxentscan is the ONLY all-species splice option
# Missense predictors are INAPPLICABLE to non-coding variants, not merely less important: the catalogue
# rates 9/10 regulatory_noncoding=not_applicable. CADD is the documented exception (it scores coding AND
# non-coding) and is deliberately absent from this list.
MISSENSE_ONLY = [p for p in PREDICTOR_DISTINCT + PREDICTOR_DERIVATIVE if p != "cadd"]
REGION_GATE_NONCODING = MISSENSE_ONLY + ["mutfunc", "paralogues", "mane", "protein", "nmd"]

# WHERE-vs-WHY discipline: taxonomy_proposal §3 split region_focus from analysis_goal precisely because a
# single axis mixed *where* the variant acts with *why* you are annotating. So region_focus drives the
# STRUCTURAL annotation of a locus and analysis_goal the INTERPRETIVE. Hanging the predictor cluster off
# both re-mixed them and — since composition takes the max — made a coding+basic-consequence quick lookup
# pull in the full predictor stack.
DRIVES = {
    "region_focus": {
        "coding": {
            # tsl/appris are web_default=on, so ranking them optional would recommend LESS than the form
            # already gives. protein/nmd sit at optional in the catalogue's own columns.
            "recommended": ["hgvs", "numbers", "cat:protein_annotation", "tsl", "appris"],
            "optional": ["protein", "uniprot", "ccds", "nmd", "coding_only"],
        },
        "regulatory-noncoding": {
            # The regulatory build IS the annotation a regulatory query asks for; without it the question
            # is unanswerable, not merely under-served.
            "critical": ["regulatory"],
            "recommended": ["cell_type", "utrannotator", "enformer", "mirna"],
            "not_applicable": REGION_GATE_NONCODING,
        },
    },
    "analysis_goal": {
        "basic-consequence": {"optional": ["most_severe", "hgvs"]},
        "clinical-interpretation": {
            "critical": ["clinvar", "hgvs", "mane"],
            "recommended": PREDICTOR_DISTINCT + SPLICE_CORE + ["phenotypes"],
            "optional": PREDICTOR_DERIVATIVE + SPLICE_ADDON + ["mastermind", "geno2mp", "loeuf",
                                                              "dosage_sensitivity", "pubmed",
                                                              "var_synonyms", "failed",
                                                              "mutfunc", "paralogues"],
        },
        "population-frequency": {
            "critical": ["af_gnomade", "af_gnomadg", "af", "af_1kg"],
            "recommended": ["frequency"],
            "optional": ["clinvar"],
        },
    },
    "origin": {
        # Origin modulates which co-located source matters; it does not independently add ClinVar.
        # Composition is max-only, so listing clinvar here forced it into EVERY germline query.
        "germline": {"recommended": ["check_existing"]},
        "somatic": {"recommended": ["check_existing"], "not_applicable": ["frequency"]},
    },
    "variant_size_class": {
        "structural-CNV": {"critical": ["gnomad_sv"], "recommended": ["dosage_sensitivity"]},
    },
    "species": {
        # canonical is web_default=off and its own when_not_to_use prefers MANE for human clinical work.
        # Its documented job is the primary-transcript fallback where MANE is unavailable.
        "non-human": {"recommended": ["canonical"]},
    },
}

# Unconditional floor, under EVERY analysis_goal value. Deliberately small. NOTE anything here can never be
# `optional` anywhere, because put() is strongest-wins — which is why hgvs/mane/canonical live in DRIVES.
BASELINE_CRITICAL = ["core_type"]
BASELINE_RECOMMENDED = ["symbol", "biotype"]

SIZE_GATE_SOURCE = "catalogue priority_by_use_case['structural_variants'] == 'not_applicable'"


def validate_priority_blocks(vep_options, factors_cfg=None):
    """Problems in the catalogue's own `priority_by_factor` blocks, as a list of human-readable strings.

    This exists because that field is the one a maintainer or reviewer edits by hand, and every kind of
    typo in it used to fail SILENTLY: a misspelt label was dropped, and a misspelt factor or value was
    stored under a key nothing ever reads. The entry looked accepted and did nothing. A configuration
    file that cannot tell you it is wrong is worse than no configuration file.

    Returns [] when clean. `verify_pipeline.py` asserts that; the engine warns and carries on, because a
    maintainer's typo should not take a user's session down with it."""
    problems = []
    if factors_cfg is None:
        try:
            factors_cfg = load_factors()
        except Exception:
            factors_cfg = None
    known = {f: set(spec.get("values", [])) for f, spec in (factors_cfg or {}).get("factors", {}).items()}
    for o in vep_options:
        block = o.get("priority_by_factor")
        if block is None:
            continue
        if not isinstance(block, dict):
            problems.append(f"{o['id']}: priority_by_factor must be an object, got {type(block).__name__}")
            continue
        for factor, valmap in block.items():
            if known and factor not in known:
                problems.append(f"{o['id']}: unknown factor {factor!r} "
                                f"(expected one of {', '.join(sorted(known))})")
                continue
            if not isinstance(valmap, dict):
                problems.append(f"{o['id']}.{factor}: expected an object of value -> priority")
                continue
            for value, label in valmap.items():
                if known and value not in known.get(factor, set()):
                    problems.append(f"{o['id']}.{factor}: unknown value {value!r} "
                                    f"(expected one of {', '.join(sorted(known[factor]))})")
                if label not in RANK:
                    problems.append(f"{o['id']}.{factor}.{value}: unknown priority {label!r} "
                                    f"(expected one of {', '.join(RANK)})")
    return problems


_PRIORITY_BLOCK_WARNED = False


def _expand_tokens(tokens, by_cat):
    """A DRIVES token is a bare option id, or `cat:<category>` meaning every option in that category."""
    ids = []
    for t in tokens:
        ids.extend(by_cat[t[4:]] if t.startswith("cat:") else [t])
    return ids


def build_priority_table(vep_options):
    """Derive the importance table from DRIVES + this catalogue. Pure function, sub-millisecond."""
    from collections import defaultdict
    global _PRIORITY_BLOCK_WARNED
    # Only pay for validation when something actually uses the field: it loads factors.json to check
    # names, which doubled the derivation cost for the (currently universal) case of no blocks at all.
    problems = (validate_priority_blocks(vep_options)
                if any(o.get("priority_by_factor") for o in vep_options) else [])
    if problems and not _PRIORITY_BLOCK_WARNED:
        _PRIORITY_BLOCK_WARNED = True
        print("\n  Note: problems in the catalogue's priority_by_factor entries — these are IGNORED:")
        for p in problems[:8]:
            print(f"    - {p}")
        if len(problems) > 8:
            print(f"    ... and {len(problems) - 8} more")
        print()
    ids = {o["id"] for o in vep_options}
    by_cat = defaultdict(list)
    for o in vep_options:
        by_cat[o.get("category", "?")].append(o["id"])
    # sorted() so the table (and any dump of it) is byte-identical run to run: `ids` is a set and set
    # iteration order depends on PYTHONHASHSEED.
    priorities = {oid: defaultdict(dict) for oid in sorted(ids)}

    def put(oid, factor, value, label):
        if oid not in priorities:
            return
        cur = priorities[oid][factor].get(value)
        if cur is None or RANK[label] > RANK[cur]:      # strongest wins; not_applicable only if nothing else
            priorities[oid][factor][value] = label

    for factor, valmap in DRIVES.items():                                   # (1) the hand-authored spec
        for value, prio_tokens in valmap.items():
            for label, tokens in prio_tokens.items():
                for oid in _expand_tokens(tokens, by_cat):
                    put(oid, factor, value, label)
    # (1b) PER-OPTION priorities carried by the catalogue entry itself, in the shape taxonomy_proposal §5
    # specifies:  "priority_by_factor": {"analysis_goal": {"clinical-interpretation": "optional"}}
    #
    # This is what makes adding an option a SINGLE-FILE edit. DRIVES above is authored the other way
    # round — per factor value, listing the options that value drives — which is how a domain expert
    # thinks about a scenario, but it means a new catalogue entry is inert until someone also edits
    # Python: it parses, validates and routes correctly, and is then never recommended in any scenario.
    # Both views compose through the same strongest-wins put(), so an option may be priced either way,
    # or both. Nothing here needs migrating; DRIVES simply shrinks as entries move into the catalogue.
    # (3) PER-OPTION OVERRIDES from the catalogue, applied by ASSIGNMENT, not by strongest-wins.
    #
    # These must be able to LOWER a priority, not only raise one. put() takes the max, so a catalogue
    # entry asking for `optional` lost to a DRIVES entry saying `recommended` and did nothing at all --
    # silently, since the validator checks spelling and not effect. Nearly every edit a reviewer asks for
    # is a demotion, so under strongest-wins the field could not express the thing it exists for.
    # A per-option statement is more specific than the broad spec, so it wins; the deterministic gates
    # below are applied afterwards and win over both, because they are safety rather than preference.
    for o in vep_options:
        for factor, valmap in (o.get("priority_by_factor") or {}).items():
            for value, label in valmap.items():
                if label in RANK and o["id"] in priorities:
                    priorities[o["id"]][factor][value] = label
    for value in ("basic-consequence", "clinical-interpretation", "population-frequency"):   # (2) the floor
        for oid in BASELINE_CRITICAL:
            put(oid, "analysis_goal", value, "critical")
        for oid in BASELINE_RECOMMENDED:
            put(oid, "analysis_goal", value, "recommended")
    # (3) species gate: human-only options, plus NARROW "human + <one species> only" sets (var_synonyms =
    # human+pig, ccds = human+mouse). The species factor is binary and cannot say "pig but not mouse", so a
    # generic non-human query cannot be guaranteed to match — gate them. Binary-granularity limitation.
    narrow_nonhuman = re.compile(r"human\s*\+\s*\w+.*only", re.IGNORECASE)
    for o in vep_options:
        restr = o.get("species_restriction", "all species")
        if _is_human_only(restr) or narrow_nonhuman.search(restr or ""):
            priorities[o["id"]]["species"]["non-human"] = "not_applicable"   # safety: overrides all
    for o in vep_options:                                                   # (4) size gate, from the KB
        if o.get("priority_by_use_case", {}).get("structural_variants") == "not_applicable":
            priorities[o["id"]]["variant_size_class"]["structural-CNV"] = "not_applicable"   # safety

    return {
        # Recorded so a table DUMPED to disk can later be detected as stale against a moved catalogue.
        # A table derived in memory is current by construction and this always matches.
        "_catalogue_sha256": catalogue_fingerprint(vep_options),
        "_status": ("PROVISIONAL — derived from the DRIVES spec in vep_assistant.py and this catalogue. "
                    "NOT mentor-validated. A validated table dropped in as priority_by_factor.json "
                    "overrides this derivation; no code changes are needed."),
        "_authoring": {
            "drives": DRIVES,
            "baseline_critical": BASELINE_CRITICAL,
            "baseline_recommended": BASELINE_RECOMMENDED,
            "predictor_tiers": {
                "_basis_missense": ("METHOD INDEPENDENCE (distinct vs derivative): a distinct predictor "
                                    "forms its own call; a derivative one (REVEL/ClinPred/dbNSFP) consumes "
                                    "other predictors' scores, so it double-counts them. Per ACMG PP3/BP4 / "
                                    "ClinGen SVI (Pejaver et al. 2022)."),
                "_basis_splice": ("ADOPTION/RECENCY, not independence: MaxEntScan and dbscSNV are "
                                  "independent models, NOT derivative of SpliceAI. SpliceAI is the current "
                                  "community default; the older tools are kept as add-ons."),
                "_caveat": ("VEP itself ranks NONE of these — both splits are our editorial judgement on "
                            "standards external to VEP. This is the 'essential vs optional' call the mentor "
                            "was asked to adjudicate."),
                "distinct": PREDICTOR_DISTINCT, "derivative": PREDICTOR_DERIVATIVE,
                "splice_core": SPLICE_CORE, "splice_addon": SPLICE_ADDON,
            },
            "species_gate": ("not_applicable for non-human where _is_human_only(species_restriction), OR "
                             "where the restriction is a narrow 'human + <one species> only' set that the "
                             "binary species factor cannot guarantee matches the query's species "
                             "(var_synonyms=human+pig, ccds=human+mouse)"),
            "size_gate": SIZE_GATE_SOURCE,
            "region_gate": {"value": "regulatory-noncoding", "not_applicable": REGION_GATE_NONCODING,
                            "_amends": ("taxonomy_proposal §3 calls region_focus 'purely soft'; the "
                                        "catalogue rates 9/10 missense predictors regulatory_noncoding="
                                        "not_applicable and constraints_dossier.md:123 prescribes a "
                                        "recommender gate. Proposed amendment — needs mentor sign-off.")},
        },
        "priorities": {oid: dict(fac) for oid, fac in priorities.items()},
    }


def load_priority_by_factor(vep_options=None):
    """The importance table: a file if one is present, otherwise derived from the catalogue.

    THE FILE IS AN OVERRIDE, NOT THE SOURCE. Deriving by default means updating an option is a single
    edit to the catalogue — there is no generated artifact to regenerate, no second copy to keep in step,
    and nothing that can silently go stale. A `priority_by_factor.json` on disk still wins, which is how a
    mentor-validated table is adopted: drop it in and it takes precedence over the spec.
    """
    path = _kb_path("VEP_PRIORITY_FACTOR_FILE",
                    "work/generation/generation_config/priority_by_factor.json",
                    "priority_by_factor.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    if vep_options is None:
        opts_path = _kb_path("VEP_OPTIONS_FILE", "work/vep_options_expanded.json", "vep_options.json")
        with open(opts_path) as f:
            vep_options = json.load(f)
    return build_priority_table(vep_options)


PRIORITY_ORDER = {"critical": 3, "recommended": 2, "optional": 1}

# --- The two-tier DISPLAY vocabulary --------------------------------------------------------------
#
# Agreed with the mentors 2026-08-07: the user sees TWO buckets, not three. `critical` and
# `recommended` merge into RECOMMENDED; `optional` becomes ADD-ON.
#
# The names are Nakib's and the reason is worth keeping: "default" reads as *applies automatically*,
# which is false for a bucket the user still has to switch on. "Recommended" says what it is — an
# expert suggestion.
#
# The merge costs nothing, because it was always only a label: `intent_priorities` enables
# `critical ∪ recommended` as one set, so both tiers were switched on together in every configuration
# the tool has ever emitted. Measured over the 31 review rows, the emitted set is identical under
# either shape (391 options on, no conflict tie-break changes).
#
# The three internal priorities STAY. Three mechanisms are defined on `critical` and lose their
# meaning without it: restore_missing_critical (the only thing that adds a missing must-have back to a
# short draft, protecting 103 option-instances across the 31 rows), --minimal, and critical-recall.
# The model is also still shown the three labels — it is the engine's input, not its output, and every
# measured number was taken with three labels in context.
#
# One map, so the CLI, the web payload and the review export cannot drift apart.
DISPLAY_TIER = {"critical": "recommended", "recommended": "recommended", "optional": "add-on"}


def display_tier(priority):
    """The bucket a user is shown for an internal priority label.

    Anything with no bucket — `not_applicable`, or an option the table prices for no factor here —
    comes back unchanged, so the caller decides whether to show it at all rather than having it
    silently renamed into a tier it is not in."""
    return DISPLAY_TIER.get(priority, priority)


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
# DERIVED from factors.json, not declared twice. The values above and this tuple used to be hardcoded
# here while factors.json separately declared `select: single|multi` for each factor, with nothing keeping
# the two in agreement — they matched only by coincidence. Changing the scheme therefore meant editing the
# config AND the engine, and editing only the config silently did nothing: the engine went on treating a
# newly-multi factor as single, so a query naming two values had one of them dropped.
# The literals stay as the fallback, so a missing or unreadable factors.json behaves exactly as before.
def _factor_scheme():
    """(values, multi) read from factors.json, falling back to the literals above."""
    try:
        spec = load_factors()["factors"]
        values = {f: list(s["values"]) for f, s in spec.items()}
        multi = tuple(f for f, s in spec.items() if s.get("select") == "multi")
        if values and multi:
            return values, multi
    except Exception:
        pass
    return dict(_FACTOR_VALUES_FALLBACK), ("region_focus", "analysis_goal")


_FACTOR_VALUES_FALLBACK = dict(FACTOR_VALUES)
FACTOR_VALUES, MULTI_FACTORS = _factor_scheme()

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
    # Derived from the tuple rather than naming the five factors and assuming which are lists: that
    # assumption is a second copy of the scheme, and it crashed the moment a factor's cardinality
    # changed in factors.json. Order follows FACTOR_VALUES so the slug stays stable and readable.
    parts = []
    for f in FACTOR_VALUES:
        v = factor_tuple.get(f)
        parts.append("+".join(v) if isinstance(v, list) else str(v))
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

def _schema_lines():
    """The JSON schema block of the classifier prompt, generated from the factor scheme.

    Written out by hand previously, which meant the prompt could disagree with factors.json about both
    the allowed values and whether a factor takes one or several — and the prompt is what the model
    actually obeys. Generating it means flipping a factor to multi-select in the config changes what the
    model is asked for, instead of leaving it to be spotted by hand."""
    out = []
    for f, vals in FACTOR_VALUES.items():
        if f in MULTI_FACTORS:
            out.append(f'  "{f}": array with any of [' + ",".join(f'"{v}"' for v in vals) + ']')
        else:
            out.append(f'  "{f}": ' + " | ".join(f'"{v}"' for v in vals) + ' | "unstated"')
    return ",\n".join(out) + "\n"


FACTOR_CLASSIFIER_PROMPT = (
    "You read a researcher's natural-language question about annotating genetic variants and identify ONLY "
    "what the question actually states or clearly implies about the analysis. Do NOT guess; if the question "
    "does not indicate a characteristic, use \"unstated\" (or [] for a list).\n\n"
    "Reply with ONLY this JSON object, no prose:\n"
    "{\n"
    + _schema_lines() +
    "}\n\n"
    "Guidance (judge by meaning, not keywords):\n"
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


def _native_chat_url():
    """Ollama's OWN /api/chat, derived from the same OLLAMA_BASE_URL the compat client uses.

    Shared by the two callers that need the native endpoint (_classify_native, _stream_native) so the
    base-URL handling cannot drift between them."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    return base.rstrip("/").removesuffix("/v1") + "/api/chat"


# A ~60-token JSON object needs nothing like this much; the cap exists to bound a runaway, and it is set
# high enough that the reasoning-ON diagnostic arm (VEP_FACTOR_THINK=1) still has room to finish its
# chain of thought AND emit the answer. A cap consumed entirely by reasoning returns empty content —
# the failure that used to surface as `factor_check_unparseable` in Stage 4 (see EXPERIMENTS.md Exp 14).
_CLASSIFY_MAX_TOKENS = 4096


def _classify_native(model, user_query, think):
    """The classifier call through the endpoint that honours `think`. Returns the raw text.

    Non-streaming sibling of _stream_native: the classifier's output is a single small JSON object that
    nothing displays incrementally, so streaming it would buy nothing. Decoding is held identical to the
    compat path (temperature 0, seed 42) so `think` is the only variable between them."""
    import urllib.request
    body = {
        "model": model, "stream": False, "keep_alive": -1, "think": think,
        "messages": [
            {"role": "system", "content": FACTOR_CLASSIFIER_PROMPT + (user_query or "")},
            {"role": "user", "content": "Return the JSON classification."},
        ],
        "options": {"temperature": 0.0, "seed": 42, "num_predict": _CLASSIFY_MAX_TOKENS},
    }
    req = urllib.request.Request(_native_chat_url(), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return (json.loads(r.read()).get("message", {}) or {}).get("content") or ""


def _factor_think_setting():
    """How the classifier should reason. Default OFF — see infer_factors.

    VEP_FACTOR_THINK is a DIAGNOSTIC, not a product switch, which is why it is an env var rather than a
    CLI flag: `--think` exists to show you the model's reasoning, and the classifier's reasoning is
    never displayed (only its JSON is parsed), so there is no user-facing reason to want it on.
      unset / 0  -> False   reasoning off, native endpoint  (default)
      1          -> True    reasoning on, native endpoint   (the A/B arm)
      compat     -> None    the original /v1 path, byte-identical to before this change
    """
    v = (os.environ.get("VEP_FACTOR_THINK") or "").strip().lower()
    if v == "compat":
        return None
    return v in ("1", "on", "true", "yes")


def infer_factors(client, model, user_query, think=False, apply_defaults=True,
                  seed=42, temperature=0.0):
    """Classify a free-text query into a factor tuple, or None if the classifier fails.

    SPECIES is taken from infer_species(), not from the classifier: species is the hard safety gate
    and the deterministic keyword layer is fail-closed by design, so it stays the authority. An
    unconfirmed species reads as 'human' here, matching what the checker already does (keep the
    human-only options and warn) — the checker still runs its own species pass regardless.

    'unstated' is preserved for the other single-select factors rather than guessed: it contributes no
    priority and triggers no hard gate, so an unstated factor simply exerts no influence. The one
    default applied is analysis_goal -> basic-consequence when nothing richer is indicated, which is
    the agreed baseline goal.

    REASONING IS OFF BY DEFAULT, AND THIS IS WHERE THE STARTUP LAG WAS. `gemma4:26b` reasons unless
    told not to, and this call went through the OpenAI-compatible /v1 endpoint, which silently DROPS
    the `think` parameter — so the classifier spent its time thinking before answering a fixed-schema
    ~60-token question. The reasoning-off change of 2026-07-31 only ever reached stream_response; this
    call was never in its scope. Measured over the 31-row review set, single-threaded, gemma4:26b:

        reasoning ON  (compat, as shipped)   8.2 s median   range 4.2-39.7 s (+ a 70 s cold first call)
        reasoning OFF (native)               1.4 s median   range 1.2-1.6 s
        reasoning ON  (native) — control     8.9 s median   => the ENDPOINT is inert; `think` is the effect

    Accuracy is unchanged, not merely similar: under the pipeline's own genlib.compare_factors scoring
    all three arms fail on the SAME three rows (1, 8, 30 = 90% whole-tuple), and those are the same rows
    Stage 4's independent gemma4:12b round-trip flags as factor_unrecoverable. Nothing is traded.

    Deterministic (temperature 0, fixed seed) — but note temp=0 is NOT reproducible under concurrency
    on a Metal/MoE stack, so a reproducible run needs concurrency 1.

    `think=None` restores the original compat path byte-identical (also via VEP_FACTOR_THINK=compat),
    so the pre-change behaviour stays reachable for anyone who needs to reproduce an older run.

    `apply_defaults=False` returns what the model actually said, WITHOUT rewriting an empty
    `analysis_goal` to ['basic-consequence']. That rewrite is the narrowest possible reading of silence
    and it was invisible: 21 of 31 review rows would lose options to it, up to 14. Callers that want to
    tell "the user asked for a basic consequence call" apart from "the user said nothing" — which is what
    clarification_plan() needs — must pass False. Default stays True so existing callers are unchanged.

    Runs on VEP_FACTOR_MODEL if set, otherwise on the SAME model as the recommendation. Defaulting to
    a second, smaller model would be faster — this is a ~60-token fixed-schema classification, so the
    big model buys nothing — but it would silently require a second download: a user who pulled only
    the quickstart model would get a failed classification, no factors, and no indication why. One
    pulled model has to be enough. Set VEP_FACTOR_MODEL=gemma4:e4b (or 12b) to get the speed back.
    NOTE that e4b is now the WRONG trade: it saves 0.4 s against reasoning-off 26b and loses 13 points
    of variant_size_class accuracy — a HARD GATE, where a wrong value silently removes an option set."""
    model = os.environ.get("VEP_FACTOR_MODEL") or model
    if think is False:                       # allow the env to override only the unrequested default
        think = _factor_think_setting()
    try:
        if think is None:                    # the original path, unchanged
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": FACTOR_CLASSIFIER_PROMPT + (user_query or "")},
                    {"role": "user", "content": "Return the JSON classification."},
                ],
                # Parameterised so a harness can run the same classification under several seeds and
                # report a spread instead of a single draw. The defaults are the old hardcoded values,
                # so every existing caller is unchanged.
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

    rec["species"] = "non-human" if infer_species(user_query) not in ("human", "unknown") else "human"
    if apply_defaults and not rec.get("analysis_goal"):
        rec["analysis_goal"] = ["basic-consequence"]
    return rec


# --- What to do when the question simply doesn't say -------------------------------------------------
#
# A factor the question never mentions contributes NOTHING, so every option it would have supplied
# disappears silently. Measured over the 31 review rows, mean options lost when one factor is blanked:
# origin 1.0, variant_size_class 1.0, region_focus 4.4, analysis_goal 5.4 (worst row 17). Over 20 REAL
# forum questions, 18/20 leave at least one factor open that changes the configuration — the generated
# rows never show this because Stage 3 wrote them to express their tuple (all 31 are fully specified).
#
# A default is only safe where one answer is rarely harmful, which is not everywhere:
#   origin              guessing germline on a tumour sample can switch ON the common-variant filter,
#                       which DISCARDS the user's variants. An option-count measure ranks by quantity and
#                       is blind to this, so it must not decide on its own what is safe to assume.
#   variant_size_class  `select: single` — there is no "both" to assume, and review row 1 is a real query
#                       naming both. A default cannot repair a vocabulary limitation.
#   analysis_goal       no safe middle: assume narrow (what the code did) and a clinical question loses
#                       ClinVar and every predictor; assume broad and a quick lookup returns thirty
#                       options. Today's narrow default was also invisible, which is the worse half.
# See research/underspecification_proposal.md for the measurements and the cases in full.
UNDERSPECIFIED_POLICY = {
    "region_focus": {
        "assume": ["coding", "regulatory-noncoding"],
        "why": "you didn't say which regions matter, so both are covered",
    },
    # FAIL-CLOSED, and measured: leaving this open is NOT the safe choice, which was the first guess.
    # Sharper than that, and verified by `work/harness/defaults_evidence.py` across all 31 review rows:
    # silence is strictly worse than EITHER value. It carries germline's risk on `frequency` AND drops
    # `check_existing`, which germline and somatic both enable. So the first decision is that something
    # must be guessed at all; only the second is that it is somatic.
    # The `somatic => frequency not_applicable` hard rule fires only when origin is EXPLICITLY somatic, so
    # an unstated origin lets the common-variant pre-filter through on 6 of the 15 somatic review rows --
    # identical harm to guessing germline. Guessing SOMATIC enables a suppressing option on 0 of the 16
    # germline rows, so it is strictly the safe direction. germline and somatic differ in the table by
    # this one rule (both merely recommend check_existing), so assuming somatic costs a germline user one
    # pre-filter and costs a somatic user nothing. That cost is real and is NOT an add-on: `frequency`
    # resolves at `recommended`, so it sits in the RECOMMENDED bucket the user sees switched on, and
    # guessing somatic drops it on 7 of the 31 review rows. Paid deliberately, not for free. Same shape
    # as infer_species being fail-closed:
    # the dangerous value is only adopted when positively indicated.
    "origin": {
        "assume": "somatic",
        "why": "you didn't say germline or somatic, so the safer reading is taken — it keeps the "
               "common-variant filter off, which would otherwise discard real tumour variants. "
               "Say 'germline' if these are inherited variants",
    },
    # GUESSABLE ONLY BECAUSE THE FACTOR IS MULTI-SELECT. Neither single value is safe -- `small` and
    # `structural-CNV` each gate away the other half of the catalogue -- so the safe answer is `both`,
    # and expressing it needs a factor that can hold two values. Across the 29 ablations where this was
    # the deleted fact, `both` loses options on 0 of 29 for 4.28 added; the error is purely additive,
    # which is the trade this whole policy is built on. See factors.json `_select_note`.
    "variant_size_class": {
        "assume": ["small", "structural-CNV"],
        "why": "you didn't say small variants or structural/CNV, so both are covered — say which if "
               "your callset is only one of them",
    },
    # ASKED, NOT GUESSED. The rule is: guess where one answer is clearly safer, ask where none is, and
    # this factor meets neither condition. The rule asks about it on 11 of the 11 ablations where it was
    # the deleted fact, and the fallback value loses options on 5 of those 11 -- subtractive error, the
    # direction that costs a user a finding rather than a column.
    #
    # The ablations overstate how often this interrupts anyone, because they delete the fact on purpose.
    # On the 8 real configuration questions from the trackers it is genuinely absent and material on 1
    # (reader disagreement, not absence, accounts for 3 more). n=8 is far too small for a frequency
    # claim and none is made.
    #
    # Skipping is free: the fallback in `resolve_underspecified` supplies basic-consequence and
    # announces itself, so nobody is blocked and nothing is substituted in silence.
    "analysis_goal": {
        "assume": None,
        "why": "you didn't say what you're after — a quick consequence call, clinical interpretation, "
               "or population frequencies; they pull in different tools",
    },
}


# --- What the user told us outright ------------------------------------------------------------------
#
# Three of the five factors are FACTS ABOUT THE SAMPLE - species, germline/somatic, small/structural -
# and the person asking knows all three without thinking. Inferring them from prose is where every
# measured failure came from: the classifier's only genuine error across the 31 review rows was the
# variant size, the two rows it could not answer were germline-vs-somatic because the query never said,
# and the one guess that can destroy data (germline on a tumour sample enables a filter that discards
# somatic variants) is a fact too. Region and goal - the INTENT half - it classified correctly.
#
# So anything the user states outright wins outright. What they leave blank still goes through the
# classifier and then the assume/say-so policy above; this only removes guessing where there is nothing
# to guess about.
#
# ASSEMBLY is here despite not being a factor. MANE exists only for GRCh38 and VEP's own form shows the
# checkbox to everyone (InputForm.pm:694-702 gates it on species alone), so a GRCh37 user can tick a box
# with no data behind it. It cannot be inferred from a query that does not mention a build, and no
# factor covers it - a field is the only thing that can fix it.
USER_CONTEXT_FIELDS = ("species", "origin", "variant_size_class", "assembly")


def apply_user_context(rec, context):
    """Overlay what the user stated on the classifier's reading. Returns (tuple, assembly, overridden).

    `context` maps any of USER_CONTEXT_FIELDS to a value; None/""/"infer" mean "work it out", which is
    the default for every field, so an untouched form behaves exactly as before this existed.
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
    # GRCh37/GRCh38 are human assemblies. Accepting one for a non-human query would let the
    # assembly gate strip human-only options on a species that never had them anyway, and would
    # report an override the user cannot have meant.
    asm = context.get("assembly")
    asm = asm if (asm in ("GRCh37", "GRCh38") and rec.get("species") != "non-human") else None
    if asm:
        overridden.append("assembly")
    return rec, asm, overridden


def _enabled_for(factor_tuple, vep_options):
    """The options a tuple switches on, or None if the priority config can't be loaded."""
    resolved = resolve_for_query(factor_tuple, vep_options)
    if not resolved:
        return None
    return {oid for oid, (en, _, _) in resolved.items() if en}


# WHICH OPTIONS COUNT AS "ESSENTIAL" FOR THE PURPOSE OF INTERRUPTING SOMEONE.
#
# The bar is the bucket the user is actually shown: RECOMMENDED, which is `critical | recommended`.
#
# It is deliberately NOT the internal `critical` tier alone, even though the mechanisms around it
# (`restore_missing_critical`, `--minimal`, critical-recall) still are. The critical/recommended
# boundary is the one the mentor review found unstable: twelve of Likhitha's twenty edits were
# critical<->recommended moves, which is why the display was merged in the first place. Deciding
# whether to INTERRUPT A USER on a boundary the reviewer redrew twelve times out of twenty edits — and
# that the user never sees — makes the interruption depend on a label nobody agrees on.
#
# The two readings were priced before choosing: on the current guesses they raise identical questions
# (`work/harness/ask_rate.py`, arms `shipped` and `shipped+wide-bar`), so the wider bar costs nothing
# today. It diverges only if the guesses are removed, where it adds 6 `origin` questions. Named rather
# than hardcoded so the comparison stays runnable.
ASK_BAR_PRIORITIES = ("critical", "recommended")


def factor_must_haves_at_stake(factor, factor_tuple, vep_options):
    """Options at the ASK_BAR whose presence depends on how this factor is answered.

    THE ASK RULE. Interrupting someone is only justified when the answer changes something essential:
    "answering this puts a different must-have in your configuration" is a sentence a user can act on,
    and it needs no threshold. The previous rule fired when >=3 options differed, which is a number
    fitted to our own 31 rows rather than derived from anything, and it could interrupt over three
    interchangeable add-ons while staying silent when a single essential option flipped.

    Note this is per QUERY, not per factor. `origin` changes nothing on a clinical question and decides
    the common-variant filter on a frequency one, so no fixed per-factor rule is right for both."""
    try:
        values = load_factors()["factors"][factor]["values"]
    except Exception:
        return set()
    # A multi-select factor's candidate ANSWERS include "both", so the comparison has to include it.
    # Without it the gate compares only the single values and can miss a difference that appears only
    # in the union — the hard gate removes an option when EVERY active value rules it out, so a union
    # tuple keeps options that either value alone would strip. `factor_impact` already scores the union
    # for this reason; this is the same fix on the rule that decides whether to interrupt at all. Only
    # reachable for a multi factor that is asked rather than assumed, which today is none of them.
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


def factor_impact(factor, factor_tuple, vep_options):
    """How much the configuration would move if this factor were answered — the largest difference
    between any two candidate answers. THE DECISION TO ASK IS DETERMINISTIC, not a model judgement:
    a factor whose answer changes nothing is not worth a question, whatever the classifier felt about it.
    On the 20 real queries this suppressed all 16 `origin` questions; asking on model uncertainty alone
    would have raised 52 questions, 16 of them about the factor that matters least."""
    try:
        values = load_factors()["factors"][factor]["values"]
    except Exception:
        return 0
    configs = []
    for v in values:
        t = dict(factor_tuple)
        t[factor] = [v] if factor in MULTI_FACTORS else v
        c = _enabled_for(t, vep_options)
        if c is not None:
            configs.append(c)
    if factor in MULTI_FACTORS:
        t = dict(factor_tuple); t[factor] = list(values)
        c = _enabled_for(t, vep_options)
        if c is not None:
            configs.append(c)
    return max((len(a ^ b) for i, a in enumerate(configs) for b in configs[i + 1:]), default=0)


OUT_OF_SCOPE_NOTE = (
    "  This assistant recommends Ensembl VEP options for a variant-annotation run, and your question\n"
    "  did not describe one. Tell it what you are annotating — the species, whether the variants are\n"
    "  germline or somatic, small or structural, and what you want out of the annotation — and it will\n"
    "  suggest a configuration."
)


def states_nothing_about_variants(rec):
    """True when the classifier read none of the four scenario factors out of the query text.

    SPECIES IS EXCLUDED, and that is the whole subtlety. `infer_factors` overwrites the classifier's
    species with `infer_species`, which returns 'unknown' for a query naming no organism and is then
    mapped to 'human' so the human-only options are not stripped from the many human queries that never
    say the word. So a populated species field is manufactured, not evidence that the text was about
    variants at all. Judging scope on it would call every string a scenario."""
    for f in FACTOR_VALUES:
        if f == "species":
            continue
        v = (rec or {}).get(f)
        if v if f in MULTI_FACTORS else (v not in (None, "unstated")):
            return False
    return True


def clarification_plan(rec, vep_options, user_query=None, assembly=None):
    """Given the RAW classification (apply_defaults=False), decide per open factor: assume, or ask.

    Returns (filled_tuple, assumptions, questions). `assumptions` are stated to the user rather than
    hidden — the point of this whole mechanism is that the tool stops making invisible choices.

    `questions` may include a non-factor entry for ASSEMBLY, which is scored by the same rule and is
    the only question the system still raises. It lives here rather than in `resolve_underspecified`
    so that the CLI, the web app and `try_reprompting.py` cannot disagree about what gets asked —
    all three read this function, and only the CLI reads the other one."""
    # The classifier returns None on a parse failure, and that is a normal outcome rather than an
    # exceptional one — a crash here would take down a request that could still be served from the
    # user's own stated context.
    if not rec:
        return dict(rec or {}), [], []
    # Checked BEFORE the assumptions run, because they populate the very fields being examined.
    off_topic = states_nothing_about_variants(rec)
    stated = dict(rec)                           # what the USER said, before anything was assumed
    rec = dict(rec)
    assumptions, questions = [], []
    for f in FACTOR_VALUES:
        if f == "species":                       # deterministic and fail-closed already
            continue
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
    # Scored against the tuple AFTER assumptions, so a question reflects what is still genuinely open.
    # The test is whether a MUST-HAVE is at stake, not how many options move: a user can act on "this
    # changes something essential in your configuration" and cannot act on "this changes four things".
    scored = []
    for f, why, _ in questions:
        at_stake = factor_must_haves_at_stake(f, rec, vep_options)
        if at_stake:
            scored.append((f, why, sorted(at_stake)))
    # A query naming none of the four scenario factors is not a variant-annotation scenario: "hello", a
    # bug report, a question about an output column. Asking it to choose between SNVs and CNVs claims we
    # understood something we did not, and it lands BEFORE the recommender's own scope check, which only
    # runs once the prompt is built. Assumptions still apply so a configuration can be produced, but the
    # interruption is withheld and the caller says what the tool is for instead.
    if off_topic:
        scored = []
    else:
        scored += assembly_question(stated, vep_options, user_query, assembly)
    return rec, assumptions, scored


def assembly_question(stated, vep_options, user_query=None, assembly=None):
    """The assembly question, as a zero-or-one-item list in the same shape as the factor questions.

    Suppressed when the text already names a build, when the user stated one, when the query is
    non-human (species gates those options long before an assembly could matter), and when nothing
    assembly-restricted is at the bar — which is the same relevance test every factor gets.

    SCORED ON WHAT THE USER STATED, not on the tuple after our own assumptions are folded in, and the
    difference is not small: assuming *both* variant sizes switches gnomAD-SV on for almost every
    query, and gnomAD-SV is GRCh38-only, so scoring the filled tuple interrupts 42 of the 81 ablations
    against 33 for the stated one. Nine of those interruptions would exist only because WE guessed.
    That follows the asymmetry the whole policy rests on: an option we added is a column the user can
    ignore, so it is not worth a question, while an option their own words called for is. MANE is
    unaffected either way (17 either way) because a stated clinical goal is what puts it there."""
    if (assembly or infer_assembly(user_query)) is not None:
        return []
    if stated.get("species") == "non-human":
        return []
    # `analysis_goal` is the one exception to scoring on the stated tuple, because an empty goal does
    # not resolve to a smaller configuration, it resolves to a broken one — about 6 options instead of
    # about 13. Scoring the hole would find nothing assembly-restricted at the bar and stay silent
    # about a build that does decide MANE, so the tool would go quiet precisely because it was missing
    # two facts rather than one. Substituted with the same value the fallback will supply.
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


_FACTOR_PROMPTS = {
    "origin": "Are these variants germline (inherited) or somatic (tumour)?",
    "variant_size_class": "Are these small variants (SNVs/indels) or structural changes (SVs/CNVs)?",
    "region_focus": "Do you care about protein-coding regions, regulatory/non-coding, or both?",
    "analysis_goal": "What are you after — a quick consequence call, clinical interpretation, "
                     "or population frequencies?",
}


def _ask_factor(factor):
    """Put one question to the user. Returns the chosen value, or None to leave it open.

    Leaving it open must always be possible and must always be the no-effort answer: a user who does not
    know is exactly the user this is for, and forcing a guess out of them is worse than assuming nothing.
    Any non-interactive context (piped stdin, no tty) answers None, so a script never blocks."""
    try:
        values = load_factors()["factors"][factor]["values"]
    except Exception:
        return None
    if not sys.stdin.isatty():
        return None
    print(f"\n  {_FACTOR_PROMPTS.get(factor, factor)}")
    for i, v in enumerate(values, 1):
        print(f"    {i}) {v}")
    if factor in MULTI_FACTORS:
        print(f"    {len(values) + 1}) both")
    print("    (enter to skip — it will be left open)")
    try:
        raw = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    if raw.isdigit():
        n = int(raw)
        if factor in MULTI_FACTORS and n == len(values) + 1:
            return list(values)
        if 1 <= n <= len(values):
            return [values[n - 1]] if factor in MULTI_FACTORS else values[n - 1]
    match = [v for v in values if v.lower().startswith(raw.lower())]
    if len(match) == 1:
        return [match[0]] if factor in MULTI_FACTORS else match[0]
    return None


# --- Assembly, which is not a factor but obeys the same rule -----------------------------------------
#
# ASSEMBLY DESCRIBES THE INPUT DATA, not the analysis, so it is deliberately outside the taxonomy. That
# is a reason to keep it out of `factors.json`, not a reason to leave it unanswered: it is the one gap
# where silence produces a WRONG configuration rather than a thin one. MANE, EVE, gnomAD-SV and MaveDB
# exist only for GRCh38; geno2mp only for GRCh37. VEP's own form does not protect anyone here — it
# shows the MANE checkbox to every human user and pre-ticks it (InputForm.pm:694-702 gates it on
# species alone), so a GRCh37 user can switch on an option with no data behind it. Our checker removes
# what the build cannot support, but only once it knows the build.
#
# It resolves through the SAME three outcomes as every factor: take it from the text, or ask. There is
# no guess, and that is the whole decision — guessing GRCh38 would be wrong for exactly the GRCh37
# clinical users the bug already affects, and it is the one place where the safer-direction argument
# that settled `origin` does not apply, because both directions delete something real.
#
# Measured, and the measurement is why asking is cheap: `infer_assembly` reads it from the text on 4 of
# the 8 real configuration questions from the trackers (one of them GRCh37), so the question is raised
# on the other 4 rather than on everyone. The 31 generated review queries name an assembly 0 times,
# which is a property of a generator that only writes about factors — the ablation set cannot measure
# this and is not asked to.
_ASSEMBLY_VALUES = ("GRCh37", "GRCh38")


def assembly_at_stake(factor_tuple, vep_options):
    """Assembly-restricted options at the ask bar that this scenario would switch on.

    Same shape as `factor_must_haves_at_stake`, and deliberately so: interrupting is justified by the
    answer moving something essential, whether or not the thing being answered is a factor."""
    resolved = resolve_for_query(factor_tuple, vep_options)
    if not resolved:
        return set()
    restriction = {o.get("id"): o.get("species_restriction", "all species") for o in vep_options}
    at_stake = set()
    for oid, (enabled, priority, _) in resolved.items():
        if not enabled or priority not in ASK_BAR_PRIORITIES:
            continue
        allowed = _assembly_restriction(restriction.get(oid, "all species"))
        if allowed and set(allowed) != set(_ASSEMBLY_VALUES):
            at_stake.add(oid)
    return at_stake


def _ask_assembly():
    """Put the assembly question. Same contract as `_ask_factor`: skipping is free and never blocks."""
    if not sys.stdin.isatty():
        return None
    print("\n  Which human genome assembly is your data on?")
    for i, v in enumerate(_ASSEMBLY_VALUES, 1):
        print(f"    {i}) {v}")
    print("    (enter to skip — no assembly-specific options will be removed)")
    try:
        raw = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(_ASSEMBLY_VALUES):
        return _ASSEMBLY_VALUES[int(raw) - 1]
    match = [v for v in _ASSEMBLY_VALUES if v.lower().replace("grch", "") == raw.lower().replace("grch", "")]
    return match[0] if len(match) == 1 else None


def resolve_underspecified(rec, vep_options, mode="state", user_query=None, assembly=None):
    """Fill what the question left open, per `mode`, and return the tuple to build the config from.

      "assume"  apply the safe defaults, say nothing   (scripts, batch, the eval harness)
      "state"   apply them and SAY SO                  (default)
      "ask"     additionally re-prompt where no default is safe and the answer moves the config

    Returns (filled_tuple, assembly), where assembly is 'GRCh37'/'GRCh38' or None for "not established".
    It rides along rather than joining the tuple because it describes the input data, not the analysis.

    The default is "state" rather than "ask" because a tool that interrogates its users has moved the
    work back onto them. Asking is opt-in. `analysis_goal` and ASSEMBLY are the two things asked about;
    every other factor has a safe value and reaches no question. Over the 81 clean ablations that is 44
    questions on 38 queries, 33 of them assembly (`work/harness/ask_rate.py`).

    Do not cite "18 of 20 real forum questions" from anywhere: that set was hand-edited and is withdrawn
    (research/underspecification_proposal.md §1).
    """
    filled, assumptions, questions = clarification_plan(rec, vep_options, user_query, assembly)
    off_topic = states_nothing_about_variants(rec)

    # Say what the tool is for before assuming four things about a query that described no analysis.
    # The recommender will also refuse further down, but only after the user has been interrogated,
    # which is the wrong order.
    if mode != "assume" and off_topic:
        print()
        print(OUT_OF_SCOPE_NOTE)

    # Whatever the text named is settled before anything is asked. `clarification_plan` already used
    # this to suppress the question; repeating it here is what puts the value in the RETURN, so the
    # checker downstream gets the build the user wrote down rather than nothing.
    assembly = assembly or infer_assembly(user_query)

    if mode == "ask":
        for factor, _why, _delta in questions:
            answer = _ask_assembly() if factor == "assembly" else _ask_factor(factor)
            if answer is None:
                continue
            if factor == "assembly":
                assembly = answer
            else:
                filled[factor] = answer
            # Say back what was understood. Answering a question and being moved straight on gives no
            # way to catch a mistyped answer, and the tool has just claimed this choice matters enough
            # to interrupt for — the least it can do is confirm what it heard.
            print(f"    → using {', '.join(answer) if isinstance(answer, list) else answer}")

    def still_open(q):
        if q[0] == "assembly":
            return assembly is None
        v = filled.get(q[0])
        return (not v) or v in (None, "unstated")

    questions = [q for q in questions if still_open(q)]

    # THE GOAL FALLBACK, SAID OUT LOUD. An empty `analysis_goal` does not fail, it COLLAPSES: the
    # priorities resolve to about 6 options instead of about 13, so something has to fill it even when
    # the user was asked and chose to skip. That is defensible; doing it silently is not, because
    # invisible substitution is the exact failure this whole mechanism exists to remove. When the
    # policy already assumed the goal, its own line covers it and this adds nothing.
    if not filled.get("analysis_goal"):
        filled["analysis_goal"] = ["basic-consequence"]
        if not any(f == "analysis_goal" for f, _, _ in assumptions):
            assumptions.append(("analysis_goal", filled["analysis_goal"],
                                "nothing was said about the goal and a configuration cannot resolve "
                                "without one, so the baseline consequence call is used — say if you "
                                "are assessing pathogenicity or need population frequencies"))
        questions = [q for q in questions if q[0] != "analysis_goal"]

    if mode != "assume" and (assumptions or questions):
        print()
        for factor, value, why in assumptions:
            shown = ", ".join(value) if isinstance(value, list) else value
            print(f"  Assumed {factor} = {shown} — {why}.")
        for factor, why, at_stake in questions:
            # `at_stake` is the list of must-have ids the answer moves, not a count. Printed as a count
            # once, which rendered as "would change ~['gnomad_sv'] options".
            names = ", ".join(at_stake) if at_stake else "part of the configuration"
            print(f"  Left open: {why} (decides {names}; --ask to be prompted).")

    return filled, assembly


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
                             retrieval_mode: str = "keyword",
                             assembly_override: str = None) -> list[dict]:
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
    assembly = assembly_override or infer_assembly(user_query)
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


def catalogue_fingerprint(vep_options):
    """Content hash of a catalogue. Canonical JSON rather than file bytes, so reformatting the file
    (indentation, key order) does not read as a change while an actual edit always does."""
    import hashlib
    return hashlib.sha256(json.dumps(vep_options, sort_keys=True).encode()).hexdigest()


def priority_table_is_stale(table, vep_options):
    """True if this table was built from a DIFFERENT catalogue than the one now loaded.

    Only meaningful for a table loaded from FILE — a derived one is current by construction. It matters
    because the file is an override that beats the derivation: a hand-authored table left in place while
    the catalogue moves on would otherwise win silently and forever.

    priority_table_covers() cannot catch this. It only notices ids the table has never heard of, so a
    catalogue that changed a species restriction or moved an option between categories keeps every id,
    passes that check, and ships wrong tiers with no warning.

    A table without the fingerprint field returns False rather than crying wolf — that includes every
    table written before this existed."""
    want = table.get("_catalogue_sha256")
    if not want:
        return False
    try:
        return catalogue_fingerprint(vep_options) != want
    except Exception:
        return False


def resolve_for_query(factor_tuple, vep_options):
    """`intent_priorities()` for a factor tuple, or None if the tuple or the config is unusable.

    One place for the try/except so the prompt builder and the output formatter can never disagree
    about what this scenario's priorities are."""
    global _PRIORITY_MISMATCH_WARNED
    if not factor_tuple:
        return None
    try:
        table = load_priority_by_factor(vep_options)
        if priority_table_is_stale(table, vep_options):
            # Fall back to deriving rather than disabling tiers: a correct table is always available, so
            # the stale file is the only thing that needs dropping. Say so — silently ignoring a
            # hand-authored table would be its own trap.
            if not _PRIORITY_MISMATCH_WARNED:
                _PRIORITY_MISMATCH_WARNED = True
                print("\n  Note: the priority table on disk was built from a different version of this "
                      "option catalogue.\n  Using the priorities derived from the current catalogue "
                      "instead.\n  Refresh the file with: python work/generation/seed_priorities.py\n")
            table = build_priority_table(vep_options)
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

    TWO BUCKETS, not three (agreed with the mentors 2026-08-07). `critical` and `recommended` merge
    into one RECOMMENDED bucket and `optional` becomes ADD-ONS. The merge is presentational and costs
    nothing: `intent_priorities` has always enabled `critical ∪ recommended` as a single set, so the
    user was already getting both and the split was only ever a label on the way out. Measured across
    the 31 review rows, the emitted configuration is identical under either shape — 391 options, no
    tie-break changes.

    The tier survives INTERNALLY, in `resolved`, because three mechanisms are defined on it and would
    otherwise lose their meaning: `restore_missing_critical` (which puts a missing must-have back),
    `--minimal`, and critical-recall. Merging the display keeps all three working.

    Naming is Nakib's and the reason matters: "default" reads as *applies automatically*, which is
    wrong for a bucket the user still has to switch on. "Recommended" is the expert suggestion it
    actually is.

    This is a different axis from :func:`tier_options`, which splits on native-flag vs plugin (i.e.
    does it need downloaded data files) — an infrastructure question, not a clinical one. An option
    can be a plugin AND recommended (AlphaMissense), or native AND an add-on (`--uniprot`).

    Returns four lists:
      recommended     — ENABLED and rated critical or recommended here.
      addons_on       — ENABLED and rated `optional`: add-ons this run switched on anyway.
      unpriced        — enabled, but the table prices them for no factor here (output/compute controls).
      addons_offered  — rated `optional` for this scenario and NOT enabled: the "offered, off by
                        default" set. Hard-gated options are never offered.

    DISPLAY ONLY: it regroups the corrected set, it never changes which options are enabled, so the
    checker and every scored metric are untouched."""
    out = {"recommended": [], "addons_on": [], "unpriced": [], "addons_offered": []}
    for oid in sorted(enabled):
        _, priority, _ = resolved.get(oid, (False, None, False))
        if priority in ("critical", "recommended"):
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


def display_flag(flag):
    """How an option's CLI flag should read in a listing.

    A few catalogue entries are not flags of their own: ClinVar significance arrives with
    `--check_existing` and its cli_flag records that. Printed literally next to check_existing's own
    row it looks like the same flag is being set twice, which reads as a bug rather than as one flag
    carrying two annotations. Say where it comes from instead. The generated command is unaffected —
    cli_flags_for already emits each flag once."""
    if "derived" in (flag or "").lower():
        base = flag.split("(")[0].strip()
        return f"(comes with {base})" if base else "(no flag of its own)"
    return flag or ""


def apply_config_level(enabled, disabled, resolved, level, vep_options, training_examples,
                       user_query, retrieval_mode="keyword"):
    """Narrow or widen the corrected set to the depth the user asked for. Mutates `enabled`.

      minimal  — keep only what the factor table calls `critical` here. For someone who wants the
                 smallest runnable configuration and will add to it themselves. `critical` is an
                 INTERNAL tier: since the two-tier merge the user sees one RECOMMENDED bucket, so
                 this level is described to them by what it is for, not by the tier it filters on.
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
        # EVERY tier the scenario justifies, not only the optional one. Adding just `optional` was
        # actively misleading whenever the model under-proposed: the add-ons went on while the core
        # stayed missing, so a run could ship REVEL/ClinPred/dbNSFP — which consume other predictors'
        # scores — with none of SIFT/PolyPhen/CADD/AlphaMissense for them to derive from. That is the
        # exact inversion of the tiering the table encodes, presented as "everything this scenario
        # justifies".
        enabled.update(oid for oid, (_, priority, gated) in resolved.items()
                       if priority in ("critical", "recommended", "optional") and not gated)
    else:
        return set()
    check_and_fix_violations(enabled, disabled, vep_options, training_examples, user_query,
                             retrieval_mode=retrieval_mode)
    return removed - set(enabled)          # a dep the re-check restored was not really removed


def restore_missing_critical(enabled, disabled, resolved, vep_options, training_examples,
                             user_query, retrieval_mode="keyword", assembly_override=None):
    """Switch on any option the factor table rates `critical` here that the draft left out.

    The checker has always been asymmetric. It REMOVES what cannot be right (species, assembly,
    conflicts) and adds a dependency the configuration implies — but nothing ever checked that the
    options the scenario actually REQUIRES are present. A short or truncated draft therefore shipped
    under the heading "authoritative" with its must-haves quietly absent, and `--full` made it worse by
    piling on add-ons while the core stayed missing. Observed on the README's own quickstart query: a
    draft naming two options produced a configuration with every derivative predictor and none of the
    distinct ones they derive from.

    Treating the table as the authority when it says an option is NOT applicable, but not when it says
    an option is ESSENTIAL, was never a defensible split; this applies the same rule in the other
    direction. Restored options are reported like any other repair, never silently inserted, and the
    checker runs again afterwards because a restored option can carry a dependency or conflict with
    something the model did propose.

    Returns the ids actually restored (an option the re-check then removed is not reported as restored).
    """
    if not resolved:
        return []
    missing = sorted(oid for oid, (_en, priority, gated) in resolved.items()
                     if priority == "critical" and not gated and oid not in enabled)
    if not missing:
        return []
    enabled.update(missing)
    for oid in missing:
        disabled.discard(oid)
    # The re-check MUST see the same assembly the first pass did. Without it this function happily
    # restored an option the assembly gate had just removed — a GRCh37 run got MANE back, which is the
    # precise hazard the assembly field exists to prevent, reintroduced one step later.
    check_and_fix_violations(enabled, disabled, vep_options, training_examples, user_query,
                             retrieval_mode=retrieval_mode, assembly_override=assembly_override)
    return [oid for oid in missing if oid in enabled]


def format_restored_critical(restored, vep_options):
    """Report recommended options the draft omitted. Empty string when the draft was complete.

    The MECHANISM is keyed on the internal `critical` tier — that is what makes it selective rather
    than "re-add everything the table recommends". The WORDING is not, because the user is shown two
    buckets and "must-have" would read as a third one."""
    if not restored:
        return ""
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    lines = ["", f"⚠️  RECOMMENDED OPTIONS THE DRAFT LEFT OUT ({len(restored)}):",
             "   The factor table recommends these for this scenario, so they are switched on:"]
    lines += [f"     + {name_by_id.get(oid, oid)} [{oid}]" for oid in restored]
    lines.append("")
    return "\n".join(lines)


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
            ("recommended", "RECOMMENDED — switched on for this scenario", "✓"),
            ("addons_on",   "ADD-ONS (enabled) — extras this run turned on", "+"),
            ("unpriced",    "OTHER (enabled) — the factor table ranks these for no factor here", "✓"),
        ):
            if not tiers[key]:
                continue
            lines.append(f"{title}  [{len(tiers[key])}]")
            lines.extend(f"  {mark} {name_by_id.get(oid, oid)} [{oid}] "
                         f"{display_flag(flag_by_id.get(oid, ''))}".rstrip()
                         for oid in tiers[key])
        if not on:
            lines.append("ENABLE: (none)")
        if tiers["addons_offered"]:
            lines.append("")
            lines.append("AVAILABLE ADD-ONS — NOT enabled; turn on if they help  "
                         f"[{len(tiers['addons_offered'])}]")
            lines.extend(f"  · {name_by_id.get(oid, oid)} [{oid}] "
                         f"{display_flag(flag_by_id.get(oid, ''))}".rstrip()
                         for oid in tiers["addons_offered"])
        lines.append("")
        lines.append("  The recommended/add-on split comes from the PROVISIONAL factor priority table — "
                     "VEP itself ranks nothing.")
    else:
        lines.append("ENABLE:")
        for oid in on:
            lines.append(f"  ✓ {name_by_id.get(oid, oid)} [{oid}] "
                         f"{display_flag(flag_by_id.get(oid, ''))}".rstrip())
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
                                              query, retrieval_mode=retrieval_mode, assembly_override=assembly)

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
            # DESCRIPTION TRUNCATION. Every one of the 58 descriptions is longer than 120 characters,
            # so at the default the model has never seen a complete one — and the cut lands badly:
            # check_existing is severed at "Returns existing variant IDs (e.g. rsIDs), C", one character
            # before the word ClinVar, which is the only place the prompt would explain why `clinvar`
            # depends on it. cadd loses "coding and non-coding", the exact property that exempts it from
            # the regulatory gate. Set desc_chars=None to send the full text (~+3.5k prompt tokens;
            # prefill is not the bottleneck, generation is, so it costs little).
            f"- **{opt['id']}** (`{opt.get('cli_flag', '')}`): {_desc(opt, desc_chars)}. "
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
                        retrieval_mode="keyword", examples_override=None, factor_tuple=None,
                        desc_chars=_SENTINEL):
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

def save_result(query, response, mode="recommend", warnings="", reasoning=""):
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
            # The model's own chain of thought. Kept because it is the actual decision process,
            # and it was previously discarded at the stream rather than recorded anywhere.
            if reasoning:
                f.write(f"\n## Model reasoning\n\n```\n{reasoning}\n```\n")
        print(f"\nResult saved to: {filename}")
    except OSError as e:
        print(f"\nWarning: Could not save result to {filename}: {e}")


# ---------------------------------------------------------------------------
# LLM streaming
# ---------------------------------------------------------------------------

# The answer and the model's reasoning share one generation budget, so the cap has to cover BOTH. At
# 4096 a long think could consume most of it and leave the answer truncated mid-sentence — observed on
# the README's own query, where the draft stopped at "Reason: Provides standard" and only two options
# survived. Measured need is ~1300-1700 reasoning + ~1100 answer tokens, and reasoning length varies
# run to run, so the cap is set well clear of the worst case. It costs nothing when unused.
_STREAM_MAX_TOKENS = 8192


def _delta_reasoning(delta):
    """The reasoning fragment in a stream delta, across the field names different servers use."""
    for attr in ("reasoning", "reasoning_content"):
        val = getattr(delta, attr, None)
        if val:
            return val
    return None


def _stream_native(model, system_prompt, user_message, think):
    """Stream from Ollama's OWN /api/chat, the only endpoint that honours `think`.

    The OpenAI-compatible /v1/chat/completions layer silently DROPS the parameter — passing it through
    `extra_body` changes nothing, which is why disabling reasoning first appeared to be impossible.
    Everything else is kept identical to the compat path so the only difference is the thinking phase.
    """
    import urllib.request
    body = {
        "model": model, "stream": True, "keep_alive": -1, "think": think,
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
                print(msg["content"], end="", flush=True)
    print()
    return answer, thinking


def stream_response(client, model, system_prompt, user_message, think=None):
    """Call the LLM with streaming; return (answer_text, reasoning_text).

    `think=False` skips the reasoning phase entirely, via the native endpoint. Measured over the 31-row
    set, single-threaded: 34.9s -> 18.1s per query with enable-F1 unchanged (78 -> 79%) and critical-recall
    slightly BETTER (92 -> 95%). Nothing is traded, so this is the default for the deployed model; pass
    --think to get the reasoning back. On the small model the gap is larger still and in the same
    direction (e4b gains 13 points of F1 with thinking off), so reasoning amplifies capability rather
    than substituting for it. See EXPERIMENTS.md Exp 14.

    THE DEPLOYED MODEL THINKS BEFORE IT ANSWERS, AND THAT USED TO LOOK LIKE A HANG. `gemma4:26b` emits
    its chain of thought into `delta.reasoning`, not `delta.content`. This function previously read only
    `delta.content`, so for the 14-20 seconds the model spent reasoning it discarded every chunk and
    printed nothing: measured 357 consecutive chunks with no content, then the answer starting at 14.3 s.
    From the outside that is indistinguishable from a stalled process, and it is the single biggest
    reason the tool felt unusable.

    So reasoning is now consumed as it arrives, surfaced as a live token count, and returned to the
    caller. Returning it matters beyond the progress display: it is the model's actual decision process,
    which is precisely what `--explain` claims to show and previously could not, because it was thrown
    away here.

    CAVEAT (unchanged): sets no temperature, so Ollama's default applies and the demo path is
    nondeterministic and at a different temperature than evaluate.py's — demo behaviour is not
    benchmarked behaviour.
    """
    if think is not None:
        return _stream_native(model, system_prompt, user_message, think)
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
        extra_body={"keep_alive": -1},
    )
    for chunk in stream:
        if not chunk.choices:                      # usage-only chunks carry no choices
            continue
        delta = chunk.choices[0].delta
        thought = _delta_reasoning(delta)
        if thought and not answering:
            reasoning_text += thought
            # One rewritten line, so the thinking phase is visibly alive without burying the answer.
            # ONLY on a terminal: `\r` overwrites in place there, but when stdout is a pipe or a file it
            # is just another character, so every update survives and buries the actual answer under
            # thousands of progress lines (34 KB of them, measured).
            if _tty:
                print(f"\r  thinking… {len(reasoning_text) // 4} tokens", end="", flush=True)
        if delta.content:
            if reasoning_text and not answering:
                print((f"\r  thought for ~{len(reasoning_text) // 4} tokens" + " " * 24) if _tty
                      else f"  (thought for ~{len(reasoning_text) // 4} tokens)")
            answering = True
            print(delta.content, end="", flush=True)
            response_text += delta.content
    if reasoning_text and not response_text:
        # The whole budget went on thinking and no answer survived. Say so: silently returning "" sends
        # an empty draft into the parser, which reads as "the model recommended nothing".
        print(f"\r  the model spent its entire generation budget (~{len(reasoning_text) // 4} tokens) "
              f"reasoning and produced no answer." + " " * 8)
    print()
    return response_text, reasoning_text


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

_CONTEXT_FLAGS = {"--species": "species", "--origin": "origin",
                  "--size": "variant_size_class", "--assembly": "assembly"}
_CONTEXT_CHOICES = {"assembly": ["GRCh37", "GRCh38"]}


def _parse_context_flags(args):
    """Pull `--species human --size structural-CNV ...` out of argv. Returns (context, error_or_None).

    Values are validated against the factor scheme rather than accepted blindly: a typo that silently
    did nothing would be worse than no flag at all, since the user would believe they had said it."""
    ctx = {}
    for i, a in enumerate(args):
        key = _CONTEXT_FLAGS.get(a.split("=", 1)[0])
        if not key:
            continue
        val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else "")
        allowed = _CONTEXT_CHOICES.get(key) or FACTOR_VALUES.get(key, [])
        if val not in allowed:
            return None, (f"{a.split('=')[0]} must be one of: {', '.join(allowed)}"
                          + (f" (got {val!r})" if val else " (no value given)"))
        ctx[key] = val
    return ctx, None


def run_recommend(client, model, vep_options, training_examples, user_query,
                   explain=False, skip_check=False, retrieval_mode="keyword", level="standard",
                   think=False, factor_think=False, clarify="state", context=None):
    """Run the recommendation mode (default).

    Args:
        skip_check: If True, skip the post-hoc constraint checker.
        retrieval_mode: "keyword" or "semantic".
        level: "minimal" (smallest runnable set), "standard" (default), or "full" (add every add-on).
    """
    if explain:
        print_decision_trace(user_query, vep_options, training_examples,
                             retrieval_mode=retrieval_mode)

    # Classify the query into factor values FIRST, so the option block can carry the priority that
    # applies to this scenario rather than the flat table of legacy use-case labels. A classifier
    # failure is non-fatal: factor_tuple stays None and the prompt falls back to the old block.
    # Say what is happening first: on the default settings this call reuses the recommendation model,
    # which takes a good ten seconds to answer, and it runs before anything else is printed. Silence
    # that long at startup reads as a hang.
    # The elapsed seconds are printed on the same line rather than kept for a summary: this call is the
    # first thing that happens and used to sit silent for ~8 s, so the number IS the progress indicator.
    # It also makes the reasoning-off change self-evidencing — run the same query with
    # VEP_FACTOR_THINK=1 and the difference is on screen, no harness needed.
    print("Reading the scenario…", end="", flush=True)
    t_classify = time.perf_counter()
    factor_tuple = infer_factors(client, model, user_query, think=factor_think, apply_defaults=False)
    t_classify = time.perf_counter() - t_classify
    print(f" {t_classify:.1f}s")
    # Anything the user stated on the form or the command line replaces what the classifier read, before
    # the assume/say-so policy runs — there is nothing to assume about a value we were given.
    factor_tuple, assembly, overridden = apply_user_context(factor_tuple, context)
    if overridden:
        print(f"  Using what you told me for: {', '.join(overridden)}.")
    if factor_tuple:
        # `assembly` goes IN as well as coming out: whatever the user stated on the form or the command
        # line is already settled, and re-asking a question someone has answered is the failure mode
        # this whole mechanism is built to avoid.
        factor_tuple, assembly = resolve_underspecified(factor_tuple, vep_options, clarify,
                                                        user_query=user_query, assembly=assembly)
        print("Detected scenario:")
        print(describe_factors(factor_tuple))
        print()

    system_prompt = build_system_prompt(vep_options, training_examples, user_query,
                                        retrieval_mode=retrieval_mode,
                                        factor_tuple=factor_tuple)
    print("Analysing your scenario...\n")

    t_recommend = time.perf_counter()
    try:
        response_text, reasoning_text = stream_response(client, model, system_prompt, user_query,
                                                        think=think)
    except Exception as e:
        print(f"\nError communicating with Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        print(f"And the model is pulled: ollama pull {model}")
        sys.exit(1)
    t_recommend = time.perf_counter() - t_recommend

    # Both phases, so it is never ambiguous which one a slow run was spent in. The two are separately
    # controllable — VEP_FACTOR_THINK for the first, --think for the second — and before this change
    # they were both reasoning, one of them invisibly.
    print(f"\n[{t_classify:.1f}s reading · {t_recommend:.1f}s analysing · "
          f"{t_classify + t_recommend:.1f}s total]")

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
            save_result(user_query, response_text, mode="recommend", warnings="",
                        reasoning=reasoning_text)
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
        # Restore must-haves BEFORE the depth flags run, so --minimal narrows a complete core rather
        # than a partial one, and --full widens from the same base.
        restored = restore_missing_critical(enabled, disabled, resolved, vep_options,
                                            training_examples, user_query,
                                            retrieval_mode=retrieval_mode)
        restored_report = format_restored_critical(restored, vep_options)
        if restored_report:
            print(restored_report)
        if resolved and level != "standard":
            removed = apply_config_level(enabled, disabled, resolved, level, vep_options,
                                         training_examples, user_query,
                                         retrieval_mode=retrieval_mode)
            note = (f"  ({len(removed)} recommended options dropped to leave the smallest runnable "
                    f"set; dependencies kept)"
                    if level == "minimal" else "  (every applicable add-on switched on)")
            print(f"\nCONFIG LEVEL: {level}\n{note}")
        elif level != "standard":
            print(f"\nCONFIG LEVEL: {level} requested, but the scenario's factors could not be "
                  f"resolved — showing the standard set.")
        corrected = format_corrected_config(enabled, disabled, vep_options, violations,
                                            resolved=resolved)
        print(corrected)
        warnings = "\n".join(x for x in (audit_report, warnings, restored_report, corrected) if x)

    save_result(user_query, response_text, mode="recommend", warnings=warnings,
                reasoning=reasoning_text)


def run_explain_result(client, model, user_query):
    """Run the VEP output explainer mode."""
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

    save_result(user_query, response_text, mode="explain", reasoning=reasoning_text)


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
    known_flags = ("--explain", "--no-check", "--semantic", "--minimal", "--full", "--think",
                   "--factor-think", "--assume", "--ask") + tuple(_CONTEXT_FLAGS)

    # A mistyped flag used to fall through into the query text: `--minmal "mouse variants"` asked the
    # model about "--minmal mouse variants" and quietly ran at the default level. Reject anything
    # unrecognised that looks like a flag instead, and list what is available.
    unknown = [a for a in args
               if a.startswith("--") and a.split("=", 1)[0] not in known_flags]
    if unknown:
        print(f"Unknown option(s): {' '.join(unknown)}")
        print(f"Available: {' '.join(known_flags)}")
        print('Usage: python vep_assistant.py [flags] "your analysis scenario"')
        sys.exit(2)

    # Reasoning is OFF by default on BOTH calls, and each has its own switch because they are separate
    # calls with separate costs. --think: recommender, 1.93x faster off with equal enable-F1 and better
    # critical-recall (Exp 14). --factor-think: classifier, 5.8x faster off with the same factor tuple on
    # 29/31 rows and no end-to-end change (89.5% vs 89.3% enable-F1, Exp 15). The flag beats the
    # VEP_FACTOR_THINK env var, which exists for the harness and the web app.
    think = False if "--think" not in args else None
    factor_think = True if "--factor-think" in args else False
    # What to do about anything the question did not say. Default states its assumptions;
    # --assume keeps quiet (scripts); --ask re-prompts where no assumption is safe.
    if "--assume" in args and "--ask" in args:
        print("--assume and --ask ask for opposite things; pick one.")
        sys.exit(2)
    clarify = "assume" if "--assume" in args else "ask" if "--ask" in args else "state"
    # What the user states outright about their data. These are facts they know; asking a model to infer
    # them from prose is where every measured classification failure came from.
    context, _ctx_err = _parse_context_flags(args)
    if _ctx_err:
        print(_ctx_err)
        sys.exit(2)
    explain = "--explain" in args
    skip_check = "--no-check" in args
    semantic = "--semantic" in args
    retrieval_mode = "semantic" if semantic else "keyword"
    # How much configuration the user wants back. --minimal for the smallest runnable set,
    # --full to switch on every add-on the scenario justifies; neither given = the standard set.
    if "--minimal" in args and "--full" in args:
        print("--minimal and --full ask for opposite things; pick one.")
        sys.exit(2)
    level = "minimal" if "--minimal" in args else "full" if "--full" in args else "standard"
    # Drop the context flags AND the value that follows a spaced one, so `--species human "query"`
    # does not leave "human" glued to the front of the query text.
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
                  retrieval_mode=retrieval_mode, level=level, think=think,
                  factor_think=factor_think, clarify=clarify, context=context)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # A run takes tens of seconds, so Ctrl-C part-way through is expected, not exceptional.
        # Exit quietly with the conventional 130 instead of dumping a traceback.
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
