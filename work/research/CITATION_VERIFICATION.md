# Citation & design-choice verification — full-text pass

**What this is.** A verification of every literature citation behind Ask VEPai's design choices and
experiments, done by **reading the full papers** (not abstracts, not memory). 27 papers across 8 parallel
readers, 2026-07-12. Each paper was checked against the *specific* claim it is cited for, with verbatim
quotes + section/figure locations; verdicts are SUPPORTS / PARTIAL / CONTRADICTS / MISATTRIBUTED.

**Headline.** No fabricated citations, no invented numbers, no non-existent papers. The large majority of
citations are **SUPPORTS**. But full-text reading surfaced **one real misattribution, two overreaches, and a
set of omitted caveats** that the docs should carry. It also **resolves the read-status gap**: the three
generation-pipeline "spine" papers previously flagged *cited-but-not-read* (SynthIE, Quality-Matters,
Self-Instruct) are now read + quote-verified and **SUPPORT** their claims.

> **Rigor note.** "Verified" here = read from full text by a verification agent on 2026-07-12 and matched to
> a verbatim quote. It does **not** upgrade the underlying science: papers that demonstrate on small models
> or narrow tasks are still cited as *precedent/analogy*, flagged below.

---

## 1. Corrections to apply (ranked)

| # | Severity | Where | Fix |
|---|---|---|---|
| 1 | **MISATTRIBUTION** | `EXPERIMENTS.md` Exp 2 (L52,54,68); `PROGRESS.md` L257,393 | The "**~50–70 examples per class**" saturation figure is **not in Agarwal 2024**. The paper's saturation is task-dependent (10→125 *total* shots; XSum declines past ~50 *total*), and its only *per-class* experiment saturates at **512–2048/class**. Relabel 50–70/class as **our own estimate**, and cite Agarwal only for "saturation exists and is task-dependent." The Exp 2 *conclusion* (we're far below any crossover; all-examples dominates our regime) **still holds — in fact more strongly**, since real per-class saturation is an order of magnitude higher. |
| 2 | **OVERREACH** | `systems_reading/README.md` (DPR); anywhere "DPR explains why top-10 hurts" | Agarwal/DPR do not establish that top-10 *hurts*. DPR's own k=10 is **near-optimal** (40.8 vs 41.5 EM). Soften to "**consistent with DPR's finding that recall rises with k**," and note the objects differ (VEP options vs passages). The top-10 harm is **our own Exp 1/10 result**, not DPR's. |
| 3 | **FACTUAL** | `systems_reading/README.md` L20 (DPR "cosine") | DPR uses **dot-product / inner-product (MIPS)** and explicitly found **cosine *worse*** (§5.2). Cosine belongs to our BGE setup, not DPR. Reword "dual encoder + cosine" → "**dual encoder + MIPS (dot-product)**." |
| 4 | **FRAMING** | `systems_reading/README.md` L43–44,62; generation proposal §1a | NeMo Guardrails: the verbatim quote is correct, but NeMo's *own* rails are **mostly LLM-mediated, not deterministic**, and §7.1 **warns against stand-alone/deterministic use**. Cite NeMo for "**programmable rails wrapping an LLM**," **not** as evidence guardrails are deterministic. (Our Python checker is *stronger* on determinism than NeMo's.) |
| 5 | **BIBLIOGRAPHIC** | generation proposal refs | Xu et al. title is "**Stronger Models Are NOT Stronger Teachers**," not "…Not *Always*…". WizardLM has two legitimate title variants ("…Pre-Trained…" is current arXiv metadata only). |
| 6 | **CAVEAT** | generation proposal §1a; EXPERIMENTS.md Exp 13 | DataMorgana's "persona marginal" is an **empirical property of the authors' chosen category sets**, not a universal law (and human NDG 2.484 = their drop-persona number). Keep it as support for "persona for audience-realism only," not as proof persona can never matter. |
| 7 | **CAVEAT** | EXPERIMENTS.md Exp 5/6 (attribution) | Add **ContextCite (Cohen-Wang 2024)** — the principled Lasso-surrogate-over-random-ablations method our Exp 6 hand-rolls (LOO = its k=1 case). Caveat: it needs response **logprobs** (Ollama exposes them). Add **ALCE (Gao 2023)** — the NLI citation precision/recall design that grounds the citation-rate deprecation. |
| 8 | **CAVEAT** | wherever CoT `Reason:` lines are described | Wei §3.3: reasoning placed *after* the answer gives **no** accuracy gain. If our `Reason:` lines follow the recommendation they are **post-hoc justification, not the CoT mechanism** — reinforcing (not resolving) the faithfulness question. |

