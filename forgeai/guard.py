"""Stage 2: groundability guard.

For every must-answer topic: retrieve the best passages, ask the model whether they really support the
topic, and then verify the model's evidence quote actually exists in the passages. A model that claims
"supported" but cannot quote real text is overruled to "unsupported". Tool-shaped needs (live data,
calculations) are checked against the tool registry instead of the documents.

Unsupported topics are flagged in the requirements, turned into must-say-not-covered rules for the agent,
and become refusal test cases, so the produced agent cannot hallucinate the gap away.
"""
from __future__ import annotations

import re

from . import prompts
from .llm import LLMClient
from .retrieval import default_index
from .docs import Document
from .schemas import Conflict, KnowledgeSource, Requirements, TopicCheck
from .textutil import content_overlap, quote_in_text, tokens
from .tools import REGISTRY

LIVE_DATA = re.compile(r"\b(live|real[- ]time|current|today'?s|latest|up[- ]to[- ]date)\b.*\b(rate|price|weather|status|position|exchange|stock|market|news)", re.I)


def _tool_can_serve(topic: str) -> str | None:
    """Only tools that fetch fresh information can serve a live-data need."""
    t = topic.lower()
    for name, spec in REGISTRY.items():
        if name not in ("weather_forecast", "current_date"):
            continue
        if any(re.search(r"\b" + re.escape(k), t) for k in spec.need_keywords):
            return name
    return None


COMPUTE = {
    "calculator": re.compile(r"\b(calculat\w*|totals?|sum|discount\w*|price calculation|cost estimat\w*|order value|multipl\w*|pro.?rat\w*)\b", re.I),
    "current_date": re.compile(r"\b(delivery (date|estimate)|estimated delivery|lead.?time|days from (now|today)|due date|expected (date|delivery)|arrival date)\b", re.I),
}


def check_topic(topic: str, index, llm: LLMClient) -> TopicCheck:
    hits = index.search(topic, top_k=5)
    if LIVE_DATA.search(topic):
        tool = _tool_can_serve(topic)
        if tool:
            return TopicCheck(topic=topic, status="supported", evidence=f"live data served by tool '{tool}'", method="tool registry")
        return TopicCheck(topic=topic, status="unsupported", evidence="needs live external data; no document or registry tool provides it", method="live data rule")
    if not hits:
        return TopicCheck(topic=topic, status="unsupported", evidence="no passage shares any keyword with the topic", method="retrieval")
    excerpts = "\n\n".join(f"[{c.doc_id}] {c.text}" for c, _ in hits)
    joined = " ".join(c.text for c, _ in hits)
    try:
        v = llm.json(prompts.messages("guard_topic", topic=topic, excerpts=excerpts[:4500]), max_tokens=300)
    except Exception as e:  # noqa: BLE001
        v = {"status": "partial", "evidence_quote": "", "source": "", "_err": str(e)}
    status = str(v.get("status", "unsupported")).lower().strip()
    if status not in ("supported", "partial", "unsupported"):
        status = "unsupported"
    if status != "supported":
        tool = next((t for t, rx in COMPUTE.items() if rx.search(topic)), None)
        # a computation over document data (totals, discounts, delivery dates) is servable by a registry tool,
        # provided the documents hold the inputs (they retrieved something relevant)
        if tool and hits and content_overlap(topic, " ".join(c.text for c, _ in hits)) >= 0.3:
            return TopicCheck(topic=topic, status="supported", evidence=f"computed by the '{tool}' tool from document data",
                              sources=sorted({c.doc_id for c, _ in hits[:2]}), method="tool registry: computation over document data")
    quote = str(v.get("evidence_quote", "")).strip()
    sources = sorted({c.doc_id for c, _ in hits[:2]})
    method = "llm + quote verification"
    if status in ("supported", "partial"):
        if not quote_in_text(quote, joined, min_overlap=0.75):
            # model asserted support but its quote is not in the passages: distrust it
            status, method = "unsupported", "llm claim overruled: evidence quote not found in documents"
        else:
            src = [c.doc_id for c, _ in hits if quote_in_text(quote, c.text, 0.75)]
            sources = sorted(set(src)) or sources
    # deterministic sanity check: topic words should appear near the evidence
    if status == "supported" and content_overlap(topic, joined) < 0.34:
        status, method = "partial", method + "; downgraded: topic keywords barely present"
    if status == "unsupported" and hits and content_overlap(topic, hits[0][0].text) >= 0.99 and len(tokens(topic)) >= 3:
        status, method = "partial", method + "; upgraded: every topic keyword appears in the top passage"
    return TopicCheck(topic=topic, status=status, evidence=quote if status != "unsupported" else (quote or ""), sources=sources if status != "unsupported" else [], method=method)


