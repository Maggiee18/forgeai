"""Stage 3: agent generator. Requirements + documents -> declarative AgentDefinition.

* tools: LLM proposal intersected with deterministic evidence (tools.select_tools)
* system prompt: written section by section so the optimizer can later patch ONE section
* retrieval: parameters derived from document statistics, later tuned by the optimizer
* output contract: fixed JSON schema the runtime validates
* not-groundable topics are injected as hard rules regardless of what the model wrote
"""
from __future__ import annotations

import statistics

from . import prompts
from .docs import Document
from .llm import LLMClient
from .runner import OUTPUT_CONTRACT, contract_section
from .schemas import AgentDefinition, Requirements
from .tools import REGISTRY, select_tools

VARIANTS = {
    "strict": "Strict and compact: numbered rules, shortest possible wording, heavy emphasis on refusing when unsure.",
    "helpful": "Warm and helpful: same rules, but explains answers in 2 to 4 sentences and mentions conditions or exceptions.",
    "checklist": "Checklist driven: before answering, the assistant checks scope, then evidence in excerpts, then answers with the exact rule and its source.",
}


def choose_tools(req: Requirements, docs: list[Document], llm: LLMClient, enabled: list[str]) -> tuple[list[dict], list[dict]]:
    has_csv = any(d.kind == "csv" for d in docs)
    reg = "\n".join(f"- {n}: {s.description}" for n, s in REGISTRY.items() if n in enabled)
    try:
        prop = llm.json(prompts.messages("generator_tools", requirements=req.as_text(), has_csv=has_csv, registry=reg), max_tokens=300)
        proposed = prop.get("tools", []) if isinstance(prop, dict) else []
    except Exception:  # noqa: BLE001
        proposed = []
    # the brief + requirements text is the evidence base for the deterministic check
    evidence_text = " ".join([req.purpose, req.scope, " ".join(req.must_answer_topics), " ".join(req.tool_needs)] + [c.answer for c in req.clarifications])
    kept, rejected = select_tools(proposed, evidence_text, has_csv, enabled)
    # a CSV the model forgot: tabular data is only reachable precisely through csv_lookup
    if has_csv and "csv_lookup" in enabled and not any(k["name"] == "csv_lookup" for k in kept):
        kept.append({"name": "csv_lookup", "reason": "documents include CSV data that needs exact row lookups", "evidence": ["documents include CSV data"], "added_by": "rule"})
    return kept, rejected


def retrieval_defaults(docs: list[Document], embedding: str = "wordllama") -> dict:
    para_lens = []
    for d in docs:
        if d.kind != "csv":
            para_lens += [len(p.split()) for p in d.text.split("\n\n") if p.strip()]
    med = statistics.median(para_lens) if para_lens else 80
    chunk = int(min(260, max(100, med * 2.2)))
    from .embeddings import get_embedder

    emb = get_embedder(embedding)
    emb_cfg = emb.describe() if emb else {"provider": "none"}
    if emb and embedding.startswith("fastembed:") and emb.provider != "fastembed":
        emb_cfg["note"] = f"requested {embedding} could not load; fell back to {emb.provider}"
    has_csv = any(d.kind == "csv" for d in docs)
    return {
        "strategy": "hybrid" if emb else "bm25",
        "embedding": emb_cfg,
        "fusion": "weighted reciprocal rank fusion",
        "rrf_k": 60,
        "bm25_weight": 1.0,
        "dense_weight": 1.0,
        "chunk_size": chunk,
        "chunk_overlap": int(chunk * 0.2),
        "csv_rows_per_chunk": 1,
        "top_k": 4,
        "min_score": 0.15,
        "query_expansion": {},
        "derived_from": f"chunk size = 2.2 x median paragraph length ({med:.0f} words), clamped to 100..260 so a chunk holds one policy section; "
                        f"overlap 20% so rules split across a boundary survive; top_k 4 keeps the context small for a small model"
                        + ("; CSV rows are chunked one per row so each part is retrievable on its own" if has_csv else ""),
    }


