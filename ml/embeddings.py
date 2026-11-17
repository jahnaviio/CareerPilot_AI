"""Embedding backends behind one interface.

* SentenceTransformerEmbedder  - real semantic embeddings (default when the package + model are available).
* HashingEmbedder              - dependency-free fallback (feature-hashed word uni/bi-grams, sublinear TF).
                                  It captures lexical overlap only, NOT deep semantics. It exists so the app
                                  and the test-suite run without downloading a model, and it is always labelled
                                  in the UI/README when it is the active backend.
"""
from __future__ import annotations

import hashlib
import logging
import re
from functools import lru_cache

import numpy as np

from config import settings

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = set("the and for with that this from are was were you your our will have has had not but all any can per via using use used into out over under more than their they them its who what when where which while also etc".split())


class Embedder:
    name = "base"
    is_semantic = False
    sim_floor = 0.0   # cosine at/below which semantic similarity is treated as "unrelated"
    sim_ceil = 1.0    # cosine at/above which it is treated as "very similar"

    def encode(self, texts: list[str]) -> np.ndarray:  # (n, d), L2-normalised
        raise NotImplementedError

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.encode([a, b])
        return float(np.dot(va, vb))

    def calibrated(self, cosine: float) -> float:
        """Map a raw cosine into 0..1 using this backend's documented floor/ceiling."""
        return float(min(1.0, max(0.0, (cosine - self.sim_floor) / (self.sim_ceil - self.sim_floor))))


class HashingEmbedder(Embedder):
    name = "hashing-bow"
    is_semantic = False
    sim_floor, sim_ceil = 0.03, 0.40

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _tokens(self, text: str) -> list[str]:
        toks = [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]
        return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            counts: dict[int, int] = {}
            for tok in self._tokens(t):
                h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
                counts[h % self.dim] = counts.get(h % self.dim, 0) + 1
            for idx, c in counts.items():
                out[i, idx] = 1.0 + np.log(c)
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class SentenceTransformerEmbedder(Embedder):
    is_semantic = True
    sim_floor, sim_ceil = 0.10, 0.65  # typical range for MiniLM-class models on resume<->job text

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import kept lazy
        self.model = SentenceTransformer(model_name)
        self.name = f"sentence-transformers:{model_name.split('/')[-1]}"

    def encode(self, texts):
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    backend = settings.embedding_backend
    if backend in ("auto", "sentence_transformers"):
        try:
            return SentenceTransformerEmbedder(settings.embedding_model)
        except Exception as exc:  # package missing, model not downloadable, etc.
            if backend == "sentence_transformers":
                raise
            log.warning("Sentence Transformers unavailable (%s); using hashing fallback.", type(exc).__name__)
    return HashingEmbedder()


def chunk_text(text: str, max_words: int = 120, overlap: int = 20) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text.strip()] if text.strip() else []
    step = max_words - overlap
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), step)]
