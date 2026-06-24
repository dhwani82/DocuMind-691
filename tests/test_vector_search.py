"""Tests for hybrid vector retrieval and LangChain tool."""

import json
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from chunking import ChunkConfig, chunk_file
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_index import ChromaVectorStore, ingest_project
from vector_search import (
    SearchFilters,
    create_retrieval_tools,
    create_vector_search_tool,
    vector_search,
)


class KeywordEmbeddings(Embeddings):
    def __init__(self, keywords: list[str]):
        self.keywords = keywords

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [1.0 if keyword in lowered else 0.0 for keyword in self.keywords]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class MisleadingEmbeddings(Embeddings):
    """Embeddings that rank save_result above load_config for the load_config query."""

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            if "save_result" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "load_config" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            elif "dataprocessor" in lowered:
                vectors.append([0.0, 0.0, 1.0])
            else:
                vectors.append([0.1, 0.1, 0.1])
        return vectors


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_project"
    project.mkdir()
    (project / "mixed.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    return project


@pytest.fixture
def misleading_store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(
        persist_dir=tmp_path / "chroma",
        embedding_model=MisleadingEmbeddings(),
    )


@pytest.fixture
def indexed_project(sample_project: Path, misleading_store: ChromaVectorStore) -> str:
    chunk_config = ChunkConfig(chunk_lines=8, chunk_lines_overlap=1, max_chars=100)
    ingest_project(
        "sample-project",
        [str(sample_project / "mixed.py")],
        vector_store=misleading_store,
        chunker=lambda _file_path: chunk_file(sample_project / "mixed.py", config=chunk_config),
    )
    return "sample-project"


def test_vector_search_tool_is_registered(indexed_project: str, misleading_store: ChromaVectorStore):
    tools = create_retrieval_tools(
        project_root=".",
        project_id=indexed_project,
        vector_store=misleading_store,
    )
    assert [tool.name for tool in tools][-1] == "vector_search"


def test_metadata_filters_language(indexed_project: str, misleading_store: ChromaVectorStore):
    hits = vector_search(
        indexed_project,
        "load_config",
        k=5,
        filters=SearchFilters(language="python"),
        vector_store=misleading_store,
        hybrid_enabled=True,
    )
    assert hits
    assert all(hit["metadata"]["language"] == "python" for hit in hits)


def test_hybrid_beats_pure_vector_on_exact_identifier(
    indexed_project: str,
    misleading_store: ChromaVectorStore,
):
    query = "load_config"

    pure_hits = vector_search(
        indexed_project,
        query,
        k=3,
        vector_store=misleading_store,
        hybrid_enabled=False,
    )
    hybrid_hits = vector_search(
        indexed_project,
        query,
        k=3,
        vector_store=misleading_store,
        hybrid_enabled=True,
        hybrid_alpha=0.35,
    )

    assert pure_hits
    assert hybrid_hits
    assert pure_hits[0]["metadata"].get("symbol_name") != "load_config"
    assert hybrid_hits[0]["metadata"].get("symbol_name") == "load_config"


def test_vector_search_tool_returns_json(indexed_project: str, misleading_store: ChromaVectorStore):
    tool = create_vector_search_tool(indexed_project, vector_store=misleading_store)
    payload = json.loads(tool.invoke({"query": "load_config", "k": 2}))

    assert isinstance(payload, list)
    assert payload
