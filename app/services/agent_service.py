"""Tool-calling / agent orchestration.

Phase 7 starts with a local `get_player_stats` tool (nailing the contract a real
Bedrock Agent action group will call), then adds `invoke_agent`, wrapping a real
Bedrock Agent + "GetPlayerStats" action group once one exists.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3

PLAYERS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "players.json"


class PlayerNotFoundError(ValueError):
    pass


def get_player_stats(player_name: str, season: int | None = None) -> dict:
    """Local stand-in for the Bedrock Agent action group of the same name.

    Looks up fictional player stats by name (case-insensitive) from the synthetic
    dataset. Real Bedrock Agents call this exact function (or a Lambda wrapping it)
    when the "GetPlayerStats" action group fires.
    """
    data = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))
    for player in data["players"]:
        if player["name"].lower() == player_name.lower():
            if season is not None and player["season"] != season:
                continue
            return player
    raise PlayerNotFoundError(f"No player found matching {player_name!r} (season={season})")


class AgentService:
    """Wraps a real Bedrock Agent via bedrock-agent-runtime invoke_agent."""

    def __init__(
        self,
        region_name: str | None = None,
        agent_id: str | None = None,
        agent_alias_id: str | None = None,
    ) -> None:
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.agent_id = agent_id or os.environ.get("BEDROCK_AGENT_ID")
        self.agent_alias_id = agent_alias_id or os.environ.get("BEDROCK_AGENT_ALIAS_ID")
        self.client = boto3.client("bedrock-agent-runtime", region_name=self.region_name)

    def invoke_agent(self, session_id: str, input_text: str) -> str:
        if not self.agent_id or not self.agent_alias_id:
            raise RuntimeError(
                "BEDROCK_AGENT_ID / BEDROCK_AGENT_ALIAS_ID not configured — "
                "create the Bedrock Agent + action group first (Phase 7)."
            )

        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=session_id,
            inputText=input_text,
        )

        completion = ""
        for event in response["completion"]:
            chunk = event.get("chunk")
            if chunk and "bytes" in chunk:
                completion += chunk["bytes"].decode("utf-8")
        return completion
