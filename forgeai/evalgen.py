"""Stage 4: eval generator. Builds the test set FROM THE DOCUMENTS, never by hand.

Distrust built in: every generated case is validated before it is accepted.
  * answerable: each key fact must be found (numbers exactly) in the source passage, else dropped
  * cross_doc: needs at least one verified fact from EACH of two different documents
  * ambiguous: rewrites must differ from the original but keep its facts/sources
  * out_of_scope: dropped if retrieval + guard finds the documents actually answer it
  * tool: built deterministically from CSV rows, with expected numbers computed in Python
Every rejected candidate is logged with its reason (eval_generation_log.json).
Cases are split into dev (the optimizer may look at failures) and holdout (reported only), so the loop
cannot simply overfit the test set.
"""
from __future__ import annotations

import random
import re

from . import prompts
from .docs import Document
from .guard import check_topic
from .llm import LLMClient
from .retrieval import Chunk, chunk_documents, default_index
from .schemas import EvalCase, Requirements
from .textutil import content_overlap, fact_in_text, jaccard, numbers, tokens


def _informative(c: Chunk) -> float:
    """Prefer passages with numbers, rules and enough text to ask about."""
    w = len(c.text.split())
    if w < 25:
        return 0
    score = min(w, 160) / 160
    score += 0.6 * min(len(numbers(c.text)), 4) / 4
    score += 0.3 * bool(re.search(r"\b(must|shall|eligible|entitled|maximum|minimum|within|days|limit|require)", c.text, re.I))
    return score


