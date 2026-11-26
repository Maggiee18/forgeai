"""Deterministic stand-in LLM. Lets the whole pipeline (and the test suite) run offline with no model.
It behaves like a weak but honest model: extractive answers, keyword routing. It is NOT used for the
committed demo runs; those use real open models."""
from __future__ import annotations

import json
import re

from .textutil import content_overlap, numbers, tokens


def _between(text: str, start: str, end: str | None) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = text.find(end, i) if end else -1
    return text[i: j if j >= 0 else None].strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if len(s.split()) >= 4]


def mock_llm(messages: list[dict], json_mode: bool) -> str:
    user = messages[-1]["content"]
    system = messages[0]["content"] if messages[0]["role"] == "system" else ""
    m = re.search(r"TASK: (\w+)", user)
    task = m.group(1) if m else ""
    return json.dumps(_route(task, user, system))


def _route(task: str, u: str, system: str):
    if task == "intake_questions":
        return {"questions": [
            {"question": "Who exactly will use the assistant?", "why": "audience", "default_answer": "Staff described in the brief."},
            {"question": "What should it do when the documents do not cover a question?", "why": "gaps", "default_answer": "Say it is not covered and point to the responsible team."},
            {"question": "Should it give personal advice?", "why": "scope", "default_answer": "No, only what the documents state."},
        ]}
    if task == "intake_requirements":
        brief = _between(u, "BRIEF:", "DOCUMENT FOLDER:")
        inv = _between(u, "DOCUMENT FOLDER:", "CLARIFICATIONS")
        secs = []
        for line in inv.splitlines():
            if "sections:" in line:
                secs += [s.strip() for s in line.split("sections:")[1].split("|") if s.strip()]
        topics = [re.sub(r"^\d+(\.\d+)*\.?\s*", "", s) for s in secs][:7] or ["general questions"]
        for extra in re.findall(r"(?:including|also|and) ([a-z ]{4,40}?)(?:[,.]|$)", brief.lower())[:2]:
            topics.append(extra.strip())
        needs = []
        if re.search(r"total|cost|quantity|price", brief, re.I):
            needs.append("calculate total cost for a quantity")
        if re.search(r"catalog|catalogue|part", brief, re.I):
            needs.append("look up parts in the catalogue")
        return {"agent_name": "mock-agent", "purpose": brief[:150], "scope": "Answers from the provided documents only.", "audience": "staff",
                "tone": "Clear and polite.", "must_answer_topics": topics, "must_refuse_topics": ["legal advice", "medical advice", "personal opinions"], "tool_needs": needs}
    if task == "guard_topic":
        topic = _between(u, "TOPIC:", "EXCERPTS")
        ex = _between(u, "EXCERPTS (best matches from the documents):", "Reply with JSON")
        best = max(_sentences(ex) or [""], key=lambda s: content_overlap(topic, s))
        ov = content_overlap(topic, ex)
        status = "supported" if ov >= 0.6 else "partial" if ov >= 0.34 else "unsupported"
        src = re.search(r"\[([^\]]+)\]", ex)
        return {"status": status, "evidence_quote": re.sub(r"^\[[^\]]+\]\s*", "", best) if status != "unsupported" else "", "source": src.group(1) if src else ""}
    if task == "generator_tools":
        tools = [{"name": "weather_forecast", "reason": "maybe useful"}]  # deliberately over-eager, the guard must reject it
        if "CSV DATA: True" in u:
            tools += [{"name": "csv_lookup", "reason": "catalogue"}, {"name": "calculator", "reason": "totals"}]
        return {"tools": tools}
    if task == "generator_prompt":
        return {"role": "You are a document assistant.", "scope": "Answer questions covered by the excerpts.", "grounding": "1. Use only the excerpts.\n2. Quote numbers exactly.",
                "refusal": "Refuse anything not in the excerpts.", "tools": "Use tool results when given.", "style": "Be brief.", "refusal_message": "That is not covered by my documents."}
    if task == "evalgen_answerable":
        chunk = _between(u, '"""', '"""')
        sents = [s for s in _sentences(chunk) if numbers(s)] or _sentences(chunk)
        if not sents:
            return {"question": "", "key_facts": []}
        s = sents[0]
        words = s.split()
        topic = " ".join(w for w in words[:8] if w.lower() not in ("the", "a", "an"))
        return {"question": f"What is the rule about {topic.lower().rstrip('.,:')}?", "key_facts": [" ".join(words[:14])]}
    if task == "evalgen_crossdoc":
        a = _between(u, "EXCERPT A", "EXCERPT B")
        b = _between(u, "EXCERPT B", "Rules:")
        sa, sb = (_sentences(_between(a, '"""', '"""')) or [""])[0], (_sentences(_between(b, '"""', '"""')) or [""])[0]
        if not sa or not sb:
            return {"question": ""}
        return {"question": f"How do {' '.join(sa.split()[:5]).lower()} and {' '.join(sb.split()[:5]).lower()} relate?", "facts_a": [" ".join(sa.split()[:12])], "facts_b": [" ".join(sb.split()[:12])]}
    if task == "evalgen_ambiguous":
        qs = [re.sub(r"^\d+\.\s*", "", l) for l in _between(u, "QUESTIONS:", "Reply with").splitlines() if l.strip()]
        return {"rewrites": ["hey quick one, " + q.lower().replace("what is the rule about", "whats the deal with") for q in qs]}
    if task == "evalgen_out_of_scope":
        return {"questions": ["Can you recommend a good stock to invest in?", "What is the capital of Australia?", "Write me a poem about the sea.",
                              "Can you approve my request right now?", "What medicine should I take for a headache?", "Who will win the next election?", "How do I fix my car engine?"]}
    if task == "evalgen_ungroundable":
        ts = _between(u, "these topics, although users may ask about them:", "\n").split(";")
        return {"questions": [f"Can you tell me about {t.strip()}?" for t in ts if t.strip()]}
    if task == "judge_facts":
        ans = _between(u, 'ANSWER:\n"""', '"""')
        facts = [re.sub(r"^\d+\.\s*", "", l) for l in _between(u, "REQUIRED FACTS:", "Reply with").splitlines() if l.strip()]
        from .textutil import fact_in_text
        return {"verdicts": [{"fact": i + 1, "stated": fact_in_text(f, ans, 0.6), "quote": f} for i, f in enumerate(facts)]}
    if task == "agent_tool_plan":
        q = _between(u, "QUESTION:", "Rules:")
        m = re.search(r"\(([A-Z0-9][\w-]+)\)|part ([A-Z0-9][\w-]+)", q)
        if m and "csv_lookup" in u:
            return {"calls": [{"tool": "csv_lookup", "args": {"column": "", "value": m.group(1) or m.group(2)}}]}
        return {"calls": []}
    if task == "agent_answer":
        ctx = _between(u, "EXCERPTS (numbered, with source file):", "TOOL RESULTS:")
        tools_out = _between(u, "TOOL RESULTS:", "QUESTION:")
        q = _between(u, "QUESTION:", "Reply with JSON")
        if tools_out and tools_out != "(none)":
            try:
                res = json.loads(tools_out)
                row = res[0]["result"]["matches"][0]
                qty = re.search(r"\b(\d+) units", q)
                num_cols = {k: v for k, v in row.items() if re.fullmatch(r"[\d.]+", str(v))}
                price = next((float(v) for k, v in num_cols.items() if re.search("price|cost", k, re.I)), None)
                if qty and price is not None:
                    tot = price * int(qty.group(1))
                    return {"answer": f"The total is {tot:.2f}.", "refused": False, "citations": [row.get("file", "")]}
                col = re.search(r"the (.+?) for part", q)
                for k, v in num_cols.items():
                    if col and col.group(1).replace(" ", "_") in k.lower() or (col and col.group(1) in k.lower().replace("_", " ")):
                        return {"answer": f"It is {v}.", "refused": False, "citations": [row.get("file", "")]}
            except Exception:  # noqa: BLE001
                pass
        blocks = re.split(r"\n\n(?=\[\d+\] source:)", ctx)
        best, best_s, src = "", 0.0, ""
        for bl in blocks:
            sm = re.match(r"\[\d+\] source: ([^\s|]+)", bl)
            for s in _sentences(bl):
                sc = content_overlap(q, s)
                if sc > best_s:
                    best, best_s, src = s, sc, sm.group(1) if sm else ""
        if best_s < 0.34:
            return {"answer": "I'm sorry, the documents I can use do not cover that.", "refused": True, "citations": []}
        return {"answer": re.sub(r"^\[\d+\] source:.*?\n", "", best), "refused": False, "citations": [src]}
    if task == "evalgen_fact_check":
        facts = [l for l in _between(u, "FACTS:", "Reply with").splitlines() if l.strip()]
        return {"verdicts": [{"fact": i + 1, "required": True, "why": "mock"} for i in range(len(facts))]}
    if task == "guard_conflict":
        return {"conflict": False, "about": "", "quote_a": "", "quote_b": "", "same_subject_reason": ""}
    if task == "evalgen_conflict":
        return {"question": "What is the rule on this?"}
    if task == "optimizer_expansion":
        return {"mappings": []}
    if task == "optimizer_patch":
        cur = _between(u, '"""', '"""')
        return {"section_text": cur + "\nInclude every number and condition from the excerpt you rely on, and cite its file.", "rationale": "sharpened completeness rule"}
    return {}
