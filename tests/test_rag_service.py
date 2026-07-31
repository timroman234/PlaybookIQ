from unittest.mock import MagicMock

from app.services.rag_service import RagService
from app.services.vector_store import Match


def test_retrieve_embeds_query_and_filters_by_threshold():
    mock_embedding_service = MagicMock()
    mock_embedding_service.embed.return_value = [1.0, 0.0]

    mock_vector_store = MagicMock()
    mock_vector_store.query.return_value = [
        Match(content="high score", score=0.9, metadata={}),
        Match(content="low score", score=0.4, metadata={}),
    ]

    rag = RagService(mock_embedding_service, mock_vector_store)
    results = rag.retrieve("some query", similarity_threshold=0.75)

    mock_embedding_service.embed.assert_called_once_with("some query")
    assert [m.content for m in results] == ["high score"]


def test_retrieve_passes_filters_through():
    mock_embedding_service = MagicMock()
    mock_embedding_service.embed.return_value = [1.0, 0.0]
    mock_vector_store = MagicMock()
    mock_vector_store.query.return_value = []

    rag = RagService(mock_embedding_service, mock_vector_store)
    rag.retrieve("query", top_k=3, filters={"document_type": "injury_log"})

    mock_vector_store.query.assert_called_once_with(
        [1.0, 0.0], top_k=3, filters={"document_type": "injury_log"}
    )
