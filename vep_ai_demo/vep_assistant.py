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
  --quiet     apply them and keep quiet (scripts and batch runs)
  --ask       also prompt you about gaps where no assumption is safe
"""

import json
import os
import re
import sys
import time
import datetime
from pathlib import Path

# The openai SDK is imported LAZILY, in main(), because it is needed in exactly one place — the client
# built for the recommender call. Importing it here made the SDK a hard requirement of merely importing
# this module, which six deterministic harnesses do purely to read the priority table. They need no
# model, no network and no SDK, and a missing dependency killed the process at import rather than at use.

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
    # The 23 stage-B examples live under legacy/ (moved 2026-09-22): the default path never reads
    # them, only --two-pass does, so a missing file is an empty corpus rather than an error.
    examples_path = Path(os.environ.get("VEP_EXAMPLES_FILE", BASE_DIR / "legacy" / "training_examples.json"))

    # RAISE, do not exit. Seven harnesses and the web app import this module and call this function;
    # a hard exit here killed their process instead of letting them report. main() catches and prints.
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


# --- The importance table ------------------------------------------------------------------------
#
# AUTHORED, NOT DERIVED (2026-09-22). `priority_by_factor.json` is the single source: one block per option,
# factor -> value -> priority. Until today it was derived at load from a DRIVES spec here plus per-option
# blocks in the catalogue, then dumped; four places to read to learn why one option was priced. The
# spec and the blocks are gone. Every comment they carried -- including the mentor quotes -- is in
# work/generation/generation_config/priority_by_factor_NOTES.md, unaltered.
#
# What stays computed is the SPECIES GATE: an option's species_restriction is a fact about the tool, not
# an opinion, so `load_priority_by_factor` stamps species.non-human = not_applicable from it at load.
# The drift the old derivation guarded against (edit the catalogue, forget the dump) cannot recur: the
# catalogue no longer holds priorities, so there is nothing to forget. `priority_table_covers` still
# catches an option the table has never heard of.

# TWO TIERS since 2026-08-19. `critical` is gone from the scheme, not merely hidden. The
# critical/recommended boundary was the one part of this table an expert reviewed, and twelve of her
# twenty edits moved options across it. Merging the DISPLAY made those corrections invisible, so they
# were never applied — while --minimal, restore_missing_* and the must-have metric went on reading the
# uncorrected boundary. Removing the tier removes the unvalidated judgement instead of hiding it.
RANK = {"recommended": 2, "optional": 1, "not_applicable": 0}


def validate_priority_table(table, factors_cfg=None):
    """Problems in `priority_by_factor.json`, as a list of human-readable strings. [] when clean.

    The table is hand-authored, so every kind of typo in it used to be able to fail silently: a misspelt
    label was dropped, a misspelt factor or value was stored under a key nothing reads. The entry looked
    accepted and did nothing. `verify_pipeline.py` asserts this returns []; the engine warns and carries
    on, because a maintainer's typo should not take a user's session down with it."""
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
    """The importance table from `priority_by_factor.json`, with the species gate stamped on.

    THE FILE IS THE SOURCE. It is required: there is no derivation to fall back to. It carries every
    authored priority; what it does not carry is species, which is stamped here from each option's
    `species_restriction` -- a fact about the tool, not an opinion, so it lives with the option. Plugins
    are skipped: Ensembl's own per-plugin species lists decide for them in the checker (2026-09-20).
    """
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
    # SPECIES GATE, computed. Same rule the old derivation applied: a human-only restriction, or a narrow
    # "human + <one species> only" set the binary factor cannot guarantee matches the query, gates the
    # option for non-human. Plugins are judged by Ensembl's lists in the checker, not by this prose.
    narrow_nonhuman = re.compile(r"human\s*\+\s*\w+.*only", re.IGNORECASE)
    _sd = load_species_data() or {}
    plugin = set(_sd.get("plugin_species") or {}) | set(_sd.get("plugin_species_all") or ())
    priorities = table.setdefault("priorities", {})
    for o in vep_options:
        if o["id"] in plugin:
            continue
        restr = o.get("species_restriction", "all species")
        if _is_human_only(restr) or narrow_nonhuman.search(restr or ""):
            priorities.setdefault(o["id"], {}).setdefault("species", {})["non-human"] = "not_applicable"
    return table



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
# THE THIRD PRIORITY WAS DELETED ON 2026-08-19, twelve days after this display merge. Keeping it
# internally is what let twelve of Likhitha's twenty edits go unapplied: merging the display made
# critical<->recommended moves invisible while --minimal, the restore and must-have recall went on
# reading the boundary she had redrawn. All three were redefined on the RECOMMENDED bucket, which is
# the one she reviewed and the one the user sees. `critical` now names nothing in this scheme, and
# `strongest()` ignores it rather than ranking it, so a stale table cannot bring it back.
#
# The LEGACY `priority_by_use_case` field is a different axis (seven use cases, not five factors) and
# still carries 26 `critical` entries. It feeds get_confidence and the offline scorer, and deleting the
# label there would silently demote every legacy critical to "low".
#
# One map, so the CLI, the web payload and the review export cannot drift apart.
DISPLAY_TIER = {"recommended": "recommended", "optional": "add-on"}


# Form controls InputForm.pm renders for HUMAN ONLY, so they are ticked-by-default only on a human
# run. `af` and `pubmed` sit inside the `_stt_Homo_sapiens` div at 574-612; `tsl`, `appris` and `mane`
# carry the same field_class at 674 / 684 / 694. All five are under the same
# `if (first { $_->{'value'} eq 'Homo_sapiens' } @$species)` guard.
#
# `clinvar` is here on a different axis. It has no control of its own -- it rides on `check_existing`,
# whose field_class is `_stt_var`, i.e. any species carrying variation data, mouse included. ClinVar
# is human-only DATA, which is why it belongs in this set; the earlier note claiming the fieldset was
# human-wrapped was wrong about the form.
#
# Every other `web_default_on` control renders for all species. Verified against
# `work/ensembl_source/VEP/InputForm.pm` (all 38 add_field blocks) on 2026-09-14.
_HUMAN_ONLY_FORM_DEFAULTS = frozenset({"appris", "tsl", "mane", "af", "clinvar", "pubmed"})


def _form_default_on(oid, vep_options, species):
    """True when the web form ships this option ticked FOR THIS SPECIES (mentor instruction,
    2026-09-13: what the form has on by default is assumed on and not recommended)."""
    opt = next((o for o in vep_options if o["id"] == oid), None)
    if not opt or not opt.get("web_default_on"):
        return False
    # Callers pass EITHER the factor value ("human") or the Ensembl production name ("homo_sapiens",
    # from resolve_species_name). Until 2026-09-15 only the first was recognised, so on every human
    # query the human-only defaults -- APPRIS, TSL, MANE, ClinVar, PubMed, 1000 Genomes AF -- were
    # judged NOT already on and printed as recommendations, undoing the mentors' instruction for
    # exactly the options it covers.
    is_human = species in (None, "human", "unknown") or str(species).lower().startswith("homo_sapiens")
    if oid in _HUMAN_ONLY_FORM_DEFAULTS and not is_human:
        return False
    return True


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

def _factor_scheme():
    """(values, multi, hard gates) read from factors.json. The file is the single source: it ships
    inside the engine, so there is no literal fallback to drift from it (removed 2026-09-22)."""
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
    """Strongest soft priority among labels (recommended>optional), ignoring
    not_applicable/None. Returns the label str or None if none apply."""
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
    """Compact, deterministic label for a tuple (for ids / filenames)."""
    # Derived from the tuple rather than naming the five factors and assuming which are lists: that
    # assumption is a second copy of the scheme, and it crashed the moment a factor's cardinality
    # changed in factors.json. Order follows FACTOR_VALUES so the slug stays stable and readable.
    parts = []
    for f in FACTOR_VALUES:
        v = factor_tuple.get(f)
        parts.append("+".join(v) if isinstance(v, list) else str(v))
    return "__".join(parts).replace("-", "").replace("_", "")


# --- One VEP run per variant size, when the callset holds both ---------------------------------------
#
# The web form cannot express a configuration covering both sizes at once. CADD's control is a four-way
# drop-down over annotation files (SNVs and InDels / SNVs / InDels / CADD-SV) and choosing one excludes
# the rest, so a single run cannot score short and structural variants together. Likhitha raised it in
# reply to the re-prompting proposal; the four labels are in the catalogue as `web_form_values`, read
# off the live form and NOT present in our release/115 snapshot.
#
# The factor STAYS `select: multi`, and the evidence for that is untouched: defaults_evidence.py still
# shows that assuming both loses options on 0 of 29 ablations where single-select loses on 15. What
# moved is the OUTPUT. The split now happens where the form imposes it, at render time, one
# configuration per size, instead of one union configuration nobody can enter.
SIZE_FACTOR = "variant_size_class"
SIZE_PASS_LABELS = {"small": "short variants (SNVs and indels)",
                    "structural-CNV": "structural variants and CNVs"}


def size_passes(factor_tuple):
    """[(size_value, label, factor tuple)] - one entry per VEP run this scenario needs.

    One pass when a single size is active, which is every row of the 31-row review set. Two when both
    are, whether the user said so or the assume policy filled it in. Each returned tuple is a COPY with
    the size pinned to one value, so the resolver, the hard gates and the checker run unchanged and none
    of them needs to know that passes exist.
    """
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
    """(form value for this pass, reason it is unavailable) for a size-dependent control.

    CADD is the only option carrying `web_form_values` today. The structure is general because Q6 of the
    round-2 sheet says ten form controls are values or modes rather than switches, and this is the first
    of them the output has had to name.

    A reason is returned when the value this pass needs is ruled out by a STATED assembly - CADD-SV is
    GRCh38-only. An unstated assembly returns none, matching the assembly gate elsewhere: act on what
    the user said, stay open when they said nothing.
    """
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
    """Remove options this pass cannot run, returning [(oid, why)]. Mutates `enabled`.

    An option left switched on with no usable data file behind it is the empty-column failure this
    project keeps finding elsewhere: it looks like an answer and returns nothing.
    """
    gone = [(oid, reason) for oid in sorted(enabled)
            for _lab, reason in [size_dependent_choice(oid, size_value, vep_options, assembly)]
            if reason]
    for oid, _ in gone:
        enabled.discard(oid)
    return gone


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


def intent_priorities(factor_tuple, catalogue, pbf, factors_cfg, enable=("recommended",), trace=None):
    """Pre-checker intent: {oid: (enabled_bool, priority_or_None, gated_bool)} from factor priorities.

    `enable` is the set of priority labels that switch an option ON. Since the tier removal there is
    one such label, `recommended`; the argument survives so a caller can still ask for a different
    enable set without a code change.

    `trace`, if a dict is passed, is FILLED IN with why each option came out the way it did:

        trace[oid] = {"priority": str|None,
                      "votes":   [(factor, value, label), ...],   every rule that spoke
                      "winner":  (factor, value, label)|None,     the one the max selected
                      "gated_by": [(factor, values), ...]}        hard gates that removed it

    The return value is UNCHANGED — thirteen call sites unpack the 3-tuple, so the derivation goes
    out through this parameter rather than by widening the tuple. Nothing in the resolve path passes
    it; it exists because the winning rule was being computed here and thrown away one line later at
    `strongest(labels)`, leaving every downstream surface able to show the conclusion and not the
    reason. `labels` is still built exactly as before, so `strongest` sees a byte-identical input."""
    av = active_values(factor_tuple)
    priorities = pbf["priorities"]
    cond_rules = factors_cfg.get("conditional_rules", [])

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
        if gated:
            out[oid] = (False, None, True)
            if trace is not None:
                trace[oid] = {"priority": None, "votes": [], "winner": None,
                              "gated_by": [(hf, av.get(hf, [])) for hf in HARD_GATE_FACTORS
                                           if av.get(hf) and all(pf.get(hf, {}).get(v) == "not_applicable"
                                                                 for v in av[hf])]}
            continue
        # (2) soft ranking over ALL active factor values
        labels, votes = [], []
        for f, vals in av.items():
            for v in vals:
                lab = pf.get(f, {}).get(v)
                labels.append(lab)                     # unchanged: strongest() sees the same list
                if lab:
                    votes.append((f, v, lab))
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
                    votes.append(("conditional rule",
                                  " + ".join(f"{k}={v}" for k, v in rule["when"].items()), lab))
        pr = strongest(labels)
        out[oid] = (pr in enable, pr, False)
        if trace is not None:
            winners = [t for t in votes if t[2] == pr]
            trace[oid] = {"priority": pr, "votes": votes,
                          "winner": winners[0] if winners else None, "gated_by": []}
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


FACTOR_CLASSIFIER_PROMPT_V1 = (
    "You read a researcher's natural-language question about annotating genetic variants and identify ONLY "
    "what the question actually states or clearly implies about the analysis. Do NOT guess; if the question "
    "does not indicate a characteristic, use \"unstated\" (or [] for a list).\n\n"
    "Reply with ONLY this JSON object, no prose:\n"
    "{\n"
    # FIRST, because _schema_lines() emits no trailing comma on its last factor and a field appended
    # after it would render the example as invalid JSON.
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


# V2 (2026-09-16). Two changes from V1, both from one diagnosed failure: with reasoning on, gemma4:26b
# read "Are any of these likely to be disease-causing?" as a request for the ANSWER rather than for a
# configuration, dithered between configure and out-of-scope for ~13,000 characters and hit the token
# cap with no JSON. V1 never said who is asking or why, so that reading was open.
#   1. A role opening: the model is step one of a VEP-settings tool, and a question about the user's
#      own variants is a request for the settings that answer it.
#   2. The question moves out of the system message into the user message (`classifier_messages`).
# V1 is kept verbatim and reachable with VEP_CLASSIFIER_PROMPT=v1, so the change can be A/B'd.
# First V2 draft (with a "what do they hit?" example and no line about unstated factors) fixed 5 grid
# cases but broke 15 "absent" ones: goal filled as basic-consequence (10), origin as germline (5). The
# last sentence of the opening is there for that.
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
    # FIRST, because _schema_lines() emits no trailing comma on its last factor and a field appended
    # after it would render the example as invalid JSON.
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


# The name every caller already imports. It is the INSTRUCTIONS only under v2; under v1 it is the old
# text that ends in "Question:\n" and expects the query appended to it.
FACTOR_CLASSIFIER_PROMPT = FACTOR_CLASSIFIER_PROMPT_V1 if _classifier_prompt_version() == "v1" else FACTOR_CLASSIFIER_PROMPT_V2


def classifier_messages(user_query, hint=""):
    """The classifier's chat messages. One builder, so the CLI, the web app and every harness send the
    same thing. v2: instructions in system, the researcher's message (plus any species hint) in user.
    v1: the historical layout, query appended to the system prompt."""
    q = user_query or ""
    if _classifier_prompt_version() == "v1":
        return [{"role": "system", "content": FACTOR_CLASSIFIER_PROMPT_V1 + q + hint},
                {"role": "user", "content": "Return the JSON classification."}]
    return [{"role": "system", "content": FACTOR_CLASSIFIER_PROMPT_V2},
            {"role": "user", "content": q + hint}]


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
    # SCOPE. Under --single-pass there is no draft, so `is_out_of_scope_response("")` returns False and
    # the only hard stop in the pipeline is disabled exactly when nothing can judge the request. The
    # tuple cannot decide this alone -- "hi" and "annotate my VCF" both state no factors -- so the
    # judgement rides on the classifier call that already runs. Unrecognised or absent -> "configure",
    # so a classifier that ignores the field leaves shipped behaviour unchanged.
    rt = obj.get("request_type")
    out["_request_type"] = rt if rt in ("configure", "not-vep", "vep-support") else "configure"
    # ORGANISM (2026-09-20). The binary species factor cannot say WHICH non-human organism, and the
    # data lists (SIFT, frequency files, per-plugin species) are per species. The model reads the name;
    # `resolve_model_organism` checks it against Ensembl's own index, so an invented name cannot enter.
    # Under the V1 prompt the field is absent and this is None, as before.
    out["_organism"] = resolve_model_organism(obj.get("organism"))
    return out


# How long Ollama keeps the model resident after a call. -1 means FOREVER, which is right on a
# dedicated eval box: reloading a 16 GB model between queries would dominate the timings this project
# publishes. It is wrong on a laptop the user is also working on -- pinning a model larger than free
# RAM froze a 16 GB machine on 2026-09-03. Env-overridable so the eval boxes keep the measured
# behaviour and a shared machine can set VEP_KEEP_ALIVE=5m (or 0 to unload immediately).
def _keep_alive():
    """Ollama wants a NUMBER (-1 = forever, 0 = unload) or a duration string ("5m"). An env var is
    always a string, so VEP_KEEP_ALIVE=-1 -- the obvious way to write the default explicitly -- used
    to be sent as "-1" and Ollama rejected every call with
        HTTP 400  time: missing unit in duration "-1"
    Numeric strings are coerced back to int so both spellings work. Confirmed against Ollama on
    2026-09-06: -1 and "5m" accepted, "-1" rejected."""
    v = os.environ.get("VEP_KEEP_ALIVE")
    if v is None:
        return -1
    try:
        return int(v)
    except ValueError:
        return v


KEEP_ALIVE = _keep_alive()


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
    """How the classifier should reason. DEFAULT ON since 2026-09-20 (David's decision).

    Measured on the 150-case grid (600 queries, gemma4:26b, prompt v2): all four versions of a case
    right on 148/150 with reasoning on against 138/150 off. It fixes the species cases the bare call
    misreads ("kennel owners, not their Labradors"), and on the organism-naming set it never names an
    animal and then answers "human" (0 of 242 contradictions, against 20 off). Cost: ~4 s a query
    against ~0.9 s, and ~530 output tokens against ~86.
    Against it: on the 31 plainly worded review scenarios it is slightly worse (28/31 by configuration
    against 30/31), reading two basic-goal scenarios as clinical interpretation.
      unset / 1  -> True    reasoning on, native endpoint  (default)
      0          -> False   reasoning off                  (the fast arm; `--no-factor-think`)
      compat     -> None    the original /v1 path, byte-identical to before this change
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

    SPECIES is the classifier's answer (since 2026-09-16; before that the keyword scan in
    infer_species() overrode it). An "unstated" answer is returned as "unstated" with
    apply_defaults=False, so the assume-human policy discloses it, and as "human" otherwise.

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
    if think is False:                       # the unrequested default: the env / the shipped setting
        think = _factor_think_setting()
    try:
        if think is None:                    # the original path, unchanged
            resp = client.chat.completions.create(
                model=model,
                messages=classifier_messages(user_query,
                                             format_species_hint(user_query) if _species_hint_on() else ""),
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

    # SPECIES: rule-overrides-model, or model-decides-on-evidence.
    #
    # The default is the historical behaviour -- `infer_species()` wins outright. That is a
    # first-match-wins keyword scan with no judgement, and it is wrong in both directions on real
    # text: "going down this rabbit hole" -> rabbit on a homo_sapiens VCF, "somatic ... zebra finch"
    # -> human, `Salmo salar` -> unknown -> treated as human. The model answers this factor correctly
    # in all three cases and its answer was being discarded here.
    #
    # With VEP_SPECIES_HINT=1 the scan instead REPORTS every match into the prompt, flagged with why
    # each might be a false hit, and the model decides. The regex supplies recall over 356 species;
    # the model supplies the judgement a regex cannot have. The model's answer is validated against
    # the index, so it cannot invent a species, and an unrecognised answer falls back to the rule.
    # UNSTATED SPECIES REACHES THE POLICY LAYER (2026-09-14). This used to map "no organism named"
    # straight to "human" here, so the assume-human fallback fired on every such query with no
    # `Assumed species = human` line -- the masking Exp 18 measured and fallback_e2e reproduced end
    # to end (14/14 silent, rule and hint alike). Same contract as analysis_goal: with
    # apply_defaults=False the tuple says "unstated" and UNDERSPECIFIED_POLICY assumes human OUT LOUD;
    # with apply_defaults=True (older callers) the value is filled here exactly as before.
    def _species_from_rule(hint_mode):
        sp = infer_species(user_query)
        if sp not in ("human", "unknown"):
            return "non-human"                  # a named organism: recall is the rule's job in both modes
        # A "human" reading from the rule comes from _HUMAN_SIGNALS, 7 of whose 28 words are analysis
        # words ("somatic", "tumour", "cancer", ...). In HINT mode the model has already been asked and
        # said "unstated", so that reading is not evidence of a stated species -- it is the fallback,
        # and the fallback belongs to UNDERSPECIFIED_POLICY where it is disclosed. In override mode the
        # rule keeps its old authority. Measured 2026-09-14: without this, 11 of 14 species-removed rows
        # still came out "human" with no disclosure.
        if sp == "human" and not hint_mode:
            return "human"
        return "human" if apply_defaults else "unstated"
    # THE MODEL DECIDES SPECIES BY DEFAULT (David, 2026-09-16). Until now the hint-off branch handed
    # species to `_species_from_rule(False)`, i.e. the keyword scan overrode the model outright -- the
    # opposite of what the 2026-09-15 handover described. Measured on factor_grid.py's 30 species cases
    # (gemma4:26b, shipped call): model trap 29/30, twin 27/30; keyword scan trap 17/30, twin 22/30.
    # An "unstated" answer is NOT sent to the scan: it reaches UNDERSPECIFIED_POLICY, which assumes
    # human and says so. VEP_SPECIES_HINT=1 keeps the older hint design (scan matches shown to the
    # model, scan as fallback).
    said = (rec.get("species") or "").strip().lower()
    if _species_hint_on():
        rec["species"] = said if said in ("human", "non-human") else _species_from_rule(True)
    else:
        rec["species"] = said if said in ("human", "non-human") else ("human" if apply_defaults else "unstated")
    # THE NAME DECIDES THE BINARY FACTOR (2026-09-20). Measured on organism_naming.py, 242 queries with
    # reasoning off: the model named an animal and then answered `species: human` on 20 of them
    # ("organism": "mus musculus", "species": "human" in one object). Deriving the factor from its own
    # answer takes the binary from 221/242 to 241/242, matching the reasoning-on arm at a twentieth of
    # the cost. Reasoning on contradicts itself 0/242, so there this is a no-op.
    # Only ever upgrades to non-human: an organism named in passing is the risk, and on the 121 decoy
    # cases ("my supervisor works on X, but the samples are Y") the model named the sample every time.
    if rec.get("_organism") and rec["_organism"] != "homo_sapiens" and rec.get("species") != "non-human":
        rec["species"] = "non-human"
    if apply_defaults and not rec.get("analysis_goal"):
        rec["analysis_goal"] = ["basic-consequence"]
    return rec


# --- What to do when the question simply doesn't say -------------------------------------------------
#
# A factor the question never mentions contributes NOTHING, so every option it would have supplied
# disappears silently. Measured over the 31 review rows, mean options lost when one factor is blanked:
# origin 1.0, variant_size_class 1.0, region_focus 4.4, analysis_goal 5.4 (worst row 17). The generated
# rows never show the problem directly, because Stage 3 wrote them to express their tuple — all 31 are
# fully specified, which is what makes the controlled ablations in `ablate_queries.py` necessary.
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
    # ASSUMED HUMAN, AND SAID SO (2026-09-14). The value is unchanged -- human has always been the
    # fallback, because withholding the human-only options from the many human queries that never say
    # "human" is the larger harm -- but until now it was applied inside infer_factors with no
    # disclosure, so a mouse query that never named the mouse got a human configuration silently.
    # The both-directions default sweep priced this as the weakest guess (row- AND column-lossy when
    # wrong), which is exactly the case for saying it out loud like the other four.
    "species": {
        "assume": "human",
        "why": "you didn't name an organism, so human is assumed and the human-only options stay "
               "available. Say the species if it isn't human",
    },
    "region_focus": {
        "assume": ["coding", "regulatory-noncoding"],
        "why": "you didn't say which regions matter, so both are covered",
    },
    # FAIL-CLOSED, and measured: leaving this open is NOT the safe choice, which was the first guess.
    # Sharper than that, and verified by `work/harness/suites/defaults_evidence.py` across all 31 review rows:
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
    #
    # UPDATE 2026-09-14: `frequency` is now an ADD-ON under population-frequency (David; see
    # MENTOR_MESSAGES.md 2026-09-14, pending Likhitha's answer on rare-variant work). So the paragraph
    # above describes the cost as it stood: today guessing somatic moves NOTHING in RECOMMENDED, and
    # `defaults_evidence.py` asserts that origin changes no enabled option on any tuple. Somatic stays
    # the guess because the somatic hard rule still keeps the filter out of the add-ons, and silence is
    # now free either way -- the only thing left to disclose is the reading itself.
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
    # this factor meets neither condition. The rule asks about it on 12 of the 12 ablations where it was
    # the deleted fact, and the fallback value loses options on 5 of those 12 -- subtractive error, the
    # direction that costs a user a finding rather than a column. (11/11 until the ablation set was
    # rebuilt at three seeds; defaults_evidence.py is the number of record.)
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
# The bar is the bucket the user is actually shown: RECOMMENDED.
#
# It was deliberately NOT the internal `critical` tier, back when that tier existed and the mechanisms
# around it (`restore_missing_recommended`, `--minimal`, must-have recall) were keyed on it. The tier
# was deleted on 2026-08-19 and those three moved onto this same bucket, so the choice recorded here is
# now the only reading available. The argument is kept because it is why the tier went. The critical/recommended
# boundary is the one the mentor review found unstable: twelve of Likhitha's twenty edits were
# critical<->recommended moves, which is why the display was merged in the first place. Deciding
# whether to INTERRUPT A USER on a boundary the reviewer redrew twelve times out of twenty edits — and
# that the user never sees — makes the interruption depend on a label nobody agrees on.
#
# The two readings were priced before choosing: on the current guesses they raise identical questions
# (`work/harness/suites/ask_rate.py`, arms `shipped` and `shipped+wide-bar`), so the wider bar costs nothing
# today. It diverges only if the guesses are removed, where it adds 6 `origin` questions. Named rather
# than hardcoded so the comparison stays runnable.
ASK_BAR_PRIORITIES = ("recommended",)


# The one option family whose leakage DESTROYS data instead of adding noise. These are values of the
# form's single "Restrict results" drop-down: each collapses the result file (a leaked per_gene
# measured 334 -> 19 transcript rows on the 10-variant panel — 94% of the user's annotation lines
# gone, work/results/leak_rate_README.md). The priority table prices none of them for any of the
# 108 factor tuples, yet the model proposes them from old examples (a tester hit `pick` on a
# rare-disease query, 2026-09-07). Everything else the model adds is at worst an extra column, so
# the gate is deliberately THIS NARROW: enforcing the whole table would change the enabled set the
# published numbers describe, while this family is unpriced everywhere, so stripping it moves
# nothing the table ever endorsed. The eval harnesses score the raw parse and never see this gate.
RESTRICT_RESULTS_FAMILY = ("pick", "pick_allele", "per_gene", "most_severe", "summary")


def enforce_restrict_results_gate(enabled, resolved):
    """Remove restrict-results values the priority table did not price for THIS scenario.

    Returns the removed ids. No-op when the factor resolution is unavailable (legacy path), and a
    family member the table DOES price for the scenario passes — the gate enforces the table's
    silence, it does not overrule its voice."""
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
    Asking on model uncertainty instead would raise a question wherever the classifier felt unsure,
    which is not the same thing as the answer mattering."""
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

# The other half of the draft prompt's `## Scope` rule: a question that IS about VEP but is not a
# request to configure a run. Separated from OUT_OF_SCOPE_NOTE because the useful reply differs —
# this user is not confused about what the tool is for, they want something it does not do.
VEP_SUPPORT_NOTE = (
    "  This assistant only recommends which Ensembl VEP options to switch on for a given analysis.\n"
    "  It does not diagnose errors, explain output columns, or help with installing or running VEP.\n"
    "  For those, see the Ensembl VEP documentation and the Ensembl helpdesk. If you do want a\n"
    "  configuration, describe what you are annotating and what you need out of it."
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


ASSEMBLY_ASSUMED_WHY = ("the VEP web form serves GRCh38 and directs GRCh37 users to a separate site, so GRCh38 is assumed — say GRCh37 if that is your build")


def clarification_plan(rec, vep_options, user_query=None, assembly=None):
    """Given the RAW classification (apply_defaults=False), decide per open factor: assume, or ask.

    Returns (filled_tuple, assumptions, questions). `assumptions` are stated to the user rather than
    hidden — the point of this whole mechanism is that the tool stops making invisible choices.

    ASSEMBLY no longer appears in `questions`: since 2026-09-15 it is assumed (GRCh38) and disclosed
    like any other filled-in value, so `analysis_goal` is the only question the system still raises.
    The assembly decision lives here rather than in `resolve_underspecified`
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
        # species is no longer skipped here (2026-09-14): infer_factors now hands an unnamed organism
        # through as "unstated", so the assume-human policy below runs and is disclosed like the rest.
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
        # ASSEMBLY IS ASSUMED, NOT ASKED (David, 2026-09-15). `assembly_question` still decides
        # RELEVANCE -- build already stated, non-human, nothing assembly-restricted at the bar -- and
        # stays a function because ask_rate monkeypatches it to toggle that arm. Where it used to
        # raise a question we now fill GRCh38 in and disclose it, for the reason recorded in
        # resolve_underspecified: the form serves GRCh38 and sends GRCh37 users elsewhere, and the two
        # wrong guesses are not equal -- GRCh38 costs one ADD-ON, GRCh37 costs four RECOMMENDATIONS.
        for _f, _why, _at_stake in assembly_question(stated, vep_options, user_query, assembly):
            assumptions.append(("assembly", "GRCh38", ASSEMBLY_ASSUMED_WHY))
    return rec, assumptions, scored


def assembly_question(stated, vep_options, user_query=None, assembly=None):
    """The assembly question, as a zero-or-one-item list in the same shape as the factor questions.

    Suppressed when the text already names a build, when the user stated one, when the query is
    non-human (species gates those options long before an assembly could matter), and when nothing
    assembly-restricted is at the bar — which is the same relevance test every factor gets.

    SCORED ON WHAT THE USER STATED, not on the tuple after our own assumptions are folded in, and the
    difference is not small: assuming *both* variant sizes switches gnomAD-SV on for almost every
    query, and gnomAD-SV is GRCh38-only, so scoring the filled tuple interrupts 40 of the 78 ablations
    against 34 for the stated one. Six of those interruptions would exist only because WE guessed.
    Regenerate both counts with ask_rate.py, whose `assembly at stake` line exists so this docstring
    cannot silently go stale again (its previous figures were the retired 81-ablation set's).
    That follows the asymmetry the whole policy rests on: an option we added is a column the user can
    ignore, so it is not worth a question, while an option their own words called for is. MANE is
    unaffected either way (16 either way) because a stated clinical goal is what puts it there."""
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


# PLAIN ENGLISH FOR THE CHOICES, not the scheme's own vocabulary. The question sentence below was
# always readable; the numbered list under it printed the internal value ids -- `basic-consequence`,
# `regulatory-noncoding` -- which name nothing a first-time user has seen. The ids stay the contract
# everywhere else; this is the one place a human reads them. Anything unlabelled falls back to the id,
# so a new factor value degrades to the old behaviour rather than disappearing.
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
    multi = factor in MULTI_FACTORS
    print(f"\n  {_FACTOR_PROMPTS.get(factor, factor)}")
    for i, v in enumerate(values, 1):
        print(f"    {i}) {_FACTOR_VALUE_LABELS.get((factor, v), v)}")
    if multi:
        # "both" is only English when there are two. analysis_goal has three values, so the old
        # hardcoded "4) both" asked the user to pick both of three.
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
    """Put the assembly question. Same contract as `_ask_factor`: skipping is free and never blocks.

    CURRENTLY UNREACHABLE (2026-09-15). The build is assumed to be GRCh38 and disclosed, because the
    form of record serves GRCh38 and sends GRCh37 users to a separate site, and because the two wrong
    guesses are not equal -- GRCh38 costs one add-on, GRCh37 costs four recommendations. See
    `clarification_plan`. This stays so that restoring the question is a one-line change there."""
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
    every other factor has a safe value and reaches no question. Over the 78 clean ablations that is 12
    questions on 12 queries, all `analysis_goal` (`work/harness/suites/ask_rate.py`, the number of record).
    It was 46 on 40 until 2026-09-15, when assembly stopped being asked and became a GRCh38
    assumption: 34 of the 40 were the build. The ablations are the stress test, not the experience: on the 31
    review rows AS WRITTEN it asks nothing on 15, never asks two questions, and never asks about
    `analysis_goal` at all -- the only question that fires is the build, on human rows.

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
            # `_ask_assembly` is UNREACHABLE since 2026-09-15: clarification_plan records the build
            # as a GRCh38 assumption instead of a question, so "assembly" never enters `questions`
            # (checked: 0 of 252 tuples). Kept so restoring the question is a one-line change there,
            # not a rewrite here.
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

    # ASSEMBLY. `clarification_plan` has already decided this and recorded it as an assumption; all
    # that is left here is to put the value in the RETURN, because assembly rides alongside the tuple
    # rather than in it. The decision and its measurement live there, in one place, so the CLI, the
    # web app and try_reprompting cannot drift apart.
    if assembly is None:
        assembly = next((v for f, v, _w in assumptions if f == "assembly"), None)

    if mode != "assume" and (assumptions or questions):
        print()
        for factor, value, why in assumptions:
            shown = ", ".join(value) if isinstance(value, list) else value
            # The VALUE, not the argument for it (David, 2026-09-15). The reasoning is still carried
            # in `assumptions` for --explain and for the JSON; it just stopped being read aloud to
            # someone who only wants to know what was filled in.
            print(f"  Assumed {factor} = {shown}")
        for factor, why, at_stake in questions:
            # `at_stake` is the list of must-have ids the answer moves, not a count. Printed as a count
            # once, which rendered as "would change ~['gnomad_sv'] options".
            names = ", ".join(at_stake) if at_stake else "part of the configuration"
            how = "run in a terminal to be prompted" if mode == "ask" else "--ask to be prompted"
            print(f"  Left open: {why} (decides {names}; {how}).")

    # Which factors were filled in rather than read. `_`-prefixed, so active_values and the decision
    # trace skip it, same convention as _request_type.
    filled["_assumed"] = sorted(f for f, _v, _w in assumptions)
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


# The model's own contradiction signals, read off the SAME line/stanza as the ✓ (see the rule in
# extract_recommendations_detailed). `priority=` here is model-generated prose, not a faithful echo of
# what the prompt showed — on the observed line the prompt said "no priority for this scenario" and the
# model wrote "NOT APPLICABLE" — so it is treated as the model's intent, which is exactly what is wanted.
_NA_PRIORITY_RE = re.compile(r"priority\s*=\s*not[\s_]*applicable", re.IGNORECASE)
_DISABLE_REASON_RE = re.compile(
    r"\s*(disabled|not applicable|not needed|not relevant|not required|should not|excluded)\b",
    re.IGNORECASE)


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


# ---------------------------------------------------------------------------
# Post-hoc constraint checker (runs AFTER LLM output, BEFORE display)
# ---------------------------------------------------------------------------

# Priority ranking for conflict resolution (higher number = higher priority)

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


_SPECIES_INDEX = None


def _species_hint_on():
    """Whether the species scan is shown to the classifier as rejectable hints.

    OFF BY DEFAULT since 2026-09-15 (VEP_SPECIES_HINT=1 turns it back on). It was on for one day, on
    the strength of 14/14 against the keyword OVERRIDE's 7/14 -- a comparison that was never run
    against the plain model. Run against the plain model it loses:

        species recall, 60 case-seeds   hinted 60  bare 57     +1  (one distractor case)
        24 keyword traps                hinted 23  bare 24     -1
        31 review rows, exact tuple     hinted 21  bare 22     -1
        species accuracy on those rows  31/31 either way        0

    It never improves the factor it exists for, and it damages a different one. The mechanism: the
    index carries "human" flagged as an ordinary English word, so the block fires on 30 of the 31
    rows and appends ~100 words of species disambiguation -- Sonic Hedgehog, Platypus, Turkey, "rabbit
    hole" -- to queries with no species ambiguity at all. On one row that is enough to push
    `clinical-interpretation` out of `analysis_goal`, losing CADD, ClinVar, Mastermind and Phenotypes
    on a query that asked whether a variant is a cancer driver.

    The scan itself is untouched and still available: `infer_species` remains the fallback when the
    model answers `unstated`, and `species_candidates` still covers all 356 species for anything that
    wants it."""
    return os.environ.get("VEP_SPECIES_HINT") == "1"


_SPECIES_DATA = None


def load_species_data():
    """Per-species DATA availability -- SIFT, PolyPhen, CCDS, variant synonyms, custom frequency files --
    built by work/harness/build/build_species_data.py from Ensembl's own sources. None if absent (additive:
    without it the gate below does nothing and non-human keeps the pre-2026-09-15 behaviour)."""
    global _SPECIES_DATA
    if _SPECIES_DATA is None:
        p = BASE_DIR.parent / "work" / "generation" / "generation_config" / "species_data.json"
        _SPECIES_DATA = json.load(open(p)) if p.exists() else {}
    return _SPECIES_DATA or None


def species_key(production_name):
    """`ovis_aries_texel` -> `ovis_aries`: the data lists are per species, the index is per strain."""
    return "_".join((production_name or "").split("_")[:2])


def load_species_index():
    """The 756-name / 356-species index, or None if it has not been generated.

    Regenerate with `work/harness/build/build_species_index.py`. Absent, everything falls back to the
    16-species `_SPECIES_KEYWORDS` scan, so this is additive.
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
    """EVERY Ensembl species name the query mentions, longest first, with why each may be a false hit.

    Deliberately not first-match-wins. `infer_species` returns one guess and it OVERRIDES the model,
    so a single bad match is final: "going down this rabbit hole" resolves to rabbit and strips every
    human-only option. Here the matches are evidence handed to the classifier, which can reject them.

    Longest-first ordering keeps `guinea pig` ahead of `pig`, which first-match-by-dict-order got
    backwards -- right family, wrong species, and the strain decides the assembly.
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
    """The hint block appended to the classifier prompt. Empty when nothing matched."""
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
    """The Ensembl production name of the organism the query names, or None.

    First the 356-species index (a non-trap, non-English-word hit; then any non-trap hit), then the
    16-word keyword scan. Used only to look up DATA availability once the factor value is already
    non-human -- it never decides the factor."""
    hits = species_candidates(user_query) or []
    for h in hits:
        if not h.get("trap") and not h.get("english_word"):
            return h["species"]
    for h in hits:
        if not h.get("trap"):
            return h["species"]
    return _WORD_TO_PRODUCTION.get(infer_species(user_query))


def resolve_model_organism(name):
    """The model's `organism` answer as an Ensembl production name, or None.

    Checked against the 356-species index (`species_index.json`) so the model cannot invent a species:
    an unrecognised answer is dropped and the caller falls back to the binary factor. Matching is on the
    index's own names, then on a production-name spelling ("Sus scrofa" -> sus_scrofa), then on the
    16-word keyword map for the common English names the index stores differently.
    """
    n = (name or "").strip().lower()
    if not n or n in ("unstated", "unknown", "none", "n/a"):
        return None
    idx = load_species_index() or {}
    by_production = {v["species"] for v in idx.values()}

    def canonical(prod):
        """`bos_taurus_wagyu` -> `bos_taurus` when Ensembl lists the plain species too. The strain
        decides the assembly, not the data lists, and the plain name is what a user recognises."""
        base = species_key(prod)
        return base if base != prod and base in by_production else prod

    if n in idx:
        return canonical(idx[n]["species"])
    flat = re.sub(r"[\s-]+", "_", n)
    if flat in by_production:
        return canonical(flat)
    if flat in _WORD_TO_PRODUCTION:
        return _WORD_TO_PRODUCTION[flat]
    # PARTIAL NAME (2026-09-20). People drop the qualifier Ensembl carries: "sharksucker" for `live
    # sharksucker`, "thornscrub tortoise" for `goodes thornscrub tortoise`. Accepted only when every
    # index name containing it belongs to ONE species, so "pig" (pig, guinea pig) stays ambiguous and
    # falls through to the binary factor rather than guessing.
    if len(n) >= 4:
        hits = {canonical(v["species"]) for k, v in idx.items() if n in k or k in n}
        if len(hits) == 1:
            return hits.pop()
    if n in ("human", "humans", "homo sapiens", "patient", "people"):
        return "homo_sapiens"
    return None


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


def _priority_rank(option_id: str, resolved) -> int:
    """Rank of an option under THIS scenario's factor resolution, for conflict tie-breaks.

    Replaced `_get_priority_rank` on 2026-09-13. That read the retired `priority_by_use_case` field
    against a use case guessed from the top retrieved example; `resolved` is the factor table's own
    answer for the tuple. An option the table does not price ranks 0, exactly as before, and with no
    resolution (legacy path) every option ranks 0 so the restrictiveness tie-break decides."""
    if not resolved:
        return 0
    _e, pri, _g = resolved.get(option_id, (False, None, None))
    return RANK.get(pri, 0) if pri else 0


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
                             assembly_override: str = None,
                             species_override: str = None,
                             resolved: dict = None) -> list[dict]:
    """Check enabled options for constraint violations and auto-correct them.

    Loads conflict rules, species restrictions and dependencies from
    vep_options.json. For conflicts, disables the option the FACTOR RESOLUTION prices lower
    (`_priority_rank(oid, resolved)`); on a tie the more restrictive option loses, then
    alphabetical order decides. For dependencies, auto-enables a required option, unless that
    option is itself a species violation, in which case the dependent option is disabled instead.

    NOT the use case. Until 2026-09-13 the ranking read the retired seven-use-case table; it now
    reads the resolved factor tuple. `_detect_use_case` is still called below and its result is
    still discarded -- see the note there.

    Returns a list of violation dicts with keys:
        type: 'conflict', 'species' or 'dependency'
        option_disabled / option_enabled: the option that was changed
        option_kept: (conflicts only) the option that was kept
        reason: human-readable explanation

    SIDE EFFECT: mutates the passed-in `enabled` / `disabled` sets in place (discard/add) — that IS how
    the corrected set reaches the caller, but it's an undocumented mutation a future caller might not expect.
    """
    violations = []
    # --- Scenario gates (the factor table's own not_applicable) ---
    # The resolver never ENABLES a gated option, but nothing stopped the MODEL proposing one, so the
    # same option in the same scenario was excluded when the table decided and shipped when the model
    # asked. In the stored eval logs the model overrode a gate 33 times, arguing its case in the
    # Reason line; 10 were `frequency` on a somatic query, the one hard rule whose violation deletes
    # findings rather than adding a column. Species and assembly were already enforced this way.
    # Scope is every gate the resolver sets — including region_focus removing the missense predictors
    # from a regulatory query, which the round-1 review asked to have back (open in STATUS.md). The
    # violation names the option so that decision stays visible. `verify_pipeline` asserts this never
    # touches the resolver's own configuration, so it can only fire on something the model added.
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

    # Order matters: species first (may remove options before they can conflict),
    # then conflicts, then dependencies (auto-enable may re-introduce options).
    # A stated species wins over the text, exactly as assembly does below. Without this, `--species
    # human` on a query whose text says mouse changed the RESOLVER's tuple while this gate went on
    # reading "mouse" out of the prose — human-only options the table recommends were then stripped
    # inside restore's re-check, whose violation list is discarded, so they vanished with no warning.
    species = species_override or infer_species(user_query)

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
        # ENSEMBL'S OWN PLUGIN LISTS WIN (2026-09-20). `species_restriction` is our catalogue text and
        # it disagrees with VEP_plugins release/116 on seven plugins: CADD is listed for pig, chicken
        # and turkey, IntAct for six non-human species, mutfunc for yeast, UTRAnnotator for everything,
        # while MaxEntScan, Paralogues and AncestralAllele are human only where we said otherwise.
        # A plugin with a list is judged by the list below (`species_data` violations), not here.
        _sdata = load_species_data() or {}
        plugin_lists = _sdata.get("plugin_species") or {}
        plugin_every = set(_sdata.get("plugin_species_all") or ())
        for oid in list(enabled):
            if oid in plugin_lists or oid in plugin_every:
                continue
            if _is_human_only(species_map.get(oid, "all species")):
                violations.append({
                    "type": "species",
                    "option_disabled": oid,
                    "reason": f"'{oid}' is restricted to {species_map[oid]} but this analysis is {species}",
                })
                enabled.discard(oid)
                disabled.add(oid)

    # --- Species DATA violations (2026-09-15) ---
    # "non-human" is one factor value, but Ensembl's data is not uniform across it: SIFT for eleven
    # non-human species, PolyPhen for none, CCDS for mouse, variant synonyms for pig, custom frequency
    # files for chicken/dog/goat/sheep (generation_config/species_data.json, from Ensembl's own pages
    # and form source). An option that needs such data is withheld for a species that lacks it, and
    # the reason names the species and the list. Same posture as assembly: a lookup beside the factor,
    # not a new factor value. Applies only to a POSITIVELY non-human query; the assume-human path is
    # untouched. An organism the index cannot resolve is treated as having no species-specific data.
    if species not in ("human", "unknown"):
        sdata = load_species_data()
        req_map = {o["id"]: o.get("requires_species_data") for o in vep_options if o.get("requires_species_data")}
        if sdata and req_map:
            sp_name = resolve_species_name(user_query)
            plugin_lists = sdata.get("plugin_species") or {}
            for oid in list(enabled):
                allowed = plugin_lists.get(oid)
                if allowed and species_key(sp_name or "") not in allowed:
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
                need = req_map.get(oid)
                if not need:
                    continue
                have = list(sdata.get("frequency_files", {})) if need == "frequency_files" else (sdata.get(need) or [])
                have_keys = {species_key(x) for x in have}
                if sp_name is None or species_key(sp_name) not in have_keys:
                    shown = ", ".join(sorted(have_keys)) if have_keys else "no species"
                    _nm = next((o.get("name", oid) for o in vep_options if o["id"] == oid), oid)
                    violations.append({
                        "type": "species_data",
                        "option_disabled": oid,
                        "reason": (f"{_nm} [{oid}] needs {need.replace('_', ' ')}, which Ensembl provides for "
                                   f"{len(have_keys)} species ({shown}); this analysis is "
                                   f"{species_key(sp_name) if sp_name else species}, which is not among them"),
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
                    "reason": (f"'{oid}' has data for {'/'.join(sorted(allowed))} only, but this "
                               f"analysis is on {assembly}"),
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
                rank_a = _priority_rank(oid_a, resolved)
                rank_b = _priority_rank(oid_b, resolved)

                # Tie-break ladder: (1) the FACTOR RESOLUTION's priority — the option this
                # scenario's tuple prices higher wins; (2) restrictiveness — drop the option
                # that suppresses more output (most_severe > pick > per_gene); (3)
                # alphabetical, purely so the result is deterministic.
                # The use case has played no part here since 2026-09-13.
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


def format_violation_warnings(violations: list[dict], reinstated=None) -> str:
    """Format constraint violations into a clearly readable warning block.

    `reinstated` is the option set as it stands AFTER every later repair. An option this block says
    was disabled can be switched back on by the restore pass a few lines further down, and printing
    the two reports in execution order showed "Disabled: hgvs" directly above "+ HGVS … switched
    on". Naming it here keeps the two blocks one account instead of two contradicting ones.

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
        back = (v.get("option_disabled") and reinstated is not None
                and v["option_disabled"] in reinstated)
        note = " (reinstated below — the option it conflicted with was itself removed)" if back else ""
        lines.append(f"  - {tag}: {v['reason']}{note}")
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


def resolve_for_query(factor_tuple, vep_options, trace=None):
    """`intent_priorities()` for a factor tuple, or None if the tuple or the config is unusable.

    One place for the try/except so the prompt builder and the output formatter can never disagree
    about what this scenario's priorities are."""
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


# Plain English for a factor value in a "because …" line. The ids are the contract everywhere else;
# this is the one place a user reads them.
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
    """One line of what ENSEMBL says the option does, or None.

    Sourced from the release-116 pages saved in `work/research/ensembl_docs_116/` (the options page
    for native flags, the plugins page for plugins) -- not from our catalogue's own prose, which we
    wrote. The output-field list is the page's own "Output fields" cell, so a user can see which
    columns the option adds before ticking it. Absent when `work/` is not beside the demo, or when the
    page has no record for the flag, in which case --explain simply omits the line."""
    global _ENSEMBL_PAGE
    if _ENSEMBL_PAGE is None:
        _ENSEMBL_PAGE = {}
        docs = BASE_DIR.parent / "work" / "research" / "ensembl_docs_116"
        # The two pages are parsed into different shapes: the options page gives {flag, description,
        # output_fields}, the plugins page {id, name, blurb}. Keying on only one of them silently left
        # every plugin without a record, and the caller then printed OUR catalogue prose under an
        # "Ensembl:" label -- the one thing the evidence rule forbids.
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
    # No page record: say whose words these are. Our catalogue prose is agent-written and must never
    # be shown as Ensembl's.
    ours = _first_sentence(opt.get("description") or "", 150)
    return f"our catalogue: {ours}" if ours else None


def why_recommended(oid, trace):
    """One plain sentence for why this option is in the configuration, from the resolver's own trace.

    `--explain` used to print the model's per-option prose, which the single-pass default does not
    produce, so every option came out bare. The derivation is what actually put the option there."""
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
    """Split the corrected option set by the priority the FACTOR table gives it for THIS scenario.

    TWO BUCKETS. `recommended` is the switched-on bucket, `optional` becomes ADD-ONS.

    The third tier is GONE, not hidden. It was merged into the display on 2026-08-07 and deleted from
    the scheme on 2026-08-19, because merging alone left an unvalidated boundary running three
    mechanisms underneath: `--minimal` filtered on `critical`, `restore_missing_recommended` restored
    it, and the must-have metric scored against it. Twelve of the reviewer's twenty edits moved
    options across that boundary and were never applied, precisely because they were invisible. So
    the three mechanisms were keyed on the one judgement she had rejected. Each is now defined on the
    RECOMMENDED bucket instead, and the must-have metric is withdrawn: with one enabled set there is
    one recall to report, which `enable-F1` already covers.

    Naming is Nakib's and the reason matters: "default" reads as *applies automatically*, which is
    wrong for a bucket the user still has to switch on. "Recommended" is the expert suggestion it
    actually is.

    This is a different axis from :func:`tier_options`, which splits on native-flag vs plugin (i.e.
    does it need downloaded data files) — an infrastructure question, not a clinical one. An option
    can be a plugin AND recommended (AlphaMissense), or native AND an add-on (`--uniprot`).

    Returns four lists:
      recommended     — ENABLED and rated `recommended` here.
      addons_on       — ENABLED and rated `optional`: add-ons this run switched on anyway.
      unpriced        — enabled, but the table prices them for no factor here (output/compute controls).
      addons_offered  — rated `optional` for this scenario and NOT enabled: the "offered, off by
                        default" set. Hard-gated options are never offered.

    DISPLAY ONLY: it regroups the corrected set, it never changes which options are enabled, so the
    checker and every scored metric are untouched."""
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
                       user_query, retrieval_mode="keyword", assembly_override=None,
                       species_override=None):
    """Narrow or widen the corrected set to the depth the user asked for. Mutates `enabled`.

      minimal  — drop the add-ons, keeping only the RECOMMENDED bucket. It used to mean "critical
                 only", a tier that no longer exists. The model's draft can switch an `optional`
                 option on and the standard level leaves it on, so this is a real narrowing.
      standard — leave it as recommended (the default).
      full     — additionally switch on every add-on the table rates `optional` and does not gate,
                 for someone who wants everything the scenario can justify.

    Re-running the checker afterwards is what makes either edit safe: narrowing can strip an option
    that a surviving one depends on (ClinVar needs check_existing), and the dependency pass puts it
    back; widening can introduce a conflict, and the conflict pass resolves it. So the result is a
    runnable configuration at every level, not just a filtered list.

    Returns the set of ids removed by narrowing (empty otherwise), for reporting."""
    if level == "minimal":
        # "no add-ons". It used to mean "critical only", a tier that no longer exists. The model's
        # draft can switch an `optional` option on, and the standard level leaves those on; minimal
        # strips them back to the RECOMMENDED bucket alone.
        keep = {oid for oid in enabled if resolved.get(oid, (False, None, False))[1] == "recommended"}
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
                       if priority in ("recommended", "optional") and not gated)
        # An add-on the re-check then REMOVES (a conflict it loses -- most_severe against the form's
        # own biotype) must be reported, or the level note says "every add-on included" while one is
        # silently missing. Seen 2026-09-14 on a basic coding query under --full.
        before = set(enabled)
    else:
        return set()
    check_and_fix_violations(enabled, disabled, vep_options, training_examples, user_query,
                             retrieval_mode=retrieval_mode, assembly_override=assembly_override,
                             species_override=species_override, resolved=resolved)
    if level == "full":
        return before - set(enabled)
    return removed - set(enabled)          # a dep the re-check restored was not really removed


