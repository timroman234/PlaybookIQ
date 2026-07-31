"""Pluggable vector store backend for RAG retrieval.

Phase 5: local pure-Python cosine-similarity k-NN, persisted to a pickle file —
deliberately plain (no FAISS/Chroma/numpy) so nothing is hidden about what OpenSearch
Serverless's managed k-NN index abstracts away later. Phase 12 adds an OpenSearchServerlessBackend
implementing this exact same interface, using the identical metadata schema
(text, document_type, player_id, timestamp) as the PRD's OpenSearch index mapping.
"""

from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Match:
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStoreBackend(Protocol):
    def upsert(self, id: str, vector: list[float], text: str, metadata: dict) -> None: ...

    def query(
        self,
        vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[Match]: ...


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class _Record:
    id: str
    vector: list[float]
    text: str
    metadata: dict


class LocalVectorStore:
    """Numpy-free cosine-similarity k-NN over an in-memory list, persisted to disk."""

    def __init__(self, persist_path: str | Path = "data/index/local_vector_store.pkl") -> None:
        self.persist_path = Path(persist_path)
        self._records: dict[str, _Record] = {}
        if self.persist_path.is_file():
            self._load()

    def upsert(self, id: str, vector: list[float], text: str, metadata: dict | None = None) -> None:
        self._records[id] = _Record(id=id, vector=vector, text=text, metadata=metadata or {})
        self._save()

    def query(
        self,
        vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[Match]:
        candidates = self._records.values()
        if filters:
            candidates = [
                r for r in candidates
                if all(r.metadata.get(key) == value for key, value in filters.items())
            ]

        scored = [
            Match(content=r.text, score=_cosine_similarity(vector, r.vector), metadata=r.metadata)
            for r in candidates
        ]
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    def _save(self) -> None:
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump(self._records, f)

    def _load(self) -> None:
        with open(self.persist_path, "rb") as f:
            self._records = pickle.load(f)


def get_vector_store() -> VectorStoreBackend:
    """Factory reading VECTOR_STORE_BACKEND from the environment (local | opensearch_serverless)."""
    backend = os.environ.get("VECTOR_STORE_BACKEND", "local")
    if backend == "local":
        return LocalVectorStore()
    if backend == "opensearch_serverless":
        from app.services.vector_store_opensearch import OpenSearchServerlessBackend

        endpoint = os.environ["OPENSEARCH_COLLECTION_ENDPOINT"]
        region = os.environ.get("AWS_REGION", "us-east-1")
        return OpenSearchServerlessBackend(endpoint=endpoint, region_name=region)
    raise ValueError(f"Unknown VECTOR_STORE_BACKEND: {backend!r}")
