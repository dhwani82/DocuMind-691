"""Tests for the code knowledge graph."""

from pathlib import Path

import networkx as nx
import pytest

from code_graph import (
    EDGE_CALLS,
    EDGE_DEFINES,
    EDGE_IMPORTS,
    EDGE_INHERITS,
    NetworkXGraphStore,
    build_graph,
    graph_edges,
    has_graph,
    load_graph,
    module_node_id,
)
from tests.sample_code_for_testing import SAMPLE_INHERITANCE, SAMPLE_MIXED

SAMPLE_CALLS = '''
def helper():
    return 1

def main():
    return helper()
'''


@pytest.fixture
def graph_store(tmp_path: Path) -> NetworkXGraphStore:
    return NetworkXGraphStore(persist_dir=tmp_path / "graphs")


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_project"
    project.mkdir()
    (project / "mixed.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    (project / "calls.py").write_text(SAMPLE_CALLS.strip() + "\n", encoding="utf-8")
    (project / "inheritance.py").write_text(SAMPLE_INHERITANCE.strip() + "\n", encoding="utf-8")
    return project


def test_build_graph_persists_and_reloads(sample_project: Path, graph_store: NetworkXGraphStore):
    files = [
        str(sample_project / "mixed.py"),
        str(sample_project / "calls.py"),
    ]
    stats = build_graph("sample-project", files, graph_store=graph_store)

    assert stats["nodes"] > 0
    assert stats["edges"] > 0
    assert has_graph("sample-project", graph_store=graph_store)

    graph = load_graph("sample-project", graph_store=graph_store)
    assert graph is not None
    assert graph.number_of_nodes() == stats["nodes"]


def test_graph_contains_import_edges(sample_project: Path, graph_store: NetworkXGraphStore):
    build_graph("sample-project", [str(sample_project / "mixed.py")], graph_store=graph_store)
    graph = load_graph("sample-project", graph_store=graph_store)
    assert graph is not None

    imports = graph_edges(graph, relation=EDGE_IMPORTS)
    targets = {edge["target"] for edge in imports}
    sources = {edge["source"] for edge in imports}

    assert any(source.startswith("file:") and source.endswith("mixed.py") for source in sources)
    assert module_node_id("os") in targets
    assert module_node_id("pathlib.Path") in targets


def test_graph_contains_define_and_call_edges(sample_project: Path, graph_store: NetworkXGraphStore):
    build_graph(
        "sample-project",
        [str(sample_project / "mixed.py"), str(sample_project / "calls.py")],
        graph_store=graph_store,
    )
    graph = load_graph("sample-project", graph_store=graph_store)
    assert graph is not None

    defines = graph_edges(graph, relation=EDGE_DEFINES)
    define_targets = {(edge["source"], edge["target"]) for edge in defines}
    assert any(target.endswith(":load_config") for _, target in define_targets)
    assert any(target.endswith(":DataProcessor") for _, target in define_targets)
    assert any(target.endswith(":helper") for _, target in define_targets)

    calls = graph_edges(graph, relation=EDGE_CALLS)
    assert any(
        edge["source"].endswith(":main") and edge["target"].endswith(":helper")
        for edge in calls
    )


def test_graph_contains_inherits_edges(sample_project: Path, graph_store: NetworkXGraphStore):
    build_graph("sample-project", [str(sample_project / "inheritance.py")], graph_store=graph_store)
    graph = load_graph("sample-project", graph_store=graph_store)
    assert graph is not None

    inherits = graph_edges(graph, relation=EDGE_INHERITS)
    assert any(
        edge["source"].endswith(":Dog") and edge["target"].endswith(":Animal")
        for edge in inherits
    )
    assert any(
        edge["source"].endswith(":Cat") and edge["target"].endswith(":Animal")
        for edge in inherits
    )


def test_graph_json_roundtrip_has_edge_metadata(graph_store: NetworkXGraphStore):
    graph = nx.DiGraph()
    graph.add_node("file:a.py", kind="file", name="a.py", file_path="a.py")
    graph.add_node("module:os", kind="module", name="os")
    graph.add_edge("file:a.py", "module:os", relation=EDGE_IMPORTS, line=1, file_path="a.py")

    graph_store.save_graph("roundtrip", graph)
    loaded = graph_store.load_graph("roundtrip")
    assert loaded is not None
    assert loaded.number_of_edges() == 1
    _, _, data = next(iter(loaded.edges(data=True)))
    assert data["relation"] == EDGE_IMPORTS
    assert data["line"] == 1
