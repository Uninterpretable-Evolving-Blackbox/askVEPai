# Prompt-engineering literature — what applies to askVEPai

`LITERATURE.md` covers RAG, in-context learning, synthetic generation, attribution and the domain-assistant
bar. This file covers the prompting layer specifically: the output contract, prompt-format sensitivity,
where the catalogue sits in the context, the ask-vs-assume policy, the confidence labels, reasoning mode,
over-recommendation, and how the evaluation numbers should be reported.

Each entry says what the paper measured, the limit of what it transfers, and the concrete change it implies
for this repository.

## Read status

`CITATION_VERIFICATION.md` sets the bar: a claim is only as good as the section it was read from. Applying
the same rule here, nothing below was read at the depth of that 2026-07-12 pass.

| depth | papers |
|---|---|
| **Results read** (tables/figures pulled from the HTML full text) | Tam 2024 (Table 9, Fig. 3), Liu 2024 (20-doc results), Su & Cardie 2026 (results summary), BiasBusters (bias table), Miller 2024 (recommendation list) |
| **Abstract / landing page only** | Sclar 2024, Sprague 2025, Xiong 2024, Turpin 2023, Huang 2024, Zhou 2023, Lu 2022, Mizrahi 2024, Khot 2023, Wang 2023, Angelopoulos 2024, Zhang 2025, Ray 2026 |

Every number below carries the source it came from. Nothing here is a verified claim about askVEPai until
the corresponding experiment is run in this repository.

---

## 1. The output contract — reopening Exp 8

Exp 8 found structured JSON output not viable on the local model (~40% valid) and the free-text
`✓/✗ [source: id]` parser was kept. That experiment tested **prompt-only** JSON, and the field has since
split that question in two.

**Tam et al. (2024), *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of
LLMs*** (arXiv:2408.02442, 18 pages). Compares three modes: constrained decoding (JSON-mode),
format-restricting instructions, and a two-step natural-language-then-convert path. On reasoning tasks the
restriction costs a lot — GPT-3.5-Turbo Table 9 gives Last Letter 56.7 → 25.2 and GSM8K 76.6 → 49.3 going
from text to JSON-mode, with Shuffled Objects flat at 20.4 → 20.9. On **classification** the trend reverses:
"When evaluating classification datasets, we observe a different trend compared to reasoning tasks", and
JSON-mode "performs competitively, and in some cases, surpasses the other three methodologies".

**The split matters because askVEPai has both kinds of call.** `FACTOR_CLASSIFIER_PROMPT` is a
classification task producing a ~60-token object, which is the regime where the paper finds JSON-mode fine.
The recommendation stream carries per-option `Reason:` text, which is the regime where it does not.

**Ray (2026), *The Constraint Tax*** (arXiv:2605.26128, single-author preprint, submitted 2026-05-20) is the
counterweight. 15,000 generations over Qwen2.5-0.5B, Qwen2.5-1.5B and SmolLM2-1.7B: hard schema constraints
took validity 61.5% → 100.0% while accuracy fell 19.7% → 11.0%, and on a deterministic calendar tool-call
task prompt-only JSON scored 91.5% executable accuracy against 48.0% under a hard schema, both 100%
schema-valid. **The limit is large:** these are 0.5–1.7B models, ours is a 26B MoE, and it is one preprint
by one author. It is a reason to measure rather than a reason to expect the same result.

**Action.** Ollama exposes schema-constrained decoding through the `format` parameter, accepting a JSON
schema object (its own guidance: temperature 0, and keep asking for JSON in the prompt). The classifier
already runs at temperature 0 with seed 42 through `_classify_native`, so the A/B is one field in the
request body. Measure `factor_check_unparseable` and the readings themselves, not just validity — the
Constraint Tax result is that validity rises while the answer gets worse, so a validity-only metric would
report success either way. Leave the recommendation stream on free text.

## 2. Prompt-format sensitivity — the ± in STATUS.md measures the wrong thing

`HANDOFF_2026-08-08.md` §6 records that making `variant_size_class` multi-select changed `_schema_lines()`,
changed the classifier prompt, and moved the measurement from 4/8 to 2/8 with **zero** spread across seeds
42/43/44. That is the published phenomenon, not a local quirk.

**Sclar et al. (2024), *Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design***
(ICLR 2024, arXiv:2310.11324). FormatSpread samples plausible prompt formats and reports the interval of
expected performance without touching weights. Abstract: differences of up to **76 accuracy points** on
LLaMA-2-13B in few-shot settings, and a spread up to 56 points with a **median of 6.4** across 320 formats
and 53 tasks on GPT-3.5, under $10 per task. The perturbations are things like separator choice and casing,
not content.

