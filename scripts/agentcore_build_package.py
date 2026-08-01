"""Assemble the AgentCore Runtime deployment zip from canonical source files.

Reuses app/services/agent_service.py rather than duplicating it, so the same
get_player_stats logic backs both the local dev path and the deployed agent.

Usage:
    uv run python scripts/agentcore_build_package.py
"""

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTCORE_DIR = ROOT / "agentcore"
STAGING_DIR = AGENTCORE_DIR / "_staging"
DIST_DIR = AGENTCORE_DIR / "dist"
ZIP_PATH = DIST_DIR / "playbookiq-agent.zip"


def main() -> None:
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(AGENTCORE_DIR / "agent.py", STAGING_DIR / "agent.py")
    shutil.copy2(AGENTCORE_DIR / "requirements.txt", STAGING_DIR / "requirements.txt")

    # Only what agent.py actually imports -- app/services/agent_service.py and its
    # __init__.py chain -- not the whole app package (FastAPI/Streamlit/OpenSearch/S3
    # dependencies aren't needed here and would bloat the deployment package).
    (STAGING_DIR / "app" / "services").mkdir(parents=True)
    shutil.copy2(ROOT / "app" / "__init__.py", STAGING_DIR / "app" / "__init__.py")
    shutil.copy2(ROOT / "app" / "services" / "__init__.py", STAGING_DIR / "app" / "services" / "__init__.py")
    shutil.copy2(ROOT / "app" / "services" / "agent_service.py", STAGING_DIR / "app" / "services" / "agent_service.py")

    (STAGING_DIR / "data" / "raw").mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "raw" / "players.json", STAGING_DIR / "data" / "raw" / "players.json")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in STAGING_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(STAGING_DIR))

    shutil.rmtree(STAGING_DIR)
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