_VALUE = re.compile(r"((?:INR|USD|Rs\.?|\$)\s?[\d,]+(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:%|percent|days?|working days|weeks?|months?|hours?|years?|km|kilometres?))", re.I)


def _values(text: str) -> set[str]:
    return {" ".join(v.split()).lower() for v in _VALUE.findall(text)}


def _same_scope(a: str, b: str) -> bool:
    """Do two 'applies to' descriptions overlap? A narrower group of the same people ('all employees' vs 'employees
    on official trips') overlaps; two different named entities ('Poseidon Marine Supplies' vs 'Harbourline Spares')
    do not. Measured against the smaller description so a subset counts as the same scope."""
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return True  # model gave no scope; the quote and value checks still apply
    return len(ta & tb) / min(len(ta), len(tb)) > 0.5


def find_conflicts(req: Requirements, index, llm: LLMClient, max_checks: int = 12, log=print, verifier: LLMClient | None = None, checks: list | None = None) -> list[Conflict]:
    """Candidate pairs = best passage per document for each topic (plus closely related passages across
    documents). Only pairs that state DIFFERENT values reach the model; the model must say they concern the
    same subject; both quotes must exist verbatim and must carry different values. Three gates, one LLM call."""
    from .textutil import jaccard

    cands, seen = [], set()
    for topic in req.must_answer_topics:
        best_per_doc = {}
        for c, _ in index.search(topic, top_k=8):
            best_per_doc.setdefault(c.doc_id, c)
        docs_ = list(best_per_doc.values())[:3]
        for i in range(len(docs_)):
            for j in range(i + 1, len(docs_)):
                a, b = docs_[i], docs_[j]
                key = tuple(sorted((a.chunk_id, b.chunk_id)))
                va, vb = _values(a.text), _values(b.text)
                if key in seen or not va or not vb or va == vb:
                    continue
                seen.add(key)
                cands.append((jaccard(a.text, b.text) + content_overlap(topic, a.text + " " + b.text), a, b))
    # passages from different documents about the same thing, independent of the topic list. Word overlap alone
    # misses short rules phrased differently, so rank by embedding similarity + shared heading words + word overlap,
    # and keep only pairs whose values are of the same kind (INR vs INR, days vs days)
    chunks = [c for c in index.chunks if "#row" not in c.chunk_id]
    emb = getattr(index, "embedder", None)
    M = emb.embed([f"{c.section}. {c.text}" for c in chunks]) if emb is not None and chunks else None

    def kinds(vs):
        return {re.sub(r"[\d,.\s]+", " ", x).strip() for x in vs}

    def head(c):
        return {t for t in tokens(c.section) if not t.isdigit()}

    for i, a in enumerate(chunks):
        for j in range(i + 1, len(chunks)):
            b = chunks[j]
            if a.doc_id == b.doc_id:
                continue
            key = tuple(sorted((a.chunk_id, b.chunk_id)))
            va, vb = _values(a.text), _values(b.text)
            if key in seen or not va or not vb or va == vb or not (kinds(va) & kinds(vb)):
                continue
            score = jaccard(a.text, b.text) + 0.3 * min(len(head(a) & head(b)), 2)
            if M is not None:
                score += float(M[i] @ M[j])
            seen.add(key)
            cands.append((score, a, b))
    cands.sort(key=lambda x: -x[0])
    # The decider is the judge model when one is given (larger, different family from the factory model); the
    # factory model's vote is recorded alongside for transparency. Code then verifies the decider's claim.
    decider, other = (verifier, llm) if verifier is not None else (llm, None)
    found: list[Conflict] = []
    for _, a, b in cands[:max_checks]:
        msgs = prompts.messages("guard_conflict", doc_a=a.doc_id, text_a=a.text, doc_b=b.doc_id, text_b=b.text)
        try:
            v = decider.json(msgs, max_tokens=350)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(v, dict):
            continue
        record = {"doc_a": a.chunk_id, "doc_b": b.chunk_id, "about": v.get("about"), "decider": decider.model,
                  "decider_vote": v.get("conflict") is True, "applies_to": [v.get("applies_to_a"), v.get("applies_to_b")]}
        if checks is not None:
            checks.append(record)
        if v.get("conflict") is not True:
            record["outcome"] = "no conflict (decider)"
            continue
        if not _same_scope(str(v.get("applies_to_a", "")), str(v.get("applies_to_b", ""))):
            record["outcome"] = "rejected: rules apply to different things"
            log(f"    conflict rejected (different scope: '{v.get('applies_to_a')}' vs '{v.get('applies_to_b')}'): {v.get('about')}")
            continue
        qa, qb = str(v.get("quote_a", "")), str(v.get("quote_b", ""))
        if not (quote_in_text(qa, a.text, 0.8) and quote_in_text(qb, b.text, 0.8)):
            record["outcome"] = "rejected: quote not found in the documents"
            log(f"    conflict rejected (quote not found in the documents): {v.get('about')}")
            continue
        vals_a, vals_b = _values(qa), _values(qb)
        if not vals_a or not vals_b or vals_a == vals_b:
            record["outcome"] = "rejected: quotes do not carry different values"
            continue

        def kind(x):
            return re.sub(r"[\d,.\s]+", " ", x).strip() or "number"
        shared = {kind(x) for x in vals_a} & {kind(x) for x in vals_b}
        clash = sorted(x for x in vals_a | vals_b if kind(x) in shared)
        if len(clash) < 2:
            record["outcome"] = "rejected: values are of different kinds"
            continue
        about = str(v.get("about", "")).strip() or "unspecified rule"
        if any(jaccard(about, f.about) > 0.5 for f in found):
            record["outcome"] = "duplicate of an accepted conflict"
            continue
        other_vote = None
        if other is not None:
            try:
                v2 = other.json(msgs, max_tokens=350)
                other_vote = isinstance(v2, dict) and v2.get("conflict") is True
            except Exception:  # noqa: BLE001
                other_vote = None
        record.update(outcome="accepted", other_model=other.model if other else None, other_vote=other_vote)
        found.append(Conflict(about=about, doc_a=a.doc_id, quote_a=qa.strip(), doc_b=b.doc_id, quote_b=qb.strip(),
                              reason=str(v.get("same_subject_reason", "")) + (f" (second model {other.model} {'agreed' if other_vote else 'disagreed'})" if other is not None else ""),
                              values=clash))
        log(f"    conflict       {about}: {a.doc_id} vs {b.doc_id}" + (f"  [{other.model} {'agrees' if other_vote else 'disagrees'}]" if other is not None else ""))
    return found


