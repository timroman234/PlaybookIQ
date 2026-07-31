"""FastAPI orchestration layer — the PRD's "REST/boto3 API" tier.

Fans a single query out to RAG retrieval (optional), then Bedrock model invocation
(optionally guardrailed), and separately exposes Bedrock Agent tool-calling.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from app.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from app.services.agent_service import AgentService
from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RagService
from app.services.vector_store import get_vector_store

load_dotenv()

app = FastAPI(title="PlaybookIQ API")


def get_bedrock_service() -> BedrockService:
    return BedrockService()


def get_rag_service() -> RagService:
    return RagService(EmbeddingService(), get_vector_store())


def get_agent_service() -> AgentService:
    return AgentService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    bedrock_service: BedrockService = Depends(get_bedrock_service),
    rag_service: RagService = Depends(get_rag_service),
) -> QueryResponse:
    retrieved_chunks: list[RetrievedChunk] = []
    context = ""

    if request.enable_rag:
        filters = {"document_type": request.document_type} if request.document_type else None
        matches = rag_service.retrieve(
            request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            filters=filters,
        )
        retrieved_chunks = [
            RetrievedChunk(
                content=m.content,
                score=m.score,
                document_type=m.metadata.get("document_type"),
                player_id=m.metadata.get("player_id"),
            )
            for m in matches
        ]
        context = "\n---\n".join(m.content for m in matches) if matches else "No high-confidence documents retrieved."

    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID") if request.enable_guardrails else None
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION") if guardrail_id else None

    answer = bedrock_service.invoke(
        request.query,
        context=context,
        use_fast_model=request.use_fast_model,
        guardrail_id=guardrail_id or None,
        guardrail_version=guardrail_version or None,
    )

    return QueryResponse(answer=answer, retrieved_chunks=retrieved_chunks)


@app.post("/agent-query", response_model=AgentQueryResponse)
def agent_query(
    request: AgentQueryRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentQueryResponse:
    answer = agent_service.invoke_agent(request.session_id, request.query)
    return AgentQueryResponse(answer=answer)
