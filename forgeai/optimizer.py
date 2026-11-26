"""Stage 6b: optimizer. Applies a TARGETED fix per failure category, never a full regeneration.

  retrieval_miss -> learn query expansions for the missed wording (LLM proposes, vocabulary verifies), then a
                    small grid search over top_k / chunk size / min_score scored deterministically by how many
                    expected facts land in the retrieved text (no LLM calls, no guessing).
  hallucination  -> patch only the GROUNDING section.
  wrong_refusal  -> patch only the REFUSAL section (over or under refusal described separately).
  prompt_defect  -> patch only the STYLE section (completeness, citations, format).

Every patch is checked: it must not quote eval questions (overfitting guard), must stay short, and the
factory's hard guardrails (not-groundable topics, must-refuse list) are re-applied after it.
Only DEV failures are shown to the optimizer; holdout cases stay unseen.
"""
from __future__ import annotations

import copy
import re

from . import prompts
from .docs import Document
from .llm import LLMClient
from .retrieval import build_index
from .schemas import AgentDefinition, CaseResult, EvalCase, Requirements
from .textutil import fact_in_text, tokens

SECTION_FOR = {"hallucination": "grounding", "wrong_refusal": "refusal", "prompt_defect": "style"}


def _ngrams(s: str, n: int = 7) -> set:
    w = re.findall(r"\w+", s.lower())
    return {" ".join(w[i : i + n]) for i in range(len(w) - n + 1)}


def quotes_eval(text: str, cases: list[EvalCase]) -> bool:
    g = _ngrams(text)
    return any(g & _ngrams(c.question) for c in cases)


def retrieval_fact_coverage(defn: AgentDefinition, docs: list[Document], cases: list[EvalCase], retrieval: dict) -> float:
    idx = build_index(docs, retrieval)
    tot, hit = 0, 0
    for c in cases:
        if c.expected_behavior != "answer" or c.type == "tool" or not c.key_facts:
            continue
        got = " ".join(ch.text for ch, _ in idx.search(c.question, top_k=int(retrieval["top_k"]), min_score=float(retrieval.get("min_score", 0))))
        for f in c.key_facts:
            tot += 1
            hit += fact_in_text(f, got)
    return hit / tot if tot else 1.0


