"""Manual smoke test for the Bedrock Guardrail — compares a clean prompt against a
PII-laden one, with the guardrail on vs. off, to prove it's actually wired into the
call path (not just created and ignored).

Requires BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION in .env (Phase 6) and
enough remaining Bedrock token quota for a few short invocations.

Usage:
    uv run python scripts/smoke_test_guardrails.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from botocore.exceptions import ClientError
from dotenv import load_dotenv

from app.services.bedrock_service import BedrockModelAccessError, BedrockService

load_dotenv()

CLEAN_PROMPT = "In one sentence, what does a Cover 3 zone blitz disguise?"
PII_PROMPT = (
    "My name is John Smith, SSN 078-05-1120, email john.smith@example.com. "
    "Please summarize my fantasy football league standings."
)


def run(service: BedrockService, label: str, prompt: str, guardrail_id: str | None) -> None:
    print(f"\n--- {label} (guardrail={'on' if guardrail_id else 'off'}) ---")
    try:
        response = service.invoke(
            prompt,
            use_fast_model=True,
            guardrail_id=guardrail_id,
            guardrail_version=os.environ.get("BEDROCK_GUARDRAIL_VERSION") if guardrail_id else None,
        )
        print(response)
    except BedrockModelAccessError as exc:
        print(f"BLOCKED: {exc}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"BLOCKED ({code}): {exc}")


def main() -> None:
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        print("BEDROCK_GUARDRAIL_ID not set in .env — create the guardrail first (Phase 6).")
        return

    service = BedrockService()

    run(service, "Clean prompt", CLEAN_PROMPT, guardrail_id=None)
    run(service, "PII prompt", PII_PROMPT, guardrail_id=None)
    run(service, "PII prompt", PII_PROMPT, guardrail_id=guardrail_id)


if __name__ == "__main__":
    main()
