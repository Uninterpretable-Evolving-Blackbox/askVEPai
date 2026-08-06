# What the assistant should ask for: proposal for review

Status: proposal, with measurements. This is the third design decision the project had to invent rather
than inherit, after the factor taxonomy (`taxonomy_proposal.md`) and the generation pipeline
(`generation_pipeline_proposal.md`). It changes the interface contract — what a user is expected to
supply — so I would like your sign-off before it is final. `underspecification_proposal.md` states the
problem this answers; read that first if you want the fuller measurement.

## 1. The problem, in one line

The tool reads five factor values out of a free-text scenario, and a factor the question never mentions
contributes nothing, so the options it would have supplied silently disappear.

Over twenty real VEP questions collected from public issue trackers and forums, **18 of 20 leave at
least one factor open that changes the resulting configuration**. Our own 31 generated examples never
show this, because the generator was told to write questions that express their factor tuple — so the
set we have been measuring on is the best case, not a representative one.

**How real those twenty are, precisely.** Nine are **verbatim**, all from Ensembl's own issue trackers
(`Ensembl/ensembl-vep` ×8, `Ensembl/VEP_plugins` ×1), with the issue URLs recorded per item. The other
eleven — ten Biostars threads and one seqanswers — are **reconstructions**: Biostars is Cloudflare-
blocked, so the thread titles and URLs are real but the body wording was rebuilt from search snippets by
a model.

That caveat bites harder here than it usually would, because this measurement is *about phrasing* —
whether a question happens to state a fact. Reconstructed wording is not the user's wording, and the
rebuild may well drift toward the same style as our generated set, which would flatter the result.

So the finding is reported on the honest slice as well: **on the nine verbatim questions alone, 7 of 9
leave a decision-relevant factor open** — consistent with 18 of 20 overall. The conclusion does not
depend on the reconstructed eleven. Replacing them with verbatim text, if Biostars can be reached, is
the obvious way to retire the caveat.

## 2. The finding that shapes the proposal

The five factors do not fail equally, and they do not fail randomly. Splitting them by the taxonomy's
own **data fact / intent** distinction sorts every observed failure onto one side:

| factor | kind | how it behaved |
|---|---|---|
| `species` | data fact | already resolved deterministically from keywords, not by the model |
| `variant_size_class` | data fact | **the only genuine classifier error across all 31 review rows** |
| `origin` | data fact | **the two rows the classifier could not answer** — the questions genuinely never said |
| `region_focus` | intent | classified correctly on **31 of 31** |
| `analysis_goal` | intent | correct once scored the way the pipeline itself scores it |

The intent half — what you want out of the annotation — the model reads well. The data-fact half — what
your variant set *is* — is where every failure lives.

And it is also where the only *dangerous* failure lives. Guessing `germline` for a tumour sample lets
the common-variant frequency filter through, which discards exactly the variants a somatic analysis
exists to find. Measured on the review set, this affects **6 of the 15 somatic rows**. An error on the
intent side costs an annotation column; an error here costs the user their findings.

## 3. Proposal

**Facts are stated. Intent is described.**

The three data facts — species, germline/somatic, small/structural — become fields the user sets
directly, in the web form and as command-line flags. Whatever they set is authoritative and replaces
whatever the model read from the text. Anything they leave alone still goes through the classifier and
then the assume-or-say-so policy, so a user who types a sentence and presses go is unaffected.

This is not a retreat from the natural-language interface. The value of the tool was never that it
guesses what species you have — you know that — it is that it knows which of sixty options that
implies. The scenario text keeps carrying the part the user genuinely cannot express as a form: what
they are trying to find out.

**Precedent:** VEP's own web form asks for species in a dropdown rather than inferring it. Asking for
the facts is native to the domain, not a workaround.

## 4. A fourth field, which is not a factor at all

**Assembly (GRCh37 / GRCh38) has no factor and cannot be inferred**, and its absence is a correctness
bug rather than a gap:

- MANE Select transcripts exist **only for GRCh38**.
- `InputForm.pm:694-702` gates the MANE checkbox on **species alone**, so VEP's own form offers it to a
  GRCh37 user.
- Our checker can enforce the restriction, but only when the *question happens to name a build* — and
  most do not.

