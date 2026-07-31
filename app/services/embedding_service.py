"""Amazon Bedrock Titan Text Embeddings V2 wrapper.

Produces 1024-dimension vectors matching the OpenSearch index schema defined in the
PRD (Phase 12 swaps the vector store backend, not the embedding dimension/shape).
"""

from __future__ import annotations

import json
import os

import boto3


class EmbeddingService:
    def __init__(self, region_name: str | None = None, model_id: str | None = None) -> None:
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.model_id = model_id or os.environ.get(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        )
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)

    def embed(self, text: str) -> list[float]:
        payload = {"inputText": text}
        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
