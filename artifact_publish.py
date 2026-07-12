"""Publish generated docs/diagrams to S3 and return signed download URLs.

Uses ``storage.upload_artifact`` / ``get_signed_url``. Soft-fails when S3 is
not configured or upload errors occur so generation endpoints still return
inline content.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from storage import get_signed_url, upload_artifact

# artifact_type -> (filename, content_type)
DOC_ARTIFACTS = {
    "readme": ("README.md", "text/markdown; charset=utf-8"),
    "architecture": ("ARCHITECTURE.md", "text/markdown; charset=utf-8"),
}

MERMAID_TYPES = (
    "architecture",
    "code_architecture",
    "sequence",
    "dependencies",
    "flowchart",
    "structure",
)

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def s3_configured() -> bool:
    return all(
        (os.getenv(name) or "").strip()
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME")
    )


def sanitize_project_id(project_id: str) -> str:
    raw = (project_id or "").strip() or "session"
    # Prefer last path segment for filesystem-style ids.
    name = Path(raw.rstrip("/")).name or raw
    cleaned = _SAFE_SEGMENT.sub("_", name).strip("._") or "session"
    return cleaned[:120]


def resolve_project_id(data: Optional[dict[str, Any]], *, fallback: str = "session") -> str:
    """Pick a stable project key from a request body."""
    data = data or {}
    for field in ("project_id", "folder_path", "path"):
        value = data.get(field)
        if value and str(value).strip():
            return sanitize_project_id(str(value))
    filename = data.get("filename")
    if filename and str(filename).strip():
        return sanitize_project_id(Path(str(filename)).stem)
    return sanitize_project_id(fallback)


def _artifact_key(project_id: str, artifact_type: str, filename: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_type = sanitize_project_id(artifact_type)
    safe_name = sanitize_project_id(filename)
    return f"{sanitize_project_id(project_id)}/{safe_type}/{stamp}_{safe_name}"


def publish_bytes(
    content: bytes,
    *,
    project_id: str,
    artifact_type: str,
    filename: str,
    content_type: str,
    expires_in: int = 3600,
) -> Optional[dict[str, str]]:
    """Upload one artifact; return ``{key, url, artifact_type}`` or ``None``."""
    if not content or not s3_configured():
        return None
    try:
        key = _artifact_key(project_id, artifact_type, filename)
        upload_artifact(content, key, content_type)
        url = get_signed_url(key, expires_in=expires_in)
        return {
            "key": key,
            "url": url,
            "artifact_type": artifact_type,
        }
    except Exception as exc:
        print(f"DocuMind S3 publish failed for {artifact_type} (non-fatal): {exc!s}")
        return None


def publish_text(
    text: str,
    *,
    project_id: str,
    artifact_type: str,
    filename: str,
    content_type: str,
    expires_in: int = 3600,
) -> Optional[dict[str, str]]:
    if text is None:
        return None
    body = str(text)
    if not body.strip():
        return None
    return publish_bytes(
        body.encode("utf-8"),
        project_id=project_id,
        artifact_type=artifact_type,
        filename=filename,
        content_type=content_type,
        expires_in=expires_in,
    )


def publish_documentation_artifacts(
    documentation: dict[str, Any],
    project_id: str,
) -> dict[str, dict[str, str]]:
    """Upload README / ARCHITECTURE markdown; return map of artifact_type → meta."""
    published: dict[str, dict[str, str]] = {}
    for artifact_type, (filename, content_type) in DOC_ARTIFACTS.items():
        content = documentation.get(artifact_type)
        meta = publish_text(
            content if isinstance(content, str) else "",
            project_id=project_id,
            artifact_type=artifact_type,
            filename=filename,
            content_type=content_type,
        )
        if meta:
            published[artifact_type] = meta
    return published


def publish_mermaid_artifacts(
    diagrams: dict[str, Any],
    project_id: str,
) -> dict[str, dict[str, str]]:
    """Upload Mermaid diagram strings keyed by diagram kind."""
    published: dict[str, dict[str, str]] = {}
    if not isinstance(diagrams, dict):
        return published
    for kind in MERMAID_TYPES:
        content = diagrams.get(kind)
        if not isinstance(content, str) or not content.strip():
            continue
        meta = publish_text(
            content,
            project_id=project_id,
            artifact_type=f"mermaid_{kind}",
            filename=f"{kind}.mmd",
            content_type="text/plain; charset=utf-8",
        )
        if meta:
            published[kind] = meta
    return published


def publish_svg_artifact(
    svg_content: str,
    project_id: str,
    *,
    function_name: Optional[str] = None,
) -> Optional[dict[str, str]]:
    name = sanitize_project_id(function_name or "flowchart") + ".svg"
    return publish_text(
        svg_content,
        project_id=project_id,
        artifact_type="svg_flowchart",
        filename=name,
        content_type="image/svg+xml",
    )


def attach_mermaid_artifacts_to_result(
    result: dict[str, Any],
    project_id: str,
) -> dict[str, Any]:
    """Mutate ``result`` with ``diagram_artifacts`` / ``project_id`` when S3 upload works."""
    diagrams = result.get("diagrams") if isinstance(result, dict) else None
    if not isinstance(diagrams, dict):
        return result
    published = publish_mermaid_artifacts(diagrams, project_id)
    if published:
        result["diagram_artifacts"] = published
        result["project_id"] = sanitize_project_id(project_id)
    return result