class Optimizer:
    def __init__(self, req: Requirements, docs: list[Document], llm: LLMClient, log=print):
        self.req, self.docs, self.llm, self.log = req, docs, llm, log

    # ------------------------------------------------------------- retrieval
    def learn_expansions(self, defn: AgentDefinition, misses: list[tuple[EvalCase, CaseResult]]) -> dict:
        idx = build_index(self.docs, defn.retrieval)
        pairs = []
        for case, _ in misses[:6]:
            best = None
            for ch in idx.chunks:
                if case.expected_sources and ch.doc_id not in case.expected_sources:
                    continue
                k = sum(fact_in_text(f, ch.text) for f in case.key_facts)
                if k and (best is None or k > best[0]):
                    best = (k, ch)
            if best:
                pairs.append(f"QUESTION: {case.question}\nPASSAGE: {best[1].text[:700]}")
        if not pairs:
            return {}
        try:
            d = self.llm.json(prompts.messages("optimizer_expansion", pairs="\n\n".join(pairs)), max_tokens=500)
        except Exception:  # noqa: BLE001
            return {}
        vocab = idx.vocab
        out = {}
        for m in d.get("mappings", []) if isinstance(d, dict) else []:
            u = str(m.get("user_term", "")).strip().lower()
            terms = [t for t in (m.get("document_terms") or []) if isinstance(t, str)]
            # verify: document terms must exist in the corpus vocabulary
            terms = [t for t in terms if tokens(t) and all(x in vocab for x in tokens(t))]
            if u and terms and len(u) <= 40:
                out[u] = terms[:3]
        return out

    def fix_retrieval(self, defn: AgentDefinition, misses, dev_cases: list[EvalCase]) -> tuple[dict, dict]:
        base = copy.deepcopy(defn.retrieval)
        before = retrieval_fact_coverage(defn, self.docs, dev_cases, base)
        exp = self.learn_expansions(defn, misses)
        merged = dict(base.get("query_expansion") or {})
        for k, v in exp.items():
            merged[k] = sorted(set(merged.get(k, [])) | set(v))
        cs = int(base["chunk_size"])
        qe = {**base, "query_expansion": merged}
        scored = []
        for top_k in sorted({int(base["top_k"]), int(base["top_k"]) + 2, int(base["top_k"]) + 4}):
            for chunk in sorted({cs, int(cs * 0.65), int(cs * 1.4)}):
                for ms in sorted({float(base.get("min_score", 0.15)), 0.0}):
                    weights = [(1.0, 1.0), (1.0, 0.5), (0.5, 1.0)] if base.get("strategy") == "hybrid" else [(1.0, 0.0)]
                    for wb, wd in weights:
                        cand = {**qe, "top_k": min(top_k, 10), "chunk_size": chunk, "chunk_overlap": int(chunk * 0.2), "min_score": ms, "bm25_weight": wb, "dense_weight": wd}
                        scored.append((retrieval_fact_coverage(defn, self.docs, dev_cases, cand), -cand["top_k"] * chunk, cand))
        # highest coverage wins; ties go to the smaller context (cheaper, less distraction for a small model)
        top = max(scored, key=lambda x: (round(x[0], 6), x[1]))
        best, best_score = (top[2], top[0]) if top[0] > before + 1e-9 else (base, before)
        change = {
            "category": "retrieval_miss",
            "target": "retrieval",
            "before": {k: base.get(k) for k in ("top_k", "chunk_size", "min_score", "bm25_weight", "dense_weight")} | {"expansions": len(base.get("query_expansion") or {})},
            "after": {k: best.get(k) for k in ("top_k", "chunk_size", "min_score", "bm25_weight", "dense_weight")} | {"expansions": len(best.get("query_expansion") or {})},
            "learned_expansions": exp,
            "rationale": f"dev fact coverage of retrieved text {before:.0%} -> {best_score:.0%} (deterministic grid search)",
        }
        return best, change

    # ----------------------------------------------------------- prompt patch
    def patch_section(self, defn: AgentDefinition, category: str, failing: list[tuple[EvalCase, CaseResult]], dev_cases: list[EvalCase]) -> tuple[str | None, dict]:
        section = SECTION_FOR[category]
        if category == "wrong_refusal":
            over = [r for _, r in failing if r.expected_behavior == "answer"]
            under = [r for _, r in failing if r.expected_behavior == "refuse"]
            desc = []
            if over:
                desc.append(f"- OVER-REFUSAL on {len(over)} questions: the answer WAS in the excerpts but the assistant refused. Examples of the kind of question: "
                            + " | ".join(r.question for r in over[:3]))
            if under:
                desc.append(f"- UNDER-REFUSAL on {len(under)} questions: the assistant answered questions it must decline. Examples: "
                            + " | ".join(r.question for r in under[:3]))
            failures = "\n".join(desc)
        else:
            failures = "\n".join(f"- {r.diagnosis}. Question type: {c.type}. Answer given (truncated): {r.answer[:160]}" for c, r in failing[:6])
        current = defn.system_prompt_sections.get(section, "")
        try:
            d = self.llm.json(prompts.messages("optimizer_patch", category=category, failures=failures, section=section, current=current), max_tokens=600)
            text = str(d.get("section_text", "")).strip()
            rationale = str(d.get("rationale", "")).strip()
        except Exception as e:  # noqa: BLE001
            return None, {"category": category, "target": f"prompt.{section}", "skipped": f"model error: {e}"}
        if not text or len(text) > 1800:
            return None, {"category": category, "target": f"prompt.{section}", "skipped": "patch empty or too long"}
        if quotes_eval(text, dev_cases):
            return None, {"category": category, "target": f"prompt.{section}", "skipped": "patch quoted eval questions (overfitting guard rejected it)"}
        return text, {"category": category, "target": f"prompt.{section}", "before": current, "after": text, "rationale": rationale}

    def reapply_guardrails(self, sections: dict) -> dict:
        s = dict(sections)
        missing = [t for t in self.req.ungroundable_topics if t.lower() not in s.get("refusal", "").lower()]
        if missing:
            s["refusal"] = s.get("refusal", "").rstrip() + "\nThe documents do NOT cover the following, so never answer them from memory; say they are not covered and set refused to true: " + "; ".join(missing) + "."
        if self.req.conflicts and "contradiction" not in s.get("grounding", "").lower():
            s["grounding"] = s.get("grounding", "").rstrip() + "\nKnown contradictions between documents: " + "; ".join(f"{c.about} ({c.doc_a} vs {c.doc_b})" for c in self.req.conflicts) + ". Give BOTH versions with their sources."
        miss_r = [t for t in self.req.must_refuse_topics if t.lower()[:20] not in s.get("refusal", "").lower()]
        if miss_r and len(miss_r) == len(self.req.must_refuse_topics):
            s["refusal"] = s["refusal"].rstrip() + "\nAlways refuse: " + "; ".join(self.req.must_refuse_topics) + "."
        return s

    # ------------------------------------------------------------------- run
    def improve(self, defn: AgentDefinition, results: list[CaseResult], cases: list[EvalCase], max_categories: int = 2, exclude: set | None = None) -> tuple[AgentDefinition, list[dict]]:
        by_id = {c.id: c for c in cases}
        dev_cases = [c for c in cases if c.split == "dev"]
        # suspected test defects are excluded: changing the agent cannot fix a wrong test, it can only overfit it
        dev_fail = [(by_id[r.case_id], r) for r in results if not r.passed and r.split == "dev" and not r.suspected_eval_defect]
        groups: dict[str, list] = {}
        for c, r in dev_fail:
            groups.setdefault(r.failure_category, []).append((c, r))
        new = defn.model_copy(deep=True)
        new.version = defn.version + 1
        changes = []
        exclude = exclude or set()
        order = [k for k in sorted(groups, key=lambda k: -len(groups[k])) if k not in exclude]
        for k in groups:
            if k in exclude:
                changes.append({"category": k, "target": "-", "skipped": "an earlier fix for this category was reverted; not retrying the same targeted fix", "addressed_cases": [c.id for c, _ in groups[k]]})
        applied = 0
        for cat in order:
            if applied >= max_categories:
                break
            failing = groups[cat]
            ids = [c.id for c, _ in failing]
            if cat == "retrieval_miss":
                ret, ch = self.fix_retrieval(new, failing, dev_cases)
                if ret != new.retrieval:
                    new.retrieval = ret
                    ch["addressed_cases"] = ids
                    changes.append(ch)
                    applied += 1
                else:
                    changes.append({**ch, "skipped": "no retrieval setting improved dev coverage", "addressed_cases": ids})
                continue
            text, ch = self.patch_section(new, cat, failing, dev_cases)
            ch["addressed_cases"] = ids
            if text:
                new.system_prompt_sections[SECTION_FOR[cat]] = text
                new.system_prompt_sections = self.reapply_guardrails(new.system_prompt_sections)
                applied += 1
            changes.append(ch)
        return new, changes
