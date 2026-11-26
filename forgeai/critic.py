"""Stage 6a: critic. Classifies every failure into exactly one category with a deterministic rule,
using evidence the runtime recorded (what was retrieved, what was cited, which numbers had no source).

  retrieval_miss  the passage holding the answer never reached the model
  hallucination   the answer states numbers/claims absent from passages and tool results, or answers
                  a must-refuse question with invented content
  wrong_refusal   refused an answerable question, or answered one it should have refused
  prompt_defect   the right passage was retrieved but the answer is incomplete, uncited or breaks the
                  output contract: the instructions, not the knowledge, are at fault
"""
from __future__ import annotations

from collections import Counter

from .schemas import CaseResult

CATEGORIES = ["retrieval_miss", "hallucination", "wrong_refusal", "prompt_defect"]


def classify(r: CaseResult) -> tuple[str, str]:
    if r.expected_behavior == "refuse":
        if r.unsupported_numbers:
            return "hallucination", f"answered a must-refuse question with unsupported specifics {r.unsupported_numbers}"
        return "wrong_refusal", "should have refused (out of scope or not covered) but answered"
    # expected an answer
    if not r.retrieval_hit:
        why = "expected source never retrieved"
        if r.refused:
            why += "; the model then (correctly, given what it saw) refused"
        return "retrieval_miss", why
    if r.refused:
        return "wrong_refusal", "the answer was in the retrieved passages but the agent refused"
    if r.unsupported_numbers:
        return "hallucination", f"numbers not found in any passage or tool result: {r.unsupported_numbers}"
    if not r.contract_ok:
        return "prompt_defect", "output contract violated (bad JSON or fields)"
    if not r.cited_expected:
        if r.facts_missing:
            return "prompt_defect", f"right passage retrieved, but answer missed {r.facts_missing} and did not cite it"
        return "prompt_defect", "correct content but did not cite the source document"
    return "prompt_defect", f"right passage retrieved but answer missed key facts {r.facts_missing}"


def critique(results: list[CaseResult]) -> dict:
    counts = Counter()
    for r in results:
        if r.passed:
            r.failure_category, r.diagnosis = None, ""
            continue
        cat, why = classify(r)
        if r.suspected_eval_defect:
            why += " [suspected test defect: the judge model reads the answer as correct, but a strict rule (exact numbers or quote) rejected it; not sent to the optimizer]"
        r.failure_category, r.diagnosis = cat, why
        counts[cat] += 1
    return {c: counts.get(c, 0) for c in CATEGORIES}
