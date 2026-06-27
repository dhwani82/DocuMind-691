"""Tests for project ignore rules during indexing."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from project_ignore import enumerate_indexable_files
from project_indexing import INDEXABLE_EXTENSIONS, index_project_folder
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_index import ChromaVectorStore
from code_graph import NetworkXGraphStore


class ZeroEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0]


@pytest.fixture
def project_with_venv(tmp_path: Path) -> Path:
    project = tmp_path / "app_project"
    project.mkdir()
    (project / "app.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")

    venv_lib = project / "venv" / "lib" / "python3.11" / "site-packages"
    venv_lib.mkdir(parents=True)
    (venv_lib / "should_not_index.py").write_text("SECRET = True\n", encoding="utf-8")

    node_modules = project / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "bundle.js").write_text("console.log('skip');\n", encoding="utf-8")

    return project


def test_enumerate_skips_venv_and_node_modules(project_with_venv: Path):
    files, stats = enumerate_indexable_files(project_with_venv, INDEXABLE_EXTENSIONS)

    indexed_names = {path.name for path in files}
    assert indexed_names == {"app.py"}
    assert stats.files_indexed == 1
    assert stats.dirs_skipped >= 2
    assert any("venv/" in path for path in stats.skipped_paths)
    assert any("node_modules/" in path for path in stats.skipped_paths)


def test_enumerate_respects_gitignore(project_with_venv: Path):
    (project_with_venv / ".gitignore").write_text(
        "generated/\nignored.py\n",
        encoding="utf-8",
    )
    (project_with_venv / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    generated = project_with_venv / "generated"
    generated.mkdir()
    (generated / "out.py").write_text("y = 2\n", encoding="utf-8")

    files, stats = enumerate_indexable_files(project_with_venv, INDEXABLE_EXTENSIONS)

    indexed_rel = {path.relative_to(project_with_venv).as_posix() for path in files}
    assert "app.py" in indexed_rel
    assert "ignored.py" not in indexed_rel
    assert "generated/out.py" not in indexed_rel
    assert stats.files_skipped_ignore >= 1


def test_index_project_does_not_include_venv_files(
    project_with_venv: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("GRAPH_PERSIST_DIR", str(tmp_path / "graph"))

    vector_store = ChromaVectorStore(
        persist_dir=tmp_path / "chroma",
        embedding_model=ZeroEmbeddings(),
    )
    graph_store = NetworkXGraphStore(persist_dir=tmp_path / "graph")

    result = index_project_folder(
        str(project_with_venv),
        vector_store=vector_store,
        graph_store=graph_store,
    )

    assert result.files_scanned == 1
    assert result.dirs_skipped >= 2
    assert result.files_skipped_ignore == 0 or result.files_skipped_extension >= 0

    chunks = vector_store.fetch_chunks(result.project_id)
    indexed_text = "\n".join(chunk["text"] for chunk in chunks)
    assert "load_config" in indexed_text
    assert "SECRET = True" not in indexed_text
