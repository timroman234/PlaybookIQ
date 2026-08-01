"""Chunk, embed, and index the synthetic data under data/raw/ into the vector store.

Requires real Bedrock access (Titan Embeddings V2). Run after
scripts/generate_synthetic_data.py and once Bedrock model access is granted.

Usage:
    uv run python scripts/ingest_documents.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import get_vector_store

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Paragraph-based chunking with a soft max-length cap."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current.strip())
    return chunks


def documents_from_players(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    docs = []
    for player in data["players"]:
        stats_str = ", ".join(f"{k}={v}" for k, v in player["stats"].items())
        text = (
            f"{player['name']} plays {player['position']} for the {player['team']} "
            f"in the {player['season']} season. Stats: {stats_str}."
        )
        docs.append({"text": text, "document_type": "player_profile", "player_id": player["player_id"]})
    return docs


def documents_from_injuries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    docs = []
    for injury in data["injuries"]:
        text = (
            f"{injury['player_name']} ({injury['player_id']}) suffered a {injury['injury_type']} "
            f"({injury['body_part']}) on {injury['date']}. Status: {injury['status']}. "
            f"Expected return: {injury['expected_return']}. Notes: {injury['notes']}"
        )
        docs.append({"text": text, "document_type": "injury_log", "player_id": injury["player_id"]})
    return docs


def documents_from_manifest_text_files(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    docs = []
    for entry in manifest["documents"]:
        if entry["path"].endswith(".json"):
            continue
        file_path = manifest_path.parent / entry["path"]
        text = file_path.read_text(encoding="utf-8")
        for chunk in chunk_text(text):
            docs.append(
                {
                    "text": chunk,
                    "document_type": entry["document_type"],
                    "player_id": entry["player_id"],
                }
            )
    return docs


def main() -> None:
    embedding_service = EmbeddingService()
    vector_store = get_vector_store()

    documents = (
        documents_from_players(DATA_DIR / "players.json")
        + documents_from_injuries(DATA_DIR / "injury_logs.json")
        + documents_from_manifest_text_files(DATA_DIR / "manifest.json")
    )

    timestamp = datetime.now(UTC).isoformat()
    for idx, doc in enumerate(documents):
        vector = embedding_service.embed(doc["text"])
        vector_store.upsert(
            id=f"doc-{idx:04d}",
            vector=vector,
            text=doc["text"],
            metadata={
                "document_type": doc["document_type"],
                "player_id": doc["player_id"],
                "timestamp": timestamp,
            },
        )

    print(f"Ingested {len(documents)} chunks into {type(vector_store).__name__}")


if __name__ == "__main__":
    main()
