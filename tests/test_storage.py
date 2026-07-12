"""Tests for S3 storage helpers."""

from unittest.mock import MagicMock

import pytest

import storage


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    storage.reset_s3_client()
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("S3_BUCKET_NAME", "documind-test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    yield
    storage.reset_s3_client()


def test_upload_artifact_puts_object_and_returns_key():
    client = MagicMock()
    key = storage.upload_artifact(
        b"hello",
        "artifacts/demo.svg",
        "image/svg+xml",
        client=client,
    )

    assert key == "artifacts/demo.svg"
    client.put_object.assert_called_once_with(
        Bucket="documind-test",
        Key="artifacts/demo.svg",
        Body=b"hello",
        ContentType="image/svg+xml",
    )


def test_upload_artifact_strips_leading_slash():
    client = MagicMock()
    key = storage.upload_artifact(b"x", "/docs/readme.md", "text/markdown", client=client)
    assert key == "docs/readme.md"
    assert client.put_object.call_args.kwargs["Key"] == "docs/readme.md"


def test_get_signed_url_generates_presigned_get():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://example.com/signed"

    url = storage.get_signed_url("artifacts/demo.svg", expires_in=120, client=client)

    assert url == "https://example.com/signed"
    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "documind-test", "Key": "artifacts/demo.svg"},
        ExpiresIn=120,
    )


def test_missing_bucket_raises(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
        storage.upload_artifact(b"x", "a.txt", "text/plain", client=MagicMock())
