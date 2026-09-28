# Leak rate of table-unpriced options — 26b, seed 42, think off, 31 review queries (2026-09-08)

**20/31 queries carry >=1 option the factor table deliberately does not give them.** Three classes:

1. **Gate overrides** (the dominant class, invisible to global endorsement counts): the model
   re-adds options the table gates off FOR THAT SCENARIO. All 9 `symbol` leaks are on
   regulatory-noncoding rows — the exact rows the mentor correction gates it off. Same mechanism:
   sift(3), canonical(4), regulatory(2), hgvs(1), protein(1), numbers(1), af_*(3), polyphen(1).
   The checker keeps them: it polices species/conflicts/dependencies, not per-scenario gates —
   the documented ONBOARDING Q2 behaviour, now quantified.
2. **Never-priced-anywhere** (the pick class): per_gene x2, most_severe x1 — output-collapsing
   restrict-results values on 3/31 queries. summary and pick leaked 0 here; Anne's pick incident
   used the docs' example query, not a review row.
3. **Add-on promotion**: check_existing switched ON by the model on 26/31 queries after the
   round-1 edit demoted it to optional. The mentor's most-repeated correction holds on 5/31 in
   the shipped output.

Since 2026-09-07 all of this renders tagged "model-suggested; not in the priority table" with
confidence capped at low. The open decision this measures: should the table's GATES be enforced
against model additions (a veto), which would change the enabled set and every published number.
Raw: leak_rate_26b_seed42.json. One seed; the deterministic protocol makes it exactly repeatable.

## Output-graded (2026-09-08): what each leak class does to the user's actual file

| leak class | count | real VEP output effect |
|---|---|---|
| symbol / check_existing / sift | 9+26+3 | **NONE** — REST returns them unasked and the form ships them ticked; the model contradicts mentor ADVICE, the file is unchanged |
| canonical / hgvs | 4+1 | extra populated columns — additive noise |
| per_gene | 2 | **deletes 94% of annotation lines** (334 -> 19 rows on the 10-variant cohort, measured) |
| most_severe | 1 | same family; REST ignores it, so unmeasured — form check needed |

So the leak problem, priced on the output axis, is narrow and severe rather than broad and mild:
the bulk of the leak count is advisory-only, and the whole user-facing risk concentrates in the
restrict-results family — rare (3/31 + the docs-example pick) but catastrophic when it fires.
A gate enforced on that ONE family (never emit a restrict-results value the table did not price)
would close the destructive class without touching the enabled set anywhere the table has an
opinion — a far smaller intervention than a full table veto, and it moves no published number
except on the 3 leaking rows.
