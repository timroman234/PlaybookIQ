"""One-time migration: push data/raw/* up to the real S3 bucket (Phase 11).

Usage:
    uv run python scripts/upload_data_to_s3.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from app.services.storage_service import LocalFileStorage, get_storage_backend

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> None:
    local = LocalFileStorage(DATA_DIR)
    remote = get_storage_backend()

    keys = local.list_objects()
    for key in keys:
        remote.put_object(key, local.get_object(key))
        print(f"Uploaded {key}")

    print(f"\nUploaded {len(keys)} objects.")


if __name__ == "__main__":
    main()
