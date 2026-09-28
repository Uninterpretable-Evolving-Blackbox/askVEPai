# D8 · the priority table's tiers, as corrected by the mentors' review

The table that decides which options are RECOMMENDED and which are ADD-ONS for each factor value is
[`../../../vep_ai_demo/priority_by_factor.json`](../../../vep_ai_demo/priority_by_factor.json) (in the engine). This folder holds the review
rounds that corrected it.

| what | file |
|---|---|
| round 1 as sent (31 scenarios, three tiers), with the cover note of eleven decisions | `mentor_review/AskVEPai_review.xlsx`, `review_queue.{csv,json}`, `review_view.txt`, `DECISIONS.md` |
| round 1 as the mentor returned it, verdicts and notes | the returned sheet (private working repository); the verdict columns alone: `mentor_verdicts.json` |
| round 2 drafts, and the Ensembl team's sheet comments | `review_round2.csv`, `review_round2_twotier.csv`, `AskVEPai_review_round2.xlsx`, `round2_comments.py` |
| DEFAULT renamed RECOMMENDED in the round-2 sheet | `retitle_review_two_tier.py` |
| round 2 exactly as sent on 2026-08-19 (four tabs) | `mentor_review/AskVEPai_round2_SENT_2026-08-19.xlsx`, with tabs 2 and 3 as `round2_questions.csv`, `scenario_rules_proposed.csv` |
| the table scored against the reviewer's own round-1 answers | `build_mentor_gold.py` (private working repository): F1 0.796 |

What the mentors said, verbatim, is in `MENTOR_MESSAGES.md` (private working repository).

**Limits.** The round-1 sheets carry three tiers (critical / recommended / optional); the critical tier was
merged into recommended on 2026-08-19. The 0.796 was computed before the 2026-09-20 plugin-list changes
and has not been re-run.