def knowledge_sources(docs: list[Document]) -> list[KnowledgeSource]:
    from .docs import headings

    out = []
    for d in docs:
        if d.kind == "csv":
            out.append(KnowledgeSource(doc=d.doc_id, kind="csv", size=f"{len(d.rows)} rows", covers=d.columns))
        else:
            secs = [re.sub(r"^\d+(\.\d+)*\.?\s*", "", h) for h in headings(d)][1:]
            out.append(KnowledgeSource(doc=d.doc_id, kind=d.kind, size=f"{d.pages} pages, {len(d.text.split())} words", covers=secs[:20]))
    return out


def run_guard(req: Requirements, docs: list[Document], llm: LLMClient, log=print, index=None, verifier: LLMClient | None = None) -> Requirements:
    index = index or default_index(docs)
    checks = []
    for topic in req.must_answer_topics:
        c = check_topic(topic, index, llm)
        checks.append(c)
        log(f"    groundability  {c.status:<11} {topic}")
    flags, limits, recs = [], [], []
    for need in req.tool_needs:
        tool = _tool_can_serve(need)
        if LIVE_DATA.search(need) and not tool:
            flags.append(f"Tool need '{need}' requires live external data that no registry tool provides; the agent will say it cannot do this.")
            limits.append(f"Cannot provide: {need} (no live data source).")
            recs.append(f"Drop '{need}' from scope, or add an API tool for it to the registry.")
    req.groundability = checks
    req.ungroundable_topics = [c.topic for c in checks if c.status == "unsupported"]
    for c in checks:
        if c.status == "unsupported":
            flags.append(f"'{c.topic}' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.")
            limits.append(f"Cannot answer: {c.topic} (not in the documents).")
            recs.append(f"Either add a source document covering '{c.topic}' or remove it from the scope.")
        elif c.status == "partial":
            flags.append(f"'{c.topic}' is only partly covered by the documents; answers may be incomplete.")
            limits.append(f"Partial coverage: {c.topic}.")
    req.conflict_checks = []
    req.conflicts = find_conflicts(req, index, llm, log=log, verifier=verifier, checks=req.conflict_checks)
    for k in req.conflicts:
        flags.append(f"Conflicting information on {k.about}: {k.doc_a} says \"{k.quote_a}\" while {k.doc_b} says \"{k.quote_b}\". The agent will present both and suggest confirming with the document owner.")
        limits.append(f"Documents contradict each other on {k.about}; answers cite both versions.")
        recs.append(f"Ask the document owners which rule on {k.about} is current, and fix the outdated document.")
    req.knowledge_sources = knowledge_sources(docs)
    req.known_limitations = limits + ["Answers only from the supplied documents; no access to personal records or live systems."]
    req.uncertainties = list(dict.fromkeys(req.uncertainties + [f"Assumed (nobody answered): {c.question} -> {c.answer}" for c in req.clarifications if c.source == "assumed"]))
    req.flags = flags
    req.recommendations = recs
    return req
