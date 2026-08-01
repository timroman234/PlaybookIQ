"""PlaybookIQ agent — Bedrock AgentCore Runtime entrypoint (Phase 7, pivoted from
Bedrock Agents Classic, which is closed to new customers).

Uses Strands Agents for orchestration (AgentCore Runtime is "bring your own framework" —
unlike Classic Agents, it doesn't include managed orchestration) and a single local
Strands @tool wrapping the existing get_player_stats lookup. No AgentCore Gateway is
used: Gateway exists to expose external APIs/Lambdas as shared tools across agents, which
doesn't apply to this one bounded, in-process tool.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool

from app.services.agent_service import PlayerNotFoundError
from app.services.agent_service import get_player_stats as _get_player_stats

app = BedrockAgentCoreApp()

MODEL_ID = os.environ.get("BEDROCK_HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

SYSTEM_PROMPT = (
    "You are PlaybookIQ's player-stats assistant. Use the get_player_stats tool to look "
    "up fictional player statistics. If the tool reports the player isn't found, say so "
    "clearly rather than guessing."
)


@tool
def get_player_stats(player_name: str, season: int | None = None) -> dict:
    """Look up a player's season stats by name.

    Args:
        player_name: Full name of the player (e.g. "Darnell Voss").
        season: Optional four-digit season year to filter by.
    """
    try:
        return _get_player_stats(player_name, season)
    except PlayerNotFoundError as exc:
        return {"error": str(exc)}


@app.entrypoint
def invoke(payload: dict) -> str:
    # A fresh Agent per invocation -- Strands Agent instances hold per-conversation state
    # and aren't safe to share across concurrent requests to the same warm container.
    agent = Agent(model=MODEL_ID, tools=[get_player_stats], system_prompt=SYSTEM_PROMPT)
    user_input = payload.get("prompt", "")
    result = agent(user_input)
    return result.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
