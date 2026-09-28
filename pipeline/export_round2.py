#!/usr/bin/env python3
"""Generate the round-2 review sheet from the current engine.

WHY THIS EXISTS. The round-2 sheet was hand-built. Its option columns were faithful — they rendered
whatever the engine said — but the hand-written preamble drifted: it claimed seven previously
unreachable plugins had been added when four of them appear on no row at all. Generating the columns
and the counts removes the class of error; only the covering prose stays hand-written, and
`check_round2_ready.py` gates that.

Column K diffs against the ROUND-1 sheet the mentor actually reviewed
(`round1_review_COMPLETED_mentor_returned.csv`), mapped to the two buckets she now sees, so
"what changed since your review" means exactly that. Critical<->recommended moves collapse to
nothing, which is the point: about twelve of her twenty edits were on that boundary.

    /opt/anaconda3/bin/python3 pipeline/export_round2.py
"""
import csv
import json
import sys
from pathlib import Path

import genlib
import resolve_config as rc

REVIEW = genlib.DATA_DIR                    # the returned round-1 sheet and the generated round-2 tab
ROUND1 = REVIEW / "round1_review_COMPLETED_mentor_returned.csv"
OUT = REVIEW / "review_round2_generated.csv"

HEADER = ["#", "Species", "Origin", "Size", "Region", "Goal", "Scenario (query)",
          "RECOMMENDED - switched on", "ADD-ONS - offered, off by default",
          "of which already on", "What changed since your review",
          "Your round-1 edit NOT applied - why",
          "Right?", "Anything missing?", "Notes"]

# Every round-1 edit we could not carry out, against the row she wrote it on. Most point at a
# numbered question in round2_questions.csv rather than restating the reasoning here - the sheet
# should be light to read, and the argument belongs in one place. The four full-text entries are
# answers to notes of hers that got no reply in round 1, so they are not questions.
NOT_APPLIED = {
    (1, "canonical"): "see Q2", (7, "canonical"): "see Q2",
    (10, "canonical"): "see Q2", (12, "canonical"): "see Q2",
    (11, "appris"): "see Q2", (11, "tsl"): "see Q2",
    (19, "appris"): "see Q2", (19, "tsl"): "see Q2",
    (25, "appris"): "see Q2", (25, "tsl"): "see Q2",
    (9, "sift"): "see Q1", (14, "sift"): "see Q1",
    (26, "sift"): "see Q1", (28, "sift"): "see Q1",
    (3, "coding_only"): "see Q3", (15, "coding_only"): "see Q3", (18, "coding_only"): "see Q3",
    (7, "mane"): "see Q4", (10, "mane"): "see Q4",
    (7, "dosage_sensitivity"): "see Q5", (10, "dosage_sensitivity"): "see Q5",
    (8, "numbers"): "see Q5", (10, "frequency"): "see Q5",
    (24, "distance"): "see Q6",
    # A statement rather than a question.
    (5, "hgvs"): "your 15 Aug note 'we don't recommend HGVS for SVs/CNVs' overrode this - this row is structural",
    (10, "hgvs"): "same as row 5",
    # Notes of yours that were questions rather than edits, and got no answer in round 1.
    (1, "allele frequency options"): "this row is structural, and the small-variant frequency sources are not applicable to SVs. gnomAD-SV is the frequency source here, and it is in RECOMMENDED",
    (10, "coding_only / check_svs"): "coding_only is not applicable to structural variants, so it is gated off here. check_svs is command-line only, outside the web form scope",
    (11, "frequency"): "this is the common-variant pre-filter (--check_frequency). It removes variants rather than annotating them. What were you asking?",
    (12, "mane"): "our catalogue records MANE as human-only (GRCh38), so the species gate removes it for mouse. Your note reads as saying it should be there - which did you mean?",
    (18, "paralogues"): "left switched on. Compara does compute paralogues for mouse (Trp53 returns two), zebrafish and pig, so I gated this off for all non-human and then reverted it. See row 12 of tab 1.",
}


def round1_buckets():
    """What she reviewed, mapped to the two buckets. critical+recommended -> RECOMMENDED."""
    out = {}
    for r in csv.reader(open(ROUND1)):
        if not r or not r[0].strip().isdigit():
            continue
        split = lambda s: {x.strip() for x in s.split(";") if x.strip()}
        out[int(r[0])] = (split(r[7]) | split(r[8]), split(r[9]))   # (recommended, add-ons)
    return out


