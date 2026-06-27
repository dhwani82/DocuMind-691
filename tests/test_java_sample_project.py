"""Tests for indexing the Java sample project."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from agent import is_project_ready
from code_graph import NetworkXGraphStore
from eval.sample_java_project import ensure_sample_java_project
from project_indexing import index_project_folder
from vector_index import ChromaVectorStore


class ZeroEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 0.0]


@pytest.fixture
def java_project(tmp_path: Path) -> Path:
    return ensure_sample_java_project(tmp_path / "java_sample")


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


def test_index_java_sample_project(java_project: Path, isolated_stores):
    vector_store, graph_store = isolated_stores

    result = index_project_folder(
        str(java_project),
        vector_store=vector_store,
        graph_store=graph_store,
    )

    assert result.ready is True
    assert result.files_scanned == 6
    assert result.chunks_indexed > 0
    assert result.graph_nodes > 0
    assert is_project_ready(result.project_id, vector_store=vector_store, graph_store=graph_store)