def restore_missing_recommended(enabled, disabled, resolved, vep_options, training_examples,
                             user_query, retrieval_mode="keyword", assembly_override=None,
                             species_override=None, violations_out=None):
    # `resolved` is this function's own argument already, and it is what the re-check below gates on.
    """Switch on any option the factor table RECOMMENDS here that the draft left out.

    Keyed on the RECOMMENDED bucket since 2026-08-19. It used to key on the internal `critical` tier,
    which was the one part of the table an expert reviewed and rejected — see the RANK comment.

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

    `violations_out`: pass a list and the RE-CHECK's violations are appended to it. Under the single-pass
    default the first checker pass sees an EMPTY set, so every gate removal in a run happens inside this
    re-check -- and until 2026-09-15 its violation list was discarded, so a zebra finch lost SIFT to the
    species-data gate with no line saying so.
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
    # The re-check MUST see the same assembly the first pass did. Without it this function happily
    # restored an option the assembly gate had just removed — a GRCh37 run got MANE back, which is the
    # precise hazard the assembly field exists to prevent, reintroduced one step later.
    v2 = check_and_fix_violations(enabled, disabled, vep_options, training_examples, user_query,
                                  retrieval_mode=retrieval_mode, assembly_override=assembly_override,
                                  species_override=species_override, resolved=resolved)
    if violations_out is not None:
        violations_out.extend(v2)
    return [oid for oid in missing if oid in enabled]


def format_restored_recommended(restored, vep_options):
    """Report recommended options the draft omitted. Empty string when the draft was complete.

    Renamed from format_restored_critical on 2026-08-31. The mechanism it reports was moved onto the
    RECOMMENDED bucket when the `critical` tier was deleted, and a name saying otherwise is how the
    last set of stale readings survived a rename of the thing underneath them."""
    if not restored:
        return ""
    name_by_id = {o["id"]: o.get("name", o["id"]) for o in vep_options}
    lines = ["", f"RECOMMENDED OPTIONS, FROM THE PRIORITY TABLE ({len(restored)}):",
             "   The factor table recommends these for this scenario, so they were added back:"]
    lines += [f"     + {name_by_id.get(oid, oid)} [{oid}]" for oid in restored]
    lines.append("")
    return "\n".join(lines)


# Canonical CONFIG_SECTIONS ids -> the label on the COLLAPSIBLE TOGGLE the user clicks to open that
# part of the form. Checked against the live form 2026-09-08: the six toggles are exactly these. The
# form also carries h2 sub-headings inside each one (Transcript annotation, Pathogenicity
# predictions, Splicing predictions, Conservation...), which is a level down and not what we name.
# `filters` was "Filters" here, which is the h2 inside it; the toggle says "Filtering options".
_WEB_SECTION_LABELS = {
    "identifiers": "Identifiers", "variants_frequency_data": "Variants and frequency data",
    "additional_annotations": "Additional annotations", "predictions": "Predictions",
    "filters": "Filtering options", "advanced": "Advanced options"}

# The two sections the form SPLITS into boxes. "Additional annotations" is seven boxes and
# "Predictions" three, so naming only the section leaves the user opening every box to find one
# checkbox. For these two the label also names the box, in the form's own words. The other four
# sections have no boxes, so a second name would only repeat the first.
_SPLIT_SECTIONS = frozenset({"additional_annotations", "predictions"})


def form_location(opt):
    """Where an option sits on the web form, as the user will see it. Read off the live release-116
    page on 2026-09-15 -- research/ensembl_docs_116/form_layout_live.json records how each was read.

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


