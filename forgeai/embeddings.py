"""Embedding providers behind one interface.

  wordllama                         default. 16 MB static embedding model shipped INSIDE the pip package, so it
                                    works fully offline: laptops, free hosting tiers, a review room without internet.
  fastembed:<model>                 e.g. fastembed:BAAI/bge-small-en-v1.5. Better quality, ONNX (no PyTorch), but
                                    downloads the model from Hugging Face on first use.
  none                              keyword retrieval only.

If a requested provider cannot load (no network, package missing), the factory falls back to wordllama and
records the provider that was actually used in the agent definition, so the definition never lies about how
it retrieves.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger("forgeai.embeddings")


class Embedder:
    provider = "base"
    model = ""
    dim = 0

    def __init__(self):
        self._cache: dict[str, np.ndarray] = {}

    def _embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def embed(self, texts: list[str]) -> np.ndarray:
        """L2-normalised embeddings, cached by text hash (chunks are re-embedded on every optimizer trial)."""
        keys = [hashlib.sha1(t.encode("utf-8", "ignore")).hexdigest() for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if k not in self._cache]
        if missing:
            vecs = np.asarray(self._embed([t for _, t in missing]), dtype=np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs = vecs / np.maximum(norms, 1e-9)
            for (k, _), v in zip(missing, vecs):
                self._cache[k] = v
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._cache[k] for k in keys])

    def describe(self) -> dict:
        return {"provider": self.provider, "model": self.model, "dim": self.dim}


class WordLlamaEmbedder(Embedder):
    provider, model = "wordllama", "l2_supercat_256"

    def __init__(self):
        super().__init__()
        import wordllama
        import wordllama.wordllama as w

        # wordllama ships its weights + tokenizer in the wheel but looks for the tokenizer under a different folder
        # name, then tries Hugging Face. Copy the bundled files into a local cache so loading never needs a network.
        pkg = Path(wordllama.__file__).parent
        cache = Path(tempfile.gettempdir()) / "forgeai_wordllama"
        for ft, src in (("tokenizer", pkg / "tokenizers" / "l2_supercat_tokenizer_config.json"), ("weights", pkg / "weights" / "l2_supercat_256.safetensors")):
            d = w.WordLlama.get_file_path(ft, cache)
            d.mkdir(parents=True, exist_ok=True)
            if src.exists() and not (d / src.name).exists():
                shutil.copy(src, d / src.name)
        logging.getLogger("wordllama").setLevel(logging.ERROR)
        self.wl = w.WordLlama.load(cache_dir=cache, disable_download=True)
        self.dim = 256

    def _embed(self, texts):
        return self.wl.embed(texts, norm=True)


class FastEmbedEmbedder(Embedder):
    provider = "fastembed"

    def __init__(self, model: str):
        super().__init__()
        from fastembed import TextEmbedding

        self.model = model
        self.m = TextEmbedding(model_name=model)
        self.dim = len(next(iter(self.m.embed(["probe"]))))

    def _embed(self, texts):
        return np.stack(list(self.m.embed(texts)))


@lru_cache(maxsize=4)
def get_embedder(spec: str = "wordllama") -> Embedder | None:
    spec = (spec or "wordllama").strip()
    if spec == "none":
        return None
    if spec.startswith("fastembed:"):
        try:
            return FastEmbedEmbedder(spec.split(":", 1)[1])
        except Exception as e:  # noqa: BLE001
            log.warning("fastembed model %s unavailable (%s); falling back to wordllama", spec, e)
    try:
        return WordLlamaEmbedder()
    except Exception as e:  # noqa: BLE001
        log.warning("wordllama unavailable (%s); using keyword retrieval only", e)
        return None
