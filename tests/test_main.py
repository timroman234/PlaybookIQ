from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app, get_agent_service, get_bedrock_service, get_rag_service
from app.services.vector_store import Match


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_with_rag_enabled_grounds_answer_in_retrieved_chunks():
    mock_bedrock = MagicMock()
    mock_bedrock.invoke.return_value = "Grounded answer"

    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = [
        Match(content="Whitfield injury note", score=0.91, metadata={"document_type": "injury_log", "player_id": "P005"})
    ]

    app.dependency_overrides[get_bedrock_service] = lambda: mock_bedrock
    app.dependency_overrides[get_rag_service] = lambda: mock_rag
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "What is Whitfield's injury status?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Grounded answer"
    assert body["retrieved_chunks"][0]["content"] == "Whitfield injury note"
    assert body["retrieved_chunks"][0]["player_id"] == "P005"

    call_kwargs = mock_bedrock.invoke.call_args.kwargs
    assert "Whitfield injury note" in call_kwargs["context"]


def test_query_with_rag_disabled_skips_retrieval():
    mock_bedrock = MagicMock()
    mock_bedrock.invoke.return_value = "Direct answer"
    mock_rag = MagicMock()

    app.dependency_overrides[get_bedrock_service] = lambda: mock_bedrock
    app.dependency_overrides[get_rag_service] = lambda: mock_rag
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "hello", "enable_rag": False})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["retrieved_chunks"] == []
    mock_rag.retrieve.assert_not_called()


def test_agent_query_returns_agent_answer():
    mock_agent = MagicMock()
    mock_agent.invoke_agent.return_value = "Player stats: ..."

    app.dependency_overrides[get_agent_service] = lambda: mock_agent
    try:
        client = TestClient(app)
        response = client.post("/agent-query", json={"session_id": "s1", "query": "Get stats for X"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["answer"] == "Player stats: ..."
    mock_agent.invoke_agent.assert_called_once_with("s1", "Get stats for X")