# TYPES, NOT TOOLS, where several tools answer the same question (round-2 item 11, Likhitha,
# 2026-09-08): "we should recommend the suite/type of tool by category. (We particularly don't want
# to endorse a commercial tool like Mastermind)." Options in these categories render as ONE line
# naming the type and listing every member the species/assembly gates left standing — her template —
# instead of a per-tool line each carrying its own reason. DISPLAY ONLY: the enabled set, the
# generated command and every scored metric are untouched, because the other half of her item-11
# question ("what should the accuracy figure become?") is still unanswered, so the tiers underneath
# must not move yet.
#
# THE FORM'S BOXES, NOT OUR CATEGORIES (David, 2026-09-15). The lines used to carry labels we wrote --
# "Pathogenicity predictors", "Splice-effect predictors", "Literature/citation evidence" -- beside the
# form's own box name in brackets, so the user saw two names for one thing and only one of them was on
# their screen. Grouping now keys on `web_form_subsection` and the line is labelled with that box.
#
# Only the two boxes that are a family of interchangeable tools group. "Literature/citation evidence"
# is gone: its only member, Mastermind, sits in the form box "Phenotype data and citations" beside
# Phenotypes, GO and Geno2MP, so labelling it with its box would print that box twice. It now prints as
# an ordinary line. That changes nothing for item 11 -- a group of one already named the commercial
# tool -- and whether Mastermind should be recommended at all is a pricing question, not a label.
TYPE_GROUPED_BOXES = ("Pathogenicity predictions", "Splicing predictions")


