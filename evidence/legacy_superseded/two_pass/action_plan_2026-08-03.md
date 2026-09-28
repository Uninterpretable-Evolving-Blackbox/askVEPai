# Action plan — the six open items

Written against the GSoC notes list. Each item: what it actually is, what we know, what I propose, what
could go wrong, and whether it is blocked. Evidence is cited to where it was measured; where a design
choice rests on judgement rather than measurement it says so.

**Read §7 first if you only read one part** — the sequencing matters more than any individual item,
because item 3 changes whether half of item 1 is worth doing.

---

## 1. The mentors filled in the example review — what now?

**Where it stands.** 10 approve / 20 edit / 1 reject. Two findings dominate:

- **The critical tier is mostly right and, where wrong, too SMALL** — "too few" outnumbers "too many"
  9 to 2. A rewrite that shrinks it was attempted in scratch and changed **all 10 approved rows**.
- **The optional tier is the contested one** — 16/31 flag it vs 12/31 for critical. It is also the tier
  with no criterion: 22 hand-written assignments, 14 hanging off one factor value.

**The thing that will bite whoever applies these.** `priority_by_factor.json` is **generated output**, not
source. It is built by `seed_priorities.py` from the `DRIVES` dict at line 75. `HANDOFF.md` §11 and
`generation/README.md` both say "replace `priority_by_factor.json`, no code changes" — that is wrong, and
an edit made that way is silently reverted the next time Stage 0 runs. `DECISIONS.md` §1 has it right.
**Fix those two docs before anyone applies anything.**

**Her 20 edits sort by the mechanism they need, not by topic:**

| bucket | edits | what it needs |
|---|---|---|
| **A — a `DRIVES` edit, then regenerate** | `cell_type`/`mirna`→optional (7 rows) · `failed` delete (3) · `protein`→recommended (5) · `canonical`→coding.recommended (3) · `af`/`af_1kg`/`af_gnomade`→recommended (1) · `enformer`→optional (1) | one file |
| **B — re-price under a different factor** | `check_existing` (6 rows) | see below |
| **C — not expressible in the scheme** | `appris`/`tsl` superseded by `mane` (4 rows) · `mane` demoted for somatic (row 25) · `hgvs` demote (contested 5 v 6) | a priority **ceiling**, which max-composition does not have |
| **D — not a priority question at all** | CLI-vs-web scope (row 11) · `distance`→optional, `buffer_size`→ask (rows 24, 31) · predictors on regulatory∧clinical (rows 14, 26) · `GO`, `RiboseqORFs` missing | scope, catalogue, `conditional_rules` |

**On `check_existing` (bucket B), a fact she should be told before ruling.** It is priced under `origin`,
and *both* values give `recommended`, so it is unconditional in practice and — because composition takes
the max — **no `analysis_goal` value can lower it**. Her six demotions are unapplicable as a table edit.
Re-pricing it under `analysis_goal` (clinical/population → recommended, basic → optional) makes them
expressible. But **nine catalogue options `depends_on` it** — `af`, `af_1kg`, `af_gnomade`, `af_gnomadg`,
`clinvar`, `frequency`, `pubmed`, `var_synonyms`, `failed` — so the checker re-enables it whenever any of
those is on. Rows 5, 7 and 10 all carry `frequency` or `clinvar`. **On exactly the rows she asked about,
the demotion changes the label and not the configuration.** That is not a reason to refuse it; it is a
reason she should know what she is buying.

**Bucket D has a free win.** Rows 14 and 26 want predictors on purely-regulatory rows; rows 4 and 24 are
purely regulatory with *no* clinical intent and she asks for none. So the rule is **regulatory ∧ clinical
⇒ predictors** — a joint condition that only *raises*, which is precisely what `conditional_rules` already
does for `non-human ∧ clinical ⇒ maxentscan`. `DECISIONS.md` §2 resolves without building anything.

**Proposed action:** fix the two docs, apply bucket A, implement bucket D's conditional rule, put B and C
to her with the dependency fact stated. **Blocked on item 3** — see §7.

---

## 2. Back-and-forth conversation (and the keyword masking)

**Built and measured** (`underspecification_proposal.md`, prototype in `vep_assistant.py`). Three response
types — assume / disclose / ask — with a **deterministic** relevance gate: resolve the configuration under
every candidate value, and if the answer cannot move it, never ask. No LLM decides whether to ask.

| | before | after |
|---|---|---|
| real forum queries needing a question | 18/20 | **13/20** |
| questions per query | 1.50 | **0.65** |

**It caught a real safety bug.** I had proposed leaving `origin` open as the safe choice. The
`somatic ⇒ no common-variant filter` rule fires only on an *explicit* somatic, so "unstated" let the filter
through on **6 of 15 somatic rows** — identical harm to guessing germline, and guessing *somatic* harms
0 of 16 germline rows. Now fail-closed; the danger audit is **0/31 on every factor**.

