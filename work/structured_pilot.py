#!/usr/bin/env python3
"""Structured-output PILOT (json_object route) — robust replacement for the fragile free-text parsers.

Approach: the model emits ONE JSON object in Ollama's json_object mode (a JSON *grammar* — always valid
JSON — but NOT a strict schema grammar, which went degenerate on this stack). We put the target shape in
the prompt, then VALIDATE + REPAIR post-hoc in Python:
  - detected_use_case must be one of the 7 (else flag);
  - each recommendation's option_id is resolved against the 58 catalogue ids, with the existing alias
    resolver as a safety net (exact -> mapped -> unmapped);
  - factual fields (cli_flag, web_form_*) are NOT asked of the model (provenance rule) — filled from KB later.
This pilot reports whether the model reliably emits valid JSON + valid ids, i.e. whether the route is sound.

Determinism: temp=0 + fixed seed, sequential (EXPERIMENTS.md Exp 6). Additive — no existing file touched.
"""
import json, os, sys
from pathlib import Path
DEMO = Path(__file__).resolve().parents[1] / "vep_ai_demo"
sys.path.insert(0, str(DEMO))
import vep_assistant as va
import evaluate as ev
from openai import OpenAI

USE_CASES = ["rare_disease_germline", "somatic_cancer", "regulatory_noncoding",
             "population_genetics", "structural_variants", "non_human", "quick_lookup"]

def schema_hint(option_ids):
    """Shape shown to the model (json_object mode doesn't enforce it; we validate after).

    DESIGN NOTE: making `species` an explicit model-filled field is the proper fix for infer_species's
    regex fail-open — but the downstream assembler must then FAIL CLOSED: if species is missing/unknown,
    withhold (do not auto-enable) human-only options and flag for the user, rather than defaulting to human.
    """
    return {
        "detected_use_case": "one of " + "|".join(USE_CASES),
        "species": "e.g. human / mouse",
        "assembly": "e.g. GRCh38 or null",
        "recommendations": [{
            "option_id": "EXACTLY one catalogue id (see list)",
            "action": "enable|disable|set_value",
            "value": "for set_value only, else null",
            "confidence": "high|medium|low",
            "reason": "<= 12 words, grounded in the KB"}]}

def instruction(option_ids):
    return ("\n\n## Output Format (STRICT)\n"
            "Respond with ONLY one valid JSON object (no prose, no code fences) of this shape:\n"
            f"{json.dumps(schema_hint(option_ids))}\n"
            "option_id MUST be copied exactly from this catalogue id list:\n"
            f"{', '.join(sorted(option_ids))}\n"
            "action=enable turns an option ON, disable OFF, set_value for dropdowns. Keep each reason brief.\n")

def call_json(client, model, sp, query, seed=42, repair_note=None):
    msgs = [{"role": "system", "content": sp}, {"role": "user", "content": query}]
    if repair_note:
        msgs.append({"role": "user", "content": repair_note})
    r = client.chat.completions.create(model=model, messages=msgs, temperature=0.0, seed=seed,
                                       response_format={"type": "json_object"}, max_tokens=16384)
    return r.choices[0].message.content, r.choices[0].finish_reason

def resolve(raw, ids, aliases):
    if raw in ids: return raw, "exact"
    m = aliases.get(str(raw).lower())
    if m in ids: return m, "mapped"
    return None, "unmapped"

def main():
    client = OpenAI(base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
    cat, examples = va.load_knowledge_base()
    ids = {o["id"] for o in cat}
    aliases = va.build_option_aliases(cat)
    agg = {"valid_json": 0, "uc_ok": 0, "exact": 0, "mapped": 0, "unmapped": 0, "n": 0}
    mapped_ex, unmapped_ex = [], []
    for t in ev.TEST_QUERIES[:int(os.environ.get("PILOT_N", "5"))]:   # PILOT_N=20 for a fuller verification
        agg["n"] += 1
        corpus = [e for e in examples if e["id"] != t.get("ground_truth_id")]
        sp = va.build_system_prompt(cat, corpus, t["query"], retrieval_mode="all")
        sp = sp.split("## Output Format")[0].rstrip() + instruction(ids)
        txt, fin = call_json(client, "gemma4:26b", sp, t["query"])
        try:
            obj = json.loads(txt)
        except Exception:                       # json_object should be valid; repair-retry once if not
            txt, fin = call_json(client, "gemma4:26b", sp, t["query"],
                                 repair_note="Your last output was not valid JSON. Return ONLY one valid JSON object.")
            try: obj = json.loads(txt)
            except Exception as e:
                print(f"[{t['id']}] INVALID JSON after repair (finish={fin}): {e}"); continue
        agg["valid_json"] += 1
        uc = obj.get("detected_use_case"); uc_ok = uc in USE_CASES; agg["uc_ok"] += uc_ok
        recs = obj.get("recommendations", [])
        ex = mp = un = 0
        for r in recs:
            if not isinstance(r, dict):          # model sometimes emits a bare string, not {option_id:...}
                un += 1
                if len(unmapped_ex) < 6: unmapped_ex.append(f"<non-dict:{r!r}>")
                continue
            rid, how = resolve(r.get("option_id"), ids, aliases)
            if how == "exact": ex += 1
            elif how == "mapped": mp += 1; (len(mapped_ex) < 6 and mapped_ex.append((r.get("option_id"), rid)))
            else: un += 1; (len(unmapped_ex) < 6 and unmapped_ex.append(r.get("option_id")))
        agg["exact"] += ex; agg["mapped"] += mp; agg["unmapped"] += un
        print(f"[{t['id']}] json=OK finish={fin} use_case={uc}({'ok' if uc_ok else 'BAD'}) "
              f"recs={len(recs)} ids: exact={ex} mapped={mp} unmapped={un}")
    n = agg["n"]; tot = max(agg["exact"] + agg["mapped"] + agg["unmapped"], 1)  # guard /0 on empty
    print(f"\n=== json_object pilot over {n} queries ===")
    print(f"valid JSON: {agg['valid_json']}/{n}   valid use_case: {agg['uc_ok']}/{n}")
    print(f"option_ids: {tot} total -> exact={agg['exact']} ({agg['exact']/tot:.0%}) "
          f"mapped={agg['mapped']} unmapped={agg['unmapped']}")
    if mapped_ex: print("  mapped (model->canonical):", mapped_ex)
    if unmapped_ex: print("  UNMAPPED (need attention):", unmapped_ex)

if __name__ == "__main__":
    main()
