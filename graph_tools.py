"""Graph query tools for deterministic structural code questions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import networkx as nx
from langchain_core.tools import BaseTool, StructuredTool

from code_graph import (
    EDGE_CALLS,
    EDGE_IMPORTS,
    EDGE_INHERITS,
    CodeGraphStore,
    NetworkXGraphStore,
    load_graph,
)


def _calls_subgraph(graph: nx.DiGraph) -> nx.DiGraph:
    edges = [
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data.get("relation") == EDGE_CALLS
    ]
    return graph.edge_subgraph(edges).copy()


def _resolve_symbol_nodes(graph: nx.DiGraph, symbol: str) -> list[str]:
    symbol = symbol.strip()
    if not symbol:
        return []

    matches: list[str] = []
    for node_id, data in graph.nodes(data=True):
        name = str(data.get("name", ""))
        if (
            name == symbol
            or name.endswith(f".{symbol}")
            or node_id.endswith(f":{symbol}")
            or node_id.endswith(f":{symbol.split('.')[-1]}")
        ):
            matches.append(node_id)

    # Prefer exact name matches over partial suffix matches.
    exact = [node_id for node_id in matches if graph.nodes[node_id].get("name") == symbol]
    if exact:
        return sorted(exact)

    qualified = [node_id for node_id in matches if node_id.endswith(f":{symbol}")]
    if qualified:
        return sorted(qualified)

    return sorted(set(matches))


def _node_summary(graph: nx.DiGraph, node_id: str) -> dict[str, Any]:
    data = dict(graph.nodes[node_id])
    data["id"] = node_id
    return data


def who_calls(
    project_id: str,
    symbol: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> list[dict[str, Any]]:
    """Return direct callers of a symbol."""
    graph = load_graph(project_id, graph_store=graph_store)
    if graph is None:
        return []

    targets = _resolve_symbol_nodes(graph, symbol)
    if not targets:
        return []

    calls = _calls_subgraph(graph)
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for target in targets:
        for caller in calls.predecessors(target):
            key = (caller, target)
            if key in seen:
                continue
            seen.add(key)
            edge_data = calls.get_edge_data(caller, target, default={})
            results.append(
                {
                    "caller": _node_summary(graph, caller),
                    "callee": _node_summary(graph, target),
                    "relation": EDGE_CALLS,
                    "line": edge_data.get("line"),
                    "file_path": edge_data.get("file_path"),
                }
            )

    return sorted(results, key=lambda item: (item["caller"]["id"], item["callee"]["id"]))


def what_calls(
    project_id: str,
    symbol: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> list[dict[str, Any]]:
    """Return direct callees of a symbol."""
    graph = load_graph(project_id, graph_store=graph_store)
    if graph is None:
        return []

    sources = _resolve_symbol_nodes(graph, symbol)
    if not sources:
        return []

    calls = _calls_subgraph(graph)
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for source in sources:
        for callee in calls.successors(source):
            key = (source, callee)
            if key in seen:
                continue
            seen.add(key)
            edge_data = calls.get_edge_data(source, callee, default={})
            results.append(
                {
                    "caller": _node_summary(graph, source),
                    "callee": _node_summary(graph, callee),
                    "relation": EDGE_CALLS,
                    "line": edge_data.get("line"),
                    "file_path": edge_data.get("file_path"),
                }
            )

    return sorted(results, key=lambda item: (item["caller"]["id"], item["callee"]["id"]))


def impact_of(
    project_id: str,
    symbol: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> list[dict[str, Any]]:
    """Return transitive callers / dependents for a symbol."""
    graph = load_graph(project_id, graph_store=graph_store)
    if graph is None:
        return []

    targets = _resolve_symbol_nodes(graph, symbol)
    if not targets:
        return []

    calls = _calls_subgraph(graph)
    reverse_calls = calls.reverse(copy=True)
    impacted: set[str] = set()

    for target in targets:
        if target in reverse_calls:
            impacted |= nx.descendants(reverse_calls, target)

    return sorted(
        (_node_summary(graph, node_id) for node_id in impacted),
        key=lambda item: item["id"],
    )


def dependencies_of(
    project_id: str,
    symbol: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> list[dict[str, Any]]:
    """Return transitive callees plus structural import/inheritance dependencies."""
    graph = load_graph(project_id, graph_store=graph_store)
    if graph is None:
        return []

    sources = _resolve_symbol_nodes(graph, symbol)
    if not sources:
        return []

    dependency_edges = {
        EDGE_CALLS,
        EDGE_IMPORTS,
        EDGE_INHERITS,
    }
    dep_graph = nx.DiGraph()
    dep_graph.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        if data.get("relation") in dependency_edges:
            dep_graph.add_edge(source, target, **data)

    dependencies: set[str] = set()
    for source in sources:
        if source in dep_graph:
            dependencies |= nx.descendants(dep_graph, source)

    return sorted(
        (_node_summary(graph, node_id) for node_id in dependencies),
        key=lambda item: item["id"],
    )


@dataclass
class GraphQueryTools:
    """LangChain graph query tools bound to a project graph."""

    project_id: str
    graph_store: Optional[CodeGraphStore] = None

    def who_calls(self, symbol: str) -> str:
        return json.dumps(
            who_calls(self.project_id, symbol, graph_store=self.graph_store),
            indent=2,
        )

    def what_calls(self, symbol: str) -> str:
        return json.dumps(
            what_calls(self.project_id, symbol, graph_store=self.graph_store),
            indent=2,
        )

    def impact_of(self, symbol: str) -> str:
        return json.dumps(
            impact_of(self.project_id, symbol, graph_store=self.graph_store),
            indent=2,
        )

    def dependencies_of(self, symbol: str) -> str:
        return json.dumps(
            dependencies_of(self.project_id, symbol, graph_store=self.graph_store),
            indent=2,
        )


def create_graph_tools(
    project_id: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> list[BaseTool]:
    """Create LangChain tools for graph queries."""
    tools = GraphQueryTools(project_id=project_id, graph_store=graph_store)

    return [
        StructuredTool.from_function(
            func=tools.who_calls,
            name="who_calls",
            description="Return direct callers of a function, method, or class symbol.",
        ),
        StructuredTool.from_function(
            func=tools.what_calls,
            name="what_calls",
            description="Return direct callees of a function, method, or class symbol.",
        ),
        StructuredTool.from_function(
            func=tools.impact_of,
            name="impact_of",
            description=(
                "Return transitive callers/dependents affected by a symbol change."
            ),
        ),
        StructuredTool.from_function(
            func=tools.dependencies_of,
            name="dependencies_of",
            description=(
                "Return transitive dependencies: callees, imports, and inherited bases."
            ),
        ),
    ]