**The whole remaining case for asking is one factor.** All 13 remaining questions are
`variant_size_class`, and its real problem is that `factors.json` declares it `select: single` so "both"
cannot be expressed — while **the resolver already accepts a multi-valued one** (verified). `region_focus`
had the identical problem and was already fixed this way.

**On masking.** The existing occlusion probe is not a valid test of keyword-vs-meaning — masking every cue
removes the *information*, so a perfect reasoner fails too (already recorded in `HANDOFF` §6). But masking
is the *right* fixture for testing **this** feature, because removing the information is the scenario being
simulated. The original question still needs the **paraphrase** arm ("the animal model in our facility" for
"mouse"), which remains unbuilt.

**Literature. [Lit ✓ partial]** Gervits et al., ICMI '21, arXiv:2110.06288 — read pp. 1–5 of 9; §5–6 not
read, so no claim about their model's performance. They select clarification questions by **maximum
expected utility** over a decision network and set the utility of asking about an already-known property to
**zero** — the same principle as our gate, reached probabilistically where ours is deterministic. Their
humans needed 1.72 ± 0.40 questions per ambiguity (n=22), so a ≤1 cap is not implausibly stingy; different
task, so context and not a target.

**Proposed action:** keep the prototype behind its modes; put `variant_size_class → select: multi` to her
as the question, not "should we ask users things".

---

## 3. Merge to two tiers (default + add-on) — **do this first**

**Mechanically it is nearly free.** `recommended_options` is *already* critical ∪ recommended; the
three-way split happens only in `export_for_review.py:66`. It is a presentation change.

**The cost is that it voids some of her own review.** Every edit of the form "move X from critical to
recommended" becomes a no-op once both are one bucket. By my count that is about **12 of her ~45 individual
edits** — the `af` split and `hgvs`/`mane` on rows 3 and 5, `phenotypes`→critical and `hgvs`→recommended on
6 and 8, `sift`→critical on 18 and 20, and the `mane`-for-somatic question on 25. *(Correction: I earlier
said "roughly half". That was wrong — it is closer to a quarter. This is a manual classification of prose,
so treat it as approximate.)* Everything that crosses the on/add-on line survives, and that is the
majority: `cell_type`, `mirna`, `check_existing`, `protein`, `canonical`, `failed`, `enformer`,
`dosage_sensitivity`, `mastermind`, plus every catalogue addition.

**And it retires a metric.** `critical-recall` — the 95.1% headline, reported net of `core_type` — is
defined on the critical tier. Under two tiers it ceases to exist and enable-F1 is the only number left.
**Decide the replacement before merging**, or the project loses its quality signal mid-flight.

**It also answers two of her complaints structurally.** 42% of every recommendation is already on when the
form loads (mean 12.6 listed, 5.3 of them web defaults, preselected menus, or derived). An
*already on / turn on* marker as a **column** rather than a third bucket resolves both the "the line is
blurry" objection and the `core_type` one — see item 6.

*(The canonical anchor for "a preselected default is not a recommendation" is Johnson & Goldstein,
"Do Defaults Save Lives?", Science 302:1338–9, 2003. **I have not read the full text** — the Science and
SSRN copies are paywalled/403. Abstract-level only; it must be read before it appears in any write-up.)*

**Proposed action:** implement the two-tier output with the marker column, decide the metric replacement,
and confirm the tier semantics with her in the same message as everything else.

---

## 4. Speed

**Done.** Recommender reasoning off (Exp 14): 34.9 s → 18.1 s. Classifier reasoning off (Exp 15):
8.2 s → 1.4 s median, 5.8×, no accuracy cost at either the factor level (29/31 identical tuples) or
end-to-end (89.3% vs 89.5% enable-F1). Measured end-to-end on the quickstart query: **11.2 s**, of which
0.9 s is the classifier.

**What is left.** 49% of the model's output is `Reason:` lines the corrected-config block never displays,
and 12% is a draft command that `cli_flags_for()` regenerates and discards. Cutting both is roughly
18 s → 8 s on the old measurement basis. **It changes what the user is shown, so it must be a flag, not a
deletion** — and it needs the same A/B treatment the other two got, because "the reasons are never
displayed" is an argument about the *current* output format, not a measurement that nobody reads them.

**Proposed action:** low priority now that the two big wins have landed. Do it after the review work.

---

## 5. A place to enter contextual information

**The strongest single argument is a correctness bug, not a convenience.** MANE exists **only for GRCh38**.
`InputForm.pm:694-702` gates the MANE checkbox on *species alone*, so a GRCh37 user can tick a box with no
data behind it, and **there is no `assembly` factor** (`DECISIONS.md` §8). The tool cannot currently know.

Second: some options need a **value only the user has**. `cell_type` requires naming a cell type —
which is exactly why she said it should be optional, "as it restricts regulatory annots to certain cell
types". No amount of inference supplies that.

