"""Vector store for RAG. ChromaDB when installed (persistent), otherwise an in-memory numpy store.
Embeddings are computed by our own embedder and passed in explicitly (Chroma never downloads a model).
Every resume chunk is stored with user_id and resume_id metadata and every query is filtered on them, so
retrieval can never cross user boundaries."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from config import settings
from ml.embeddings import Embedder

log = logging.getLogger(__name__)


@dataclass
class Passage:
    id: str
    text: str
    meta: dict
    score: float


class VectorStore:
    def __init__(self, embedder: Embedder, persist_dir: str | None = None, force_memory: bool = False):
        self.embedder = embedder
        self._mem: dict[str, list[tuple[str, str, dict, np.ndarray]]] = {}
        self._chroma = None
        if not force_memory and settings.vector_backend != "memory":
            try:
                import chromadb
                self._chroma = chromadb.PersistentClient(path=persist_dir or settings.chroma_dir) if persist_dir != ":ephemeral:" else chromadb.EphemeralClient()
            except Exception as exc:
                log.warning("ChromaDB unavailable (%s); using in-memory store.", type(exc).__name__)
        self.backend = "chromadb" if self._chroma else "memory"

    def _col(self, name: str):
        return self._chroma.get_or_create_collection(f"{name}_{abs(hash(self.embedder.name)) % 10**6}", metadata={"hnsw:space": "cosine"})

    def add(self, collection: str, ids: list[str], texts: list[str], metas: list[dict]) -> None:
        if not ids:
            return
        vecs = self.embedder.encode(texts)
        if self._chroma:
            self._col(collection).upsert(ids=ids, documents=texts, embeddings=vecs.tolist(), metadatas=metas)
        else:
            bucket = self._mem.setdefault(collection, [])
            existing = {i for i, *_ in bucket}
            bucket[:] = [b for b in bucket if b[0] not in set(ids)] if existing & set(ids) else bucket
            bucket.extend(zip(ids, texts, metas, vecs))

    def delete(self, collection: str, where: dict) -> None:
        if self._chroma:
            try:
                self._col(collection).delete(where=_chroma_where(where))
            except Exception:
                pass
        else:
            self._mem[collection] = [b for b in self._mem.get(collection, []) if not all(b[2].get(k) == v for k, v in where.items())]

    def query(self, collection: str, text: str, k: int, where: dict) -> list[Passage]:
        qv = self.embedder.encode([text])[0]
        if self._chroma:
            col = self._col(collection)
            if col.count() == 0:
                return []
            r = col.query(query_embeddings=[qv.tolist()], n_results=min(k, col.count()), where=_chroma_where(where))
            return [Passage(i, d, m, 1 - dist) for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]
        cands = [b for b in self._mem.get(collection, []) if all(b[2].get(kk) == v for kk, v in where.items())]
        scored = sorted(((float(qv @ b[3]), b) for b in cands), key=lambda x: -x[0])[:k]
        return [Passage(b[0], b[1], b[2], sc) for sc, b in scored]


def _chroma_where(where: dict) -> dict:
    return where if len(where) == 1 else {"$and": [{k: v} for k, v in where.items()]}
