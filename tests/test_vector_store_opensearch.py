from unittest.mock import MagicMock, patch

from app.services.vector_store_opensearch import OpenSearchServerlessBackend


@patch("app.services.vector_store_opensearch.OpenSearch")
@patch("app.services.vector_store_opensearch.boto3")
def test_upsert_indexes_document_with_expected_shape(mock_boto3, mock_opensearch_cls):
    mock_client = MagicMock()
    mock_opensearch_cls.return_value = mock_client

    backend = OpenSearchServerlessBackend(endpoint="https://abc.us-east-1.aoss.amazonaws.com")
    backend.upsert(
        "doc-1",
        vector=[0.1, 0.2],
        text="hello",
        metadata={"document_type": "injury_log", "player_id": "P005", "timestamp": "2026-01-01"},
    )

    mock_client.index.assert_called_once_with(
        index="playbookiq-vectors-index",
        body={
            "vector_field": [0.1, 0.2],
            "text": "hello",
            "document_type": "injury_log",
            "player_id": "P005",
            "timestamp": "2026-01-01",
        },
        id="doc-1",
    )


@patch("app.services.vector_store_opensearch.OpenSearch")
@patch("app.services.vector_store_opensearch.boto3")
def test_query_returns_matches_from_hits(mock_boto3, mock_opensearch_cls):
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 0.87,
                    "_source": {"text": "injury note", "document_type": "injury_log", "player_id": "P005"},
                }
            ]
        }
    }
    mock_opensearch_cls.return_value = mock_client

    backend = OpenSearchServerlessBackend(endpoint="https://abc.us-east-1.aoss.amazonaws.com")
    results = backend.query(vector=[0.1, 0.2], top_k=3)

    assert len(results) == 1
    assert results[0].content == "injury note"
    assert results[0].score == 0.87
    assert results[0].metadata["player_id"] == "P005"


@patch("app.services.vector_store_opensearch.OpenSearch")
@patch("app.services.vector_store_opensearch.boto3")
def test_query_applies_filters_to_knn_clause(mock_boto3, mock_opensearch_cls):
    mock_client = MagicMock()
    mock_client.search.return_value = {"hits": {"hits": []}}
    mock_opensearch_cls.return_value = mock_client

    backend = OpenSearchServerlessBackend(endpoint="https://abc.us-east-1.aoss.amazonaws.com")
    backend.query(vector=[0.1, 0.2], top_k=5, filters={"document_type": "injury_log"})

    body = mock_client.search.call_args.kwargs["body"]
    knn_filter = body["query"]["knn"]["vector_field"]["filter"]
    assert knn_filter == {"bool": {"must": [{"term": {"document_type": "injury_log"}}]}}