Third: it removes 2 of the 3 measured classifier failures at the root (rows 8 and 30 are queries that never
state germline vs somatic; a field does what no classifier can).

Fourth, already agreed with her in thread 4: *"optional variant input (a VCF line / consequence class)
alongside the query, so region comes from the data"*.

**Proposed action:** an optional context panel — assembly, species, variant class, cell type — feeding the
factor tuple directly and bypassing the classifier for whatever it supplies. Independent of the review, so
buildable now.

---

## 6. `failed` is weird, and some options need a value not a switch

**Two separate things, both real.**

**(a) `failed` should go, and the argument is self-contained.** Its own catalogue entry says
`when_not_to_use`: *"Most clinical and standard analyses, where excluding QC-failed variants (the default)
gives higher-confidence co-located annotations."* `web_default: off`. Yet the priority table offers it as an
optional add-on under `clinical-interpretation` — on clinical rows, which is precisely where its own
documentation says not to use it. She flagged it on rows 1, 3 and 5. **This is not deference; the catalogue
contradicts the table.** It is bucket A above.

**(b) A class of options takes a CHOICE, not a switch — and the tool hardcodes one.**
`VALUE_DEFAULTS = {"sift": "b", "polyphen": "b", "check_existing": "yes"}`; everything else gets `True`.
But:

| option | the choice | current behaviour |
|---|---|---|
| **`core_type`** | `--refseq \| --merged \| --gencode_basic \| …` | always Ensembl/GENCODE |
| `sift`, `polyphen` | `[b\|p\|s]` — score, prediction, or both | always `b` |
| `cell_type` | *which* cell type | `True`, which is not a value |
| `frequency` | which population, which threshold | `True` |
| `buffer_size` | a number (default 5000) | never recommended at all |

**`core_type` is the consequential one, and it explains her row 11.** She wrote *"core_type — no such
option"* because on the CLI there is no such flag: there is `--refseq`, `--merged`, `--gencode_basic`. It is
a **preselected radiolist** on the web form — the user changes it or leaves it. So listing it as a
must-have asks her to validate a non-decision, which is exactly her complaint, and the fix is the
*already on / turn on* marker from item 3 rather than a demotion (which would contradict its 19
endorsements). RefSeq vs Ensembl is a genuine clinical choice — many labs report against RefSeq — and the
tool currently never offers it.

**Proposed action:** (a) delete `failed` with bucket A. (b) Model "which value" as a distinct output field
rather than folding it into on/off, and treat `core_type` as a *choice* the user makes, surfaced with its
default, not as a recommendation. Whether the **LLM** should pick the value — as the note suggests — is the
open question: Exp 8 found this model cannot reliably emit structured JSON, so a free-text value that then
has to be parsed and validated is the same fragility that cost ~30 F1 points once already. My inclination
is deterministic defaults plus an explicit user choice (item 5's context panel), with the LLM only
*justifying* the default, not selecting it. Worth arguing about.

---

## 7. Sequencing, and what one message to the mentor should contain

**Order, and why:**

1. **Item 3 (two tiers).** It decides whether ~12 of her edits are worth applying at all, and it retires
   `critical-recall`. Everything in item 1 waits on it.
2. **Item 1 bucket A + item 6(a).** Same file, one regeneration, all clean and unopposed.
3. **Item 1 bucket D's conditional rule** (regulatory ∧ clinical ⇒ predictors). Free; resolves
   `DECISIONS.md` §2.
4. **Item 6(b) + the already-on/turn-on marker.** Structurally answers `core_type` and `clinvar`.
5. **Item 5 (context panel).** Independent, fixes the GRCh37/MANE hazard.
6. **Item 2** stays a prototype pending her ruling on `variant_size_class`.
7. **Item 4 (terse mode)** last.

**One message to her, four questions — not four messages:**

1. **Two tiers**: confirm default + add-on with an *already on / turn on* marker, and note it makes ~12 of
   her edits no-ops so she does not re-send them.
2. **`variant_size_class → multi-select`**, with row 1 as the exhibit: `region_focus` already works this
   way; it is the single reason 13 of 20 real questions would need an interruption.
3. **CLI-vs-web scope**: `--overlaps` (7 rows), `max_af`, `check_svs`, `clin_sig_allele`,
   `clinvar_somatic_classification` are all real CLI options and **none is web-exposed** in release/115,
   116 or main. Row 11 is the exhibit. `GO` and `RiboseqORFs` *are* web-exposed and simply missing — those
   we just add.
4. **The contested edits**: `hgvs` (5 demote v 6 approve), `mane` (2 v 2), `check_existing` (with the
   dependency fact above).

**What is NOT blocked and can proceed regardless:** the 8 missing plugins, the `--explain` migration (it
still runs the dead 7-use-case scheme and is called *before* `infer_factors`, so it explains a procedure the
system no longer uses), the context panel, and Stage 7 (Web-VEP execution check — her own step 3, and the
largest independent deliverable left).
