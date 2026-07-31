import io
import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.bedrock_service import BedrockModelAccessError, BedrockService


def _fake_response(text: str):
    body = json.dumps({"content": [{"text": text}]}).encode("utf-8")
    return {"body": io.BytesIO(body)}


@patch("app.services.bedrock_service.boto3")
def test_invoke_returns_model_text(mock_boto3):
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _fake_response("Sonnet says hi")
    mock_boto3.client.return_value = mock_client

    service = BedrockService(region_name="us-east-1")
    result = service.invoke("What's the injury report?", context="Injury log context")

    assert result == "Sonnet says hi"
    called_kwargs = mock_client.invoke_model.call_args.kwargs
    assert called_kwargs["modelId"] == service.sonnet_model_id
    body = json.loads(called_kwargs["body"])
    assert "Injury log context" in body["messages"][0]["content"]


@patch("app.services.bedrock_service.boto3")
def test_invoke_routes_to_haiku_when_fast_model_requested(mock_boto3):
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _fake_response("Haiku says hi")
    mock_boto3.client.return_value = mock_client

    service = BedrockService(region_name="us-east-1")
    service.invoke("quick question", use_fast_model=True)

    called_kwargs = mock_client.invoke_model.call_args.kwargs
    assert called_kwargs["modelId"] == service.haiku_model_id


@patch("app.services.bedrock_service.boto3")
def test_invoke_passes_guardrail_kwargs(mock_boto3):
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _fake_response("guarded response")
    mock_boto3.client.return_value = mock_client

    service = BedrockService(region_name="us-east-1")
    service.invoke("hello", guardrail_id="gr-123", guardrail_version="1")

    called_kwargs = mock_client.invoke_model.call_args.kwargs
    assert called_kwargs["guardrailIdentifier"] == "gr-123"
    assert called_kwargs["guardrailVersion"] == "1"


@patch("app.services.bedrock_service.boto3")
def test_invoke_raises_friendly_error_on_access_denied(mock_boto3):
    mock_client = MagicMock()
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no access"}}, "InvokeModel"
    )
    mock_boto3.client.return_value = mock_client

    service = BedrockService(region_name="us-east-1")
    with pytest.raises(BedrockModelAccessError):
        service.invoke("hello")
