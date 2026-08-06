I now have comprehensive, verified data. Here is the deliverable.

---

# Open-Source LLM Landscape for a Local Ollama RAG System (Genomics Config Recommendation) — June 2026

Scope: local Ollama-hosted, structured JSON output, strict citation/format instruction-following, 7B-class production RAG plus QLoRA fine-tuning on an M5 Max 128GB (Apple Silicon / MLX). Focus on Gemma 4 with comparisons.

## Bottom line up front
- **Gemma 4 EXISTS and is verified** (released April 2, 2026). It is genuinely strong for this use case: Apache 2.0 license, native function calling + structured JSON output + native system instructions, 128K context (edge) / 256K (medium), and it is on Ollama with MLX builds for Apple Silicon. The user's flag is correct.
- The relevant "7B-class" Gemma 4 variants are **E4B (~4.5B effective)** and **12B**. There is no exact 7B Gemma 4; the 12B dense is the best instruction-following fit that still fits comfortably for QLoRA on 128GB.
- Recommended for the proposal's structured model-comparison: **Gemma 4 12B**, **Qwen3.x ~9B/27B (Instruct, non-thinking)**, and **Mistral Small 3.2 (24B)** — with Qwen2.5-7B-Instruct kept as the demo baseline.

---

## Comparison table

