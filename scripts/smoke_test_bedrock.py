"""Manual smoke test for real Bedrock model invocation.

Requires: `.env` configured with AWS_PROFILE/AWS_REGION pointing at an account with
Bedrock model access granted for Claude 3.5 Sonnet and Claude 3 Haiku.

Usage:
    uv run python scripts/smoke_test_bedrock.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from botocore.exceptions import ClientError
from dotenv import load_dotenv

from app.services.bedrock_service import BedrockModelAccessError, BedrockService

load_dotenv()


def main() -> None:
    service = BedrockService()
    prompt = "In two sentences, what should a defense look for on 3rd-and-long plays?"

    for label, use_fast_model in [("Haiku", True), ("Sonnet", False)]:
        print(f"\n--- {label} ---")
        start = time.perf_counter()
        try:
            response = service.invoke(prompt, use_fast_model=use_fast_model)
        except BedrockModelAccessError as exc:
            print(f"BLOCKED: {exc}")
            continue
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            print(f"BLOCKED ({code}): {exc}")
            continue
        elapsed = time.perf_counter() - start
        print(f"({elapsed:.2f}s) {response}")


if __name__ == "__main__":
    main()
