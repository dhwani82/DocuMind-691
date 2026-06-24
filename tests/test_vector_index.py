"""Tests for project vector indexing."""

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from chunking import chunk_file
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_index import ChromaVectorStore, ingest_project, is_indexed, query_project


class KeywordEmbeddings(Embeddings):
    """Deterministic local embeddings for tests without network calls."""

    def __init__(self, keywords: list[str]):
        self.keywords = keywords

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [1.0 if keyword in lowered else 0.0 for keyword in self.keywords]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_project"
    project.mkdir()
    (project / "mixed.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    return project


@pytest.fixture
def embeddings() -> KeywordEmbeddings:
    return KeywordEmbeddings(
        keywords=["load_config", "dataprocessor", "process", "validate", "save_result"]
    )


@pytest.fixture
def vector_store(tmp_path: Path, embeddings: KeywordEmbeddings) -> ChromaVectorStore:
    return ChromaVectorStore(persist_dir=tmp_path / "chroma", embedding_model=embeddings)


def test_ingest_and_is_indexed(sample_project: Path, vector_store: ChromaVectorStore):
    files = [str(sample_project / "mixed.py")]
    count = ingest_project(
        "sample-project",
        files,
        vector_store=vector_store,
        chunker=lambda file_path: chunk_file(sample_project / "mixed.py"),
    )

    assert count > 0
    assert is_indexed("sample-project", vector_store=vector_store)


def test_similarity_query_returns_grounded_chunk(
    sample_project: Path,
    vector_store: ChromaVectorStore,
):
    files = [str(sample_project / "mixed.py")]
    ingest_project(
        "sample-project",
        files,
        vector_store=vector_store,
        chunker=lambda _file_path: chunk_file(sample_project / "mixed.py"),
    )

    hits = query_project(
        "sample-project",
        "load_config function",
        top_k=3,
        vector_store=vector_store,
    )

    assert hits
    assert any("def load_config" in hit["text"] for hit in hits)
    assert any(hit["metadata"].get("symbol_name") == "load_config" for hit in hits)


def test_query_empty_when_project_not_indexed(vector_store: ChromaVectorStore):
    assert is_indexed("missing-project", vector_store=vector_store) is False
    assert query_project("missing-project", "anything", vector_store=vector_store) == []
