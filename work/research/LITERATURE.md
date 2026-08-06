# Literature grounding

This is the reading that informs Ask VEPai's design, grouped by the part of the system each body of work
supports. For each entry I note **what it contributes to the design** and, where it matters, **the limit of
what it actually shows** — so it is clear which choices are literature-backed and which are my own judgement
(collected at the end).

A note on honesty: several of these papers demonstrate on tasks or model scales different from ours, and a
few are cited for a *concept* rather than a transferable result. I flag those cases rather than overstate
them.

---

## RAG and retrieval — why the knowledge lives in an editable store, not the weights

- **Lewis et al. (2020), Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks — NeurIPS 2020.**
  The foundation: a generator conditioned on retrieved text, where the knowledge is a non-parametric,
  editable index. Their index hot-swap experiment shows knowledge can be updated *without retraining* — the
  core reason Ask VEPai keeps the VEP option catalogue in JSON rather than in a fine-tuned model.
- **Karpukhin et al. (2020), Dense Passage Retrieval — EMNLP 2020.** The dual-encoder retrieval paradigm our
  `--semantic` mode mirrors. Two honest points: DPR ranks by **inner product** (it found cosine *worse*, §5.2)
  — cosine is our BGE choice, not DPR's; and DPR shows retrieval recall **rises with k**, but its own k=10 is
  near-optimal. So DPR grounds "recall improves with k," *not* our finding that hard-filtering the options to
  a top-10 hurts — that result is our own (see the experiments), over a small option set rather than a large
  passage corpus.
- **Asai et al. (2023), Self-RAG — ICLR 2024.** A model that decides when to retrieve and then critiques and
  cites its own output via reflection tokens. The conceptual cousin of our `[source:]` citations plus checker
  — with the difference that Self-RAG's critique is the same model judging itself (probabilistic), whereas our
  checker is a separate deterministic layer.

## In-context learning — why we put worked examples in the prompt

- **Brown et al. (2020), GPT-3 / Language Models are Few-Shot Learners — NeurIPS 2020.** Defines in-context
  learning: specify a task by examples in the prompt, with no weight updates. The mechanism the whole
  "examples in the prompt" design rests on.
- **Agarwal et al. (2024), Many-Shot In-Context Learning — NeurIPS 2024.** Shows that adding many *distinct*
  demonstrations keeps helping (the gain is from new information, not context length), up to a
  **task-dependent** saturation point. This grounds our "include the examples we have" stance. Two limits to
  keep straight: the paper uses randomly sampled demonstrations and runs **no retrieval/selection baseline**,
  so it supports "more distinct examples help," not our specific "all-examples beats keyword selection"
  crossover (that is our own result); and its saturation is high — for its per-class experiment, hundreds to
  thousands of examples per class — so our small gold set sits far below any plateau.
- **Wei et al. (2022), Chain-of-Thought Prompting — NeurIPS 2022.** Eliciting step-by-step reasoning improves
  reasoning tasks. Relevant to our per-option `Reason:` lines — with the paper's own caveat carried forward:
  it explicitly leaves open whether the stated reasoning is *faithful* to the computation, and it finds that
  reasoning placed *after* the answer gives no accuracy gain. Since our reasons are emitted alongside the
  recommendation, they are best treated as justification, not as evidence of the model's actual decision path.

## Grounded generation and citations — making the output traceable

- **Gao et al. (2023), ALCE / Enabling LLMs to Generate Text with Citations — EMNLP 2023.** Evaluates citation
  quality as **precision and recall of whether each source actually supports the statement** (via NLI
  entailment), not merely whether a citation tag is present. This is the published template for why we
  retired a format-only "citation-rate" metric in favour of measuring whether a `[source:]` claim is grounded.

## Guardrails — the deterministic checker

- **Rebedea et al. (2023), NeMo Guardrails — EMNLP 2023 (demo).** Prior art for **programmable rails wrapping
  an LLM**, which is the shape of our defense-in-depth checker. Important scope point: NeMo's own safety rails
  are largely LLM-mediated, and the paper advises against using it as a stand-alone guarantee — so I cite it
  for the programmable-rails *concept*, not for determinism. Ask VEPai's checker is pure Python and is the
  deterministic part of our system.

## Synthetic data generation — the gold-example pipeline

- **Josifoski et al. (2023), SynthIE — EMNLP 2023.** The reverse/asymmetric idea: for structured-output tasks
  a model can't reliably do forward, fix the target structure first and generate plausible input text second.
  This is exactly our pipeline shape — deterministic code fixes the VEP config, the model writes only the
  query. SynthIE also balances coverage by sampling inversely to frequency (over its structured labels), which
  our stratified sampler echoes.
- **Alberti et al. (2019), Synthetic QA Corpora with Roundtrip Consistency — ACL 2019.** Generate a question
  from an answer, re-answer, keep only if recovered. The basis of our in-context usefulness screen — with the
  caveat that their "recovered" is exact span-match; for open-ended config answers we need our own definition
  of recovery.
- **Iskander et al. (2024), Quality Matters: Evaluating Synthetic Data for Tool-Using LLMs — EMNLP 2024.**
  Motivates quality gates for synthetic tool data (they find parameter-alignment errors in a large fraction of
  a popular tool dataset) and defines In-Context Evaluation (ICE) — scoring whether an example *helps* a model
  learn in context, which is distinct from human-judged correctness. Our filter criteria and ICE screen follow
  this.