**Mizrahi et al. (2024), *State of What Art? A Call for Multi-Prompt LLM Evaluation*** (TACL) analyses
single-prompt brittleness across 6.5M instances, 20 LLMs and 39 tasks, and argues for evaluating with a set
of diverse prompts.

**Limit.** Both are read from abstracts. Sclar's 76-point figure is a maximum on a 13B dense model over
classification-style tasks; the median 6.4 is the number to plan against.

**Action.** `STATUS.md` reports enable-F1 89.5% ± 0.6 over 3 seeds. That interval prices decoding noise,
which is near zero at temperature 0 with a fixed seed, and prices nothing about the prompt. A format arm in
`eval_factor_set.py` — N formats × the existing seeds, varying separators and label casing in the option
block and in `_schema_lines()` — turns ±0.6 into an interval that means something. Do this before the
priority table is signed off, because a format spread wider than the tier effect would make the tier A/B
unreadable.

## 3. Where the 65 options sit in the context

**Liu et al. (2024), *Lost in the Middle: How Language Models Use Long Contexts*** (TACL). Multi-document QA
at 20 documents, gold document at position 0 / 9 / 19: GPT-3.5-Turbo 75.8% / 53.8% / 63.2%,
LongChat-13B-16K 68.6% / 55.3% / 55.0%, MPT-30B-Instruct 53.7% / 52.2% / 56.3%. Closed-book GPT-3.5-Turbo
scores 56.1% and oracle 88.3%, so middle placement drops it below answering with no documents at all.

**What transfers and what does not.** The task is retrieval of one gold passage among distractors; ours is
selection of a subset from a catalogue where most entries are legitimately irrelevant to a given query.
Nobody has shown the U-curve holds for that shape. The mechanism — position in the context predicts
whether an item is used — is the part worth testing.

**Action.** `compress_options` emits the catalogue in a fixed order every run, so option position is a
constant that has never been varied. Shuffling option order across seeds costs one line and answers whether
any part of the 89.5% is positional. It also bears on the tier signal: if late-listed options are
under-recommended regardless of tier, the "under-recommends the recommended tier" diagnostic has a second
explanation.

Two secondary sources, both weaker:

- **BiasBusters** (arXiv:2510.00307v2, ICLR 2026 per the listing) measures tool-selection bias over clusters
  of **5 functionally equivalent APIs**, 100 queries each, 10 clusters. Positional bias as total-variation
  distance from uniform ranges 0.168 (Qwen3-235B) to 0.504 (DeepSeek-V3.2-Exp); filtering to a relevant
  subset then sampling uniformly cuts δ_pos from 0.422 to 0.079. The setup is a fairness study over
  interchangeable tools, which our catalogue is not. Cite for "position moves selection", nothing more.
- Blog and secondary summaries claim tool-selection accuracy collapses somewhere past 200 tools. **Not
  verified against any paper I read.** At 65 options we are well below any threshold these sources name,
  which is consistent with our own result that hard-filtering to top-10 hurts.

## 4. Ask when it matters — the policy should not be the model's

The re-prompting design decides in Python when to interrupt (`ASK_BAR_PRIORITIES`, `assembly_question()`,
`UNDERSPECIFIED_POLICY`). The literature says that is the right place for it.

**Su & Cardie (2026), *Knowing but Not Showing: LLMs Recognize Ambiguity but Rarely Ask Clarifying
Questions*** (arXiv:2605.25284v1, 2026-05-24, preprint; keywords indicate an ICML submission). 10 models
across OpenAI, Claude and Qwen families on 1,000 AmbigQA items (425 unambiguous, 575 ambiguous). Models hit
**60–80%** accuracy at judging ambiguity when asked to judge it, and answer directly **above 95%** of the
time in the QA setting. Retrieved context raises QA accuracy 9–13 points and makes clarification *rarer*.
"Models can recognize that a query is ambiguous when explicitly asked to judge it, yet in the QA setting
they overwhelmingly default to direct answers."

**This is the citation for §9 of `reprompting_proposal.md`.** A retrieval-augmented assistant that asked
nothing would be the expected behaviour, not a design. It also predicts the direction of our own
measurement: an LLM-decided ask policy would interrupt far less than 38-of-78, and would look better on
interruption rate while being worse.

**Limit.** AmbigQA ambiguity is entity/temporal/scope ambiguity in short factoid questions. Ours is a
missing factor value in a workflow description, and the models are frontier APIs rather than a local 26B.
The mechanism claim (recognition does not produce asking) is what transfers.