def main():
    va = genlib.load_va()
    cat = genlib.load_catalogue()
    pbf = genlib.load_priority_by_factor()
    factors = genlib.load_factors()
    corpus = genlib.load_corpus()
    src = json.load(open(genlib.DATA_DIR / "iced.json"))
    # The form ships these already; the reviewer is not really being asked to change them.
    already_on = {o["id"] for o in cat if o.get("web_default_on")}
    prev = round1_buckets()

    rows = []
    for n, s in enumerate(src, 1):
        r = rc.resolve_row(s["factor_labels"], cat, pbf, factors, va, corpus)
        opts = r["recommended_options"]
        enabled = {k for k, v in opts.items() if v.get("enabled")}
        # File by PRIORITY, not by enabled-ness, so an enabled `optional` lands in ADD-ONS rather
        # than being quietly promoted by the merge.
        recd = sorted(o for o in enabled if opts[o].get("priority") != "optional")
        adds = sorted(set(r.get("add_on_options", {})) | {o for o in enabled
                                                          if opts[o].get("priority") == "optional"})
        tag = lambda ids: "; ".join(f"{o} [already on]" if o in already_on else o for o in ids)

        moved = []
        if n in prev:
            was_rec, was_add = prev[n]
            now_rec, now_add = set(recd), set(adds)
            for o in sorted((was_rec | was_add) - (now_rec | now_add)):
                moved.append(f"{o}: removed")
            for o in sorted(now_rec - was_rec - was_add):
                moved.append(f"{o}: added to RECOMMENDED")
            for o in sorted(now_add - was_add - was_rec):
                moved.append(f"{o}: added as an add-on")
            for o in sorted(was_rec & now_add):
                moved.append(f"{o}: recommended -> add-on")
            for o in sorted(was_add & now_rec):
                moved.append(f"{o}: add-on -> recommended")

        fl = s["factor_labels"]
        j = lambda v: "+".join(v) if isinstance(v, list) else v
        rows.append([n, fl["species"], fl["origin"], j(fl["variant_size_class"]),
                     j(fl["region_focus"]), j(fl["analysis_goal"]), s["user_query"],
                     tag(recd), tag(adds),
                     f"{len(set(recd) & already_on)} of {len(recd)}",
                     "; ".join(moved) or "no change",
                     " | ".join(f"{o}: {why}" for (rn, o), why in sorted(NOT_APPLIED.items())
                                if rn == n),
                     "", "", ""])

    reach = lambda oid: sum(1 for r in rows if oid in r[7] or oid in r[8])
    plugins = ["ancestral_allele", "blosum62", "go", "intact", "mavedb", "opentargets", "riboseqorfs"]
    live = [p for p in plugins if reach(p)]
    dead = [p for p in plugins if not reach(p)]

    preamble = [
        ["Ask VEPai - candidate review set, round 2 (31 examples)"],
        ["Two buckets, not three: RECOMMENDED (switched on) and ADD-ONS (offered, off by default). "
         "The critical/recommended split is gone from the output. Naming per Nakib."],
        [f"Options tagged [already on] are set by the web form before we recommend anything - "
         f"{len(already_on)} of {len(cat)} options. Column J counts them per row. That is the part "
         f"you are not really being asked to change."],
        ["Column K lists what moved since your round-1 sheet. Edits that only swapped critical for "
         "recommended are not listed - both are RECOMMENDED now, so nothing visibly moved."],
        ["Column L names any round-1 edit we could not apply. Most point at a numbered question in "
         'tab 2, "Questions on your sheet" - the seven there settle every one of them, so that tab is '
         "the one to read. You do not need to go through these 31 rows again."],
        [f"Previously unreachable plugins now appearing: {', '.join(live) if live else 'none'}. "
         f"Still unreachable, no rule ever switches them on: {', '.join(dead) if dead else 'none'}."],
        [],
    ]

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerows(preamble)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(genlib.ROOT)}  ({len(rows)} rows)")
    print(f"  already-on options: {len(already_on)}/{len(cat)}")
    print(f"  plugins now reachable: {', '.join(live) or 'none'}")
    print(f"  plugins still unreachable: {', '.join(dead) or 'none'}")
    print(f"  rows with no change since round 1: {sum(1 for r in rows if r[10] == 'no change')}")


if __name__ == "__main__":
    sys.exit(main())
