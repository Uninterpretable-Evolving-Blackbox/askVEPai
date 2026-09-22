#!/usr/bin/env python3
"""Build `work/research/output_effects_dossier.md` from Ensembl's own documentation.

WHY. The mentors' position (2026-09-13): the official VEP documentation records what every option does
to the output and how options interact, so evaluation should rest on that record rather than on running
VEP. This script turns the three official pages (saved under `work/research/ensembl_docs_116/`) into one
per-option table, reconciled against our 65-option catalogue, so that:

  1. every option's OUTPUT BEHAVIOUR (adds fields / removes rows / swaps the transcript set / changes row
     extent / changes values only) is read off the page, with the page's own words beside it;
  2. every option's INTERACTIONS are the page's "Incompatible with" column, not ours;
  3. every place our catalogue disagrees with the page is listed as a discrepancy.

Nothing here comes from a VEP run. The one thing a run found that the page cannot say is recorded in §5.

  python3 work/harness/build/build_output_effects_dossier.py
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va                                              # noqa: E402

DOCS = ROOT / "work" / "research" / "ensembl_docs_116"
OUT = ROOT / "work" / "research" / "output_effects_dossier.md"

# --- behaviour classes, decided from the page's wording -------------------------------------------
# Verbatim fragments that put an option in the ROWS class. Everything with a non-empty "Output fields"
# cell on the page is in the FIELDS class. The remainder are VALUES-only or no-output.
REMOVES_ROWS = {
    "coding_only": "Only return consequences that fall in the coding regions of transcripts.",
    "most_severe": "Output only the most severe consequence per variant. Transcript-specific columns will be left blank.",
    "summary": "Output only a comma-separated list of all observed consequences per variant. Transcript-specific columns will be left blank.",
    "per_gene": "Output only the most severe consequence per gene.",
    "pick": "Pick one line or block of consequence data per variant, including transcript-specific columns.",
    "pick_allele": "Like --pick, but chooses one line or block of consequence data per variant allele.",
    "frequency": "Use this to include or exclude variants based on the frequency of co-located existing variants in the Ensembl Variation database.",
}
SWAPS_SET = {"core_type": "Limit your analysis to transcripts belonging to the GENCODE basic set. / Consequence output will be given relative to these transcripts in place of the default Ensembl transcripts"}
ROW_EXTENT = {"distance": "Modify the distance up and/or downstream between a variant and a transcript for which Ensembl VEP will assign the upstream_gene_variant or downstream_gene_variant consequences."}
VALUES_ONLY = {
    "shift_3prime": "Right aligns all variants relative to their associated transcripts prior to consequence calculation.",
    "transcript_version": "Add version numbers to Ensembl transcript identifiers",
    "failed": "by default Ensembl VEP will exclude variants that have been flagged as failed. Set this flag to include such variants.",
    "buffer_size": "Sets the internal buffer size ... Set this lower to use less memory at the expense of longer run time",
    "cell_type": "Report only regulatory regions that are found in the given cell type(s).",
}

# The form page's control names that do not carry a `vep_options.html#opt_` link, mapped by hand.
FORM_NAME_TO_ID = {
    "Frequency data for co-located variants": "check_existing",
    "Paralogue variants": "paralogues",
    "Open Targets Platform": "opentargets",
    "Gene Ontology": "go",
    "By frequency": "frequency",
    "Exclude common variants": "frequency",
    "Advanced filtering": "frequency",
    "Restrict results": None,                 # the dropdown itself; its values map individually
    "Show one selected consequence": "pick",  # page anchor says per_gene, page TEXT says --pick
    "AVI": "avi",          # added to the catalogue 2026-09-13 from this page
    "ProtVar": "protvar",  # same
}


def flag_of(o):
    m = re.search(r"--([a-z0-9_]+)", o.get("cli_flag", "") or "")
    return m.group(1) if m else None


def plugin_key(o):
    m = re.search(r"--plugin\s+(\S+)", o.get("cli_flag", "") or "")
    return (m.group(1) if m else o["id"]).lower()


def prio_summary(p):
    if not p:
        return "unpriced `{}`"
    parts = []
    for f, vm in p.items():
        for v, lab in vm.items():
            parts.append(f"{f}.{v}={lab}")
    return "; ".join(parts)


def main():
    catalogue, _ = va.load_knowledge_base()
    by_id = {o["id"]: o for o in catalogue}
    flag2id = {flag_of(o): o["id"] for o in catalogue if flag_of(o)}
    opts = {r["id"]: r for r in json.load(open(DOCS / "vep_options_parsed.json"))}
    form = json.load(open(DOCS / "vep_form_parsed.json"))
    plugs = {p["id"].lower(): p for p in json.load(open(DOCS / "vep_plugins_parsed.json"))}
    # The table as the engine uses it: the file does not carry the species gate, the loader stamps it on
    # (since engine commit 7401b98). Reading the file raw drops every species.non-human row.
    prio = va.load_priority_by_factor(catalogue)["priorities"]

    # --- form control -> catalogue id ---------------------------------------------------------
    form_of = defaultdict(list)          # id -> [(section, control)]
    form_unmatched = []
    for c in form["controls"]:
        if c["section"] == "Data input":
            continue
        oid = None
        if c["control"] in FORM_NAME_TO_ID:
            oid = FORM_NAME_TO_ID[c["control"]]
        else:
            for f in c["equivalent_flags"]:
                if f in flag2id:
                    oid = flag2id[f]
                    break
            if oid is None:
                n = c["control"].lower().replace(" ", "")
                for o in catalogue:
                    if o["name"].lower().replace(" ", "") == n or o["id"].replace("_", "") == n:
                        oid = o["id"]
                        break
        if oid:
            form_of[oid].append((c["section"], c["control"]))
        elif c["control"] not in FORM_NAME_TO_ID:
            form_unmatched.append(c)
    # Present on the form page but outside the <li><b> markup the parser reads.
    form_of["core_type"].append(("Data input", "Transcript database to use"))
    form_of["mane"].append(("Additional annotations", "MANE (checkbox, ticked)"))
    form_of["clinvar"].append(("Variants and frequency data", "via *Frequency data for co-located variants* — no separate control"))
    # The documented form page lists four Restrict-results values; the form SOURCE (Object_VEP.pm) has five,
    # including "Show one selected consequence per variant allele". Page omission, not a form omission.
    form_of["pick_allele"].append(("Filtering options", "Restrict results value — in Object_VEP.pm, omitted from the form page"))

    # --- discrepancies ------------------------------------------------------------------------
    disc = []
    missing_edges = []
    for o in catalogue:
        f = flag_of(o)
        r = opts.get(f) if va.option_source(o) == "native" else None
        if not r:
            continue
        ours = set(o.get("conflicts_with") or [])
        page = {flag2id.get(i.lstrip("-")) for i in r["incompatible_with"]} - {None}
        for m in sorted(page - ours):
            missing_edges.append((o["id"], m))
    missing_edges = sorted({tuple(sorted(e)) for e in missing_edges})
    if missing_edges:
        disc.append(("Conflict edges the page lists and our catalogue lacks",
                     [f"`{a}` × `{b}`" for a, b in missing_edges]))
    disc.append(("On the web form, added to our catalogue on 2026-09-13 from this page",
                 ["**AVI** (`avi`) — \"AlphaGenome Variant Impact (AVI) scores for single nucleotide variants\" (plugins page); Predictions.",
                  "**ProtVar** (`protvar`) — \"provides contextualised information for missense variation, including destabilisation of protein structures, overlapping protein pockets, and protein-protein interaction interfaces\" (form page); Additional annotations."]))
    # Why each of these is absent from the DOCUMENTATION page while still being on the FORM (checked in
    # InputForm.pm / Object_VEP.pm / vep_custom_web_config.json on 2026-09-14). None is CLI-only.
    FORM_PAGE_OMISSIONS = {
        "cell_type": "ON THE FORM: InputForm.pm:763-795 renders one checkbox per available cell type "
                     "(`cell_type_<name>`) at runtime, so the documentation page has no static control for it",
        "clinvar": "ON THE FORM via *Frequency data for co-located variants* (`check_existing`); no separate control",
        "gnomad_sv": "ON THE FORM as a `--custom` dataset rendered from vep_custom_web_config.json, not a documented control",
        "pick_allele": "ON THE FORM: a Restrict-results value in Object_VEP.pm that the documentation page omits",
    }
    not_on_form = [o["id"] for o in catalogue if o["id"] not in form_of]
    disc.append(("In our catalogue, absent from the documented form page — but every one is on the form",
                 [f"`{i}` — {FORM_PAGE_OMISSIONS.get(i, 'catalogue web_form_section = ' + str(by_id[i].get('web_form_section')))}"
                  for i in sorted(not_on_form)]))
    sec_mismatch = []
    for oid, places in form_of.items():
        ours = (by_id[oid].get("web_form_section") or "").replace("_", " ")
        theirs = places[0][0].lower()
        if ours and ours.split()[0] not in theirs and not (ours == "filters" and theirs.startswith("filtering")):
            sec_mismatch.append(f"`{oid}` — form: {places[0][0]}; ours: `{by_id[oid].get('web_form_section')}`")
    if sec_mismatch:
        disc.append(("Form section differs from our `web_form_section`", sec_mismatch))
    norm = {"pathogenicity_predictions": "pathogenicity", "pathogenicity_prediction": "pathogenicity",
            "splicing_predictions": "splice", "splice_prediction": "splice",
            "gene_tolerance_to_change": "constraint", "gene_constraint": "constraint",
            "phenotype_data_and_citations": "phenotype", "phenotype": "phenotype",
            "literature_citation": "phenotype", "regulatory_impact": "regulatory", "regulatory": "regulatory"}
    cat_mismatch = []
    for o in catalogue:
        if va.option_source(o) == "native":
            continue
        p = plugs.get(plugin_key(o))
        if p and norm.get(p["category"], p["category"]) != norm.get(o.get("category"), o.get("category")):
            cat_mismatch.append(f"`{o['id']}` — page: `{p['category']}`; ours: `{o.get('category')}`")
    if cat_mismatch:
        disc.append(("Plugin category differs from the plugins page", cat_mismatch))
    disc.append(("Modelled as a switch on our side, a value or multi-control on theirs",
                 ["`frequency` — the form's *Filter by frequency* is a three-way radio (No filtering / Exclude common variants / Advanced filtering). *Exclude common variants* is `--filter_common`, which our catalogue never names; *Advanced* exposes `freq_filter`, `freq_gt_lt`, `freq_freq`, `freq_pop`. We price one on/off.",
                  "`core_type` — five values on the form; page lists `--gencode_basic`, `--gencode_primary`, `--refseq`, `--merged` each with their own incompatibilities. We recommend the option on every tuple and never name a value.",
                  "`sift` / `polyphen` — page: `b` prediction+score, `p` prediction, `s` score. We price the switch.",
                  "`distance` — free-text, page default 5000. Unpriced by us.",
                  "The form page's *Show one selected consequence* links to `#opt_per_gene` but its text says \"Equivalent to --pick\". Page error; recorded so nobody \"fixes\" our mapping to match the anchor."]))

    # --- write ----------------------------------------------------------------------------------
    L = []
    w = L.append
    w("# What each VEP option does to the output, and how options interact — from Ensembl's documentation")
    w("")
    w("Built 2026-09-13 from the official release-116 pages saved in `research/ensembl_docs_116/` by")
    w("`harness/build/build_output_effects_dossier.py`. **Nothing in §1–§4 comes from running VEP.** The pages are the")
    w("record; this file reconciles our catalogue against them. Re-run the script after any catalogue edit.")
    w("")
    w("Sources (all now 308-redirect to `jun2026.archive.ensembl.org`, the same move the form made):")
    w("")
    w("- `vep_options.html` — every CLI flag with **Description · Output fields · Incompatible with**")
    w("- `vep_online_input.html` — the **web form**: each control, its CLI equivalent, the form's own warnings")
    w("- `vep_plugins.html` — every plugin, its category and what it adds")
    w("")
    w("## 0. The page's own warnings, verbatim")
    w("")
    w("These three sentences are Ensembl's, on the form page, about the whole *Filtering options* section:")
    w("")
    w("> Ensembl VEP allows you to pre-filter your results e.g. by MAF or consequence type. Note that it is also")
    w("> possible to perform equivalent operations on the results page for Ensembl VEP, so if you aren't sure,")
    w("> don't use any of these options!")
    w("")
    w("> Note that enabling one of these options not only loses potentially relevant data, but in some cases may")
    w("> be scientifically misleading.")
    w("")
    w("> NB: Restricting results may exclude biologically important data!")
    w("")
    w("So the product's own documentation says: do not pre-filter unless you are sure. That is the premise for")
    w("everything in §6.")
    w("")
    w("## 1. Five output behaviours, as the page describes them")
    w("")
    w("| class | what the page says the option does | options |")
    w("|---|---|---|")
    w(f"| **removes rows or variants** | \"Only return…\", \"Output only…\", \"Pick one line…\", \"exclude variants\" | {', '.join('`'+k+'`' for k in REMOVES_ROWS)} |")
    w("| **swaps the transcript set** | \"in place of the default Ensembl transcripts\", \"Limit your analysis to transcripts belonging to…\" | `core_type` (`--refseq`, `--merged`, `--gencode_basic`, `--gencode_primary`) |")
    w("| **changes which rows exist** | \"Modify the distance … for which Ensembl VEP will assign the upstream_gene_variant or downstream_gene_variant consequences\" | `distance` |")
    w("| **adds fields** | non-empty *Output fields* cell on the page | every other native option with an *Output fields* entry, and every plugin |")
    w("| **changes values only / no output effect** | positions, identifiers, matching, performance | `shift_3prime`, `transcript_version`, `failed`, `buffer_size` |")
    w("")
    w("`cell_type` is in two classes: it adds `CELL_TYPE` and restricts regulatory rows to the named cell types.")
    w("")

    # --- §2 native table -------------------------------------------------------------------------
    w("## 2. Native options — page record vs our catalogue")
    w("")
    w("Columns: what the page says it does · the *Output fields* the page names · the page's default · the page's")
    w("*Incompatible with* (as catalogue ids; page flags outside our catalogue are dropped) · our `conflicts_with` ·")
    w("how our priority table prices it · whether it is on by default on the form.")
    w("")
    w("| option | form control | behaviour | output fields (page) | default (page) | incompatible with (page) | ours: conflicts_with | ours: priority | form default |")
    w("|---|---|---|---|---|---|---|---|---|")
    for o in sorted(catalogue, key=lambda x: x["id"]):
        if va.option_source(o) != "native":
            continue
        f = flag_of(o)
        r = opts.get(f, {})
        oid = o["id"]
        if oid in REMOVES_ROWS:
            beh = "**removes rows**"
        elif oid in SWAPS_SET:
            beh = "**swaps transcript set**"
        elif oid in ROW_EXTENT:
            beh = "**changes row extent**"
        elif oid in VALUES_ONLY:
            beh = "values only" if oid != "cell_type" else "adds field + restricts regulatory rows"
        elif r.get("output_fields"):
            beh = "adds fields"
        else:
            beh = "no output field"
        outf = r.get("output_fields") or "—"
        dflt = ("off" if r.get("not_used_by_default") else (r.get("default") or "—")) if r else "—"
        page_inc = sorted({flag2id.get(i.lstrip("-")) for i in r.get("incompatible_with", [])} - {None})
        ours_inc = sorted(o.get("conflicts_with") or [])
        ctrl = "; ".join(c for _, c in form_of.get(oid, [])) or "*(not on form page)*"
        pr = prio_summary(prio.get(oid))
        on = "**on**" if o.get("web_default_on") else "off"
        w(f"| `{oid}` | {ctrl} | {beh} | {outf} | {dflt} | {', '.join('`'+x+'`' for x in page_inc) or '—'} | {', '.join('`'+x+'`' for x in ours_inc) or '—'} | {pr} | {on} |")
    w("")
    w("Verbatim page text for the row-affecting options, so the class is traceable:")
    w("")
    for k, v in list(REMOVES_ROWS.items()) + list(SWAPS_SET.items()) + list(ROW_EXTENT.items()):
        w(f"- `{k}` — \"{v}\"")
    w("")
    w("Two page notes that change how a recommendation should read:")
    w("")
    w("- `--most_severe`: \"To include regulatory consequences, use the --regulatory option in combination with this flag.\"")
    w("- `--check_frequency`: \"Frequencies used in filtering are added to the output under the FREQS key in the Extra field.\" — the filter also *adds* a field, so an option-count diff sees it as +1 while it deletes variants.")
    w("")

    # --- §3 plugins ------------------------------------------------------------------------------
    w("## 3. Plugins — page record vs our catalogue")
    w("")
    w("Every plugin adds fields; none removes rows. The page gives a category and a blurb; the form page says")
    w("which are offered on the web form and in which section.")
    w("")
    w("| option | form control (section) | page category | ours | page description (first sentence) | ours: priority |")
    w("|---|---|---|---|---|---|")
    for o in sorted(catalogue, key=lambda x: x["id"]):
        if va.option_source(o) == "native":
            continue
        p = plugs.get(plugin_key(o))
        places = form_of.get(o["id"], [])
        ctrl = "; ".join(f"{c} ({s})" for s, c in places) or "*(not on form page)*"
        if p:
            first = re.split(r"(?<=\.)\s+", p["blurb"], maxsplit=1)[0]
            adds = (f"**{p['long_name']}** — " if p["long_name"] else "") + first
        else:
            adds = "*(not on plugins page)*"
        adds = adds.replace("|", "/")[:220]
        w(f"| `{o['id']}` | {ctrl} | {p['category'] if p else '—'} | {o.get('category')} | {adds} | {prio_summary(prio.get(o['id']))} |")
    w("")

    # --- §4 interactions -------------------------------------------------------------------------
    w("## 4. Interactions — the page's incompatibility graph")
    w("")
    w("The *Restrict results* family is one dropdown on the form (`summary`), so its five values are mutually")
    w("exclusive by construction. The page additionally lists these as incompatible with the transcript-level")
    w("annotations, because \"Transcript-specific columns will be left blank\":")
    w("")
    for k in ("most_severe", "summary"):
        r = opts[k]
        w(f"- `--{k}` × " + ", ".join(f"`{i}`" for i in r["incompatible_with"]))
    w("")
    on_default = {o["id"] for o in catalogue if o.get("web_default_on")}
    clash = sorted({flag2id.get(i.lstrip("-")) for i in opts["most_severe"]["incompatible_with"]} & on_default)
    w(f"Of those, the ones that are **on by default on the form** are {', '.join('`'+c+'`' for c in clash)}. So choosing")
    w(f"*Show most severe* or *Show only list of consequences* on the form conflicts with {len(clash)} controls the form has")
    w("already ticked. How the form resolves that is not stated on the page.")
    w("")
    w("`coding_only` × `most_severe` and `coding_only` × `summary` are on the page and **absent from our catalogue** (§5).")
    w("")
    w("`core_type` values: `--gencode_basic` × `--gencode_primary` × `--refseq`; `--merged` × `--refseq`. `--gencode_primary` is")
    w("\"Only available for human on the GRCh38 assembly\" — an assembly gate on one value of an option we recommend everywhere.")
    w("")
    w("The frequency filter is four controls, not one: `--freq_filter` (exclude / include only), `--freq_gt_lt`, `--freq_freq`,")
    w("`--freq_pop`. `--filter_common` is the page's shortcut for the form's *Exclude common variants* radio: \"this will exclude")
    w("variants that have a co-located existing variant with global AF > 0.01 (1%)\".")
    w("")

    # --- §5 discrepancies ------------------------------------------------------------------------
    w("## 5. Where our catalogue disagrees with the page")
    w("")
    for title, items in disc:
        w(f"**{title}**")
        w("")
        for it in items:
            w(f"- {it}")
        w("")
    w("**The one thing the page cannot tell you** — documented behaviour that does not happen. `--check_frequency` with")
    w("the shipped default population `1KG_ALL` deletes nothing on a release-116 cache: the code path for `1KG_ALL`")
    w("reads two fields (`minor_allele`, `minor_allele_freq`) that the cache no longer carries, so every variant passes.")
    w("Every other population name (`AF`, `1KG_AFR`, `gnomADe`, …) reads a live column and filters as documented.")
    w("This is the only finding in three days of local runs that a careful read could not have produced, and it is the")
    w("reason to keep one local VEP install: not to characterise options, but to catch the page being wrong.")
    w("")

    # --- §6 implications -------------------------------------------------------------------------
    w("## 6. What this changes in the priority table")
    w("")
    w("Sourced from the page, not from a run. **Applied 2026-09-14/15** unless marked open:")
    w("")
    w("1. **Do not recommend any option in the removes-rows class from a factor value.** The form's own instruction is")
    w("   \"if you aren't sure, don't use any of these options!\" That removes `frequency` from")
    w("   `analysis_goal.population-frequency` (the four AF *column* options in the same list already answer the question),")
    w("   `coding_only` from `region_focus.coding`, and `most_severe` from `analysis_goal.basic-consequence`.")
    w("2. **Price `pick`, `pick_allele`, `per_gene`, `summary` as `not_applicable`** so the resolver blocks them from the")
    w("   table rather than from a special-case function. They are never recommended today, so no configuration moves.")
    w("3. **Add the two missing conflict edges** so the checker sees what the page sees.")
    w("4. **`core_type`** — OPEN by decision (David, 2026-09-14): it is the form's default and now sits under ALREADY ON,")
    w("   so the user is never told to change it. Its value question (Likhitha, row 11) stays with the mentors.")
    w("5. **`distance`** — OPEN: unpriced, on by default at 5000, listed under ALREADY ON. Left at the form default.")
    w("6. **AVI and ProtVar** — applied 2026-09-13 as add-ons. blosum62 and ancestral_allele priced 2026-09-15 (add-ons);")
    w("   blosum62 moved to Ensembl's `conservation` category and out of the pathogenicity line.")
    w("7. **Species data** — applied 2026-09-15, gated like assembly; since 2026-09-22 each option's own `species`")
    w("   list from Ensembl's sources; `species_frequency` added for the four species with files; removals printed by default.")
    w("")
    w("## 7. Evaluation rule going forward")
    w("")
    w("An option's cost class comes from §1 of this file. A recommendation error is scored by class — a missed")
    w("add-fields option costs a column; a volunteered removes-rows option costs data — not by counting options.")
    w("The page is the ground truth for behaviour; a local run is only for confirming the page where there is a")
    w("specific reason to doubt it.")
    w("")
    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}  ({len(L)} lines)")
    print(f"discrepancy groups: {len(disc)}; missing conflict edges: {missing_edges}")
    print(f"form controls unmatched to any catalogue id: {[c['control'] for c in form_unmatched]}")


if __name__ == "__main__":
    main()