Adjacent, abstract-only, useful if a benchmark framing is ever wanted: **CLAMBER** (arXiv:2405.12063, ~12K
items, reports limited practical utility of off-the-shelf LLMs at identifying and clarifying ambiguous
queries) and **ClarQ-LLM** (arXiv:2409.06097).

## 5. The `confidence: high|medium|low` field

The output contract asks for a confidence label on every line. Nothing in the repository measures whether it
means anything.

**Xiong et al. (2024), *Can LLMs Express Their Uncertainty?*** (ICLR 2024, arXiv:2306.13063). Frames
confidence elicitation as prompting strategy × sampling method × aggregation. Verbalized confidence is
overconfident, "potentially imitating human patterns of expressing confidence"; human-inspired prompts plus
consistency across multiple responses plus better aggregation mitigate it; white-box beats black-box but
narrowly, "0.522 to 0.605 in AUROC". No single technique wins everywhere, and all struggle on tasks needing
specialist expertise.

**Action, two options.** Score the label on the 31 reviewed rows — group recommendations by stated
confidence and check whether accuracy separates. If it does not separate, remove the field: it costs decode
tokens on a latency-bound path and reads as calibrated information to a user for whom it is not. Consistency
aggregation is the alternative, and it costs k× the 18 s.

## 6. Reasoning mode, and what the `Reason:` lines are

**Sprague et al. (2025), *To CoT or not to CoT? Chain-of-thought helps mainly on math and symbolic
reasoning*** (ICLR 2025, arXiv:2409.12183). Meta-analysis over 100+ papers plus their own evaluation on 20
datasets × 14 models. CoT gains concentrate on math and symbolic problems; on MMLU, answering without CoT is
near-equivalent except where the question contains symbolic operations. Their conclusion is that CoT can be
applied selectively to save inference cost.

Exp 14 measured 18.1 s with reasoning off against 34.9 s with `--think`, on **one seed**. That is the
predicted shape for a task that is classification and lookup rather than symbolic reasoning. A 3-seed re-run
with the accuracy arm attached converts a latency observation into a defensible default.

**Turpin et al. (2023), *Language Models Don't Always Say What They Think*** (NeurIPS 2023,
arXiv:2305.04388). Adding biasing features to inputs — for example reordering options so the answer is
always "(A)" — drops accuracy by as much as **36%** across 13 BIG-Bench Hard tasks on GPT-3.5 and Claude 1.0,
and models systematically fail to mention the bias while generating CoT that rationalises the biased answer.

This is the sharper version of the caveat `LITERATURE.md` already carries under Wei et al. The `Reason:`
lines and `[source:]` tags are a justification surface. The ablation work in Exp 6 is the thing that
measures grounding, and the two should never be described in the same breath.

## 7. Over-recommendation — the precision headroom

77% recall with 87 extras on the mentor's 12 draft queries, and the tiering work, both attack the same
problem from the output side. Two lines from the literature attack it from the decision side.

**Khot et al. (2023), *Decomposed Prompting*** (ICLR 2023, arXiv:2210.02406). Delegate sub-tasks to
separately-optimised prompts, each replaceable by a better prompt, a trained model, or a symbolic function.
The shape this suggests here is a per-option decision rather than one generation that must produce the whole
set. **The cost is the reason not to do it naively:** 65 options × per-query calls against an 18 s
decode-bound path. A restricted version — decompose only the options where the tier signal is weakest —
keeps the idea affordable.

**Angelopoulos et al. (2024), *Conformal Risk Control*** (arXiv:2208.02814). Extends conformal prediction
to bound the expected value of any monotone loss, with a coverage guarantee tight to O(1/n); the abstract
names bounding the **false negative rate** among its worked examples.

**Why this fits.** Must-have recall is a false-negative-rate constraint stated as a percentage. Conformal
risk control is the machinery for turning "we measured 95.1%" into "we calibrated a threshold that bounds
the miss rate at 5%", with the reviewed rows as the calibration set. **Two limits, both real.** The set is
31 rows, so the O(1/n) slack is not small; and the guarantee assumes exchangeability between calibration and
deployment queries, which is exactly what the 8 real tracker questions suggest does not hold yet. Worth
writing down as the shape the metric should eventually take, not as something to implement this month.

**Zhang et al. (2025), *CFBench*** (ACL 2025) is the benchmark framing for the six hard rules in the system
prompt: 1,000 samples, 200+ scenarios, 10 primary constraint categories and 25+ subcategories, reporting
substantial room for improvement in constraint following. Abstract only, and it is a Chinese-language
benchmark, so it supports the general claim that stacked constraints degrade compliance and no number
transfers.

