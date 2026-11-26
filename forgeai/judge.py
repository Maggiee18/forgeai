"""Stage 5: judge. Scores every case on four questions:
    refused when it should?   correct against the expected facts?   grounded?   cited the right source?

Design against the known failure modes of LLM-as-judge:
  * position bias   -> the judge never compares two answers side by side; it grades one answer against
                       fixed facts. (The prompt tournament compares candidates by eval pass rates, never by a
                       pairwise LLM verdict.) Facts are presented in shuffled order.
  * self preference -> deterministic checks decide first; the LLM is only consulted for facts the string
                       matcher could not confirm, and the judge model can be a different family (judge_model).
  * verbosity bias  -> per fact binary verdicts; a "stated" verdict only counts if the judge quotes words that
                       really occur in the answer AND every number in the fact appears in the answer. Padding
                       cannot earn credit. Unsupported numbers anywhere in a long answer still fail grounding.
  * leniency/lying  -> a self test runs the judge on synthetic gold, corrupted and padded answers before the
                       evals; if it scores below 80%, the LLM judge is switched off and only deterministic
                       checks are used, and the report says so.
"""
from __future__ import annotations

import random

from . import prompts
from .llm import LLMClient
from .schemas import AgentResponse, CaseResult, EvalCase
from .textutil import fact_in_text, looks_like_refusal, numbers, quote_in_text, value_numbers