---

## 2. Verdicts by cluster (all 27 papers)

Legend: ✅ SUPPORTS · 🟡 PARTIAL · 🔴 CONTRADICTS/MISATTRIBUTED. arXiv IDs verified to resolve.

### Generation pipeline (the spine + supporting)
| Paper | Cited for | Verdict | Key caveat to carry |
|---|---|---|---|
| SynthIE — Josifoski EMNLP 2023 (2303.04132) | reverse/asymmetric generation; §3.2 inverse-freq coverage | ✅ | inverse-freq is over KG entities by *running* frequency, not generic corpus-freq; shown only for closed IE |
| Quality-Matters/ICE — Iskander EMNLP 2024 (2409.16341) | 47.9%/>33% param errors; six criteria; ICE def; 10K=0.54 vs 73K=0.45 | ✅ | restore "…as a one-shot example" in the ICE quote; 0.54 used *combined* filters on a pass-rate metric |
| Self-Instruct — Wang ACL 2023 (2212.10560) | dedup ROUGE-L < 0.7 | ✅ | rule is over *instructions* vs whole pool; one component of a larger filter |
| DataMorgana — Filice ACL 2025 Ind. (2501.12789) | explicit category grid; persona marginal (NDG 2.536→2.484 vs →1.777) | ✅ | "persona marginal" is empirical to their category sets, not a law (see fix #6) |
| Xu — NAACL 2025 (2411.07133) | Larger Models' Paradox; 9b>27b teacher; OSS>GPT-4; compatibility (CAR) | ✅ | title misquoted (fix #5); real thesis = *compatibility* governs, which supports empirical teacher choice |
| Alberti — ACL 2019 (1906.05416) | roundtrip: emit (C,Q,A) iff A′ matches | ✅ | their "recovered" = extractive span-match, same-family QG/QA; open-ended ICE needs its own match def |
| ARES — Saad-Falcon NAACL 2024 (2311.09476) | 150+ human set; PPI confidence intervals | ✅ | "calibrate" = PPI statistical correction at eval time, not classifier retraining |
| WizardLM — Xu ICLR 2024 (2304.12244) | Evol-Instruct "rewrite step by step" (a thing we *don't* do) | ✅ | title variant (fix #5) |
| Sechidis — ECML PKDD 2011 | iterative multi-label stratification > random | ✅ | 3-way comparison; iterative isn't *universally* best (labelsets wins some); scikit-multilearn link is external |

### Architecture (RAG / retrieval / guardrails / ICL / citations / eval / clinical)
| Paper | Cited for | Verdict | Key caveat / fix |
|---|---|---|---|
| Lewis RAG — NeurIPS 2020 (2005.11401) | editable external knowledge, update-without-retrain | ✅ | clean; hot-swap demonstrated §4.5/§6 |
| DPR — Karpukhin EMNLP 2020 (2004.04906) | dense dual-encoder; "top-10 hurts" | 🟡 | **cosine→dot-product (fix #3); top-10 overreach (fix #2)** |
| Self-RAG — Asai 2023 (2310.11511) | retrieve-critique-cite reflection tokens | ✅ | its critique is same-LM/probabilistic — "conceptual cousin" is right |
| NeMo Guardrails — Rebedea EMNLP 2023 (2310.10501) | programmable rails wrapping an LLM | ✅ quote / 🟡 "deterministic" | **reframe (fix #4)**; §7.1 disclaims stand-alone use |
| GPT-3 — Brown NeurIPS 2020 (2005.14165) | ICL foundation, no weight updates | ✅ | clean; ICL coined here |
| Many-Shot ICL — Agarwal NeurIPS 2024 (2404.11018) | (a) more helps > selection; (b) ~50–70/class; (c) §4.7 order | 🟡 (a) / 🔴 (b) / ✅ (c) | **(a) no selection baseline tested; (b) MISATTRIBUTION fix #1; (c) order → Exp 9 solid** |
| CoT — Wei NeurIPS 2022 (2201.11903) | elicits reasoning; faithfulness open | ✅ | post-hoc `Reason:` caveat (fix #8) |
| ALCE — Gao EMNLP 2023 (2305.14627) | citation recall/precision via NLI | ✅ | grounds citation-rate deprecation — add to Exp 5/6 (fix #7) |
| RAGAS — Es 2023 (2309.15217) | reference-free faithfulness/answer/context relevance | ✅ | support metrics ≠ correctness; small 50-item validation |
| Med-PaLM — Singhal 2023 (2212.13138) | rigor bar: multi-axis clinician eval | ✅ | **not RAG** — fine as rigor bar; misattribution if ever cited as a RAG/citation system |
| Almanac — Zakka 2023 (2303.01229) | RAG clinical analogue, clinician-evaluated | ✅ | completeness gain non-significant; physicians preferred ChatGPT 57% — don't cite as "grounding wins" |

### Attribution & interpretability (Exp 5/6 + future work)
| Paper | Cited for | Verdict | Key caveat |
|---|---|---|---|
| ContextCite — Cohen-Wang 2024 (2409.00729) | black-box context attribution; generalizes Exp-6 LOO | ✅ | needs response **logprobs** (not text-only); contributive ≠ corroborative — matches faithful-vs-parametric |
| ROME — Meng NeurIPS 2022 (2202.05262) | white-box causal analogue (corrupt→restore→edit) | ✅ | native term "**Causal Tracing**"; "activation patching" is a later synonym; white-box (not Ollama) |
| Integrated Gradients — Sundararajan ICML 2017 (1703.01365) | Sensitivity + Implementation Invariance; needs white-box | ✅ | paper adds Completeness/Linearity/Symmetry for its uniqueness proof — not the *only* axioms |
| IOI — Wang 2022 (2211.00593) | canonical reverse-engineered circuit | ✅ | GPT-2 small; authors note it's not fully complete |
| SAEs — Cunningham 2023 (2309.08600) | sparse over-complete autoencoder → monosemantic features | ✅ | small models (Pythia ≤410M); imperfect reconstruction |
| Gemma Scope — Lieberum 2024 (2408.05147) | pretrained SAE suite (future white-box) | ✅ asset / caveat | **Gemma 2 only (2B/9B/27B)** — a retraining target for a Gemma-4 deployment, not plug-in |
| Transcoders — Dunefsky NeurIPS 2024 (2406.11944) | features → input-invariant feature circuits | ✅ | ≤1.4B models; circuit is an approximation |

---

## 3. Read-status resolution

Before this pass the two design proposals labelled several citations **⚠ cited-but-not-read** (per the
project notes). After full-text reading on 2026-07-12, the following are **read + quote-verified** and
SUPPORT their claims (upgrade ⚠→✅ in the provenance tables): **SynthIE, Quality-Matters/ICE, Self-Instruct**
(the generation "spine"), plus **Alberti, ARES, WizardLM, Sechidis** (previously read-status-unconfirmed).
**DataMorgana, Xu, NeMo Guardrails** were already read and remain verified. Net: the generation pipeline's
literature spine is now **verified**, with the caveats in §1–2 folded in — not blindly upgraded.

**Bottom line.** The design is well-grounded and the citations are real and (now) read. The exercise's value
was the exceptions: **one misattribution (Agarwal 50–70/class), two overreaches (DPR cosine + top-10, NeMo
determinism), and ~10 omitted caveats** — all actionable, none fatal, and several (Agarwal saturation, CAR
compatibility) actually *strengthen* the underlying design decision once stated correctly.