def _compact(fact: str, source: str, max_words: int = 15) -> str:
    """Small models copy whole sentences as 'key facts'. Keep the clauses that carry the numbers (or the most
    specific clause), capped at max_words, and only if the shortened fact is still verifiable in the source."""
    f = " ".join(fact.split())
    if len(f.split()) <= max_words:
        return f
    parts = [p.strip() for p in re.split(r",\s|;\s?|:\s|\.\s|\s\band\b\s|\bwhich\b|\bwhile\b", f) if p.strip()]
    keep = [p for p in parts if numbers(p)] or sorted(parts, key=lambda p: -len(tokens(p)))[:1]
    if parts[0] not in keep and len((parts[0] + " " + " ".join(keep)).split()) <= max_words:
        keep = [parts[0]] + keep   # keep the subject so the fact still says what the number is about
    words = " ".join(keep).split()
    if len(words) > max_words:
        # window centred on the first number so the value itself always survives
        idx = next((i for i, w in enumerate(words) if numbers(w)), 0)
        lo = max(0, min(idx - max_words // 2, len(words) - max_words))
        words = words[lo: lo + max_words]
    out = " ".join(words)
    return out if fact_in_text(out, source, 0.6) else f


def _evidence(facts: list[str], chunk: Chunk) -> list[dict]:
    """The sentence in the source passage that best supports each fact."""
    from .textutil import content_overlap

    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", chunk.text) if x.strip()]
    out = []
    for f in facts:
        best = max(sents, key=lambda x: (fact_in_text(f, x), content_overlap(f, x)), default="")
        if best and {"doc": chunk.doc_id, "quote": best} not in out:
            out.append({"doc": chunk.doc_id, "quote": best})
    return out


def _pick_chunks(chunks: list[Chunk], n: int, rng: random.Random) -> list[Chunk]:
    """Stratified across documents so every document is tested."""
    by_doc: dict[str, list[Chunk]] = {}
    for c in chunks:
        if _informative(c) > 0:
            by_doc.setdefault(c.doc_id, []).append(c)
    for v in by_doc.values():
        v.sort(key=lambda c: -_informative(c) + rng.random() * 0.4)
    picked, i = [], 0
    while len(picked) < n and any(by_doc.values()):
        doc = list(by_doc)[i % len(by_doc)]
        if by_doc[doc]:
            picked.append(by_doc[doc].pop(0))
        i += 1
    return picked


class EvalGenerator:
    def __init__(self, req: Requirements, docs: list[Document], llm: LLMClient, cfg, log=print):
        self.req, self.docs, self.llm, self.cfg, self.log = req, docs, llm, cfg, log
        self.rng = random.Random(cfg.seed)
        text_docs = [d for d in docs if d.kind != "csv"]
        self.chunks = chunk_documents(text_docs, chunk_size=140, overlap=0)
        self.all_index = default_index(docs, embedding=getattr(cfg, 'embedding', 'wordllama'))
        self.rejected: list[dict] = []
        self.cases: list[EvalCase] = []

    def _reject(self, kind, what, why):
        self.rejected.append({"type": kind, "candidate": what, "reason": why})

    def _necessary(self, question: str, facts: list[str], kind: str) -> list[str]:
        """Second opinion on every key fact: drop facts a correct answer to exactly this question would not need.
        Over-specified facts turn correct answers into false failures, so this makes the test fairer, not easier."""
        if len(facts) <= 1:
            return facts
        try:
            v = self.llm.json(prompts.messages("evalgen_fact_check", question=question, facts="\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))), max_tokens=300)
            keep = list(facts)
            for item in v.get("verdicts", []) if isinstance(v, dict) else []:
                try:
                    i = int(item.get("fact")) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(facts) and item.get("required") is False and facts[i] in keep:
                    keep.remove(facts[i])
                    self._reject(kind + "_fact", {"question": question, "fact": facts[i]}, f"fact not required by the question: {item.get('why', '')}")
            return keep or facts[:1]
        except Exception:  # noqa: BLE001
            return facts

    def _dup(self, q: str) -> bool:
        return any(jaccard(q, c.question) > 0.75 for c in self.cases)

    def _add(self, **kw):
        if kw.get("key_facts"):
            kw["key_facts"] = list(dict.fromkeys(kw["key_facts"]))
        kw["id"] = f"{kw['type'][:3]}-{sum(1 for c in self.cases if c.type == kw['type']) + 1:02d}"
        self.cases.append(EvalCase(**kw))

    # -------------------------------------------------------------- answerable
    def answerable(self, n: int):
        pool = _pick_chunks(self.chunks, n * 2, self.rng)
        made = 0
        for c in pool:
            if made >= n:
                break
            try:
                d = self.llm.json(prompts.messages("evalgen_answerable", audience=self.req.audience, source=c.doc_id, chunk=c.text), max_tokens=300)
            except Exception as e:  # noqa: BLE001
                self._reject("answerable", c.chunk_id, f"model error: {e}")
                continue
            q = str(d.get("question", "")).strip()
            facts = [str(f).strip() for f in d.get("key_facts", []) if str(f).strip()][:3]
            if not q or not facts:
                self._reject("answerable", d, "empty question or facts")
                continue
            if re.search(r"\b(excerpt|document|passage|text above)\b", q, re.I):
                self._reject("answerable", q, "question refers to the document itself")
                continue
            good = [_compact(f, c.text) for f in facts if fact_in_text(f, c.text, 0.6)]
            restated = [f for f in good if content_overlap(f, q) >= 0.75 and not (numbers(f) - numbers(q))]
            good = [f for f in good if f not in restated]
            if good:
                good = self._necessary(q, good, "answerable")
            bad = [f for f in facts if f not in good] + [f"(restates the question) {f}" for f in restated]
            if not good:
                self._reject("answerable", {"q": q, "facts": facts}, "no key fact is verifiably in the source passage (possible hallucinated fact)")
                continue
            if self._dup(q):
                self._reject("answerable", q, "near duplicate of an existing case")
                continue
            self._add(type="answerable", question=q, expected_behavior="answer", expected_sources=[c.doc_id], key_facts=good, origin=c.chunk_id, evidence=_evidence(good, c),
                      note=(f"dropped unverifiable facts: {bad}" if bad else ""))
            made += 1

    # --------------------------------------------------------------- cross doc
    def cross_doc(self, n: int):
        docs = sorted({c.doc_id for c in self.chunks})
        if len(docs) < 2:
            self._reject("cross_doc", None, "only one text document; cross document cases not possible")
            return
        pairs = []
        cand = [c for c in self.chunks if _informative(c) > 0.4]
        for i, a in enumerate(cand):
            for b in cand[i + 1 :]:
                if a.doc_id != b.doc_id:
                    pairs.append((jaccard(a.text, b.text), a, b))
        pairs.sort(key=lambda x: -x[0])
        used, made = set(), 0
        for _, a, b in pairs[: n * 6]:
            if made >= n:
                break
            if a.chunk_id in used or b.chunk_id in used:
                continue
            try:
                d = self.llm.json(prompts.messages("evalgen_crossdoc", audience=self.req.audience, source_a=a.doc_id, chunk_a=a.text, source_b=b.doc_id, chunk_b=b.text), max_tokens=350)
            except Exception as e:  # noqa: BLE001
                self._reject("cross_doc", (a.chunk_id, b.chunk_id), f"model error: {e}")
                continue
            q = str(d.get("question", "")).strip()
            fa = [_compact(f, a.text) for f in map(str, d.get("facts_a", []) or []) if fact_in_text(f, a.text, 0.6)][:2]
            fb = [_compact(f, b.text) for f in map(str, d.get("facts_b", []) or []) if fact_in_text(f, b.text, 0.6)][:2]
            if not q:
                self._reject("cross_doc", (a.chunk_id, b.chunk_id), "model said the passages cannot be combined")
                continue
            if fa and fb:
                kept = self._necessary(q, fa + fb, "cross_doc")
                fa, fb = [f for f in fa if f in kept], [f for f in fb if f in kept]
            if not fa or not fb:
                self._reject("cross_doc", {"q": q, "facts_a": d.get("facts_a"), "facts_b": d.get("facts_b")}, "needs a verified fact from each document")
                continue
            if self._dup(q):
                continue
            used |= {a.chunk_id, b.chunk_id}
            self._add(type="cross_doc", question=q, expected_behavior="answer", expected_sources=[a.doc_id, b.doc_id], key_facts=fa + fb, origin=f"{a.chunk_id} + {b.chunk_id}",
                      evidence=_evidence(fa, a) + _evidence(fb, b))
            made += 1

    # --------------------------------------------------------------- ambiguous
    def ambiguous(self, n: int):
        base = [c for c in self.cases if c.type == "answerable"]
        self.rng.shuffle(base)
        base = base[:n]
        if not base:
            return
        qs = "\n".join(f"{i+1}. {c.question}" for i, c in enumerate(base))
        try:
            d = self.llm.json(prompts.messages("evalgen_ambiguous", questions=qs), max_tokens=500)
            rew = [str(x) for x in d.get("rewrites", [])]
        except Exception as e:  # noqa: BLE001
            self._reject("ambiguous", qs, f"model error: {e}")
            return
        for orig, r in zip(base, rew):
            r = re.sub(r"^\d+[.)]\s*", "", r).strip()
            if not r or jaccard(r, orig.question) > 0.85:
                self._reject("ambiguous", r, "rewrite too close to the original")
                continue
            # numbers the user put in the question must survive the rewrite
            if not numbers(orig.question) <= numbers(r):
                self._reject("ambiguous", r, "rewrite changed numbers in the question")
                continue
            self._add(type="ambiguous", question=r, expected_behavior="answer", expected_sources=orig.expected_sources, key_facts=orig.key_facts, origin=f"rewrite of {orig.id}",
                      evidence=orig.evidence, note=f"original: {orig.question}")

    # ------------------------------------------------------------ out of scope
    def out_of_scope(self, n: int):
        try:
            d = self.llm.json(
                prompts.messages("evalgen_out_of_scope", audience=self.req.audience, scope=self.req.scope + " Topics: " + "; ".join(self.req.must_answer_topics),
                                 refuse_topics="; ".join(self.req.must_refuse_topics), n=n + 2),
                max_tokens=600,
            )
            qs = [str(q).strip() for q in d.get("questions", []) if str(q).strip()]
        except Exception as e:  # noqa: BLE001
            self._reject("out_of_scope", None, f"model error: {e}")
            return
        made = 0
        for q in qs:
            if made >= n:
                break
            if self._dup(q):
                continue
            chk = check_topic(q, self.all_index, self.llm)
            if chk.status == "supported":
                self._reject("out_of_scope", q, f"documents actually answer this ({chk.sources}); not a valid refusal case")
                continue
            from .textutil import content_overlap

            topic = max(self.req.must_refuse_topics, key=lambda t: content_overlap(t, q), default="")
            reason = (f"falls under must-refuse topic '{topic}'" if topic and content_overlap(topic, q) >= 0.5 else "outside the assistant's scope")
            reason += f"; documents do not answer it (guard: {chk.status})"
            self._add(type="out_of_scope", question=q, expected_behavior="refuse", origin="must_refuse / off domain", refusal_reason=reason)
            made += 1

    def ungroundable(self):
        topics = self.req.ungroundable_topics[:3]
        if not topics:
            return
        try:
            d = self.llm.json(prompts.messages("evalgen_ungroundable", topics="; ".join(topics), audience=self.req.audience), max_tokens=300)
            qs = [str(q).strip() for q in d.get("questions", []) if str(q).strip()]
        except Exception as e:  # noqa: BLE001
            self._reject("ungroundable", topics, f"model error: {e}")
            return
        for q, t in zip(qs, topics):
            self._add(type="ungroundable", question=q, expected_behavior="refuse", origin=f"ungroundable topic: {t}",
                      refusal_reason=f"the brief asks for '{t}' but the documents do not cover it; answering would mean inventing it")

    # ---------------------------------------------------------------- conflict
    def conflicts(self):
        """Questions that touch a documented contradiction: a correct answer gives BOTH values."""
        for k in self.req.conflicts[:3]:
            try:
                d = self.llm.json(prompts.messages("evalgen_conflict", about=k.about, audience=self.req.audience), max_tokens=150)
                q = str(d.get("question", "")).strip()
            except Exception:  # noqa: BLE001
                q = ""
            q = q or f"What is the rule on {k.about}?"
            self._add(type="conflict", question=q, expected_behavior="answer", expected_sources=[k.doc_a, k.doc_b], key_facts=k.values[:3],
                      evidence=[{"doc": k.doc_a, "quote": k.quote_a}, {"doc": k.doc_b, "quote": k.quote_b}], origin=f"conflict: {k.about}",
                      note="documents contradict each other; a correct answer states both values")

    # ------------------------------------------------------------------- tools
    def tool_cases(self, n: int, tool_names: list[str]):
        """Deterministic, numerically exact cases from CSV rows: no LLM can get the expected value wrong."""
        csvs = [d for d in self.docs if d.kind == "csv" and d.rows]
        if not csvs or not tool_names:
            return
        d = csvs[0]
        cols = d.columns
        num_cols = [c for c in cols if all(_num(r.get(c)) is not None for r in d.rows[:20])]
        id_cols = [c for c in cols if c not in num_cols]
        if not num_cols or not id_cols:
            return
        name_col = next((c for c in id_cols if re.search(r"desc|name|item|title", c, re.I)), id_cols[-1])
        key_col = next((c for c in id_cols if re.search(r"(part|item|sku|code|id)\b|number|no\b", c, re.I)), id_cols[0])
        price_col = next((c for c in num_cols if re.search(r"price|cost|rate|amount", c, re.I)), None)
        other_num = [c for c in num_cols if c != price_col]
        rows = list(d.rows)
        self.rng.shuffle(rows)
        made = 0
        for r in rows:
            if made >= n:
                break
            key, name = r.get(key_col, "").strip(), r.get(name_col, "").strip()
            if not key:
                continue
            if made % 2 == 0 and price_col and "calculator" in tool_names:
                qty = self.rng.choice([3, 4, 6, 12])
                total = round(_num(r[price_col]) * qty, 2)
                q = f"What would {qty} units of {name} ({key}) cost in total at the catalogue {price_col.lower().replace('_', ' ')}?"
                facts = [_fmt(total)]
                note = f"expected = {r[price_col]} x {qty} computed in Python"
            else:
                col = other_num[made % len(other_num)] if other_num else price_col
                q = f"What is the {col.lower().replace('_', ' ')} for part {key}?"
                facts = [_fmt(_num(r[col]))]
                note = f"exact value from row {key}"
            row_txt = "; ".join(f"{k}: {v}" for k, v in r.items())
            self._add(type="tool", question=q, expected_behavior="answer", expected_sources=[d.doc_id], key_facts=facts, origin=f"{d.doc_id}:{key}", note=note,
                      evidence=[{"doc": d.doc_id, "quote": row_txt}])
            made += 1

    # -------------------------------------------------------------------- run
    def run(self, tool_names: list[str]) -> list[EvalCase]:
        c = self.cfg
        self.log("    answerable ...")
        self.answerable(c.n_answerable)
        self.log("    cross document ...")
        self.cross_doc(c.n_cross_doc)
        self.log("    ambiguous phrasing ...")
        self.ambiguous(c.n_ambiguous)
        self.log("    out of scope ...")
        self.out_of_scope(c.n_out_of_scope)
        self.ungroundable()
        self.conflicts()
        self.tool_cases(c.n_tool, tool_names)
        self._split()
        return self.cases

    def _split(self):
        """Stratified dev/holdout split. Ambiguous rewrites follow their source case to avoid leakage."""
        rng = random.Random(self.cfg.seed + 1)
        by_type: dict[str, list[EvalCase]] = {}
        for x in self.cases:
            if x.type != "ambiguous":
                by_type.setdefault(x.type, []).append(x)
        for lst in by_type.values():
            rng.shuffle(lst)
            k = round(len(lst) * self.cfg.holdout_fraction)
            if len(lst) >= 3 and k == 0:
                k = 1
            for x in lst[:k]:
                x.split = "holdout"
        ids = {x.id: x for x in self.cases}
        for x in self.cases:
            if x.type == "ambiguous":
                src = x.origin.replace("rewrite of ", "")
                x.split = ids[src].split if src in ids else "dev"


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"
