"""Generic agent runtime: loads ANY agent definition produced by the factory and answers questions.

Flow per question: retrieve -> (optional) tool plan + execution -> grounded answer in the output contract.
The runtime validates the contract itself so the judge and the critic can tell a format defect from a
knowledge defect.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import prompts
from .docs import Document, load_folder
from .llm import LLMClient, extract_json
from .retrieval import build_index
from .schemas import AgentDefinition, AgentResponse
from .textutil import looks_like_refusal
from .tools import CsvLookup, make_tool_functions, tool_menu

OUTPUT_CONTRACT = {
    "type": "object",
    "required": ["answer", "refused", "citations"],
    "properties": {
        "answer": {"type": "string", "description": "answer text shown to the user"},
        "refused": {"type": "boolean", "description": "true when declining or when the documents do not contain the answer"},
        "citations": {"type": "array", "items": {"type": "string"}, "description": "file names of the excerpts used"},
    },
}


def contract_section() -> str:
    return (
        "Reply with ONE JSON object and nothing else: "
        '{"answer": string, "refused": boolean, "citations": [file names]}. '
        "citations must list only file names that appear in the EXCERPTS you used. "
        "When refusing, set refused to true and citations to []."
    )


class Agent:
    def __init__(self, definition: AgentDefinition, llm: LLMClient, docs: list[Document] | None = None, docs_folder: str | None = None):
        self.d = definition
        self.llm = llm
        folder = docs_folder or definition.docs_folder
        self.docs = docs if docs is not None else load_folder(folder)
        self.index = build_index(self.docs, definition.retrieval)
        csv_paths = [d.path for d in self.docs if d.kind == "csv"]
        self.tools = make_tool_functions(definition.tool_names(), csv_paths)
        self.csv_schema = CsvLookup(csv_paths).schema() if csv_paths and "csv_lookup" in self.tools else ""
        self.doc_ids = {d.doc_id for d in self.docs}

    @classmethod
    def from_file(cls, path: str | Path, llm: LLMClient, docs_folder: str | None = None) -> "Agent":
        path = Path(path)
        d = AgentDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        folder = docs_folder or d.docs_folder
        if folder and not Path(folder).is_absolute() and not Path(folder).exists():
            cand = (path.parent / folder).resolve()
            if cand.exists():
                folder = str(cand)
        return cls(d, llm, docs_folder=folder)

    # ------------------------------------------------------------------
    def _context(self, hits) -> str:
        if not hits:
            return "(no excerpts found)"
        return "\n\n".join(f"[{i+1}] source: {c.doc_id}{' | section: ' + c.section if c.section else ''}\n{c.text}" for i, (c, _) in enumerate(hits))

    def _run_tools(self, question: str, context: str) -> list[dict]:
        """Up to two planning rounds, so the model can look a value up and THEN compute with it."""
        if not self.tools:
            return []
        results: list[dict] = []
        for _round in range(2):
            ctx = context[:3500]
            if results:
                ctx += "\n\nEARLIER TOOL RESULTS:\n" + json.dumps(results, ensure_ascii=False)[:1500]
            try:
                plan = self.llm.json(
                    prompts.messages("agent_tool_plan", tools=tool_menu(list(self.tools), self.csv_schema), context=ctx, question=question),
                    max_tokens=300,
                )
            except Exception:  # noqa: BLE001
                break
            calls = plan.get("calls", []) if isinstance(plan, dict) else []
            new = 0
            for call in calls[:2]:
                if not isinstance(call, dict):
                    continue
                name, args = call.get("tool"), call.get("args") or {}
                if any(r.get("tool") == name and r.get("args") == args for r in results):
                    continue  # identical repeat call
                new += 1
                if name not in self.tools:
                    results.append({"tool": name, "args": args, "error": "tool not attached to this agent"})
                    continue
                try:
                    out = self.tools[name](**args) if isinstance(args, dict) else self.tools[name](args)
                except Exception as e:  # noqa: BLE001
                    out = {"error": str(e)}
                results.append({"tool": name, "args": args, "result": out})
            if not new or len(results) >= 3:
                break
        return results

    def answer(self, question: str, history: list[tuple[str, str]] | None = None) -> AgentResponse:
        t0 = time.time()
        rq = question
        if history:
            rq = history[-1][0] + " " + question  # carry the previous user turn into retrieval for follow ups
        r = self.d.retrieval
        hits = self.index.search(rq, top_k=int(r.get("top_k", 4)), min_score=float(r.get("min_score", 0.0)))
        context = self._context(hits)
        tool_results = self._run_tools(question, context)
        hist = ""
        if history:
            hist = "CONVERSATION SO FAR:\n" + "\n".join(f"User: {u}\nAssistant: {a}" for u, a in history[-2:]) + "\n\n"
        msgs = [
            {"role": "system", "content": self.d.system_prompt},
            {
                "role": "user",
                "content": prompts.render(
                    "agent_answer",
                    context=context,
                    tool_results=json.dumps(tool_results, ensure_ascii=False)[:2500] if tool_results else "(none)",
                    history=hist,
                    question=question,
                ),
            },
        ]
        raw = self.llm.chat(msgs, json_mode=True, temperature=self.d.temperature, max_tokens=500)
        errors = []
        try:
            data = extract_json(raw)
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except Exception as e:  # noqa: BLE001
            data = {"answer": raw, "refused": looks_like_refusal(raw), "citations": []}
            errors.append(f"unparseable JSON: {e}")
        ans = data.get("answer")
        if not isinstance(ans, str):
            errors.append("answer missing or not a string")
            ans = json.dumps(ans) if ans is not None else ""
        refused = data.get("refused")
        if not isinstance(refused, bool):
            errors.append("refused missing or not boolean")
            refused = str(refused).lower() == "true" or looks_like_refusal(ans)
        cits = data.get("citations")
        if not isinstance(cits, list):
            errors.append("citations missing or not a list")
            cits = []
        cits = [str(c) for c in cits]
        # normalise citations to file names; drop invented ones
        norm = []
        for c in cits:
            if not c.strip():
                continue
            match = next((d for d in self.doc_ids if d.lower() in c.lower() or c.lower() in d.lower()), None)
            if match:
                norm.append(match)
            else:
                errors.append(f"citation '{c}' is not a known document")
        if refused and not ans.strip():
            ans = self.d.refusal_message
        return AgentResponse(
            answer=ans,
            refused=refused,
            citations=sorted(set(norm)),
            retrieved=[{"chunk_id": c.chunk_id, "doc": c.doc_id, "section": c.section, "score": round(s, 3), "text": c.text} for c, s in hits],
            tool_calls=tool_results,
            contract_ok=not errors,
            contract_errors=errors,
            raw=raw[:2000],
            latency_s=round(time.time() - t0, 2),
        )
