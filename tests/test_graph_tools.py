"""Tests for graph query tools."""

from pathlib import Path

import pytest

from code_graph import NetworkXGraphStore, build_graph
from graph_tools import (
    create_graph_tools,
    dependencies_of,
    impact_of,
    what_calls,
    who_calls,
)

CALL_CHAIN = '''
def leaf():
    return 1

def middle():
    return leaf()

def top():
    return middle()
'''

METHOD_CALLS = '''
class Service:
    def run(self):
        return self.process()

    def process(self):
        return 1
'''


@pytest.fixture
def graph_store(tmp_path: Path) -> NetworkXGraphStore:
    return NetworkXGraphStore(persist_dir=tmp_path / "graphs")


@pytest.fixture
def call_chain_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "chain.py").write_text(CALL_CHAIN.strip() + "\n", encoding="utf-8")
    return project


@pytest.fixture
def method_project(tmp_path: Path) -> Path:
    project = tmp_path / "method_project"
    project.mkdir()
    (project / "service.py").write_text(METHOD_CALLS.strip() + "\n", encoding="utf-8")
    return project


def test_who_calls_direct_only(call_chain_project: Path, graph_store: NetworkXGraphStore):
    build_graph("chain", [str(call_chain_project / "chain.py")], graph_store=graph_store)

    callers = who_calls("chain", "leaf", graph_store=graph_store)
    caller_names = {item["caller"]["name"] for item in callers}

    assert caller_names == {"middle"}


def test_what_calls_direct_only(call_chain_project: Path, graph_store: NetworkXGraphStore):
    build_graph("chain", [str(call_chain_project / "chain.py")], graph_store=graph_store)

    callees = what_calls("chain", "top", graph_store=graph_store)
    callee_names = {item["callee"]["name"] for item in callees}

    assert callee_names == {"middle"}


def test_impact_of_is_transitive(call_chain_project: Path, graph_store: NetworkXGraphStore):
    build_graph("chain", [str(call_chain_project / "chain.py")], graph_store=graph_store)

    impacted = impact_of("chain", "leaf", graph_store=graph_store)
    impacted_names = {item["name"] for item in impacted}

    assert impacted_names == {"middle", "top"}


def test_dependencies_of_is_transitive(call_chain_project: Path, graph_store: NetworkXGraphStore):
    build_graph("chain", [str(call_chain_project / "chain.py")], graph_store=graph_store)

    deps = dependencies_of("chain", "top", graph_store=graph_store)
    dep_names = {item["name"] for item in deps}

    assert dep_names == {"middle", "leaf"}


def test_method_call_edge_resolves_qualified_name(
    method_project: Path,
    graph_store: NetworkXGraphStore,
):
    build_graph("method", [str(method_project / "service.py")], graph_store=graph_store)

    callees = what_calls("method", "Service.run", graph_store=graph_store)
    callee_names = {item["callee"]["name"] for item in callees}

    assert "Service.process" in callee_names


def test_create_graph_tools_exposes_four_tools(graph_store: NetworkXGraphStore):
    tools = create_graph_tools("demo", graph_store=graph_store)
    assert [tool.name for tool in tools] == [
        "who_calls",
        "what_calls",
        "impact_of",
        "dependencies_of",
    ]
