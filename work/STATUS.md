# Ask VEPai — where the project stands

The single "where are we" page: what is done, what is next, and what needs a decision. The README
covers what the tool is, how it is built and how to run it. Design rationale lives in `research/` —
`taxonomy_proposal.md` for the factor scheme, `generation_pipeline_proposal.md` for how examples are
built, `underspecification_proposal.md` for the measurements on what a question leaves unsaid, and
`reprompting_proposal.md` for the design that answers it. Evidence for every number below is in
`EXPERIMENTS.md`.

## Status

| | |
|---|---|
| Option catalogue | **68 options**, grounded in Ensembl `public-plugins` release/115 and the release-116 documentation pages (`research/ensembl_docs_116/`); AVI, ProtVar and the species frequency files added 2026-09-13/15 |
| Recommender + checker + gates | working, published, runnable |
| Deterministic invariant suite | **79 checks**, seconds, no GPU (section 10 added 2026-09-15: canonical, the removes-rows class, species disclosure, scope, the species-data gate) |
| Per-query latency | **~1.2 s** (single-pass default since 2026-09-14, 26b local; the draft call is `--two-pass`, ~18 s). `EXPERIMENTS.md` Exp 20 |
| Agreement with the priority table | **enable-F1 is undefined on the shipped path** since single-pass became the default (it scored the draft, which no longer exists). Current figures, 26b local, 3 seeds: factor tuple **22/31 exact**, end-to-end F1 **0.969 ± 0.000**; class-weighted F1 (errors priced by documented output effect, `harness/class_weighted_f1.py`) **single 0.942 vs two-pass 0.936**. enable-F1 88.0% ± 0.2 (2026-09-04, L4) stands as the last two-pass figure. `EXPERIMENTS.md` Exp 20–21 |
| Candidate review set | 31 scenarios, reviewed by the Ensembl mentors |
| Output tiers | **two** — RECOMMENDED and OPTIONAL — plus **ALREADY ON** (options the form ships ticked, named once, never recommended; species-aware). Species-data removals print under NOT AVAILABLE FOR THIS SPECIES |
| Generation pipeline | stages 0–6 built and verified; stage 7 not started |

**What that agreement figure is and is not.** It measures how faithfully the model reproduces the
configuration our own priority table specifies — self-consistency, on a table that still labels itself
provisional. It is not a benchmark, and it will not be one until the priorities are signed off. Every
number here is directional until then.

**Must-have recall is withdrawn, and 95.1% should not be quoted.** It scored against the internal
`critical` tier. That tier was the one part of the table an expert reviewed, and twelve of her twenty
edits moved options across it — corrections never applied, because merging the display had made them
invisible. Three mechanisms went on reading the uncorrected boundary: `--minimal` filtered on it,
`restore_missing_critical` restored it, and this metric scored against it. So 95.1% measured agreement
with a judgement its only reviewer had rejected, scored against itself.

The tier was deleted on 2026-08-19 rather than hidden. `--minimal` now means "no add-ons",
`restore_missing_recommended` restores the RECOMMENDED bucket, and with one enabled set there is one
recall to report, which enable-F1 already covers. `enable-F1 89.5%` was unaffected by the merge and
the deletion: it was always scored on the enabled set, which both leave unchanged. (It has since been
superseded by 88.0% for unrelated reasons — see the table above.)

## Recent work

