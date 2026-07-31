"""Manual smoke test for the local RAG pipeline after running ingest_documents.py.

Usage:
    uv run python scripts/query_smoke_test.py "What is Isaiah Whitfield's injury status?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RagService
from app.services.vector_store import LocalVectorStore

load_dotenv()


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "What is Isaiah Whitfield's injury status?"

    rag = RagService(EmbeddingService(), LocalVectorStore())
    results = rag.retrieve(query, top_k=3, similarity_threshold=0.0)

    print(f"Query: {query}\n")
    for i, match in enumerate(results, 1):
        print(f"[{i}] score={match.score:.4f} type={match.metadata.get('document_type')}")
        print(f"    {match.content}\n")


if __name__ == "__main__":
    main()
