"""S3-backed implementation of StorageBackend (Phase 11), replacing LocalFileStorage."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


class S3Storage:
    def __init__(self, bucket_name: str, region_name: str = "us-east-1") -> None:
        self.bucket_name = bucket_name
        self.client = boto3.client("s3", region_name=region_name)

    def put_object(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=data)

    def get_object(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise FileNotFoundError(f"No object at key: {key}") from exc
            raise
        return response["Body"].read()

    def list_objects(self, prefix: str = "") -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return sorted(keys)
