from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    use_fast_model: bool = False
    enable_rag: bool = True
    enable_guardrails: bool = True
    document_type: str | None = None
    similarity_threshold: float = 0.75
    top_k: int = 5


class RetrievedChunk(BaseModel):
    content: str
    score: float
    document_type: str | None = None
    player_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    retrieved_chunks: list[RetrievedChunk]


class AgentQueryRequest(BaseModel):
    session_id: str
    query: str


class AgentQueryResponse(BaseModel):
    answer: str
