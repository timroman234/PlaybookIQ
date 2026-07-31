"""Pluggable document-storage backend.

Phase 3: local filesystem stand-in for S3. Phase 11 adds an S3-backed implementation
of the same interface — callers never need to change when the backend swaps.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put_object(self, key: str, data: bytes) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def list_objects(self, prefix: str = "") -> list[str]:
        ...


class LocalFileStorage:
    """Stores objects as files under a root directory, keyed by relative path."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_object(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_object(self, key: str) -> bytes:
        path = self.root / key
        if not path.is_file():
            raise FileNotFoundError(f"No object at key: {key}")
        return path.read_bytes()

    def list_objects(self, prefix: str = "") -> list[str]:
        keys = []
        for path in self.root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self.root).as_posix()
                if rel.startswith(prefix):
                    keys.append(rel)
        return sorted(keys)


def get_storage_backend() -> StorageBackend:
    """Factory reading STORAGE_BACKEND from the environment (local | s3)."""
    backend = os.environ.get("STORAGE_BACKEND", "local")
    if backend == "local":
        root = os.environ.get("LOCAL_STORAGE_ROOT", "data/raw")
        return LocalFileStorage(root)
    if backend == "s3":
        from app.services.storage_service_s3 import S3Storage

        bucket = os.environ["S3_BUCKET_NAME"]
        region = os.environ.get("AWS_REGION", "us-east-1")
        return S3Storage(bucket_name=bucket, region_name=region)
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend!r}")
