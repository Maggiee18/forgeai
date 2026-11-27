"""Stage 1: intake interviewer. Reads the brief, inspects the folder, asks at most 5 clarifying
questions, and writes the structured requirements document.

Three answer modes, so the same code works live and unattended:
  interactive  -> questions on the terminal (empty reply = accept the default)
  answers file -> YAML/JSON list or {index: answer} map recorded ahead of time
  unattended   -> the interviewer's own conservative default, recorded as an ASSUMPTION
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

from . import prompts
from .docs import Document, inventory_text
from .llm import LLMClient
from .schemas import Clarification, Requirements

MAX_QUESTIONS = 5
# questions about the assistant's own behaviour or the requester's wishes are never "answered by the documents"
PREFERENCE_Q = re.compile(r"\b(assistant|agent|bot|chatbot|you want|would you like|prefer|should (it|the)|tone|format|style|audience|who (will|should) use|users?\b|escalat|contact|respond when|handle)", re.I)


def _load_answers(path: str | None):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "answers" in data:
        data = data["answers"]
    return data


def _answer_for(answers, i: int, question: str):
    if answers is None:
        return None
    if isinstance(answers, list):
        return answers[i] if i < len(answers) else None
    if isinstance(answers, dict):
        if i + 1 in answers:
            return answers[i + 1]
        if str(i + 1) in answers:
            return answers[str(i + 1)]
        # allow matching by keyword in the question
        for k, v in answers.items():
            if isinstance(k, str) and not k.isdigit() and k.lower() in question.lower():
                return v
    return None


def ask_questions(brief: str, docs: list[Document], llm: LLMClient) -> list[dict]:
    def validate(d):
        qs = d.get("questions") if isinstance(d, dict) else None
        if not isinstance(qs, list) or not qs:
            raise ValueError("need a non empty 'questions' list")
        out = []
        for q in qs:
            if isinstance(q, str):
                q = {"question": q}
            if q.get("question"):
                out.append({"question": str(q["question"]).strip(), "why": str(q.get("why", "")), "default_answer": str(q.get("default_answer", ""))})
        return out[:MAX_QUESTIONS]  # hard cap, whatever the model says

    return llm.json(prompts.messages("intake_questions", brief=brief, inventory=inventory_text(docs)), validator=validate)


# Unattended, nobody can confirm that a ticketing API, HR system or live feed exists, so an assumed answer must
# never grant one: a small model's "safest default" once invented "use the existing ticketing system API".
INTEGRATION = re.compile(r"\b(api|apis|integrat\w*|connect\w*|live|real[- ]time|system access|database|portal data|"
                         r"ticketing system|hrms data|crm|erp|feed|webhook|sync\w*|fetch\w*)\b", re.I)
NO_INTEGRATION = ("No live system or integration is available. The assistant answers only from the supplied documents, says "
                  "plainly when something needs live data or personal records, and points to the right team or channel.")


def interview(brief: str, docs: list[Document], llm: LLMClient, interactive: bool, answers_file: str | None, log=print, index=None) -> list[Clarification]:
    from .guard import check_topic
    from .retrieval import default_index

    qs = ask_questions(brief, docs, llm)
    answers = _load_answers(answers_file)
    out = []
    # never ask the requester something the documents already answer: check each question against the docs,
    # with the same verified-quote rule the groundability guard uses
    index = index or default_index(docs)
    kept = []
    for q in qs:
        if PREFERENCE_Q.search(q["question"]):
            kept.append(q)  # about what the requester wants: documents can never answer this
            continue
        chk = check_topic(q["question"], index, llm)
        if chk.status == "supported" and chk.evidence:
            out.append(Clarification(question=q["question"], why=q["why"], answer=f"Answered by {', '.join(chk.sources)}: \"{chk.evidence}\"", source="documents"))
            log(f"    skipped (documents answer it): {q['question']}")
        else:
            kept.append(q)
    qs = kept
    if interactive and sys.stdin.isatty():
        log("\nForgeAI intake: a few questions before I build (press Enter to accept the suggested default)\n")
    for i, q in enumerate(qs):
        pre = _answer_for(answers, i, q["question"])
        if pre is not None:
            out.append(Clarification(question=q["question"], why=q["why"], answer=str(pre), source="answers_file"))
            continue
        if interactive and sys.stdin.isatty():
            reply = input(f"  Q{i+1}. {q['question']}\n      [default: {q['default_answer']}] > ").strip()
            if reply:
                out.append(Clarification(question=q["question"], why=q["why"], answer=reply, source="requester"))
                continue
        default = q["default_answer"] or "No preference; use a conservative default."
        if INTEGRATION.search(q["question"]) or INTEGRATION.search(default):
            default = NO_INTEGRATION  # never assume a capability nobody confirmed
        out.append(Clarification(question=q["question"], why=q["why"], answer=default, source="assumed"))
    return out


def write_requirements(brief: str, docs: list[Document], clar: list[Clarification], llm: LLMClient) -> Requirements:
    ctext = "\n".join(f"- Q: {c.question}\n  A ({c.source}): {c.answer}" for c in clar) or "(none)"

    def validate(d):
        if not isinstance(d, dict):
            raise ValueError("expected an object")
        for k in ("must_answer_topics", "must_refuse_topics"):
            if not isinstance(d.get(k), list) or len(d[k]) < 2:
                raise ValueError(f"'{k}' must be a list with at least 2 items")
        d.setdefault("tool_needs", [])
        if not isinstance(d["tool_needs"], list):
            d["tool_needs"] = [str(d["tool_needs"])]
        for k in ("agent_name", "purpose", "scope", "audience", "tone"):
            d[k] = str(d.get(k) or "").strip() or "unspecified"
        d["must_answer_topics"] = [str(t).strip() for t in d["must_answer_topics"] if str(t).strip()][:12]
        d["must_refuse_topics"] = [str(t).strip() for t in d["must_refuse_topics"] if str(t).strip()][:10]
        d["tool_needs"] = [str(t).strip() for t in d["tool_needs"] if str(t).strip()]
        u = d.get("uncertainties") or []
        d["uncertainties"] = [str(x).strip() for x in (u if isinstance(u, list) else [u]) if str(x).strip()][:6]
        d["agent_name"] = "-".join(d["agent_name"].lower().split())[:40]
        return d

    data = llm.json(prompts.messages("intake_requirements", brief=brief, inventory=inventory_text(docs), clarifications=ctext), validator=validate, max_tokens=1000)
    return Requirements(**{k: data[k] for k in ("agent_name", "purpose", "scope", "audience", "tone", "must_answer_topics", "must_refuse_topics", "tool_needs", "uncertainties")}, clarifications=clar)


def requirements_markdown(req: Requirements) -> str:
    L = [f"# Requirements: {req.agent_name}", "", f"**Purpose:** {req.purpose}", f"**Scope:** {req.scope}", f"**Audience:** {req.audience}", f"**Tone:** {req.tone}", ""]
    L += ["## Must answer"] + [f"- {t}" for t in req.must_answer_topics] + [""]
    L += ["## Must refuse"] + [f"- {t}" for t in req.must_refuse_topics] + [""]
    L += ["## Tool needs"] + ([f"- {t}" for t in req.tool_needs] or ["- none (documents only)"]) + [""]
    L += ["## Knowledge sources", "", "| Document | Type | Size | Covers |", "|---|---|---|---|"]
    for k in req.knowledge_sources:
        L.append(f"| {k.doc} | {k.kind} | {k.size} | {', '.join(k.covers)[:160]} |")
    L.append("")
    L += ["## Groundability check", "", "| Topic | Status | Evidence | Source |", "|---|---|---|---|"]
    for g in req.groundability:
        ev = g.evidence.replace("|", "/")[:140]
        L.append(f"| {g.topic} | **{g.status}** | {ev} | {', '.join(g.sources)} |")
    L.append("")
    if req.conflicts:
        L += ["## Conflicting information across documents", ""]
        for c in req.conflicts:
            L += [f"- **{c.about}**", f"  - {c.doc_a}: \"{c.quote_a}\"", f"  - {c.doc_b}: \"{c.quote_b}\"", f"  - why it is the same subject: {c.reason}"]
        L.append("")
    if req.flags:
        L += ["## Flags raised at requirements stage"] + [f"- ⚠ {f}" for f in req.flags] + [""]
    if req.recommendations:
        L += ["## Recommended clarifications or scope changes"] + [f"- {r}" for r in req.recommendations] + [""]
    L += ["## Known limitations"] + [f"- {x}" for x in req.known_limitations] + [""]
    L += ["## Uncertainties and assumptions"] + ([f"- {x}" for x in req.uncertainties] or ["- none recorded"]) + [""]
    L += ["## Clarifying interview", ""]
    for i, c in enumerate(req.clarifications, 1):
        L.append(f"{i}. **{c.question}**  \n   _{c.source}_: {c.answer}")
    L += ["", f"**Approved:** {req.approved} {('(' + req.approval_note + ')') if req.approval_note else ''}"]
    return "\n".join(L)


def human_checkpoint(req: Requirements, path: Path, log=print) -> Requirements:
    """Stretch goal: the requester approves or edits requirements before generation proceeds."""
    path.write_text(json.dumps(req.model_dump(), indent=2), encoding="utf-8")
    if not sys.stdin.isatty():
        req.approved = True
        req.approval_note = "auto approved: no terminal attached (unattended run)"
        return req
    log(f"\nRequirements written to {path}. Review it now.")
    while True:
        r = input("  Approve? [y]es / [e]dited the file, reload / [n]o, abort > ").strip().lower()
        if r in ("y", "yes", ""):
            req.approved, req.approval_note = True, "approved by requester"
            return req
        if r.startswith("e"):
            req = Requirements.model_validate_json(path.read_text(encoding="utf-8"))
            req.approved, req.approval_note = True, "edited and approved by requester"
            return req
        if r.startswith("n"):
            raise SystemExit("Requester rejected the requirements; stopping before generation.")
