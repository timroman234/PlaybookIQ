"""Retrieval orchestration: embeds a query and searches the configured vector store.

Phase 5 uses the local vector store; Phase 12 adds `retrieve_via_kb`, an alternative
path through a real Bedrock Knowledge Base (managed retrieval, no local embed step).
"""

from __future__ import annotations

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import Match, VectorStoreBackend


class RagService:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStoreBackend) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        filters: dict | None = None,
    ) -> list[Match]:
        query_vector = self.embedding_service.embed(query)
        matches = self.vector_store.query(query_vector, top_k=top_k, filters=filters)
        return [m for m in matches if m.score >= similarity_threshold]