def write_prompt_sections(req: Requirements, tools: list[dict], llm: LLMClient, variant: str = "strict") -> dict:
    tools_txt = ", ".join(f"{t['name']} ({REGISTRY[t['name']].description})" for t in tools) or "none"

    def validate(d):
        if not isinstance(d, dict):
            raise ValueError("expected object")
        for k in ("role", "scope", "grounding", "refusal", "style"):
            v = d.get(k)
            if isinstance(v, list):
                v = "\n".join(str(x) for x in v)
            if not v or not str(v).strip():
                raise ValueError(f"section '{k}' is empty")
            d[k] = str(v).strip()
        t = d.get("tools")
        d["tools"] = "\n".join(map(str, t)) if isinstance(t, list) else str(t or "No tools.")
        d["refusal_message"] = str(d.get("refusal_message") or "I'm sorry, that is not covered by the documents I can use.")
        return d

    return llm.json(
        prompts.messages("generator_prompt", requirements=req.as_text(), tools=tools_txt, variant=VARIANTS.get(variant, variant)),
        validator=validate,
        max_tokens=1100,
    )


def enforce_guardrails(sections: dict, req: Requirements, tools: list[dict]) -> dict:
    """Deterministic rules appended after generation so a weak model cannot drop them."""
    s = dict(sections)
    if req.ungroundable_topics:
        s["refusal"] = s["refusal"].rstrip() + "\n" + (
            "The documents do NOT cover the following, so never answer them from memory; say they are not covered "
            "and set refused to true: " + "; ".join(req.ungroundable_topics) + "."
        )
    if req.must_refuse_topics and not any(t.lower()[:20] in s["refusal"].lower() for t in req.must_refuse_topics):
        s["refusal"] = s["refusal"].rstrip() + "\nAlways refuse: " + "; ".join(req.must_refuse_topics) + "."
    if not tools:
        s["tools"] = "No tools. Use only the excerpts."
    else:
        s["tools"] = s["tools"].rstrip() + "\nTool results appear under TOOL RESULTS; treat them as exact. Copy computed numbers exactly."
    if req.conflicts:
        s["grounding"] = s["grounding"].rstrip() + "\n" + "Known contradictions between documents: " + "; ".join(
            f"{c.about} ({c.doc_a} vs {c.doc_b})" for c in req.conflicts) + ". When a question touches one, give BOTH versions with their source files and advise confirming which is current; never pick one silently."
    if "never" not in s["grounding"].lower():
        s["grounding"] = s["grounding"].rstrip() + "\nNever add facts, numbers or names that are not in the excerpts or tool results."
    s["output_contract"] = contract_section()
    return s


def generate(req: Requirements, docs: list[Document], docs_folder: str, llm: LLMClient, enabled_tools: list[str], variant: str = "strict", tools=None, embedding: str = "wordllama") -> tuple[AgentDefinition, dict]:
    if tools is None:
        tools, rejected = choose_tools(req, docs, llm, enabled_tools)
    else:
        rejected = []
    tools = [{**t, "schema": REGISTRY[t["name"]].describe()} for t in tools]
    raw = write_prompt_sections(req, tools, llm, variant)
    refusal_message = raw.pop("refusal_message")
    sections = enforce_guardrails({k: raw[k] for k in ("role", "scope", "grounding", "refusal", "tools", "style")}, req, tools)
    d = AgentDefinition(
        name=req.agent_name,
        version=0,
        description=req.purpose,
        system_prompt_sections=sections,
        retrieval=retrieval_defaults(docs, embedding),
        tools=tools,
        output_contract=OUTPUT_CONTRACT,
        refusal_message=refusal_message,
        docs_folder=docs_folder,
        temperature=0.0,
        provenance={"variant": variant, "generator_model": llm.model},
    )
    return d, {"tools_kept": tools, "tools_rejected": rejected}