| Model (variant) | Sizes / variants | Ollama? | License | Context | Structured output / instruction-following | Fit: 7B-class prod RAG + QLoRA on M5 Max 128GB |
|---|---|---|---|---|---|---|
| **Gemma 4** (Google) | E2B (~2.3B eff), E4B (~4.5B eff), **12B dense**, 26B-A4B MoE (~3.8–4B active), 31B dense | **Yes** — `gemma4` with `e2b/e4b/12b/26b/31b`, plus **MLX** tags (`-mlx`) and a cloud tag (verified) | **Apache 2.0** (verified, official Google blog) — major change from old Gemma Terms | 128K (E2B/E4B), **256K** (12B/26B/31B) | Native function calling, **native structured JSON output**, native system prompts; "significant improvements in instruction-following." Caveat: independent tests still flag exact-constraint following (e.g. strict word limits) as a weak spot. | **Strong.** 12B is the sweet spot: best IF in the small range, MLX QLoRA supported, fits 128GB easily. E4B is the true edge/7B-class option. |
| **Qwen3 / Qwen3.5 / Qwen3.6** (Alibaba) | Qwen3: 0.6/1.7/4/8/14/32B + 30B & 235B MoE. Qwen3.5 small: 0.8/2/4/**9B**. Qwen3.6: **27B dense**, 35B-A3B MoE | **Yes** — `qwen3`, `qwen3.5`, `qwen3.6` (verified library pages) | **Apache 2.0** | Up to 262K native (extendable ~1M on some) | Top-tier IF (Qwen3.5-27B leads IFEval ~0.95). Strong JSON. **Caveat:** `response_format` historically `json_object` not `json_schema`; **thinking mode can leak reasoning into JSON** — use Instruct/non-thinking variants for RAG. | **Strong.** Use ~9B (Qwen3.5) for 7B-class, or 27B dense for higher quality. QLoRA via MLX supported (Qwen2 arch). |
| **Qwen2.5-7B-Instruct** (demo baseline) | 0.5–72B; 7B is the demo model | **Yes** — `qwen2.5:7b-instruct` | Apache 2.0 | 128K | Explicitly designed for JSON / structured-data output and instruction following; resilient to system prompts. Solid, well-understood baseline. | **Good baseline.** Keep as control. QLoRA well-supported on MLX. |
| **Llama 4** (Meta) | Scout (17B active / 109B total, 16E MoE), Maverick (17B active / 400B total, 128E) | **Yes** — `llama4:scout`, `llama4:maverick` (verified) | **Llama 4 Community License** (custom, not OSI; acceptance required) | Scout up to **10M**, Maverick ~1M | Natively multimodal, MoE. Capable but **no sub-17B-active dense** option; Scout ~67GB, Maverick ~245GB. | **Poor fit for "7B-class."** Scout runs on 128GB at Q4 but is heavy for a small-RAG comparison; license is restrictive vs Apache. Not recommended for the 7B test suite. |
| **Mistral Small 3.x** (Mistral) | Small 3 / 3.1 / **3.2** (24B); Ministral-3; Magistral (reasoning); Medium 3.5 (128B, Modified MIT) | **Yes** — `mistral-small3.2`, `magistral`, etc. | **Apache 2.0** (Small line); Medium 3.5 is Modified MIT | 32K (Small 3) → **128K** (3.1/3.2) | Strong instruction-following; reliable JSON for straightforward-to-moderate schemas (community-confirmed on Ollama). 3.1/3.2 add multimodal. | **Good.** 24B fits 128GB for QLoRA; a strong non-Google/non-Qwen diversity pick. Slightly above 7B-class but a useful upper-bound comparator. |
| **Phi-4 / Phi-4-mini** (Microsoft) | Phi-4 (14B), **Phi-4-mini (3.8B)**, Phi-4-multimodal, Phi-4-mini-reasoning | **Yes** — `phi4`, `phi4-mini` | **MIT** | 128K | Function calling supported; structured output supported; very strong reasoning-per-parameter. Can be terse / over-aligned for long-form cited RAG answers. | **Decent small option.** Phi-4 (14B) is a reasonable 7B-class-ish comparator; mini (3.8B) for edge. MIT license is clean. |

**Cross-cutting (verified):** Ollama supports **schema-constrained structured outputs** via the `format` parameter using **XGrammar / grammar-constrained decoding** (since v0.5). This works with *any* model but quality varies — so the model's *native* JSON/tool-calling training still matters for semantic correctness (the grammar only guarantees *structural* validity). Always describe the schema in the system prompt AND pass `format`.

---

## QLoRA on M5 Max 128GB (verified)
- MLX (`mlx-lm`) natively supports LoRA/QLoRA for **Gemma, Qwen2, Llama, Mistral, Phi** architectures. Passing a 4-bit base + `--train` auto-runs QLoRA (base stays quantized, adapters full precision).
- 128GB unified memory removes the VRAM wall — sources cite QLoRA up to ~70B on a 128GB M3 Max. A 7B–27B QLoRA run is comfortable (Mistral-7B QLoRA ~90 min / ~7GB peak on a 32GB M2 Max as a reference point). M5 Max 128GB is over-provisioned for 7B–24B.
- Practical note: Apple-Silicon QLoRA is via **MLX**, not bitsandbytes; train with MLX then export/quantize to GGUF for Ollama serving. Verify the exact GGUF conversion path for Gemma 4's newer arch before committing (see Uncertain).

---

## RECOMMENDATION — 2–3 models for the structured model-comparison

Run the proposal's structured comparison on the expanded test suite with:

1. **Gemma 4 12B (Apache 2.0)** — primary candidate. Best instruction-following in the small-dense range, native JSON + function calling + system prompts, 256K context (great for long genomics docs), first-class MLX/Ollama support, clean license. Use the 12B dense, not E4B, for production-quality citation following; keep E4B as an edge fallback.
2. **Qwen3.5-9B-Instruct (or Qwen3.6-27B dense), Apache 2.0** — strongest measured IFEval-class instruction-following; excellent JSON. **Use the Instruct / non-thinking variant** to avoid reasoning-leak-into-JSON. The 9B is the head-to-head 7B-class peer; 27B is the quality-ceiling option if 128GB headroom allows.
3. **Mistral Small 3.2 (24B), Apache 2.0** — diversity/robustness check from a different model family; reliable JSON, 128K context, strong IF. Acts as an upper-bound comparator above the 7B class.

**Baseline/control:** keep **Qwen2.5-7B-Instruct** (the demo model) in the suite so results are comparable to existing work.

Skip for the 7B-class suite: **Llama 4** (no small dense variant, restrictive custom license, heavy footprint) — note it only if you later want a long-context (10M) experiment.

Evaluation tip: in the test harness, enforce structure with Ollama's `format`/JSON-schema parameter for ALL models so you isolate *semantic* IF and citation accuracy from raw JSON-validity, then separately score strict format constraints (the area where Gemma 4 and others are weakest).

---

## Verified vs Uncertain

**Verified (official or multiple independent sources):**
- Gemma 4 exists, released ~April 2, 2026; variants E2B/E4B/12B/26B-A4B/31B; **Apache 2.0** (official Google blog); 128K/256K context; native function calling + structured JSON + system instructions; on Ollama incl. MLX tags.
- Qwen3 family Apache 2.0, sizes, ~262K context, on Ollama; Qwen3.5 small models (0.8/2/4/9B) and Qwen3.6 (27B dense, 35B-A3B) on Ollama.
- Qwen2.5-7B-Instruct: Apache 2.0, 128K, JSON-oriented; on Ollama.
- Llama 4 Scout/Maverick sizes, custom Community License, on Ollama.
- Mistral Small 3/3.1/3.2 Apache 2.0, contexts (32K→128K), on Ollama; Medium 3.5 Modified MIT.
- Phi-4 (14B) / Phi-4-mini (3.8B) MIT, 128K, function calling + structured output, on Ollama.
- Ollama uses XGrammar grammar-constrained decoding for JSON-schema `format`; MLX supports QLoRA for these architectures; 128GB easily handles 7B–27B QLoRA.

**Uncertain / verify before relying:**
- **Exact Ollama tag for Gemma 4 12B GGUF + the MLX→GGUF conversion path for the new Gemma 4 arch** — Ollama listing was read via fetch, not a live `ollama pull`; confirm by pulling. Newer architectures sometimes lag in llama.cpp/GGUF support.
- **Precise "effective parameter" semantics** for Gemma 4 E2B/E4B and the 26B-A4B active-param count (sources vary: "3.8B" vs "4B" active; E4B "~4.5B effective").
- **Current single "latest" Qwen** — Qwen3, 3.5, and 3.6 all coexist on Ollama; pick the specific Instruct variant deliberately. Some Qwen3.5 MoE JSON-schema + thinking-mode leak issues are reported (HF discussion); use Instruct/non-thinking for RAG.
- Independent structured-output reliability rankings between Gemma 4 vs Qwen3.x are mostly from blogs/benchmarks of varying rigor — treat the head-to-head IF/JSON claims as indicative; **your expanded test suite should be the tiebreaker.**

## Sources
- [Gemma 4 — official Google blog (license, sizes, JSON/function calling)](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [Gemma 4 core docs — Google AI for Developers](https://ai.google.dev/gemma/docs/core)
- [Gemma 4 on Ollama (variants, MLX, context)](https://ollama.com/library/gemma4)
- [Gemma 4 Apache 2.0 license analysis — MindStudio](https://www.mindstudio.ai/blog/gemma-4-apache-2-license-commercial-use)
- [Gemma 4 vs Qwen 3.6 agentic / structured output — MindStudio](https://www.mindstudio.ai/blog/gemma-4-vs-qwen-3-6-plus-agentic-workflows)
- [Gemma 4 production structured outputs (independent IF caveats) — DEV](https://dev.to/system_rationale/part-3-making-gemma-4-agents-production-ready-guardrails-structured-outputs-and-self-healing-575n)
- [Qwen3 on Ollama](https://ollama.com/library/qwen3) · [Qwen3.5](https://ollama.com/library/qwen3.5) · [Qwen3.6](https://ollama.com/library/qwen3.6)
- [Qwen2.5-7B-Instruct on Ollama](https://ollama.com/library/qwen2.5:7b-instruct) · [Qwen2.5-7B-Instruct on HF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
- [IFEval leaderboard (Qwen3.5-27B ~0.95)](https://llm-stats.com/benchmarks/ifeval)
- [Qwen3.5 JSON-schema/thinking-mode reasoning leak (HF discussion)](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/18)
- [Llama 4 on Ollama](https://ollama.com/library/llama4) · [Llama 4 — Meta blog](https://ai.meta.com/blog/llama-4-multimodal-intelligence/)
- [Mistral Small 3.2 on Ollama](https://ollama.com/library/mistral-small3.2) · [Mistral Medium 3.5 on Ollama](https://ollama.com/library/mistral-medium-3.5) · [Magistral on Ollama](https://ollama.com/library/magistral)
- [Phi-4 on Ollama](https://ollama.com/library/phi4) · [Phi-4-mini on Ollama](https://ollama.com/library/phi4-mini) · [Microsoft Phi-4 models blog](https://techcommunity.microsoft.com/blog/educatordeveloperblog/welcome-to-the-new-phi-4-models---microsoft-phi-4-mini--phi-4-multimodal/4386037)
- [Ollama structured outputs (XGrammar, JSON schema)](https://ollama.com/blog/structured-outputs)
- [MLX LoRA/QLoRA fine-tuning on Mac](https://insiderllm.com/guides/fine-tuning-mac-lora-mlx/) · [Fine-tuning Gemma 4 on Apple Silicon + MLX](https://antigravitylab.net/en/articles/antigravity/gemma-4-finetuning-apple-silicon-mlx-guide)