"""Index a project folder for Ask DocuMind (vector store + code graph)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from chunking import chunk_file
from code_graph import NetworkXGraphStore, build_graph, has_graph
from code_tools import SKIP_DIRS
from vector_index import ChromaVectorStore, ingest_project, is_indexed

INDEXABLE_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyw",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".sql",
    }
)


def resolve_project_folder(path_or_id: str) -> Path:
    """Resolve user input to an existing project directory."""
    raw = (path_or_id or "").strip()
    if not raw:
        raise ValueError("folder path is required")

    candidate = Path(raw).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    cwd_candidate = (Path.cwd() / raw).resolve()
    if cwd_candidate.is_dir():
        return cwd_candidate.resolve()

    raise ValueError(
        f"Project directory not found for '{path_or_id}'. "
        "Use an absolute path or a folder under the current working directory."
    )


def canonical_project_id(path_or_id: str) -> str:
    """Return the stable project_id used for indexing and agent queries."""
    return resolve_project_folder(path_or_id).as_posix()


def collect_indexable_files(project_root: Path) -> list[Path]:
    """Collect source files under project_root for indexing."""
    root = project_root.resolve()
    files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
                continue
            if path.is_file():
                files.append(path.resolve())

    return files


@dataclass
class IndexProjectResult:
    """Outcome of indexing a project folder."""

    success: bool
    project_id: str
    project_root: str
    ready: bool
    files_scanned: int
    chunks_indexed: int
    graph_nodes: int
    graph_edges: int
    phases: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def index_project_folder(
    folder_path: str,
    *,
    vector_store: Optional[ChromaVectorStore] = None,
    graph_store: Optional[NetworkXGraphStore] = None,
) -> IndexProjectResult:
    """Ingest vectors and build the code graph for a folder."""
    project_root = resolve_project_folder(folder_path)
    project_id = project_root.as_posix()
    phases: list[dict[str, Any]] = []

    files = collect_indexable_files(project_root)
    phases.append(
        {
            "phase": "scan",
            "status": "complete",
            "files_scanned": len(files),
        }
    )

    if not files:
        raise ValueError(f"No indexable source files found under {project_root}")

    store = vector_store or ChromaVectorStore()
    graph = graph_store or NetworkXGraphStore()

    file_strings = [str(path) for path in files]
    chunks_indexed = ingest_project(
        project_id,
        file_strings,
        vector_store=store,
        chunker=chunk_file,
        project_root=project_root,
    )
    phases.append(
        {
            "phase": "vector_ingestion",
            "status": "complete",
            "chunks_indexed": chunks_indexed,
        }
    )

    graph_stats = build_graph(
        project_id,
        file_strings,
        graph_store=graph,
        project_root=project_root,
    )
    phases.append(
        {
            "phase": "graph_build",
            "status": "complete",
            "graph_nodes": graph_stats["nodes"],
            "graph_edges": graph_stats["edges"],
        }
    )

    ready = is_indexed(project_id, vector_store=store) and has_graph(
        project_id, graph_store=graph
    )

    return IndexProjectResult(
        success=True,
        project_id=project_id,
        project_root=project_id,
        ready=ready,
        files_scanned=len(files),
        chunks_indexed=chunks_indexed,
        graph_nodes=graph_stats["nodes"],
        graph_edges=graph_stats["edges"],
        phases=phases,
    )
