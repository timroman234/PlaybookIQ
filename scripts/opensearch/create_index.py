"""Create the k-NN vector index on the OpenSearch Serverless collection (Phase 12).

Matches the PRD's index schema: knn_vector field (1024-dim, hnsw/nmslib/cosinesimil)
plus text/document_type/player_id/timestamp fields — identical to the local
LocalVectorStore's metadata shape, so RagService's callers don't change.

Usage:
    uv run python scripts/opensearch/create_index.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import boto3
from dotenv import load_dotenv
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

load_dotenv()

INDEX_NAME = "playbookiq-vectors-index"


def main() -> None:
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint = os.environ["OPENSEARCH_COLLECTION_ENDPOINT"]
    host = endpoint.replace("https://", "")

    session = boto3.Session(region_name=region)
    credentials = session.get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )

    if client.indices.exists(index=INDEX_NAME):
        print(f"Index {INDEX_NAME!r} already exists.")
        return

    body = {
        "settings": {"index.knn": True},
        "mappings": {
            "properties": {
                "vector_field": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"},
                },
                "text": {"type": "text"},
                "document_type": {"type": "keyword"},
                "player_id": {"type": "keyword"},
                "timestamp": {"type": "date"},
            }
        },
    }

    client.indices.create(index=INDEX_NAME, body=body)
    print(f"Created index {INDEX_NAME!r}.")


if __name__ == "__main__":
    main()
