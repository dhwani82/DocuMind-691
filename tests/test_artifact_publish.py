"""Tests for S3 artifact publishing helpers."""

from unittest.mock import patch

import artifact_publish as ap


def test_sanitize_and_resolve_project_id():
    assert ap.sanitize_project_id("/Users/me/My Repo!") == "My_Repo"
    assert ap.resolve_project_id({"folder_path": "/tmp/demo-app"}) == "demo-app"
    assert ap.resolve_project_id({}, fallback="session") == "session"


def test_publish_documentation_artifacts_uploads_readme_and_architecture(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")

    calls = []

    def fake_upload(content, key, content_type):
        calls.append((content, key, content_type))
        return key

    def fake_signed(key, expires_in=3600):
        return f"https://signed.example/{key}?e={expires_in}"

    with (
        patch("artifact_publish.upload_artifact", side_effect=fake_upload),
        patch("artifact_publish.get_signed_url", side_effect=fake_signed),
    ):
        published = ap.publish_documentation_artifacts(
            {
                "readme": "# Hello",
                "architecture": "## Arch",
                "docstrings": "skip me",
            },
            "demo",
        )

    assert set(published) == {"readme", "architecture"}
    assert published["readme"]["url"].startswith("https://signed.example/demo/readme/")
    assert published["architecture"]["key"].endswith("_ARCHITECTURE.md")
    assert len(calls) == 2


def test_publish_skips_when_s3_not_configured(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    with patch("artifact_publish.upload_artifact") as upload:
        assert ap.publish_documentation_artifacts({"readme": "x"}, "p") == {}
        upload.assert_not_called()


def test_generate_docs_includes_artifact_urls(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")

    with (
        patch(
            "artifact_publish.upload_artifact",
            side_effect=lambda content, key, content_type: key,
        ),
        patch(
            "artifact_publish.get_signed_url",
            side_effect=lambda key, expires_in=3600: f"https://cdn.test/{key}",
        ),
    ):
        response = client.post(
            "/api/generate-docs",
            json={"code": "def ok():\n    return 42", "project_id": "unit-demo"},
        )

    data = response.get_json()
    assert response.status_code == 200
    assert "artifacts" in data
    assert "readme" in data["artifacts"]
    assert data["artifacts"]["readme"]["url"].startswith("https://cdn.test/")
    assert "architecture" in data["artifacts"]


def test_svg_flowchart_returns_json_with_signed_url_when_s3_configured(
    client, monkeypatch
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")

    code = (
        "def branchy(x):\n"
        "    if x > 0:\n"
        "        for i in range(3):\n"
        "            pass\n"
        "    return x\n"
    )
    with (
        patch(
            "artifact_publish.upload_artifact",
            side_effect=lambda content, key, content_type: key,
        ),
        patch(
            "artifact_publish.get_signed_url",
            side_effect=lambda key, expires_in=3600: f"https://cdn.test/{key}",
        ),
    ):
        response = client.post(
            "/api/generate-svg-flowchart",
            json={"code": code, "project_id": "svg-demo"},
        )

    data = response.get_json()
    assert response.status_code == 200
    assert response.is_json
    assert "<svg" in data["svg"]
    assert data["url"].startswith("https://cdn.test/")
    assert data["artifact"]["artifact_type"] == "svg_flowchart"
