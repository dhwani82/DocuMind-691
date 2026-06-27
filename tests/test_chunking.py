"""Tests for AST-aware code chunking."""

from pathlib import Path

import pytest

from chunking import ChunkConfig, chunk_file, chunk_source, lines_are_tiled
from tests.sample_code_for_testing import SAMPLE_MIXED, SAMPLE_SIMPLE_FUNCTIONS


@pytest.fixture
def mixed_file(tmp_path: Path) -> Path:
    path = tmp_path / "mixed.py"
    path.write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    return path


@pytest.fixture
def simple_file(tmp_path: Path) -> Path:
    path = tmp_path / "simple.py"
    path.write_text(SAMPLE_SIMPLE_FUNCTIONS.strip() + "\n", encoding="utf-8")
    return path


def test_chunks_tile_file_with_small_line_windows(simple_file: Path):
    config = ChunkConfig(chunk_lines=4, chunk_lines_overlap=1, max_chars=500)
    chunks = chunk_file(simple_file, config=config)
    total_lines = len(simple_file.read_text(encoding="utf-8").splitlines())

    assert chunks
    assert lines_are_tiled(chunks, total_lines)


def test_chunk_metadata_is_populated(mixed_file: Path):
    chunks = chunk_file(mixed_file, config=ChunkConfig(chunk_lines=8, chunk_lines_overlap=2))

    assert chunks
    for chunk in chunks:
        assert chunk.metadata["file_path"] == mixed_file.as_posix()
        assert chunk.metadata["language"] == "python"
        assert chunk.metadata["start_line"] >= 1
        assert chunk.metadata["end_line"] >= chunk.metadata["start_line"]
        assert chunk.metadata["chunker"] in {
            "code_splitter",
            "fallback_lines",
            "fallback_sentences",
            "fallback_whole_file",
        }


def test_chunk_carries_enclosing_symbol_from_parser(mixed_file: Path):
    chunks = chunk_file(
        mixed_file,
        config=ChunkConfig(chunk_lines=6, chunk_lines_overlap=1, max_chars=200),
    )

    load_config_chunks = [
        chunk for chunk in chunks if "def load_config" in chunk.text
    ]
    assert load_config_chunks
    assert load_config_chunks[0].metadata.get("symbol_name") == "load_config"

    processor_chunks = [
        chunk for chunk in chunks if "class DataProcessor" in chunk.text
    ]
    assert processor_chunks
    assert processor_chunks[0].metadata.get("symbol_name") == "DataProcessor"


def test_fallback_splitter_used_when_code_splitter_unavailable(monkeypatch):
    code = SAMPLE_SIMPLE_FUNCTIONS.strip()

    def fail_code_splitter(*_args, **_kwargs):
        raise RuntimeError("CodeSplitter unavailable")

    monkeypatch.setattr("chunking._split_with_code_splitter", fail_code_splitter)

    chunks = chunk_source(
        file_path="simple.py",
        code=code,
        config=ChunkConfig(chunk_lines=4, chunk_lines_overlap=1, max_chars=200),
        language="python",
    )

    assert chunks
    assert any(chunk.metadata["chunker"].startswith("fallback") for chunk in chunks)
    assert lines_are_tiled(chunks, len(code.splitlines()))


def test_no_file_is_dropped_for_unsupported_language():
    code = "int main() { return 0; }\n"
    chunks = chunk_source(
        file_path="main.c",
        code=code,
        config=ChunkConfig(chunk_lines=2, chunk_lines_overlap=0, max_chars=200),
        language="c",
    )

    assert chunks
    assert chunks[0].text
    assert chunks[0].metadata["language"] == "c"