def format_corrected_config(enabled, disabled, vep_options, violations, resolved=None,
                            reason_by_id=None, restored=(), size_value=None, assembly=None,
                            meta_notes=False, show_cli=True, species=None, show_optional=True):
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
             "  YOUR VEP CONFIGURATION"]
    # Count EVERY repair. This used to report len(violations) alone, so a run that resolved three
    # conflicts and switched two omitted options back on announced "corrected 3 things" above a
    # block listing five changes.
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
        # Essential-vs-optional view: group the SAME corrected set by this scenario's priorities.
        tiers = tier_by_importance(enabled, resolved)
        # TWO buckets, matching the two tiers (2026-08-19). There used to be four: RECOMMENDED,
        # "ADD-ONS (enabled)", "OTHER (enabled)" and "AVAILABLE ADD-ONS". The middle two were
        # artefacts of the draft — options the MODEL switched on that the table rates `optional`, or
        # prices for no factor here. An add-on the model happened to enable is still an add-on, and
        # --minimal already strips exactly those, so the split contradicted the config levels.
        # TWO sections, and the first one IS the command. There used to be four buckets:
        # RECOMMENDED, "ADD-ONS (enabled)", "OTHER (enabled)" and "AVAILABLE ADD-ONS". The middle two
        # were both switched ON, so the user read three lists to learn what to tick and the generated
        # command silently spanned all three. Now everything the run switches on is one list,
        # annotated with why it is there, and everything else applicable is the second.
        core = set(tiers["recommended"]) | set(tiers["unpriced"])
        extra = set(tiers["addons_on"])
        switch_on = sorted(core | extra)
        # ALREADY ON WHEN THE FORM LOADS (mentor instruction, 2026-09-13). An option the form ships
        # ticked is a confirmation, not a recommendation: it leaves the switch-on list and is named
        # once at the end. `enabled` is untouched, so dependencies, the checker and the CLI command
        # (which has no defaults) still carry it. Species-aware -- see _HUMAN_ONLY_FORM_DEFAULTS.
        already_on = {oid for oid in switch_on if _form_default_on(oid, vep_options, species)}
        switch_on = [oid for oid in switch_on if oid not in already_on]
        # WEB FORM FIRST, CLI SECOND (mentor feedback, 2026-09-07, public-repo test). The old lines
        # mixed the two surfaces -- "Transcript database to use [core_type] --refseq | --merged | ..."
        # read as internal labels plus flags a web user cannot type anywhere. Web users get the
        # form's own control names and section headings here; every flag now lives only in the CLI
        # block below. `sect_by_id` is the InputForm.pm section, so "where on the form" is answered.
        sect_by_id = {o["id"]: form_location(o) for o in vep_options}
        defval_by_id = {o["id"]: o.get("web_default_value") for o in vep_options}
        box_by_id = {o["id"]: o.get("web_form_subsection") for o in vep_options}
        sec_label_by_id = {o["id"]: (f"{_WEB_SECTION_LABELS[o['web_form_section']]} section"
                                     if o.get("web_form_section") in _WEB_SECTION_LABELS else "")
                           for o in vep_options}
        dep_by_id = {o["id"]: o.get("deprecated") for o in vep_options}
        unpriced = set(tiers["unpriced"])
        # A grouped member the table prices NOTHING for stays individual: its "model-suggested"
        # warning below matters more than the tidier line, and folding it in would launder a
        # model-only pick into the type's listing.
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
                # An option only the MODEL wants -- the table prices nothing for it here -- must not
                # render identically to the table's own picks. The mentor-reported case was `pick`
                # on a rare-disease query, shown as confidently as ClinVar.
                tag = ("   (add-on)" if oid in extra else
                       "   (model-suggested)"
                       if oid in unpriced else "")
                where = f"   ({sect_by_id[oid]})" if sect_by_id.get(oid) else ""
                dep = (f"   (deprecated — {dep_by_id[oid].split(';')[0]})"
                       if dep_by_id.get(oid) else "")
                lines.append(f"  {name_by_id.get(oid, oid)}{where}{tag}{dep}")
                # A radiolist recommended AT ITS OWN DEFAULT is an instruction to leave it alone,
                # and the output should say so instead of making the user hunt for what to change.
                if oid == "core_type" and (defval_by_id.get(oid) or "core") == "core":
                    lines.append("      keep the form's default: Ensembl/GENCODE transcripts")
                if oid in ("pick", "pick_allele", "per_gene", "most_severe", "summary"):
                    lines.append(f"      set the 'Restrict results' drop-down to: {oid}")
                # The model's per-option prose is its own commentary, of uneven quality, and it
                # triples the length of the list a user is trying to work through on the form.
                # --explain keeps it for whoever is auditing the draft.
                if meta_notes and (reason_by_id or {}).get(oid):
                    lines.append(f"      {reason_by_id[oid]}")   # guarded above
                # A form control whose VALUE depends on the variant size. Naming the file is the whole
                # point of splitting the passes: "switch CADD on" is not actionable when the drop-down
                # offers four files and only one of them scores what this pass is about.
                _choice, _ = size_dependent_choice(oid, size_value, vep_options, assembly)
                if _choice:
                    lines.append(f"      drop-down: {_choice}")
            # One line per TYPE, after the singles. Members switched on are starred; the rest of
            # the type rides on the same line as available, so no member reads as our pick.
            for box in TYPE_GROUPED_BOXES:
                label = box                                    # the form's own words
                on_members = [oid for oid in switch_on if oid in grouped_on
                              and box_by_id.get(oid) == box]
                if not on_members:
                    continue
                off_members = [oid for oid in sorted(tiers["addons_offered"])
                               if box_by_id.get(oid) == box]
                # The line is already named after the box, so the bracket gives only the section.
                sect = next((sec_label_by_id.get(oid) for oid in on_members
                             if sec_label_by_id.get(oid)), "")
                for_clause = (f" for {species}" if species and species != "unknown" else "")
                if assembly:
                    for_clause += f" ({assembly})"
                picked = ", ".join(name_by_id.get(o, o) for o in on_members)
                lines.append(f"  {label}: {picked}" + (f"   ({sect})" if sect else ""))
                # The rest of the family, and the "any subset works" caveat, are --explain material:
                # true, and not what someone filling in the form needs on the screen.
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
            # Provenance for --explain readers. Out of the default output on mentor feedback
            # (2026-09-07): it describes OUR decision-making, not the user's next action.
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
        # WEB-FORM-ONLY BY DEFAULT (mentor feedback, 2026-09-07): the target of record is the web
        # form, and a web user cannot type a flag anywhere. --cli appends the command for the users
        # who do run VEP locally; the JSON output's generated_command is unaffected either way.
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


