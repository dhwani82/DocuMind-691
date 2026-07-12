"""MongoDB status tracking around project indexing (does not alter parse/index logic)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import models
from code_graph import NetworkXGraphStore
from project_indexing import IndexProjectResult, index_project_folder, resolve_project_folder
from vector_index import ChromaVectorStore


@dataclass
class TrackedIndexResult:
    """Indexing outcome plus the MongoDB project document id."""

    index: IndexProjectResult
    mongo_project_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.index.to_dict()
        payload["mongo_project_id"] = self.mongo_project_id
        return payload


def _vector_store_label() -> str:
    return (os.getenv("VECTOR_STORE_PROVIDER") or models.DEFAULT_VECTOR_STORE).strip().lower()


def _ensure_project_doc(
    owner_id: Any,
    *,
    name: str,
    source_type: str,
    source_ref: str,
    vector_store: str,
) -> Any:
    """Create a pending project or reset an existing one for this owner+source."""
    existing = models.get_project_by_owner_and_source(owner_id, source_ref)
    if existing is not None:
        mongo_id = existing["_id"]
        models.set_project_index_status(
            mongo_id,
            models.INDEX_STATUS_PENDING,
            name=name,
            source_type=source_type,
            vector_store=vector_store,
        )
        return mongo_id

    doc = models.create_project(
        owner_id,
        name,
        source_type,
        source_ref,
        index_status=models.INDEX_STATUS_PENDING,
        vector_store=vector_store,
    )
    return doc["_id"]


def index_project_with_status(
    folder_path: str,
    owner_id: Any,
    *,
    source_type: str = "folder",
    vector_store: Optional[ChromaVectorStore] = None,
    graph_store: Optional[NetworkXGraphStore] = None,
) -> TrackedIndexResult:
    """Resolve folder, track Mongo status, then run ``index_project_folder`` unchanged.

    Status flow: ``pending`` → ``indexing`` → ``ready`` | ``failed``.
    Invalid paths raise before a document is written (indexing never started).
    """
    project_root: Path = resolve_project_folder(folder_path)
    source_ref = project_root.as_posix()
    store_label = _vector_store_label()

    mongo_id = _ensure_project_doc(
        owner_id,
        name=project_root.name,
        source_type=source_type,
        source_ref=source_ref,
        vector_store=store_label,
    )

    models.set_project_index_status(mongo_id, models.INDEX_STATUS_INDEXING)

    try:
        result = index_project_folder(
            folder_path,
            vector_store=vector_store,
            graph_store=graph_store,
        )
    except Exception:
        models.set_project_index_status(mongo_id, models.INDEX_STATUS_FAILED)
        raise

    final_status = (
        models.INDEX_STATUS_READY if result.ready else models.INDEX_STATUS_FAILED
    )
    models.set_project_index_status(mongo_id, final_status)

    return TrackedIndexResult(
        index=result,
        mongo_project_id=str(mongo_id),
    )
