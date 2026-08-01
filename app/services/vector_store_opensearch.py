"""OpenSearch Serverless-backed implementation of VectorStoreBackend (Phase 12).

Same upsert/query contract as LocalVectorStore, using the real k-NN index created by
scripts/opensearch/create_index.py, so RagService doesn't change when the backend swaps.
"""

from __future__ import annotations

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from app.services.vector_store import Match

INDEX_NAME = "playbookiq-vectors-index"


class OpenSearchServerlessBackend:
    def __init__(self, endpoint: str, region_name: str = "us-east-1") -> None:
        host = endpoint.replace("https://", "")
        session = boto3.Session(region_name=region_name)
        credentials = session.get_credentials()
        auth = AWSV4SignerAuth(credentials, region_name, "aoss")

        self.client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

    def upsert(self, id: str, vector: list[float], text: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        document = {
            "vector_field": vector,
            "text": text,
            "document_type": metadata.get("document_type"),
            "player_id": metadata.get("player_id"),
            "timestamp": metadata.get("timestamp"),
        }
        self.client.index(index=INDEX_NAME, body=document, id=id)

    def query(
        self,
        vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[Match]:
        knn_query: dict = {"vector_field": {"vector": vector, "k": top_k}}

        if filters:
            filter_clauses = [{"term": {key: value}} for key, value in filters.items()]
            knn_query["vector_field"]["filter"] = {"bool": {"must": filter_clauses}}

        body = {"size": top_k, "query": {"knn": knn_query}}
        response = self.client.search(index=INDEX_NAME, body=body)

        matches = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            matches.append(
                Match(
                    content=source.get("text", ""),
                    score=hit["_score"],
                    metadata={
                        "document_type": source.get("document_type"),
                        "player_id": source.get("player_id"),
                        "timestamp": source.get("timestamp"),
                    },
                )
            )
        return matches