So a GRCh37 user can be recommended, and can tick, an option with no data behind it. No amount of
inference fixes this: a description that never mentions an assembly contains no assembly to infer. A
field is the only thing that can.

This was raised as an open decision in `../generation/candidates/review/DECISIONS.md` §8 ("should
assembly be a sixth factor, or is inferring it from the question good enough?"). This proposal answers
it a third way: **neither** — it is not a scenario factor, because it does not describe the analysis,
and it should not be inferred, because it cannot be. It is a property of the input data, like the file
format, and belongs beside the query rather than inside it.

## 5. What this does and does not change

**Removes** the two classifier failures that came from questions which never stated a fact, and the
dangerous germline-on-tumour guess, and the MANE-on-GRCh37 hazard.

**Does not change** anything for a user who ignores the fields — verified: with no field set, the
resolved configuration, the priority labels, the checker's changes and the classifier's own output are
byte-identical to before.

**Reduces, but does not remove, the case for asking questions.** Stated facts plus safe assumptions take
the clarifying questions needed from 1.50 per query to 0.65. What remains is one factor
(`variant_size_class`) whose real problem is that the scheme allows only one value where real questions
say "SNVs **and** CNVs" — see §7.

## 6. Design-choice provenance

Tags as in `taxonomy_proposal.md`: **[Src]** Ensembl VEP source / form / docs · **[Std]** external
clinical or field standard · **[Meas]** measured in this repository · **[Judg]** my own synthesis.

| Design choice | Grounding | Specific basis |
|---|---|---|
| Facts stated, intent inferred | **[Meas]** + **[Judg]** | every classifier failure across 31 rows fell on a data fact; both intent factors classified correctly. The split itself is the taxonomy's existing data-fact/intent distinction **[Judg]** |
| A stated value overrides the model | **[Judg]** | a field the model can overrule is not a field; the alternative (merge, model wins ties) was tested and rejected — it silently discards what the user said |
| Untouched fields fall back to inference | **[Judg]** | the tool's premise is that a plain description is enough; the fields must be optional or that premise is withdrawn |
| Species asked rather than inferred | **[Src]** | VEP's own form asks for species in a dropdown; `InputForm.pm` gates fields on the selection |
| Assembly as a field, not a factor | **[Src]** + **[Judg]** | MANE is GRCh38-only and `InputForm.pm:694-702` gates its checkbox on species alone **[Src]**; that it is a property of the input rather than of the analysis is my reading **[Judg]** |
| `origin` fail-closed to somatic when unstated | **[Meas]** + **[Std]** | leaving it open lets the frequency filter through on 6/15 somatic rows, identical harm to guessing germline; guessing somatic harms 0/16 germline rows **[Meas]**. That a somatic workflow must not drop common variants is the taxonomy's one hard origin rule **[Std]** |

| The 20-question sample itself | **[Meas]**, partly | 9 verbatim from Ensembl issue trackers; 11 reconstructed from search snippets because Biostars is Cloudflare-blocked. The headline holds on the verbatim slice alone (7/9), so it is not an artifact of the reconstruction — but the reconstructed wording is not user wording, and this measurement is about wording |

**Honest summary:** the *structure* here is my own reading, grounded in measurements taken on this
repository and in how VEP's own form behaves. Nothing in it is derived from a published interface
standard, because I did not find one that applies. The measurements are reproducible
(`work/harness/test_user_context.py`, 17 checks, no GPU); the judgement calls are marked as such.

## 7. What I would like you to rule on

1. **Is asking for the three facts acceptable**, or does it undercut what the tool is for? I think it
   sharpens it, but the interface promise is yours to set.
2. **Assembly** — a field, as proposed, or should it become a sixth factor after all? A field cannot
   affect option *priorities*, only availability; a factor could.
3. **Should a variant set be allowed to be both small and structural?** Review row 1 is a real question
   saying "both coding SNVs and larger structural variants or CNVs", and the scheme forces one answer,
   which is why that row carries an unrecoverable-factor flag. Allowing both removes the last remaining
   reason to interrupt a user with a question. `region_focus` already works this way.
4. **Are there facts I have missed** that a user knows and we are currently guessing? Cell type for the
   regulatory annotations is the candidate I am least sure about — it requires a value only the user
   has, which is part of why you asked for `cell_type` to be optional.
