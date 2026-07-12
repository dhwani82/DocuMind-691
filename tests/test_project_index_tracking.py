"""Tests for MongoDB status tracking around project indexing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import call, patch

import pytest
from bson import ObjectId

import models
from project_index_tracking import index_project_with_status
from project_indexing import IndexProjectResult


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo_repo"
    root.mkdir()
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return root


def test_index_project_with_status_pending_indexing_ready(project_root: Path):
    owner_id = ObjectId()
    mongo_id = ObjectId()
    fake_result = IndexProjectResult(
        success=True,
        project_id=project_root.as_posix(),
        project_root=project_root.as_posix(),
        ready=True,
        files_scanned=1,
        chunks_indexed=2,
        graph_nodes=3,
        graph_edges=1,
        phases=[],
    )

    with (
        patch(
            "project_index_tracking.models.get_project_by_owner_and_source",
            return_value=None,
        ),
        patch(
            "project_index_tracking.models.create_project",
            return_value={"_id": mongo_id},
        ) as create_project,
        patch("project_index_tracking.models.set_project_index_status") as set_status,
        patch(
            "project_index_tracking.index_project_folder",
            return_value=fake_result,
        ) as index_folder,
    ):
        tracked = index_project_with_status(str(project_root), owner_id)

    assert tracked.mongo_project_id == str(mongo_id)
    assert tracked.index.ready is True
    create_project.assert_called_once()
    assert create_project.call_args.kwargs["index_status"] == models.INDEX_STATUS_PENDING
    assert create_project.call_args.args[0] == owner_id
    assert create_project.call_args.args[3] == project_root.as_posix()

    assert set_status.call_args_list == [
        call(mongo_id, models.INDEX_STATUS_INDEXING),
        call(mongo_id, models.INDEX_STATUS_READY),
    ]
    index_folder.assert_called_once()


def test_index_project_with_status_marks_failed_on_error(project_root: Path):
    owner_id = ObjectId()
    mongo_id = ObjectId()

    with (
        patch(
            "project_index_tracking.models.get_project_by_owner_and_source",
            return_value={"_id": mongo_id},
        ),
        patch("project_index_tracking.models.set_project_index_status") as set_status,
        patch(
            "project_index_tracking.index_project_folder",
            side_effect=ValueError("No indexable source files"),
        ),
    ):
        with pytest.raises(ValueError, match="No indexable"):
            index_project_with_status(str(project_root), owner_id)

    assert set_status.call_args_list[0] == call(
        mongo_id, models.INDEX_STATUS_PENDING, name=project_root.name, source_type="folder", vector_store="chroma"
    )
    assert call(mongo_id, models.INDEX_STATUS_INDEXING) in set_status.call_args_list
    assert call(mongo_id, models.INDEX_STATUS_FAILED) in set_status.call_args_list


def test_index_project_with_status_skips_mongo_for_missing_folder(tmp_path: Path):
    owner_id = ObjectId()
    missing = tmp_path / "nope"

    with patch("project_index_tracking.models.create_project") as create_project:
        with pytest.raises(ValueError, match="not found"):
            index_project_with_status(str(missing), owner_id)

    create_project.assert_not_called()