# --- Structured-output assembler (deterministic ✓/✗ → schema-valid JSON) ---------------------
# Exp 8 showed the local model cannot reliably emit JSON, but it reliably emits the
# `✓/✗ [source: id]` format. So OUR code assembles the schema-valid JSON from the parsed records +
# the checker's corrected set + KB factual fields — valid by construction, the LLM never emits JSON.
# Target contract: work/output_schema/vep_recommendation.schema.json (+ SCHEMA_DESIGN.md mapping table).

# The 'Restrict results' dropdown: these catalogue ids are mutually-exclusive VALUES of one control
# whose HTML name is `summary` (InputForm.pm). web_form_field='summary', value=<the id>.

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


def _first_sentence(text: str, limit: int = 240) -> str:
    """First sentence (or a bounded prefix) of a description — a non-empty reason fallback."""
    text = (text or "").strip()
    if not text:
        return ""
    head = text.split(". ")[0].strip()
    return (head if head.endswith(".") else head + ".")[:limit]


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
        violations = check_and_fix_violations(enabled, disabled, vep_options, training_examples,
                                              query, retrieval_mode=retrieval_mode, assembly_override=assembly,
                                              resolved=resolved_override)
        if resolved_override:
            restored = restore_missing_recommended(enabled, disabled, resolved_override, vep_options,
                                                   training_examples, query, retrieval_mode=retrieval_mode,
                                                   assembly_override=assembly, violations_out=violations)

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