**2026-09-13 → 15.** The draft call is gone from the default path: the checker rebuilds RECOMMENDED
from the factor tuple whatever the draft said (31/31), so the model's only decision is prose → five
factor values, at ~1 s. Scope is decided on that same call (`request_type`). Ask is the default;
every assumption is disclosed, now including species. The mentors' position that Ensembl's own
documentation records what each option does became the evaluation basis:
`research/output_effects_dossier.md` classes every option by documented effect and the priority
table follows it — nothing that removes rows is ever recommended, `frequency` is an add-on pending
Likhitha's answer, canonical is recommended everywhere (her rows 1/7/10), the four Restrict-results
values are vetoed at the resolver. Species data (SIFT ×12, PolyPhen ×1, CCDS, variant synonyms, four
species' frequency files) is a lookup beside the binary factor, gated like assembly, and the tool now
says what a species cannot have. Keyword rules for the four model-read factors are refuted at 26b
(24 traps: model 24/24, override 6/24).


**Round-2 replies received (2026-09-08).** Eight threaded comments on tab 1 of the sheet, recorded
verbatim in `MENTOR_MESSAGES.md`. What moved:

- **Type-level output (item 11) — display layer implemented.** Options in the three multi-tool
  categories (`pathogenicity_prediction`, `splice_prediction`, `literature_citation`) now render as one
  line per type — her template: "supported in Ensembl VEP for [species] ([assembly]): [options]" — with
  switched-on members starred, instead of a per-tool line each carrying its own reason. Mastermind is
  no longer a standalone endorsed line. The enabled set, the generated command and every scored metric
  are untouched: her "what should the accuracy figure become?" question is still open, so the tiers
  underneath must not move yet. A model-suggested option the table prices nothing for stays on its own
  line with its warning rather than being folded into the type listing.
- **CCDS (item 13) — deprecated, not deleted**, per her "i like the idea of deprecation for now, yes".
  The catalogue entry carries a `deprecated` note ("superseded by MANE for human") and the output
  prints it wherever CCDS appears. CCDS was already never RECOMMENDED anywhere (add-on on 12 of 108
  tuples), so no tier moved. APPRIS/TSL stay as they are — their half of the judgement is blocked on
  tab-2 Q2, which got no reply.
- **Crops (item 9) — out of scope for now**, per "let's not prioritise this for now. no work for now".
  The which-form roadmap question below stays open; the crop-coverage half is parked.
- **A fourth analysis goal (item 8) — approved in principle** ("makes sense to add a new
  analysys_value"), shaped as phenotype–gene association. They will come back with an example; nothing
  is built until it arrives, since the goal's option mapping is exactly what the example decides.
- **Non-human frequency (item 6)** — "provide frequency files for non-human where applicable". The
  applicability list, read from our own release/115 snapshot (`vep_custom_web_config.json`): the web
  form ships custom frequency datasets for exactly four non-human species — chicken (EVA PRJEB44919),
  dog (EVA PRJEB24066), goat (NextGen), sheep (NextGen IROA/MOOA) — and none for cattle or pig, which
  is what our row-7 text told her. Staged design, not yet applied: one species-gated catalogue option
  ("species frequency data", Variants and frequency data section) recommended on population-frequency
  scenarios for those four species. It grows the catalogue she is mid-review on from 65 options, so it
  waits for David's go.
- **Paralogues (item 12)** — her "check and get back if paralogue is used for non-humans", checked:
  the web plugin config passes Paralogues no parameters (`available => 1` only), and the plugin's
  no-parameter default (read from `VEP_plugins` release/115) is the on-the-fly Compara annotation mode,
  which works for any species with Ensembl paralogues — not the ClinVar-derived matches file, which is
  the human-only mode and needs an explicit `matches=` parameter. Caveat for the reply: the job-runner
  side sits outside our snapshot, so this is the form config's word, not a live-run observation.
  Non-human paralogues stay switched on, which this supports.
- **Symbol on regulatory (item 2)** — "sounds good": the shipped approach (not recommended there,
  rather than forced off) stands.
- **Gene lists (item 10)** — "we will get back on this". Pending, nothing to do.

**Two tiers instead of three.** RECOMMENDED (the former must-have and recommended, merged) and ADD-ONS.
Naming per Nakib: *"default" carries a different meaning — something that applies automatically instead
of some expert suggestion*, which is wrong for a bucket the user still has to switch on.

That distinction is meant to be carried by an *already on* marker, on the grounds that **54%** of a
typical recommendation (6.2 of 11.5 options per row) is switched on by the VEP form before anything is
suggested. **The marker is not implemented yet** — the rationale for the naming stands, the surface does
not exist, and this line should not be read as describing shipped behaviour.

The merge changed **no configuration**: the engine had always enabled must-have ∪ recommended as one
set, so the split was only ever a label on the way out. Verified as a pure regrouping over all 72
factor tuples; export totals unchanged at 391 recommended and 121 add-ons. Those two numbers are the
2026-08-07 state and are quoted only as the before/after of the merge. The mentor corrections landed
afterwards, so the sheet as generated today reads **328 recommended and 183 add-ons**.

## What is next

1. **Two separate passes for short and structural variants — BUILT 2026-08-31, one piece outstanding.**
   A scenario carrying both sizes now emits one configuration per size instead of one union of them,
   because the web form cannot express both at once: CADD's control is a four-way annotation-file
   drop-down and the files are mutually exclusive. The four labels are in the catalogue as
   `web_form_values`, read off the live form and **absent from our release/115 snapshot**, so they need
   re-checking against the form.

   `variant_size_class` stays `select: multi` and the evidence for that is untouched — assuming both
   still loses options on 0 of 29 ablations where single-select loses on 15. The split happens at render
   time, where the form imposes it. **The two passes together enable exactly what the single
   configuration did**, checked over all 36 both-size factor tuples (`verify_pipeline.py` §8b), so this
   re-assigns options to the run that can use them rather than changing any recommendation.

   CADD-SV is GRCh38-only, so a stated GRCh37 drops CADD from the structural pass with a reason rather
   than leaving it on with no file behind it. An unstated build keeps it, as the assembly gate does
   everywhere else.

   Outstanding: **the browser rendering is unverified.** The payload and the command are correct per
   pass and were tested directly; the page itself could not be exercised here because Ollama is not
   installed on this machine. Her question about whether coding/non-coding should split the same way is
   still unanswered. Verbatim in `MENTOR_MESSAGES.md`.
2. **Apply the mentor review.** Ten rows approved, twenty edited, one rejected. The unopposed edits are
   in. About twelve of the edits were must-have↔recommended moves and are **no-ops** under two tiers.
   Newly confirmed and not yet applied: `check_existing` → add-on wherever the condition holds (21 rows,
   not the 6 originally flagged), and the 8 missing web-exposed plugins.
3. **[SUPERSEDED 2026-09-13 — the record of what each option does is Ensembl's documentation, see `research/output_effects_dossier.md`; local runs are kept only to catch the page being wrong, which happened once (`1KG_ALL`).]** The output axis — run configurations through real VEP and diff the RESULT, not the option list.
   BUILT 2026-09-07/08** (`harness/run_vep_rest.py` + `harness/run_vep_ab.py`, evidence in
   `EXPERIMENTS.md` Exp 16 as corrected). A VEP result is rows (one per transcript hit) and columns
   (one per annotation); the harnesses run BOTH configurations end to end — per variant class and as
   a 10-variant cohort — with positive controls, because REST silently accepts parameters it does not
   implement.

   Census: **50 of 65 options are output-characterised.** 4 proven row-changers (the restrict-results
   family plus core_type), 32 proven column-togglable (including most plugins — CADD, SpliceAI,
   AlphaMissense, EVE, MaveDB…), 14 always present regardless of the configuration (REST returns them
   unasked AND the form ships them ticked, so a recommendation can never change the user's file for
   these — only match or contradict advice).

   The two verdicts that matter for the metrics: a clinical→basic fallback loses **19 columns at
   cohort scale, the per-variant ceiling** — so option-counting is a fair proxy there, which is
   enable-F1's defence — while a popfreq→basic fallback loses **zero columns at every scale**, so
   option-counting overstates frequency-shaped losses entirely. And the one destructive model habit:
   a leaked `per_gene` deletes **94% of the annotation lines** (334 → 19 rows, measured).

4. **[SUPERSEDED 2026-09-13 — same reason as 3.]** Stage 7 is now a named 15-option shortlist, not "run everything against Web VEP": the four
   row-changers REST ignores (`frequency` — the origin guess's entire cost — plus the `most_severe`/
   `summary`/`coding_only` family), 3 unserved column options, and 8 plugins the public service does
   not load (`mastermind` by licence). The dangerous four are NATIVE flags needing no plugin files,
   so one session with the official VEP Docker image and the human cache (~20 GB, CPU is enough)
   closes the destructive half. The web form stays the target of record for a final by-hand pass.
5. **Ask when it matters, assume when it does not.** Built, tested and live. On 78 controlled ablations,
   one fact removed from our own queries so the right answer is known, the tool interrupts on **40 of
   78**, raising 46 questions: **34** about assembly and **12** about `analysis_goal`. Reproduce with
   `harness/ask_rate.py`, which prices every candidate policy on the same cases with no model.

   That is a lot of interruption for a design whose first principle is that asking is the exception, and
   it is flagged as such in `reprompting_proposal.md` §9. The assembly share is the part the ablations
   can only overstate: their queries never name a build, while **4 of the 8** real tracker questions do,
   and the question is suppressed whenever the text says.

   How often real users omit things is **not established**: of 43 issues pulled verbatim from the
   trackers, only 8 are configuration questions. That number decides how aggressive to be, and needs the
   `real_data` Likhitha has offered.

## Open questions

These need a domain decision, not more code:

- **Which predictors are the core set,** and on what axis? VEP itself ranks none of them; the current
  split follows a clinical-genetics standard external to VEP.
- **Should a purely regulatory query keep the missense predictors?** They produce empty columns, but
  the review asked for them back.
- ~~**Should the assistant say what it cannot do?**~~ **Answered 2026-09-15.** A species-data gate
  withholds SIFT/PolyPhen/CCDS/variant synonyms/frequency files where Ensembl has none for that
  species and prints why under NOT AVAILABLE FOR THIS SPECIES. "Population frequencies for my mouse
  variants" now says there is no file for mouse and names the four species that have one.

- **The form our catalogue is built from has moved to the archive host, and the main site now serves a
  new VEP.** Checked live on 2026-09-02: `www.ensembl.org/tools/vep` **and** `www.ensembl.org/Tools/VEP`
  both serve the new interface ("Release 2026-07", "Variant Effect Predictor v110", a genome selector
  "across the tree of life"), while `www.ensembl.org/Homo_sapiens/Tools/VEP` redirects to
  `jun2026.archive.ensembl.org` ("Ensembl genome browser 116") — the classic `InputForm.pm` form the
  65-option catalogue is derived from. PROGRESS.md §10 flagged this as a risk to confirm; it has
  happened. **Ask them which form the project should target**, because the answer decides whether the
  catalogue's provenance still holds.

- **Crops are IN the new form's genome selector.** Searching it for "wheat" returns **35 genomes**,
  including *Triticum aestivum* (IWGSC RefSeq v1.0, release 2026-07, "integrated"). The round-2 sheet's
  row 9 says covering crops "would mean a second option catalogue, not a new species value" — true of
  the **classic** form, where plants are served separately (`plants.ensembl.org/Triticum_aestivum/Tools/VEP`
  still resolves, via `eg63-plants`, to `jun2026-plants.ensembl.org`, "Ensembl Genomes 63"). On the new
  form it looks like exactly a genome selection. Bare `plants.ensembl.org` now redirects to
  `www.ensembl.org`. **Not verified:** whether the new form offers the same option set, for plants or
  at all — that needs a pass over the live form, not our release/115 snapshot.

**Settled:** Ask VEPai stays **web-form-only** — CLI-only options (`--overlaps`, `--max_af`,
`--variant_class`, `--check_svs`, `--clin_sig_allele`, `--clinvar_somatic_classification`) are out of
scope. Two tiers, named RECOMMENDED and ADD-ONS. `check_existing` may move to add-on.

**Decided from measurement** (`reprompting_proposal.md` §9, each reversible by one line, each with the
alternative priced in `harness/ask_rate.py`):

- **A variant set can be both small and structural.** `variant_size_class` is `select: multi`, guessed
  *both*. This amends the signed-off taxonomy, so §5 carries the full argument. No configuration moves:
  the 31 review rows are single-valued and the export totals 391 recommended / 121 add-ons.
- **`analysis_goal` is asked, not guessed.** It meets neither of our conditions for guessing. On the 8
  real tracker questions it is genuinely absent once, so asking costs less than the ablations imply.
  Skipping is free and the fallback announces itself.
- **Assembly is asked, never guessed** — the one gap where silence gives a *wrong* answer, and where
  both guesses delete something real. Read from the text where it is there (4 of 8 real questions), and
  scored on what the user stated rather than on what we assumed for them.
- **The interrupt bar is the RECOMMENDED bucket the user sees**, named as `ASK_BAR_PRIORITIES`. Not the
  internal `critical` tier: twelve of the twenty mentor edits moved options across that boundary, so an
  interruption should not depend on it. Both bars raise identical questions on the current guesses.

## Honesty note

The example configurations are generated from a priority table that is our own editorial judgement.
VEP does not rank its own options, so somebody had to, and that somebody was us. Until the Ensembl
mentors sign that table off, the agreement figures above measure fidelity to a proposal rather than
correctness — and the decisions it rests on are written down in
`generation/candidates/review/DECISIONS.md` precisely so they can be argued with.
