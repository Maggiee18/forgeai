"""Runs an eval set against an agent and aggregates a scorecard."""
from __future__ import annotations

from collections import defaultdict

from .critic import CATEGORIES, critique
from .judge import Judge
from .runner import Agent
from .schemas import CaseResult, EvalCase


def run_evals(agent: Agent, cases: list[EvalCase], judge: Judge, log=None, subset: list[str] | None = None) -> list[CaseResult]:
    out = []
    todo = [c for c in cases if subset is None or c.id in subset]
    for i, c in enumerate(todo, 1):
        resp = agent.answer(c.question)
        r = judge.score(c, resp)
        out.append(r)
        if log:
            log(f"      [{i:>2}/{len(todo)}] {'PASS' if r.passed else 'fail'}  {c.id:<7} {c.question[:70]}")
    critique(out)
    return out


def _rate(rs: list[CaseResult]) -> float | None:
    return round(sum(r.passed for r in rs) / len(rs), 3) if rs else None


def scorecard(results: list[CaseResult]) -> dict:
    by_type = defaultdict(list)
    for r in results:
        by_type[r.type].append(r)
    answer = [r for r in results if r.expected_behavior == "answer"]
    refuse = [r for r in results if r.expected_behavior == "refuse"]
    cats = {c: sum(1 for r in results if r.failure_category == c) for c in CATEGORIES}
    return {
        "n_cases": len(results),
        "pass_rate": _rate(results),
        "dev_pass_rate": _rate([r for r in results if r.split == "dev"]),
        "holdout_pass_rate": _rate([r for r in results if r.split == "holdout"]),
        "by_type": {t: {"n": len(v), "pass_rate": _rate(v)} for t, v in sorted(by_type.items())},
        "answer_fact_recall": round(sum(r.fact_recall for r in answer) / len(answer), 3) if answer else None,
        "completeness": round(sum(r.fact_recall for r in answer if not r.refused) / max(1, sum(1 for r in answer if not r.refused)), 3) if answer else None,
        "citation_precision": round(sum(r.citation_precision for r in answer) / len(answer), 3) if answer else None,
        "answer_relevance": (round(sum(v) / len(v), 3) if (v := [r.answer_relevance for r in answer if r.answer_relevance is not None]) else None),
        "refusal_accuracy": _rate(refuse),
        "wrong_refusals_on_answerable": sum(1 for r in answer if r.refused),
        "grounded_rate": round(sum(r.grounded for r in results) / len(results), 3) if results else None,
        "contract_ok_rate": round(sum(r.contract_ok for r in results) / len(results), 3) if results else None,
        "retrieval_hit_rate": round(sum(r.retrieval_hit for r in answer) / len(answer), 3) if answer else None,
        "failures_by_category": cats,
        "suspected_eval_defects": sum(1 for r in results if not r.passed and r.suspected_eval_defect),
        "avg_latency_s": round(sum(r.latency_s for r in results) / len(results), 2) if results else None,
    }
