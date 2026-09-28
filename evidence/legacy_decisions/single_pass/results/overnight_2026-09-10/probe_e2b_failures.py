#!/usr/bin/env python3
"""Why did gemma4:e2b fail to classify the same 7 (all non-human) rows on every seed? Print the raw reply."""
import json, os, sys
from pathlib import Path
ROOT = Path("/Users/david/Desktop/GSoC_WORK")
sys.path.insert(0, str(ROOT / "vep_ai_demo"))
os.environ.setdefault("VEP_OPTIONS_FILE", str(ROOT / "work" / "vep_options_expanded.json"))
import vep_assistant as va
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
done = {x["id"] for x in json.load(open(ROOT / "work/results/overnight_2026-09-10/singlepass_eval_e2b.json"))["rows"][0]["detail"]}
rows = [r for r in json.load(open(ROOT / "work/generation/candidates/iced.json")) if r["id"] not in done]
for r in rows[:3]:
    print("=====", r["id"])
    print("QUERY:", r["user_query"][:300])
    # arm A = exactly what full_eval_singlepass.classify_raw sends (no think flag, no max_tokens)
    # arm B = think off via extra_body, as the CLI's native path does
    for label, kw in (("A classify_raw-style", {}),
                      ("B think=False", {"max_tokens": va._CLASSIFY_MAX_TOKENS,
                                         "extra_body": {"keep_alive": va.KEEP_ALIVE, "think": False}})):
        resp = client.chat.completions.create(
            model="gemma4:e2b", temperature=0.0, seed=42,
            messages=[{"role": "system", "content": va.FACTOR_CLASSIFIER_PROMPT + r["user_query"]},
                      {"role": "user", "content": "Return the JSON classification."}], **kw)
        raw = resp.choices[0].message.content
        print(f"  [{label}] finish={resp.choices[0].finish_reason} len={len(raw or '')}")
        print("  RAW:", repr((raw or "")[:600]))
        print("  parsed:", va.parse_factor_classification(raw or ""))