def build_explain_result_prompt(consequences):
    """Build system prompt for the VEP output explainer mode."""
    consequence_text = []
    for term, info in consequences.items():
        if term.startswith("_"):      # `_source` and friends are metadata, not consequence terms
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


# ---------------------------------------------------------------------------
# Decision trace (Layer 1 + 2: retrieval transparency + provenance)
# ---------------------------------------------------------------------------

def print_decision_trace(user_query, vep_options, training_examples,
                         retrieval_mode="keyword", factor_tuple=None, two_pass=False):
    """Print the retrieval and reasoning trace for --explain mode.

    `factor_tuple` is what Layer 2 explains. It is optional so the function still runs before the
    classifier has spoken, but Layer 2 has nothing to say without it."""
    print("=" * 60)
    print(f"  DECISION TRACE (--explain mode, retrieval={retrieval_mode})")
    print("=" * 60)

    # Layer 1 describes the corpus put into the DRAFT prompt. The single-pass default builds no
    # such prompt, so the whole layer is --two-pass only (it used to announce "All 23 worked
    # examples are sent" on a run that sent none).
    print(f"Query: \"{user_query}\"")
    if two_pass:
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

    # Layer 2: WHY each option came out the way it did, for THIS query's factor tuple.
    #
    # REWRITTEN 2026-08-19. The previous version priced every option against `priority_by_use_case`,
    # the legacy seven-use-case table, picking the use case from the top-scoring retrieved EXAMPLE
    # rather than from the query. On "mouse tumour, coding variants" it reported
    # `rare_disease_germline`, then printed three tiers that no longer exist. It described neither the
    # query nor the scheme the engine resolves with.
    #
    # This prints the derivation instead: which rule raised each option, what else voted, and which
    # gate removed it. All of it was already computed inside intent_priorities and discarded at the
    # `strongest(labels)` max; the `trace` parameter added alongside this keeps it.
    print("--- Layer 2: Why each option is where it is ---")
    if factor_tuple is None:
        print("  (needs the query's factor tuple; run without --explain-only, or pass one in)\n")
        print("=" * 60)
        return
    # `_`-prefixed keys are metadata (e.g. _request_type), not factors — same convention active_values uses.
    _shown = ", ".join(f"{k}={v}" for k, v in sorted(factor_tuple.items())
                       if v and not k.startswith("_"))
    print(f"Factors read from the query: {_shown}\n")

    tr = {}
    intent_priorities(factor_tuple, vep_options, load_priority_by_factor(vep_options),
                      load_factors(), trace=tr)
    prov = {o["id"]: (o.get("provenance") or "") for o in vep_options}

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
            print(f"    {'':20s} in our catalogue: {prov[oid].split(';')[0][:88]}")

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
                # THE DRAFT IS NOT PRINTED (2026-08-19) — see the note in stream_response. This is the
                # path the deployed model actually takes: `think` defaults to False on gemma4:26b, so
                # `think is not None` sends every real run through here rather than the compat path.
                if sys.stdout.isatty():
                    print(f"\r  drafting… {len(answer) // 4} tokens", end="", flush=True)
    if sys.stdout.isatty():
        print("\r" + " " * 40 + "\r", end="", flush=True)
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
        extra_body={"keep_alive": KEEP_ALIVE},
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
            response_text += delta.content
            # THE DRAFT IS NO LONGER PRINTED (2026-08-19). It is pre-checker, pre-gate and
            # pre-restore, so it is wrong by construction — which is why the corrected block below it
            # had to say "use THIS, not the draft above". Showing a configuration and then telling the
            # user to ignore it is worse than not showing it. What the draft is still FOR is its
            # per-option Reason: prose, which is carried across onto the corrected set.
            # Streaming still drives a live counter, because the generate phase is ~40 s and silence
            # that long reads as a hang — the same reason the thinking counter exists above.
            if _tty:
                print(f"\r  drafting… {len(response_text) // 4} tokens", end="", flush=True)
    if _tty and answering:
        print("\r" + " " * 40 + "\r", end="", flush=True)
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
        if key == "assembly":
            # The prose reader accepts hg19/hg38 and any casing (_ASSEMBLY_ALIASES); the flag must
            # not reject the same tokens it would have read out of the query text.
            val = _ASSEMBLY_ALIASES.get(re.sub(r"[\s_-]", "", val.lower()), val)
        elif key in MULTI_FACTORS:
            # A multi-select factor must be STATEABLE at its honest value. `variant_size_class` is
            # multi precisely because a WGS callset holds both classes — so the flag accepts `both`,
            # and `small+structural-CNV` (or comma) for the general case. Rejecting the value the
            # assume-policy itself guesses would force a user back through the classifier to say
            # something the scheme already believes.
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
                   explain=False, skip_check=False, retrieval_mode="keyword", level="standard",
                   think=False, factor_think=False, clarify="ask", context=None, show_cli=False,
                   single_pass=True):
    """Run the recommendation mode (default).

    Args:
        skip_check: If True, skip the post-hoc constraint checker.
        retrieval_mode: "keyword" or "semantic".
        level: "minimal" (smallest runnable set), "standard" (default), or "full" (add every add-on).
    """
    # NOTE the trace is printed AFTER classification, further down. Layer 2 explains the derivation
    # for this query's factor tuple, which does not exist yet at this point in the function.

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

    # SCOPE, decided on the call that always runs.
    #
    # `is_out_of_scope_response` reads the DRAFT, and under --single-pass the draft is empty, so it
    # returns False and the pipeline resolved a full two-pass configuration out of the assume-defaults
    # for the query "hi" -- 21 options across two VEP runs, no model involved after this line. The
    # tuple alone cannot tell scope: "hi" and "annotate my VCF" state no factors either way. So the
    # judgement the draft prompt's `## Scope` section already asks for now rides on the classifier,
    # and the stop happens before anything is assumed rather than after the user has been interrogated.
    #
    # Both paths gate here. The draft's own OUT OF SCOPE marker stays as the second line of defence
    # for a query that names a scenario and still cannot be served.
    request_type = (factor_tuple or {}).get("_request_type", "configure")
    if request_type != "configure":
        print()
        print(OUT_OF_SCOPE_NOTE if request_type == "not-vep" else VEP_SUPPORT_NOTE)
        print()
        return

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

    # AFTER resolve_underspecified, deliberately. The classifier returns only what the query stated,
    # so at the earlier point analysis_goal is often absent and Layer 2 would explain a tuple the run
    # never used — it listed symbol, core_type and biotype as "no rule prices these" while the final
    # configuration switched all three on, because the analysis_goal floor had not been applied yet.
    if explain:
        print_decision_trace(user_query, vep_options, training_examples,
                             retrieval_mode=retrieval_mode, factor_tuple=factor_tuple)

    # SINGLE PASS -- THE DEFAULT since 2026-09-13; --two-pass restores the draft call.
    # The second model call is skipped and the draft is left empty.
    #
    # Not a degraded mode. `restore_missing_recommended` reconstructs the RECOMMENDED set from the
    # factor tuple whatever the draft said -- verified 2026-09-09 on the 31-row set: an empty draft,
    # a one-option draft, and a draft explicitly DISABLING sift/clinvar/mane all yield the same 20
    # options. The draft has no authority in either direction, so the only thing the model decides
    # that reaches the user is the factor tuple pass 1 already returned.
    #
    # Given up: the model's per-option prose (already --explain only), and the options it proposes
    # that the priority table prices for nothing -- the `pick` class the output has to tag and cap.
    #
    # Conflict ranking is UNAFFECTED. `_detect_use_case` retrieves over the examples using the query
    # and its `enabled` parameter is dead, so it never read the draft.
    if single_pass:
        response_text, reasoning_text, t_recommend = "", "", 0.0
    else:
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
    if explain:
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
    if skip_check:
        # THE CHECKER IS THE BUILDER on the single-pass default, so skipping it used to print no
        # configuration at all -- the flag silently produced an empty run. It now shows what the
        # priority table alone says, with the gates and repairs plainly not applied.
        for size_value, pass_label, pass_tuple in size_passes(factor_tuple):
            resolved = resolve_for_query(pass_tuple, vep_options)
            if not resolved:
                print("\n  --no-check: the scenario's factors could not be resolved, so there is "
                      "nothing to show.")
                break
            raw = {oid for oid, (en, _p, _g) in resolved.items() if en}
            print(f"\n  --no-check: UNCHECKED configuration for {pass_label}. Species restrictions, "
                  f"assembly gates, conflicts and dependencies were NOT applied.")
            print(format_corrected_config(raw, set(), vep_options, [], resolved=resolved,
                                          size_value=size_value, assembly=assembly,
                                          show_cli=show_cli, meta_notes=explain,
                                          species=(factor_tuple or {}).get("species")))
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
            # PRINT IT. The draft stopped being streamed on 2026-08-19, and this branch returns
            # before anything else prints, so a declined query showed "Analysing your scenario..."
            # and then a file path — indistinguishable from a crash. The refusal is the only answer
            # the run produced, so it is the one thing that has to reach the screen.
            print(response_text.strip())
            print()
            save_result(user_query, response_text, mode="recommend", warnings="",
                        reasoning=reasoning_text)
            return

        # DIAGNOSTICS ARE BUFFERED, NOT PRINTED HERE. They explain how the configuration was
        # repaired, so they belong after it: a user who wanted the answer had to scroll past two
        # warning blocks to reach it. Order among themselves is unchanged.
        diagnostics = []
        audit_report = format_citation_audit(audit, len(vep_options))
        if audit_report:
            diagnostics.append(audit_report)
        # ONE parse of the draft, reused for the sets, the per-option prose and the override
        # report, so the three cannot disagree about what the model actually said.
        _recs = extract_recommendations_detailed(response_text, option_aliases)
        enabled = {r["option_id"] for r in _recs if r["action"] == "enable"}
        disabled = {r["option_id"] for r in _recs if r["action"] == "disable"}
        override_report = format_marker_overrides(_recs, vep_options)
        if override_report:
            diagnostics.append(override_report)
        # `assembly_override=assembly` is NOT optional. Without it the checker falls back to
        # infer_assembly(user_query), which reads a build out of the PROSE only — so `--assembly
        # GRCh37` was acknowledged on screen, used to suppress the assembly question, and then
        # dropped before the gate that acts on it. A GRCh37 run shipped MANE, EVE and MaveDB, all
        # GRCh38-only, with no warning: strictly worse than saying nothing, which at least prints
        # "Left open". test_user_context.py passed throughout because it calls these helpers with
        # the override directly; it tests the functions, not this wiring.
        species_stated = (context or {}).get("species") or None
        # The checker's own species reading is the 16-word keyword scan, which does not know a zebra
        # finch from a human; the TUPLE does (the classifier, or the species hint). Hand it down through
        # the override channel so the human-only pass and the species-DATA gate see what the resolver
        # saw. --species still wins when given. (2026-09-15)
        # The TUPLE's species, human included (2026-09-16). Passing None for a human tuple let the checker
        # fall back to infer_species(), so "not a mouse study, the samples are human" was read as mouse
        # there and human-only options were stripped from a human run.
        _tuple_species = (factor_tuple or {}).get("species")
        species_for_checker = species_stated or (_tuple_species if _tuple_species in ("human", "non-human") else None)
        # For the ALREADY-ON list (human-only form defaults) and the species-data lookup, the production
        # name is the useful thing -- but only once the tuple says non-human. The name lookup still reads
        # the text (the factor is binary and cannot say WHICH organism); it never decides human vs not.
        if species_for_checker == "human":
            species_for_display = "human"
        else:
            # WHICH organism, for the data lookups. The classifier's own `organism` answer comes first
            # (2026-09-20): it is read from the sentence, where `resolve_species_name` is a name scan that
            # takes the first index hit -- "not a mouse study ... pig herd" resolves to mouse there.
            # Used ONLY once the binary factor says non-human: on a human run the name is irrelevant, and
            # a stray organism in the prose ("our lab mascot is a zebra finch, but these are human exomes")
            # must not decide the data lists.
            species_for_display = (species_stated
                                   or (factor_tuple or {}).get("_organism")
                                   or resolve_species_name(user_query)
                                   or species_for_checker or "human")
        # ONE VEP RUN PER VARIANT SIZE. The form cannot express both sizes at once (see size_passes),
        # so a scenario carrying both prints two configurations rather than one union of them. Each pass
        # starts from the SAME parsed draft and its OWN copies of the sets, because the checker repairs
        # in place: sharing them would let pass 1's repairs decide where pass 2 starts.
        passes = size_passes(factor_tuple)
        if len(passes) > 1:
            how = ("both variant sizes assumed"
                   if "variant_size_class" in (factor_tuple or {}).get("_assumed", [])
                   else "this callset has both variant sizes")
            print(f"\nTWO VEP RUNS — {how}. Run VEP once per size, with the settings below.")
        reports = []
        for _i, (size_value, pass_label, pass_tuple) in enumerate(passes, 1):
            # Copies per pass, for the reason above.
            p_enabled, p_disabled = set(enabled), set(disabled)
            if len(passes) > 1:
                header = f"\n{'─' * 60}\nPASS {_i} of {len(passes)} — {pass_label}\n{'─' * 60}"
                print(header)
                reports.append(header)
            # Resolved FIRST (it was computed after this call): the checker needs the scenario's gates to
            # enforce them on the model's draft, and resolve_for_query is pure, so moving it up is free.
            why_trace = {} if explain else None
            resolved = resolve_for_query(pass_tuple, vep_options, trace=why_trace)
            violations = check_and_fix_violations(
                p_enabled, p_disabled, vep_options, training_examples, user_query,
                retrieval_mode=retrieval_mode, assembly_override=assembly,
                species_override=species_for_checker, resolved=resolved,
            )
            # Restore must-haves BEFORE the depth flags run, so --minimal narrows a complete core rather
            # than a partial one, and --full widens from the same base.
            restored = restore_missing_recommended(p_enabled, p_disabled, resolved, vep_options,
                                                training_examples, user_query,
                                                retrieval_mode=retrieval_mode,
                                                assembly_override=assembly,
                                                species_override=species_for_checker,
                                                violations_out=violations)
            # An option whose data file this pass cannot use is dropped here, AFTER the restore, so the
            # restore cannot put it back. Reported rather than removed silently.
            for oid, why in drop_unavailable_size_values(p_enabled, vep_options, size_value, assembly):
                line = f"  Dropped {oid} on this pass: {why}."
                print(line)
                reports.append(line)
            # PRINTED AFTER THE RESTORE, though the repair happened before it. In execution order the
            # two blocks contradicted each other six lines apart; in this order the violation report can
            # name the options that came back.
            pass_warnings = format_violation_warnings(violations, reinstated=set(p_enabled))
            if pass_warnings:
                diagnostics.append(pass_warnings)
            # Species-DATA removals are said BY DEFAULT, not only under --explain. STATUS.md's open
            # question "should the assistant say what it cannot do?" -- a mouse frequency query used to
            # return a configuration with no frequency data and no explanation. Now a cattle user asking
            # for frequencies is told there is no file for cattle, and for which species there is one.
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
                                             training_examples, user_query,
                                             retrieval_mode=retrieval_mode,
                                             assembly_override=assembly,
                                             species_override=species_for_checker)
                if level == "minimal":
                    # Nothing is dropped from RECOMMENDED on the single-pass default: the table is what
                    # put those options there, so there is no looser set to trim. What --minimal does
                    # now is hide the add-ons, which is the smallest set that still runs.
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
            # Carry the model's per-option prose across from the draft, which is no longer printed.
            # WHY EACH OPTION IS THERE (2026-09-20). Under --explain every recommended option carries
            # the rule that placed it, derived by the resolver. The draft's prose is still preferred
            # when --two-pass produced any, so nothing is lost on that path.
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
            corrected = format_corrected_config(p_enabled, p_disabled, vep_options, violations,
                                                resolved=resolved, reason_by_id=_reasons,
                                                restored=restored,
                                                size_value=size_value, assembly=assembly,
                                                show_cli=show_cli, meta_notes=explain,
                                                species=species_for_display,
                                                show_optional=(level != "minimal"))
            print(corrected)
            # DIAGNOSTICS ARE --explain ONLY. A corrected configuration is just a configuration; the
            # repair log is for whoever audits the decision, not for someone who wants the answer.
            # The header line already says how many things were corrected, and the saved .md keeps
            # the full log either way, so nothing is lost by leaving it off the screen.
            if diagnostics and explain:
                print("\nHOW THIS WAS CORRECTED\n" + "-" * 60)
                for d in diagnostics:
                    print(d)
            diagnostics.clear()
            # Same order as the screen: the configuration, then how it was repaired. The saved file
            # and the terminal must not disagree about which came first.
            reports.extend(x for x in (corrected, pass_warnings, restored_report) if x)
        # Safety net: the flush above lives inside the per-pass loop, so anything left here means the
        # loop never ran. A buffered warning that never prints is worse than one printed too early.
        if diagnostics and explain:
            print("\nHOW THIS WAS CORRECTED\n" + "-" * 60)
            for d in diagnostics:
                print(d)
        warnings = "\n".join(x for x in (reports + [audit_report, override_report]) if x)
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

    # The draft stopped being streamed on 2026-08-19; the recommend mode replaced it with the
    # corrected-config block, but this mode has no equivalent, so it printed a token count and a
    # file path with the entire answer only in the file.
    if response_text.strip():
        print(response_text.strip())
        print()
    save_result(user_query, response_text, mode="explain", reasoning=reasoning_text)