- **Filice et al. (2025), DataMorgana — ACL 2025 (Industry).** Query diversity should come from an explicit
  grid of categorisations, not from hoping the model varies phrasing. Their own ablation finds the
  *persona/user* axis contributes only marginally to diversity while the *question* axes carry it — an
  empirical result on their category sets, not a universal law. We keep a persona axis for audience realism
  (this tool serves clinicians, bioinformaticians and students) while treating its diversity value as unproven,
  and we test it directly.
- **Xu et al. (2025), Stronger Models Are Not Stronger Teachers for Instruction Tuning — NAACL 2025.** A larger
  same-family model is not reliably a better teacher; what predicts teacher quality is *compatibility* with the
  student. This is why the query-writing teacher for our pipeline is chosen empirically (by the ICE screen),
  not assumed from size.
- **Wang et al. (2023), Self-Instruct — ACL 2023.** Source of the near-duplicate filter we adopt (keep a new
  item only if its ROUGE-L similarity to any existing one is below a threshold).
- **Xu et al. (2024), WizardLM / Evol-Instruct — ICLR 2024.** Instruction-evolution by rewriting prompts into
  progressively more complex ones. Cited as a technique we deliberately do *not* apply to configs (evolving a
  structured option set would manufacture constraint violations); if used at all, only on the query text.
- **Sechidis, Tsoumakas & Vlahavas (2011), On the Stratification of Multi-Label Data — ECML PKDD 2011.**
  Iterative stratification preserves each label's distribution across splits far better than random sampling,
  at the cost of exact per-fold example counts — the basis for how we would split a multi-label gold set once
  it is large enough for a held-out test set.

## Evaluation

- **Es et al. (2023), RAGAS — EACL 2024 (demo).** Reference-free RAG metrics (faithfulness, answer relevance,
  context relevance) computed without gold answers — the framing for the gold-free metrics we rely on while
  real gold data is pending. Their own caveat holds: these are support metrics, not correctness.
- **Saad-Falcon et al. (2024), ARES — NAACL 2024.** A small human-preference set (on the order of 150
  annotations) plus prediction-powered inference gives calibrated, confidence-bounded automatic judges — the
  target for turning the first mentor-reviewed rows into a calibration set.

## Attribution and interpretability

- **Cohen-Wang et al. (2024), ContextCite — NeurIPS 2024.** Black-box context attribution: fit a sparse linear
  surrogate over random context ablations; the surrogate weights are the attribution scores. This is the
  principled form of the leave-one-out ablation our faithfulness experiments hand-roll (leave-one-out is its
  single-source special case), and it runs on a black-box endpoint since it needs only the response
  probabilities — a natural upgrade path for our attribution work.
- **Meng et al. (2022), ROME / Locating and Editing Factual Associations — NeurIPS 2022.** Causal tracing
  (corrupt the input, restore internal states to localise where a fact lives, then edit it). The white-box
  analogue of our input-side ablation, and a reference point if we ever probe whether the model *internally*
  represents species gating.
- **Sundararajan et al. (2017), Integrated Gradients — ICML 2017.** The axiomatic vocabulary for attribution
  (Sensitivity, Implementation Invariance). It needs a gradient/backward pass, so it is white-box and not
  usable on our local black-box stack — noted to explain why we use ablation-based attribution instead.
- **Interpretability frontier (future direction):** Wang et al. (2022, IOI circuit), Cunningham et al. (2023,
  sparse autoencoders), Lieberum et al. (2024, Gemma Scope pretrained SAEs), Dunefsky et al. (2024,
  transcoders). These sketch a possible mechanistic pilot — does the model internally represent "non-human"
  and suppress human-only options, or is the deterministic checker carrying it? Two honest caveats: these
  results are on small models and are approximate, and Gemma Scope's pretrained SAEs are for **Gemma 2**, so a
  Gemma-4 deployment would need retraining rather than reuse.

## Domain assistants — the bar a scientific tool must clear

- **Singhal et al. (2023), Med-PaLM — Nature 2023.** The evaluation-rigor bar: multi-axis expert (and lay)
  human evaluation covering factuality, harm, and bias. Cited for that bar only — Med-PaLM is not itself
  retrieval-augmented.
- **Zakka et al. (2023), Almanac — NEJM AI 2024.** The closest architectural analogue: a retrieval-augmented
  clinical assistant grounding answers in a curated source and evaluated by clinicians for factuality,
  completeness and safety. Read for what made it credible to domain experts — with the honest note that its
  completeness gain was not statistically significant and clinicians still often preferred the ungrounded
  baseline, so grounding is necessary but not automatically sufficient.

---

## What is my own judgement, not literature

To keep the line clear, these design choices are mine (grounded in the VEP web form and in reasoning), not
taken from any paper:

- **The factor taxonomy itself** (species / origin / variant-size / region-focus / analysis-goal, multi-label).
  There is no canonical variant-annotation workflow taxonomy in the literature; the factor structure is my own
  reading of the VEP web form and of how the clinical field separates germline/somatic, SV/CNV, and species.
- **The per-option, per-factor priorities.** No authoritative source ranks option importance per scenario;
  these are expert judgement, flagged provisional and pending mentor validation.
- **Keeping the persona query axis** (the literature suggests persona is marginal for diversity — I keep it for
  audience realism and test it).
- **The de-duplication thresholds and the AND rule** (one threshold follows Self-Instruct; the rest are
  hand-picked and flagged for an ablation).
- **The example-count saturation estimate for our task** (a conservative own-estimate; the many-shot
  literature's measured saturation is far higher, which only reinforces that our small gold set is well within
  the "more examples help" regime).

Everything above is directional while the gold standard is simulated and the priorities are provisional; none
of it is a validated benchmark until the mentor signs off the taxonomy and priorities.
