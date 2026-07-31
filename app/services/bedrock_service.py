"""Amazon Bedrock Runtime wrapper for Claude model invocation.

Wraps `bedrock-runtime` `invoke_model` using the Anthropic Messages API shape,
with model routing between Sonnet (deep synthesis) and Haiku (low-latency), and
optional Guardrails enforcement (wired in Phase 6).
"""

from __future__ import annotations

import json
import os

import boto3
from botocore.exceptions import ClientError

SYSTEM_PROMPT = (
    "You are PlaybookIQ, an elite enterprise sports intelligence analyst. "
    "Provide precise, highly tactical game insights based solely on retrieved contexts. "
    "If context is insufficient, state that clearly."
)


class BedrockModelAccessError(RuntimeError):
    """Raised when the account doesn't yet have access to a requested model."""


class BedrockService:
    def __init__(
        self,
        region_name: str | None = None,
        sonnet_model_id: str | None = None,
        haiku_model_id: str | None = None,
    ) -> None:
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.sonnet_model_id = sonnet_model_id or os.environ.get(
            "BEDROCK_SONNET_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        self.haiku_model_id = haiku_model_id or os.environ.get(
            "BEDROCK_HAIKU_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)

    def invoke(
        self,
        user_message: str,
        context: str = "",
        use_fast_model: bool = False,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        model_id = self.haiku_model_id if use_fast_model else self.sonnet_model_id

        content = f"Context Data:\n{context}\n\nUser Query:\n{user_message}" if context else user_message

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        }

        kwargs = {
            "modelId": model_id,
            "contentType": "application/json",
            "accept": "application/json",
            "body": json.dumps(payload),
        }
        if guardrail_id:
            kwargs["guardrailIdentifier"] = guardrail_id
            kwargs["guardrailVersion"] = guardrail_version or "DRAFT"

        try:
            response = self.client.invoke_model(**kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "AccessDeniedException":
                raise BedrockModelAccessError(
                    f"No access to model {model_id!r} — request/verify Bedrock model "
                    f"access in the console for region {self.region_name!r}."
                ) from exc
            raise

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