def main():
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # gemma4:26b — the model this system is built and benchmarked on (Exp 10: 84% enable-F1).
    #
    # The default matters more than it looks. A 3B-class model cannot hold the `✓/✗ ... [source: id]`
    # output contract the whole pipeline depends on: it frequently emits no [source:] tags at all, which
    # drops the parser into its prose fallback (built for the no-KB experimental condition), and that
    # fallback INVERTS the meaning — "✗ polyphen: ON" parses as ENABLE. Exp 1/10 measure 3B-class models
    # at 31-39% enable-F1, the worst of everything tested. A small default would make a first impression
    # out of the system's worst configuration.
    model = os.environ.get("VEP_MODEL", "gemma4:26b")

    args = sys.argv[1:]

    # Imported here, not at the top of main: --help must work on a machine that has cloned the repo
    # and installed nothing, and it used to die on this import before the help handling was reached.
    def make_client(required=True):
        try:
            from openai import OpenAI
        except ImportError:
            if required:
                print("Error: openai SDK not installed. Run: pip install openai")
                sys.exit(1)
            # The recommend path never touches the client: the CLI always passes think=True/False,
            # and both route stream_response through the native endpoint. Only explain-result (which
            # calls stream_response with think=None) still needs the SDK.
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

    # --- Mode: recommend (with optional --explain, --no-check) ---
    known_flags = ("--explain", "--minimal", "--full",
                   "--factor-think", "--no-factor-think", "--quiet", "--assume", "--ask", "--no-ask", "--cli",
                   "--single-pass", "--two-pass") + tuple(_CONTEXT_FLAGS)
    # REMOVED 2026-09-16. Both only ever acted on the draft call, which single-pass (the default since
    # 2026-09-13) does not make: --think set reasoning on the recommender stream, --semantic chose which
    # examples went into the draft prompt. On the default path neither changed a recommendation. Named
    # here so an old command line gets a reason instead of "Unknown option".
    removed_flags = {
        "--think": "removed: it only set reasoning on the draft call, which the default single-pass "
                   "run does not make (Exp 14 measured no gain from it)",
        "--semantic": "removed: it only chose which examples went into the draft prompt, which the "
                      "default single-pass run does not build",
        "--no-check": "removed: it existed to show the model's raw draft before the checker repaired "
                      "it, and the default single-pass run has no draft -- the checker IS what builds "
                      "the configuration, so there is nothing to skip",
    }
    _gone = [a for a in args if a in removed_flags]
    if _gone:
        for a in _gone:
            print(f"{a} {removed_flags[a]}.")
        sys.exit(2)

    # --help is the first thing anyone types, and rejecting it with "Unknown option(s): --help" (exit 2)
    # is a poor greeting for someone who just cloned the repo. Handled before the unknown-flag check.
    if any(a in ("--help", "-h", "help") for a in args):
        print('Usage: python3 vep_assistant.py [flags] "your analysis scenario"')
        print("\nModes:")
        print("  <scenario>                    recommend a VEP web-form configuration")
        print('  explain-result "<question>"   explain a VEP output annotation')
        print("\nFlags:")
        for f, h in (("--explain", "say why each option is recommended, and how the checker resolved it"),
                     ("--minimal", "only the options you must tick; hides the optional add-ons"),
                     ("--full", "add every add-on"),
                     ("--cli", "append the equivalent VEP command line (web-form output is the default)"),
                     ("--two-pass", "also run the legacy draft call (slower; the checker rebuilds the same set, 31/31 measured)"),
                     ("--single-pass", "the default since 2026-09-13; accepted for compatibility"),
                     ("--factor-think", "the default since 2026-09-20: the classifier reasons first "
                                        "(~4 s a query; 148/150 on the trap grid against 138/150 without)"),
                     ("--no-factor-think", "skip the reasoning (~0.9 s a query, weaker on misleading wording)"),
                     ("--ask", "the default since 2026-09-14: prompt when a gap changes something in RECOMMENDED (needs a terminal)"),
                     ("--no-ask", "never prompt; state the assumed values instead"),
                     ("--quiet", "apply the safe defaults without the disclosure lines"),
                     ("--species / --origin / --size / --assembly", "state a fact instead of inferring it")):
            print(f"  {f:<44} {h}")
        print("\nEnvironment: VEP_MODEL (default gemma4:26b), VEP_FACTOR_MODEL, VEP_OPTIONS_FILE,")
        print("             VEP_FACTORS_FILE, VEP_PRIORITY_FACTOR_FILE, VEP_CLASSIFIER_PROMPT (v1 restores")
        print("             the pre-2026-09-16 prompt), VEP_FACTOR_THINK=0 (reasoning off),")
        print("             VEP_KEEP_ALIVE, VEP_RESULTS_DIR, NO_PROXY=localhost,127.0.0.1 behind a proxy.")
        sys.exit(0)

    # A mistyped flag used to fall through into the query text: `--minmal "mouse variants"` asked the
    # model about "--minmal mouse variants" and quietly ran at the default level. Reject anything
    # unrecognised that looks like a flag instead, and list what is available.
    unknown = [a for a in args
               if a.startswith("--") and a.split("=", 1)[0] not in known_flags]
    if unknown:
        print(f"Unknown option(s): {' '.join(unknown)}")
        print(f"Available: {' '.join(known_flags)}")
        print('Usage: python3 vep_assistant.py [flags] "your analysis scenario"')
        sys.exit(2)

    # The classifier reasons by default (2026-09-20); the draft call under --two-pass does not, and each has its own switch because they are separate
    # calls with separate costs. --think: recommender, 1.93x faster off with equal enable-F1 and better
    # critical-recall (Exp 14). --factor-think: classifier, 5.8x faster off with the same factor tuple on
    # 29/31 rows and no end-to-end change (89.5% vs 89.3% enable-F1, Exp 15). The flag beats the
    # VEP_FACTOR_THINK env var, which exists for the harness and the web app.
    think = False
    # False here means "unset", which `infer_factors` resolves through _factor_think_setting(); the
    # flags pin it either way.
    factor_think = True if "--factor-think" in args else (None if "--no-factor-think" in args else False)
    if factor_think is None:
        os.environ["VEP_FACTOR_THINK"] = "0"
        factor_think = False
    # What to do about anything the question did not say. Default states its assumptions;
    # RENAMED --assume -> --quiet (2026-08-31). Assuming was never what the flag switched on — the
    # defaults are applied on every run without --ask, so its only effect was suppressing the
    # disclosure lines. A flag named for a behaviour that happens anyway teaches the wrong model of
    # the tool, which is what Likhitha's second question about the proposal exposed. --assume still
    # works so nothing breaks, but says what it actually did.
    if "--assume" in args:
        print("note: --assume is now --quiet — assuming happens by default; this flag only silences "
              "the disclosure lines.")
    quiet = "--quiet" in args or "--assume" in args
    if quiet and "--ask" in args:
        print("--quiet and --ask ask for opposite things; pick one.")
        sys.exit(2)
    # ASK IS THE DEFAULT since 2026-09-14. `_ask_factor` returns None off a tty, so a piped run
    # falls through to the assumed value with its disclosure line -- nothing hangs, nothing is silent.
    clarify = "assume" if quiet else ("state" if "--no-ask" in args else "ask")
    # What the user states outright about their data. These are facts they know; asking a model to infer
    # them from prose is where every measured classification failure came from.
    context, _ctx_err = _parse_context_flags(args)
    if _ctx_err:
        print(_ctx_err)
        sys.exit(2)
    explain = "--explain" in args
    skip_check = False
    # ALL examples, not a keyword-selected two (2026-08-19). Three reasons, in order of weight:
    #   1. It is what every published number was measured on. `run_attribution.py` pins
    #      retrieval_mode="all", `eval_factor_set.py` reports "all-examples LOO", and Exp 1's best
    #      config is `gemma4:26b + all-examples`. The CLI was shipping a DIFFERENT arm from the one
    #      the figures describe.
    #   2. Exp 1 measured no cost: "no corpus-size crossover — all-examples ≈ keyword at every N".
    #   3. The selection it replaces was indefensible. `retrieve_examples_keyword` ranks on raw
    #      whitespace-token overlap with no stopword removal, so "a" and "from" score as highly as
    #      "mouse". On "somatic SNVs from a mouse tumour" three examples tied at 4, the tie went to
    #      list order, and the two sent to the model were a human-germline rare-disease case and the
    #      mouse one — the example matching on `somatic` ranked third and was never sent.
    # 23 examples is well inside the context budget; the harnesses have always sent them all.
    retrieval_mode = "all"
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
        print("  Tip: use --explain for full decision trace, --semantic for embedding retrieval")
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
                  explain=explain, skip_check=skip_check,
                  retrieval_mode=retrieval_mode, level=level, think=think,
                  factor_think=factor_think, clarify=clarify, context=context,
                  show_cli="--cli" in sys.argv,
                  single_pass="--two-pass" not in sys.argv)


if __name__ == "__main__":
    try:
        # main() RETURNS a status now rather than calling sys.exit itself, so that the library paths it
        # shares with the harnesses can raise instead of killing the process. Propagate it, or a failed
        # run exits 0 and any script wrapping the CLI reads that as success.
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        # A run takes tens of seconds, so Ctrl-C part-way through is expected, not exceptional.
        # Exit quietly with the conventional 130 instead of dumping a traceback.
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
