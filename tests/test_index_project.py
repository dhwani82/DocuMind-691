"""Tests for project indexing API and canonical project_id handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from agent import is_project_ready
from code_graph import NetworkXGraphStore
from project_indexing import canonical_project_id, index_project_folder
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_index import ChromaVectorStore


class ZeroEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 0.0]


@pytest.fixture
def tiny_project(tmp_path: Path) -> Path:
    project = tmp_path / "tiny_project"
    project.mkdir()
    (project / "mixed.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    return project


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chroma_dir = tmp_path / "chroma"
    graph_dir = tmp_path / "graph"
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(chroma_dir))
    monkeypatch.setenv("GRAPH_PERSIST_DIR", str(graph_dir))

    vector_store = ChromaVectorStore(
        persist_dir=chroma_dir,
        embedding_model=ZeroEmbeddings(),
    )
    graph_store = NetworkXGraphStore(persist_dir=graph_dir)
    return vector_store, graph_store


def test_canonical_project_id_resolves_relative_and_absolute(
    tiny_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tiny_project.parent)
    absolute_id = canonical_project_id(str(tiny_project))
    relative_id = canonical_project_id("tiny_project")

    assert absolute_id == relative_id
    assert absolute_id == tiny_project.resolve().as_posix()


def test_index_project_folder_marks_project_ready(
    tiny_project: Path,
    isolated_stores,
):
    vector_store, graph_store = isolated_stores

    result = index_project_folder(
        str(tiny_project),
        vector_store=vector_store,
        graph_store=graph_store,
    )

    assert result.success is True
    assert result.ready is True
    assert result.files_scanned == 1
    assert result.chunks_indexed > 0
    assert result.graph_nodes > 0
    assert result.project_id == tiny_project.resolve().as_posix()
    assert is_project_ready(result.project_id, vector_store=vector_store, graph_store=graph_store)


def test_normalize_folder_input_adds_leading_slash_for_macos_users_path():
    from project_indexing import normalize_folder_input

    assert normalize_folder_input("Users/me/project") == "/Users/me/project"
    assert normalize_folder_input('"/Users/me/project"') == "/Users/me/project"


def test_resolve_project_folder_accepts_users_prefix_without_leading_slash(
    tiny_project: Path,
):
    from project_indexing import resolve_project_folder

    # Simulate macOS paste: strip mount prefix from absolute path.
    abs_path = tiny_project.as_posix()
    if abs_path.startswith("/Users/"):
        users_prefixed = abs_path[len("/") :]  # "Users/..."
        assert resolve_project_folder(users_prefixed) == tiny_project.resolve()


def test_index_project_api_returns_ready_project(
    client,
    tiny_project: Path,
    isolated_stores,
    monkeypatch: pytest.MonkeyPatch,
):
    vector_store, graph_store = isolated_stores
    monkeypatch.setattr(
        "project_indexing.ChromaVectorStore",
        lambda *args, **kwargs: vector_store,
    )
    monkeypatch.setattr(
        "project_indexing.NetworkXGraphStore",
        lambda *args, **kwargs: graph_store,
    )

    response = client.post(
        "/api/index-project",
        json={"folder_path": str(tiny_project)},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["ready"] is True
    assert data["project_id"] == tiny_project.resolve().as_posix()
    assert data["files_scanned"] == 1


def test_index_project_api_rejects_missing_folder(client):
    response = client.post(
        "/api/index-project",
        json={"folder_path": "/path/that/does/not/exist"},
    )
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data


def test_index_project_api_requires_folder_path(client):
    response = client.post("/api/index-project", json={})
    data = response.get_json()

    assert response.status_code == 400
    assert "folder_path" in data["error"].lower()
