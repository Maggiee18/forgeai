"""Chunking + retrieval.

Hybrid retrieval: a BM25 keyword ranking and a dense embedding ranking, fused with reciprocal rank fusion
(RRF). RRF combines ranks, not raw scores, so BM25's unbounded scores and cosine similarities never need
calibrating against each other. BM25 is exact on part numbers, amounts and policy terms; embeddings catch
paraphrases ("vacation" vs "annual leave"). The optimizer tunes every parameter here per agent:
chunk size/overlap, top_k, min_score, query expansion, and the dense/keyword weights."""
from __future__ import annotations

import math
import re

import numpy as np
from collections import Counter
from dataclasses import dataclass

from .docs import Document
from .textutil import tokens


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    section: str = ""

    def cite(self) -> str:
        return f"{self.doc_id}" + (f" > {self.section}" if self.section else "")


_HEAD = re.compile(r"^(\d+(\.\d+)*\.?\s+[A-Z].{0,70}|[A-Z][A-Za-z/&,\- ]{2,60})$")


def _paragraphs(text: str):
    """Yield (section, paragraph) pairs, tracking the most recent heading."""
    section = ""
    for block in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        buf = []
        for line in lines:
            if len(line) <= 75 and _HEAD.match(line) and not line.endswith("."):
                if buf:
                    yield section, " ".join(buf)
                    buf = []
                section = line
            else:
                buf.append(line)
        if buf:
            yield section, " ".join(buf)


