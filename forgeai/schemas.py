"""Typed artifacts the factory produces. Everything is JSON serialisable and committed per run."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Clarification(BaseModel):
    question: str
    why: str = ""
    answer: str = ""
    source: Literal["requester", "assumed", "answers_file", "documents"] = "assumed"


class TopicCheck(BaseModel):
    topic: str
    status: Literal["supported", "partial", "unsupported"]
    evidence: str = ""
    sources: list[str] = []
    method: str = ""


class Conflict(BaseModel):
    about: str
    doc_a: str
    quote_a: str
    doc_b: str
    quote_b: str
    reason: str = ""
    values: list[str] = []      # the clashing values, e.g. ["INR 2,000", "INR 5,000"]


class KnowledgeSource(BaseModel):
    doc: str
    kind: str
    size: str
    covers: list[str] = []


class Requirements(BaseModel):
    agent_name: str
    purpose: str
    scope: str
    audience: str
    tone: str
    must_answer_topics: list[str]
    must_refuse_topics: list[str]
    tool_needs: list[str] = []
    clarifications: list[Clarification] = []
    groundability: list[TopicCheck] = []
    ungroundable_topics: list[str] = []
    conflicts: list[Conflict] = []
    conflict_checks: list[dict] = []     # every candidate pair checked, with each model's vote and the outcome
    knowledge_sources: list[KnowledgeSource] = []
    known_limitations: list[str] = []
    uncertainties: list[str] = []          # open questions nobody answered + assumptions the factory made
    flags: list[str] = []
    recommendations: list[str] = []        # clarification or scope reduction suggested to the requester
    approved: bool = False
    approval_note: str = ""

    def as_text(self) -> str:
        return (
            f"Agent: {self.agent_name}\nPurpose: {self.purpose}\nScope: {self.scope}\nAudience: {self.audience}\n"
            f"Tone: {self.tone}\nMust answer: {'; '.join(self.must_answer_topics)}\n"
            f"Must refuse: {'; '.join(self.must_refuse_topics)}\nTool needs: {'; '.join(self.tool_needs) or 'none stated'}\n"
            + (f"NOT groundable in the documents (agent must say so): {'; '.join(self.ungroundable_topics)}\n" if self.ungroundable_topics else "")
            + "".join(f"CONFLICT between documents on {c.about}: {c.doc_a} says '{c.quote_a}' but {c.doc_b} says '{c.quote_b}'\n" for c in self.conflicts)
        )


PROMPT_SECTIONS = ["role", "scope", "grounding", "refusal", "tools", "style", "output_contract"]


class AgentDefinition(BaseModel):
    name: str
    version: int = 0
    description: str = ""
    system_prompt_sections: dict[str, str]
    retrieval: dict = Field(default_factory=dict)
    tools: list[dict] = []
    output_contract: dict = Field(default_factory=dict)
    refusal_message: str = ""
    docs_folder: str = ""
    temperature: float = 0.0
    provenance: dict = Field(default_factory=dict)

    @property
    def system_prompt(self) -> str:
        parts = []
        for k in PROMPT_SECTIONS:
            v = self.system_prompt_sections.get(k, "").strip()
            if v:
                parts.append(f"## {k.replace('_', ' ').upper()}\n{v}")
        for k, v in self.system_prompt_sections.items():
            if k not in PROMPT_SECTIONS and v.strip():
                parts.append(f"## {k.upper()}\n{v}")
        return "\n\n".join(parts)

    def tool_names(self) -> list[str]:
        return [t["name"] for t in self.tools]


CaseType = Literal["answerable", "cross_doc", "ambiguous", "out_of_scope", "ungroundable", "tool", "conflict"]


class EvalCase(BaseModel):
    id: str
    type: CaseType
    question: str
    expected_behavior: Literal["answer", "refuse"]
    expected_sources: list[str] = []
    key_facts: list[str] = []
    evidence: list[dict] = []     # [{"doc": file, "quote": supporting sentence}] for answer cases
    refusal_reason: str = ""      # why a refuse case must be refused
    split: Literal["dev", "holdout"] = "dev"
    origin: str = ""          # chunk ids / topic / derivation used to make the case
    note: str = ""


class AgentResponse(BaseModel):
    answer: str
    refused: bool
    citations: list[str] = []
    retrieved: list[dict] = []
    tool_calls: list[dict] = []
    contract_ok: bool = True
    contract_errors: list[str] = []
    raw: str = ""
    latency_s: float = 0.0


class CaseResult(BaseModel):
    case_id: str
    type: str
    split: str
    question: str
    expected_behavior: str
    answer: str
    refused: bool
    citations: list[str]
    retrieved_sources: list[str]
    tool_calls: list[dict] = []
    contract_ok: bool
    refusal_ok: bool
    fact_recall: float
    facts_matched: list[str] = []
    facts_missing: list[str] = []
    grounded: bool
    unsupported_numbers: list[str] = []
    cited_expected: bool
    citation_precision: float = 1.0      # share of cited files that were retrieved AND expected
    answer_relevance: float | None = None  # embedding similarity of answer to question (reported, not a pass gate)
    retrieval_hit: bool
    passed: bool
    suspected_eval_defect: bool = False   # judge model thinks the answer is right; a strict rule rejected it
    failure_category: str | None = None
    diagnosis: str = ""
    judge_method: str = ""
    latency_s: float = 0.0