## 8. Why the checker is a checker and not a critic

**Huang et al. (2024), *Large Language Models Cannot Self-Correct Reasoning Yet*** (ICLR 2024,
arXiv:2310.01798). "LLMs struggle to self-correct their responses without external feedback, and at times,
their performance even degrades after self-correction."

This is the published defence of the deterministic Python checker over an LLM critic, and it belongs next to
the NeMo Guardrails citation in `LITERATURE.md` rather than replacing it. Abstract only; I did not read what
the paper reports for self-correction *with* oracle feedback, which is the arm that would matter if a critic
were ever proposed.

## 9. The 21% that is parametric

Exp 6 found ~79% of recommendations KB-grounded, 21% parametric. **Zhou et al. (2023), *Context-faithful
Prompting for Large Language Models*** (EMNLP 2023 Findings, arXiv:2303.11315) offers two levers:
opinion-based prompts, which reframe the context as a narrator's statement and ask for the narrator's
opinion, and counterfactual demonstrations. The abstract claims significant improvement in faithfulness and
gives no numbers; I did not read the results.

Directly testable here, because the harness exists: `run_attribution.py` already measures the grounded
fraction, so an opinion-framed variant of the option block is an arm rather than a rewrite. The prize is a
higher grounded fraction with the option set unchanged.

## 10. How the numbers should be reported

**Miller (2024), *Adding Error Bars to Evals*** (arXiv:2411.00640, 2024-11-01). Five recommendations from
the introduction: standard errors of the mean via the CLT; **clustered** standard errors when questions come
in related groups; variance reduction by resampling answers and by analysing next-token probabilities;
inference on **question-level paired differences** when comparing two models rather than on population-level
summaries; and power analysis to check whether an eval can test the hypothesis at all. The paper advises
**against** lowering sampling temperature to reduce variance unless the aim is to study the model at that
temperature.

**Three consequences for this repository.**

1. The 31 rows are generated from 72 factor tuples by a shared priority table, which is the "related groups"
   case. Per-row standard errors treat them as independent and will read too tight.
2. The two-tier A/B in `eval_factor_set.py --merged-tiers` is a two-model comparison, so score it as
   paired per-row differences.
3. Temperature 0 plus a fixed seed is the right call for reproducibility, given
   [[ollama-temp0-nondeterminism]]. It also means the reported ± is not the eval's sampling variance, and
   `STATUS.md` should say which quantity it is showing.

Power analysis answers a question already open in `STATUS.md`: whether 31 rows can detect the tier effect at
all. Running it before the A/B is cheaper than reading a null result afterwards.

---

## Ranked actions

| # | Action | Cost | Evidence |
|---|---|---|---|
| 1 | Format arm in `eval_factor_set.py`; report a format interval next to the seed interval | half a day | Sclar 2024; Mizrahi 2024; our own §6 finding |
| 2 | Re-run Exp 8 for the **classifier only**, using Ollama `format` schema-constrained decoding; score readings, not validity | hours | Tam 2024 (classification arm); Ray 2026 (the counterweight) |
| 3 | Shuffle option order across seeds in `compress_options` | one line | Liu 2024 |
| 4 | Cite Su & Cardie 2026 in `reprompting_proposal.md` §9 for why the ask policy is deterministic | minutes | Su & Cardie 2026 |
| 5 | Score or drop `confidence: high\|medium\|low` on the 31 rows | hours | Xiong 2024 |
| 6 | 3-seed re-run of the `--think` arm with accuracy attached | hours | Sprague 2025; Exp 14 |
| 7 | Clustered SEs and paired per-row differences for the tier A/B; power analysis first | half a day | Miller 2024 |
| 8 | Opinion-framed option block as an arm in `run_attribution.py` | half a day | Zhou 2023 |
| 9 | Write conformal risk control into the metric design as the eventual shape of must-have recall | design note | Angelopoulos 2024 |

## What is my own judgement here

- **That the factor classifier is "a classification task" in Tam et al.'s sense.** Their classification set is
  DDXPlus, MultiFin, Sports Understanding and NI-Task 280; ours emits a five-field object with an
  `unstated` escape. The analogy is mine.
- **That 65 options is safely below the tool-count regime where selection degrades.** The threshold numbers
  I saw come from secondary sources I did not verify.
- **The ranking above.** No paper says format sensitivity should be fixed before constrained decoding; that
  ordering is because the format interval changes how every later A/B is read.
