# `research/` — what each file is for

## The design, in four documents

Each states a problem the project had to decide rather than inherit, the measurements behind the choice,
and what would overturn it. Read in this order; each is current with the pipeline as it runs today.

| | decides |
|---|---|
| `taxonomy_proposal.md` | the five factors every other piece is keyed to. Signed off, with two amendments pending: the `region_focus` hard gate and `variant_size_class` multi-select, both noted in `factors.json` |
| `generation_pipeline_proposal.md` | how `(query → config)` examples are built without a model ever choosing an option |
| `underspecification_proposal.md` | what a real question leaves unsaid — the raw measurements |
| `reprompting_proposal.md` | what the assistant assumes, states and asks when a fact is missing. The two-tier output and the assume/ask policy both live here |

Numbers in these are reproducible without a GPU: `../harness/defaults_evidence.py` re-derives every
guessed value, `../harness/ask_rate.py` prices how often the tool interrupts, and
`../generation/verify_pipeline.py` holds the pipeline's invariants.

## Two dossiers, kept because the catalogue points at them

These are not design documents and are not read end-to-end. They are the extraction notes from Ensembl
`public-plugins` release/115, and they survive because **the catalogue cites them as provenance**:

- `plugins_dossier.md` — named in the `provenance` field of seven catalogue options. Delete it and those
  options lose their source.
- `constraints_dossier.md` — the constraint graph the checker was built from. `constraints_dossier.md:123`
  is the cited evidence for the `region_focus` hard gate in `factors.json`, `priority_by_factor.json`,
  `DECISIONS.md` and the engine, and that gate is still awaiting sign-off.

Everything else they documented now lives in `../vep_options_expanded.json`, which carries `cli_flag`,
`species_restriction`, `web_form_section` and a per-option `provenance` string for all 65 options. That
is the file to read, not these.

## Literature

| | |
|---|---|
| `LITERATURE.md` | the reading behind each part of the system, grouped by which part |
| `CITATION_VERIFICATION.md` | a full-text pass over every citation, recording what each source does and does not support |

Model choice is **not** decided here. It was settled empirically — `../EXPERIMENTS.md` Exp 10, a 5-seed
comparison of the three Gemma sizes under the corrected parser.