def chunk_documents(docs: list[Document], chunk_size: int = 160, overlap: int = 30, csv_rows_per_chunk: int = 1) -> list[Chunk]:
    chunks: list[Chunk] = []
    for d in docs:
        if d.kind == "csv":
            for i in range(0, len(d.rows), csv_rows_per_chunk):
                rows = d.rows[i : i + csv_rows_per_chunk]
                text = "\n".join("; ".join(f"{k}: {v}" for k, v in r.items()) for r in rows)
                chunks.append(Chunk(f"{d.doc_id}#row{i+1}", d.doc_id, text, section=f"row {i+1}"))
            continue
        n = 0
        cur_words: list[str] = []
        cur_section = ""
        for section, para in _paragraphs(d.text):
            words = para.split()
            if cur_words and (section != cur_section or len(cur_words) + len(words) > chunk_size):
                n += 1
                chunks.append(Chunk(f"{d.doc_id}#c{n}", d.doc_id, " ".join(cur_words), cur_section))
                tail = cur_words[-overlap:] if (overlap and section == cur_section) else []
                cur_words = list(tail)
            cur_section = section
            # split paragraphs that are longer than a chunk
            while len(cur_words) + len(words) > chunk_size:
                take = max(1, chunk_size - len(cur_words))
                cur_words += words[:take]
                words = words[take:]
                n += 1
                chunks.append(Chunk(f"{d.doc_id}#c{n}", d.doc_id, " ".join(cur_words), cur_section))
                cur_words = cur_words[-overlap:] if overlap else []
                if len(cur_words) >= chunk_size:
                    cur_words = []
            cur_words += words
        if cur_words:
            n += 1
            chunks.append(Chunk(f"{d.doc_id}#c{n}", d.doc_id, " ".join(cur_words), cur_section))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75, query_expansion: dict | None = None):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.expansion = {k.lower(): v for k, v in (query_expansion or {}).items()}
        # index section headings + doc name along with body so "leave policy" style queries land
        self.docs_tokens = [tokens(f"{c.section} {c.section} {c.doc_id.rsplit('.',1)[0].replace('_',' ')} {c.text}") for c in chunks]
        self.tf = [Counter(t) for t in self.docs_tokens]
        self.dl = [len(t) for t in self.docs_tokens]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        df = Counter()
        for t in self.docs_tokens:
            df.update(set(t))
        N = len(chunks) or 1
        self.idf = {w: math.log(1 + (N - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.vocab = set(df)

    def expand(self, query: str) -> list[str]:
        q = tokens(query)
        extra = []
        ql = query.lower()
        for term, syns in self.expansion.items():
            if term in ql or tokens(term) and set(tokens(term)) <= set(q):
                for s in syns:
                    extra += tokens(s)
        return q + extra

    def score(self, q_tokens: list[str], i: int) -> float:
        s = 0.0
        tf, dl = self.tf[i], self.dl[i]
        for w in q_tokens:
            if w not in tf:
                continue
            f = tf[w]
            s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def search(self, query: str, top_k: int = 4, min_score: float = 0.0) -> list[tuple[Chunk, float]]:
        q = self.expand(query)
        scored = [(c, self.score(q, i)) for i, c in enumerate(self.chunks)]
        scored = [x for x in scored if x[1] > 0]
        scored.sort(key=lambda x: -x[1])
        if not scored:
            return []
        top = scored[0][1]
        # min_score is relative to the best hit, so it transfers across corpora
        res = [x for x in scored if x[1] >= min_score * top]
        return res[:top_k]


class HybridIndex:
    """BM25 + dense embeddings fused with weighted reciprocal rank fusion."""

    def __init__(self, chunks: list[Chunk], embedder, query_expansion: dict | None = None, rrf_k: int = 60,
                 bm25_weight: float = 1.0, dense_weight: float = 1.0):
        self.bm25 = BM25Index(chunks, query_expansion=query_expansion)
        self.chunks, self.vocab = chunks, self.bm25.vocab
        self.embedder = embedder
        self.rrf_k, self.wb, self.wd = rrf_k, bm25_weight, dense_weight
        # section heading is embedded with the body: it carries the topic word the body often omits
        self.matrix = embedder.embed([f"{c.section}. {c.text}" for c in chunks]) if chunks else None

    def expand(self, query: str):
        return self.bm25.expand(query)

    def search(self, query: str, top_k: int = 4, min_score: float = 0.0) -> list[tuple[Chunk, float]]:
        n = len(self.chunks)
        if not n:
            return []
        depth = min(n, max(top_k * 5, 20))
        fused = {}
        for rank, (c, _) in enumerate(self.bm25.search(query, top_k=depth)):
            fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + self.wb / (self.rrf_k + rank + 1)
        if self.wd > 0:
            # expansion terms help the dense side too (e.g. "PTO" -> "annual leave")
            extra = [s for t, syns in self.bm25.expansion.items() if t in query.lower() for s in syns]
            q = self.embedder.embed([query + (" " + " ".join(extra) if extra else "")])[0]
            sims = self.matrix @ q
            for rank, i in enumerate(np.argsort(-sims)[:depth]):
                if sims[i] <= 0:
                    break
                cid = self.chunks[i].chunk_id
                fused[cid] = fused.get(cid, 0.0) + self.wd / (self.rrf_k + rank + 1)
        if not fused:
            return []
        by_id = {c.chunk_id: c for c in self.chunks}
        ranked = sorted(fused.items(), key=lambda x: -x[1])
        top = ranked[0][1]
        return [(by_id[cid], sc) for cid, sc in ranked if sc >= min_score * top][:top_k]


def build_index(docs: list[Document], retrieval_cfg: dict):
    chunks = chunk_documents(
        docs,
        chunk_size=int(retrieval_cfg.get("chunk_size", 160)),
        overlap=int(retrieval_cfg.get("chunk_overlap", 30)),
        csv_rows_per_chunk=int(retrieval_cfg.get("csv_rows_per_chunk", 1)),
    )
    qe = retrieval_cfg.get("query_expansion") or {}
    strategy = retrieval_cfg.get("strategy", "bm25")
    if strategy in ("hybrid", "dense"):
        from .embeddings import get_embedder

        emb = get_embedder(_embedding_spec(retrieval_cfg))
        if emb is not None:
            return HybridIndex(chunks, emb, query_expansion=qe, rrf_k=int(retrieval_cfg.get("rrf_k", 60)),
                               bm25_weight=0.0 if strategy == "dense" else float(retrieval_cfg.get("bm25_weight", 1.0)),
                               dense_weight=float(retrieval_cfg.get("dense_weight", 1.0)))
    return BM25Index(chunks, query_expansion=qe)


def _embedding_spec(cfg: dict) -> str:
    e = cfg.get("embedding") or {}
    if e.get("provider") == "fastembed":
        return f"fastembed:{e.get('model', 'BAAI/bge-small-en-v1.5')}"
    if e.get("provider") == "none":
        return "none"
    return "wordllama"


def default_index(docs: list[Document], chunk_size: int = 160, overlap: int = 30, embedding: str = "wordllama"):
    """Index used by factory stages (guard, eval validation) that are not tuned per agent."""
    cfg = {"strategy": "hybrid", "chunk_size": chunk_size, "chunk_overlap": overlap, "embedding": _spec_to_cfg(embedding)}
    return build_index(docs, cfg)


def _spec_to_cfg(spec: str) -> dict:
    if spec.startswith("fastembed:"):
        return {"provider": "fastembed", "model": spec.split(":", 1)[1]}
    return {"provider": spec}