class Judge:
    def __init__(self, llm: LLMClient | None, use_llm: bool = True, seed: int = 7):
        self.llm = llm
        self.use_llm = use_llm and llm is not None
        self.rng = random.Random(seed)
        self.selftest_report: dict = {}

    # ----------------------------------------------------------- fact grading
    def grade_facts(self, question: str, answer: str, facts: list[str]) -> tuple[list[str], list[str], str]:
        self.llm_believed = set()
        matched = [f for f in facts if fact_in_text(f, answer, question=question)]
        missing = [f for f in facts if f not in matched]
        method = "deterministic"
        if missing and self.use_llm and answer.strip():
            order = list(missing)
            self.rng.shuffle(order)
            try:
                v = self.llm.json(
                    prompts.messages("judge_facts", question=question, answer=answer[:2500], facts="\n".join(f"{i+1}. {f}" for i, f in enumerate(order))),
                    max_tokens=400,
                )
                for item in v.get("verdicts", []) if isinstance(v, dict) else []:
                    try:
                        idx = int(item.get("fact")) - 1
                    except (TypeError, ValueError):
                        continue
                    if not (0 <= idx < len(order)) or not item.get("stated"):
                        continue
                    f = order[idx]
                    quote = str(item.get("quote", ""))
                    self.llm_believed.add(f)
                    # accept only with evidence: real quote from the answer + all value numbers of the fact present
                    if quote_in_text(quote, answer, 0.8) and value_numbers(f, question) <= numbers(answer):
                        if f in missing:
                            missing.remove(f)
                            matched.append(f)
                method = "deterministic + verified llm"
            except Exception:  # noqa: BLE001
                method = "deterministic (llm judge error)"
        return matched, missing, method

    # ------------------------------------------------------------------ score
    def score(self, case: EvalCase, resp: AgentResponse) -> CaseResult:
        retrieved_sources = sorted({r["doc"] for r in resp.retrieved})
        refused = resp.refused or (not resp.contract_ok and looks_like_refusal(resp.answer))
        # evidence = passage bodies + their section headings + tool results + the question itself
        evidence = " ".join(f'{r.get("section", "")} {r["text"]}' for r in resp.retrieved) + " " + " ".join(str(t.get("result", "")) for t in resp.tool_calls) + " " + case.question
        # label numbers ("Section 5", "Level 2", "Tier 1") are references, not claims
        ans_nums = value_numbers(resp.answer)
        unsupported = sorted(n for n in ans_nums - numbers(evidence) if not _trivial(n))
        retrieval_hit = (not case.expected_sources) or bool(set(case.expected_sources) & set(retrieved_sources))
        if case.type == "tool":
            retrieval_hit = True  # tool cases are served by csv_lookup, not by passages

        if case.expected_behavior == "refuse":
            refusal_ok = refused
            grounded = not unsupported or refused
            passed = refusal_ok and not (unsupported and not refused)
            res = CaseResult(
                case_id=case.id, type=case.type, split=case.split, question=case.question, expected_behavior="refuse",
                answer=resp.answer, refused=refused, citations=resp.citations, retrieved_sources=retrieved_sources, tool_calls=resp.tool_calls,
                contract_ok=resp.contract_ok, refusal_ok=refusal_ok, fact_recall=1.0, grounded=grounded, unsupported_numbers=unsupported,
                cited_expected=True, retrieval_hit=True, passed=passed, judge_method="deterministic", latency_s=resp.latency_s,
            )
            return res

        cits = set(resp.citations)
        good_cits = cits & set(retrieved_sources) & (set(case.expected_sources) or cits)
        citation_precision = round(len(good_cits) / len(cits), 3) if cits else (1.0 if refused else 0.0)
        relevance = _relevance(case.question, resp.answer) if not refused else None
        if refused:
            matched, missing, method = [], list(case.key_facts), "deterministic"
        else:
            matched, missing, method = self.grade_facts(case.question, resp.answer, case.key_facts)
        n = len(case.key_facts) or 1
        recall = len(matched) / n
        need = 1.0 if n <= 2 else 2 / 3
        cited_expected = (not case.expected_sources) or bool(set(case.expected_sources) & set(resp.citations)) or case.type == "tool"
        grounded = not unsupported
        passed = (not refused) and recall >= need - 1e-9 and grounded and resp.contract_ok and cited_expected
        suspect = bool(missing) and not refused and grounded and set(missing) <= getattr(self, "llm_believed", set())
        return CaseResult(
            case_id=case.id, type=case.type, split=case.split, question=case.question, expected_behavior="answer",
            answer=resp.answer, refused=refused, citations=resp.citations, retrieved_sources=retrieved_sources, tool_calls=resp.tool_calls,
            contract_ok=resp.contract_ok, refusal_ok=not refused, fact_recall=round(recall, 3), facts_matched=matched, facts_missing=missing,
            grounded=grounded, unsupported_numbers=unsupported, cited_expected=cited_expected, retrieval_hit=retrieval_hit,
            citation_precision=citation_precision, answer_relevance=relevance, passed=passed, judge_method=method, latency_s=resp.latency_s,
            suspected_eval_defect=suspect and not passed,
        )

    # -------------------------------------------------------------- self test
    def self_test(self, cases: list[EvalCase], k: int = 4) -> dict:
        """Calibrate the LLM part of the judge on answers whose correct grade we know."""
        if not self.use_llm:
            self.selftest_report = {"ran": False, "reason": "llm judge disabled"}
            return self.selftest_report
        pool = [c for c in cases if c.expected_behavior == "answer" and c.key_facts and c.type != "tool"]
        self.rng.shuffle(pool)
        pool = pool[:k]
        trials, correct = [], 0
        filler = ("Our team values clarity and we always aim to support every employee in a fair and transparent way. "
                  "Please read all related guidance carefully and reach out if anything is unclear. ") * 4
        for c in pool:
            gold = "Here is what applies: " + "; ".join(_paraphrase(f) for f in c.key_facts) + "."
            corrupted = "Here is what applies: " + "; ".join(_corrupt(f) for f in c.key_facts) + "."
            padded_wrong = filler + "In short, the usual practice applies and details vary by situation."
            padded_gold = filler + gold
            for label, ans, expect in (("gold_paraphrase", gold, True), ("numbers_corrupted", corrupted, False),
                                       ("long_but_empty", padded_wrong, False), ("long_and_correct", padded_gold, True)):
                # test the LLM path only: bypass deterministic matching on purpose
                matched, missing, _ = self._llm_only(c.question, ans, c.key_facts)
                verdict = len(missing) == 0
                ok = verdict == expect
                correct += ok
                trials.append({"case": c.id, "variant": label, "expected_pass": expect, "judge_pass": verdict, "agree": ok})
        acc = correct / len(trials) if trials else 1.0
        self.selftest_report = {"ran": True, "trials": len(trials), "accuracy": round(acc, 3), "details": trials,
                                "decision": "llm judge enabled" if acc >= 0.8 else "llm judge DISABLED (below 80% on known answers); deterministic checks only"}
        if acc < 0.8:
            self.use_llm = False
        return self.selftest_report

    def _llm_only(self, question, answer, facts):
        try:
            order = list(facts)
            v = self.llm.json(prompts.messages("judge_facts", question=question, answer=answer[:2500], facts="\n".join(f"{i+1}. {f}" for i, f in enumerate(order))), max_tokens=400)
            stated = set()
            for item in v.get("verdicts", []) if isinstance(v, dict) else []:
                try:
                    idx = int(item.get("fact")) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(order) and item.get("stated") and quote_in_text(str(item.get("quote", "")), answer, 0.8) and numbers(order[idx]) <= numbers(answer):
                    stated.add(order[idx])
            return list(stated), [f for f in order if f not in stated], "llm"
        except Exception:  # noqa: BLE001
            return [], list(facts), "error"


def _relevance(question: str, answer: str) -> float | None:
    try:
        from .embeddings import get_embedder

        emb = get_embedder("wordllama")
        if emb is None or not answer.strip():
            return None
        v = emb.embed([question, answer])
        return round(float(v[0] @ v[1]), 3)
    except Exception:  # noqa: BLE001
        return None


def _trivial(n: str) -> bool:
    """Numbers an answer may use without evidence: list markers, 0/1, small counts in prose."""
    try:
        return float(n) in (0, 1, 2, 3)
    except ValueError:
        return False


def _paraphrase(f: str) -> str:
    return f[0].lower() + f[1:] if f else f


def _corrupt(f: str) -> str:
    import re

    def bump(m):
        v = m.group(0).replace(",", "")
        try:
            x = float(v)
        except ValueError:
            return m.group(0)
        y = x * 2 + 3
        return str(int(y)) if y.is_integer() else f"{y:.2f}"

    out = re.sub(r"\d[\d,]*(?:\.\d+)?", bump, f)
    if out == f:
        out = "it is not allowed and " + "no " + f
    return out
