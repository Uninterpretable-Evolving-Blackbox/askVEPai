# First actual output-vs-output diff (2026-09-07, Ensembl 116 REST, mouse)

ENSMUST00000108108.9:c.100G>A run through BOTH configs (truth non-human clinical vs human-guess),
18 transcript rows each. Differences in the real annotations:
- canonical: 1 -> ABSENT under the human guess (the only navigation flag; mouse has no MANE)
- mane, PolyPhen, check_existing: requested by the guess, mouse returns NOTHING
  (empirically confirms L24: no PolyPhen for mouse — in VEP's own output)
- appris=P3, tsl=1: gained AND populated for mouse (so "gains carry no data" is too strong for
  these two; both are MANE-superseded per mentors, and web_default_on regardless)
- all 26 remaining fields identical, including sift_prediction=deleterious both sides.

One variant, one pair: a demonstration, not a metric. Known harness gap found doing it:
run_vep_ab.py's PANEL is human-only (all 5 probes HTTP 400 on the mouse endpoint) and it exits 0
on all-errors. Needs a per-species panel before Stage 7 leans on it.
