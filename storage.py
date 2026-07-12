"""S3 artifact storage helpers for DocuMind (boto3).

Reads ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, and ``S3_BUCKET_NAME``
from the environment. Optional ``AWS_REGION`` (default ``us-east-1``).

Higher-level publish helpers live in ``artifact_publish.py`` (docs, Mermaid, SVG).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Union

import boto3
from botocore.client import BaseClient

BytesLike = Union[bytes, bytearray]


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(
            f"Missing {name}. Set it in the environment or .env."
        )
    return value


def _bucket_name() -> str:
    return _require_env("S3_BUCKET_NAME")


def _region() -> str:
    return (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1").strip()


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    """Return a process-wide boto3 S3 client."""
    return boto3.client(
        "s3",
        aws_access_key_id=_require_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("AWS_SECRET_ACCESS_KEY"),
        region_name=_region(),
    )


def reset_s3_client() -> None:
    """Clear the cached client (tests)."""
    get_s3_client.cache_clear()


def upload_artifact(
    file_bytes: BytesLike,
    key: str,
    content_type: str,
    *,
    client: Optional[BaseClient] = None,
) -> str:
    """Upload bytes to ``S3_BUCKET_NAME`` under ``key`` and return the S3 key."""
    object_key = (key or "").strip().lstrip("/")
    if not object_key:
        raise ValueError("key is required")
    if not content_type or not str(content_type).strip():
        raise ValueError("content_type is required")

    s3 = client or get_s3_client()
    s3.put_object(
        Bucket=_bucket_name(),
        Key=object_key,
        Body=bytes(file_bytes),
        ContentType=str(content_type).strip(),
    )
    return object_key


def get_signed_url(
    key: str,
    expires_in: int = 3600,
    *,
    client: Optional[BaseClient] = None,
) -> str:
    """Return a presigned GET URL for ``key`` (default 1 hour)."""
    object_key = (key or "").strip().lstrip("/")
    if not object_key:
        raise ValueError("key is required")
    if expires_in <= 0:
        raise ValueError("expires_in must be a positive integer")

    s3 = client or get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket_name(), "Key": object_key},
        ExpiresIn=expires_in,
    )
