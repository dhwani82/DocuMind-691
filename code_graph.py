"""Code knowledge graph built from existing parser outputs."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from code_parser import CodeParser
from javascript_parser import JavaScriptParser
from java_parser import JavaParser
from language_detector import LanguageDetector
from sql_parser import SQLParser

PARSEABLE_LANGUAGES = frozenset({"python", "javascript", "java", "sql"})
DEFAULT_GRAPH_DIR = Path(os.getenv("GRAPH_PERSIST_DIR", ".graph_store"))

EDGE_IMPORTS = "imports"
EDGE_DEFINES = "defines"
EDGE_CALLS = "calls"
EDGE_INHERITS = "inherits"

NODE_FILE = "file"
NODE_CLASS = "class"
NODE_FUNCTION = "function"
NODE_MODULE = "module"


def _safe_project_filename(project_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id).strip("_")
    if not safe:
        raise ValueError("project_id must contain at least one alphanumeric character")
    return safe


def _parse_code(code: str, language: str) -> dict[str, Any]:
    lang = (language or "python").lower()
    if lang == "python":
        return CodeParser().parse(code)
    if lang == "javascript":
        return JavaScriptParser().parse(code)
    if lang == "java":
        return JavaParser().parse(code)
    if lang == "sql":
        return SQLParser().parse(code)
    return {}


def file_node_id(file_path: str) -> str:
    return f"{NODE_FILE}:{file_path}"


def class_node_id(file_path: str, name: str) -> str:
    return f"{NODE_CLASS}:{file_path}:{name}"


def function_node_id(file_path: str, name: str) -> str:
    return f"{NODE_FUNCTION}:{file_path}:{name}"


def module_node_id(module_name: str) -> str:
    return f"{NODE_MODULE}:{module_name}"


class CodeGraphStore(ABC):
    """Interface for persisting and loading project code graphs."""

    @abstractmethod
    def save_graph(self, project_id: str, graph: nx.DiGraph) -> None:
        """Persist a project graph."""

    @abstractmethod
    def load_graph(self, project_id: str) -> Optional[nx.DiGraph]:
        """Load a persisted project graph if present."""

    @abstractmethod
    def has_graph(self, project_id: str) -> bool:
        """Return True when a graph exists for the project."""

    @abstractmethod
    def delete_graph(self, project_id: str) -> None:
        """Delete a persisted project graph."""


class NetworkXGraphStore(CodeGraphStore):
    """NetworkX-backed graph store persisted as node-link JSON."""

    def __init__(self, persist_dir: str | Path = DEFAULT_GRAPH_DIR) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def _graph_path(self, project_id: str) -> Path:
        return self.persist_dir / f"{_safe_project_filename(project_id)}.json"

    def save_graph(self, project_id: str, graph: nx.DiGraph) -> None:
        path = self._graph_path(project_id)
        payload = nx.node_link_data(graph)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_graph(self, project_id: str) -> Optional[nx.DiGraph]:
        path = self._graph_path(project_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return nx.node_link_graph(payload, directed=True)

    def has_graph(self, project_id: str) -> bool:
        return self._graph_path(project_id).is_file()

    def delete_graph(self, project_id: str) -> None:
        path = self._graph_path(project_id)
        if path.exists():
            path.unlink()


class CodeGraphBuilder:
    """Build a directed code graph from parsed file results."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._module_paths: dict[str, str] = {}
        self._definitions: dict[str, dict[str, str]] = {}

    def _ensure_node(
        self,
        node_id: str,
        *,
        kind: str,
        name: str,
        file_path: str = "",
        line: Optional[int] = None,
    ) -> None:
        if node_id not in self.graph:
            self.graph.add_node(
                node_id,
                kind=kind,
                name=name,
                file_path=file_path,
                line=line,
            )

    def _add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        line: Optional[int] = None,
        file_path: str = "",
    ) -> None:
        if source == target:
            return
        attrs: dict[str, Any] = {"relation": relation}
        if line is not None:
            attrs["line"] = line
        if file_path:
            attrs["file_path"] = file_path
        self.graph.add_edge(source, target, **attrs)

    def _register_module(self, file_path: str) -> None:
        self._module_paths[Path(file_path).stem] = file_path

    def _register_definition(self, file_path: str, name: str, node_id: str) -> None:
        self._definitions.setdefault(file_path, {})[name] = node_id

    def add_structure(self, file_path: str, parsed: dict[str, Any]) -> None:
        """Add file nodes, imports, and symbol definitions."""
        self._register_module(file_path)
        file_id = file_node_id(file_path)
        self._ensure_node(file_id, kind=NODE_FILE, name=file_path, file_path=file_path)

        for import_info in parsed.get("imports", []):
            module_name = self._import_target(import_info)
            if not module_name:
                continue
            module_id = module_node_id(module_name)
            self._ensure_node(module_id, kind=NODE_MODULE, name=module_name)
            self._add_edge(
                file_id,
                module_id,
                EDGE_IMPORTS,
                line=import_info.get("line"),
                file_path=file_path,
            )

        for func in parsed.get("functions", []):
            if func.get("is_nested"):
                continue
            func_name = func.get("name", "")
            if not func_name:
                continue
            func_id = function_node_id(file_path, func_name)
            self._ensure_node(
                func_id,
                kind=NODE_FUNCTION,
                name=func_name,
                file_path=file_path,
                line=func.get("line"),
            )
            self._add_edge(
                file_id,
                func_id,
                EDGE_DEFINES,
                line=func.get("line"),
                file_path=file_path,
            )
            self._register_definition(file_path, func_name, func_id)

        for cls in parsed.get("classes", []):
            cls_name = cls.get("name", "")
            if not cls_name:
                continue
            cls_id = class_node_id(file_path, cls_name)
            self._ensure_node(
                cls_id,
                kind=NODE_CLASS,
                name=cls_name,
                file_path=file_path,
                line=cls.get("line"),
            )
            self._add_edge(
                file_id,
                cls_id,
                EDGE_DEFINES,
                line=cls.get("line"),
                file_path=file_path,
            )
            self._register_definition(file_path, cls_name, cls_id)

            for base in cls.get("bases", []) or []:
                if not base:
                    continue
                base_id = class_node_id(file_path, str(base))
                self._ensure_node(
                    base_id,
                    kind=NODE_CLASS,
                    name=str(base),
                    file_path=file_path,
                )
                self._add_edge(
                    cls_id,
                    base_id,
                    EDGE_INHERITS,
                    line=cls.get("line"),
                    file_path=file_path,
                )

            for method in cls.get("methods", []):
                method_name = method.get("name", "")
                if not method_name:
                    continue
                qualified = f"{cls_name}.{method_name}"
                method_id = function_node_id(file_path, qualified)
                self._ensure_node(
                    method_id,
                    kind=NODE_FUNCTION,
                    name=qualified,
                    file_path=file_path,
                    line=method.get("line"),
                )
                self._add_edge(
                    cls_id,
                    method_id,
                    EDGE_DEFINES,
                    line=method.get("line"),
                    file_path=file_path,
                )
                self._register_definition(file_path, qualified, method_id)

    def add_calls(self, file_path: str, parsed: dict[str, Any]) -> None:
        """Add call edges after all project symbols are registered."""
        for call in parsed.get("function_calls", []):
            caller = call.get("caller")
            callee = call.get("callee")
            if not caller or not callee:
                continue
            caller_id = function_node_id(file_path, str(caller))
            callee_id = self._resolve_call_target(file_path, str(callee), parsed)
            self._ensure_node(
                caller_id,
                kind=NODE_FUNCTION,
                name=str(caller),
                file_path=file_path,
            )
            self._add_edge(
                caller_id,
                callee_id,
                EDGE_CALLS,
                line=call.get("line"),
                file_path=file_path,
            )

        for call in parsed.get("method_calls", []):
            caller = call.get("caller") or call.get("caller_class")
            method = call.get("method") or call.get("callee")
            class_name = call.get("class_name")
            if not caller or not method:
                continue
            callee = f"{class_name}.{method}" if class_name else str(method)
            caller_id = function_node_id(file_path, str(caller))
            callee_id = function_node_id(file_path, callee)
            self._ensure_node(
                caller_id,
                kind=NODE_FUNCTION,
                name=str(caller),
                file_path=file_path,
            )
            self._add_edge(
                caller_id,
                callee_id,
                EDGE_CALLS,
                line=call.get("line"),
                file_path=file_path,
            )

    def add_file(self, file_path: str, parsed: dict[str, Any]) -> None:
        """Add structure and call edges for one parsed file."""
        self.add_structure(file_path, parsed)
        self.add_calls(file_path, parsed)

    def _import_aliases(self, parsed: dict[str, Any]) -> dict[str, tuple[str, Optional[str]]]:
        aliases: dict[str, tuple[str, Optional[str]]] = {}
        for import_info in parsed.get("imports", []):
            if import_info.get("type") == "from_import":
                module = str(import_info.get("module") or "")
                name = import_info.get("name")
                alias = import_info.get("alias") or name
                if module and name and alias:
                    aliases[str(alias)] = (module, str(name))
                continue

            module = str(import_info.get("module") or "")
            alias = import_info.get("alias") or module.split(".")[-1]
            if module and alias:
                aliases[str(alias)] = (module, None)
        return aliases

    def _lookup_in_module(self, module: str, name: str) -> Optional[str]:
        target_file = self._module_paths.get(module)
        if not target_file:
            return None
        return self._definitions.get(target_file, {}).get(name)

    def _resolve_imported_callee(
        self,
        callee: str,
        parsed: dict[str, Any],
    ) -> Optional[str]:
        aliases = self._import_aliases(parsed)
        if "." not in callee:
            if callee not in aliases:
                return None
            module, imported_name = aliases[callee]
            return self._lookup_in_module(module, imported_name or callee)

        head, remainder = callee.split(".", 1)
        if head not in aliases:
            return None
        module, imported_name = aliases[head]
        base = imported_name or head
        qualified = f"{base}.{remainder}"
        return self._lookup_in_module(module, qualified) or self._lookup_in_module(
            module,
            remainder,
        )

    def _import_target(self, import_info: dict[str, Any]) -> str:
        if import_info.get("type") == "from_import":
            module = import_info.get("module") or ""
            name = import_info.get("name")
            if module and name:
                return f"{module}.{name}"
            return module or str(name or "")
        return str(import_info.get("module") or "")

    def _resolve_call_target(
        self,
        file_path: str,
        callee: str,
        parsed: dict[str, Any],
    ) -> str:
        local = self._definitions.get(file_path, {}).get(callee)
        if local:
            return local

        for func in parsed.get("functions", []):
            if func.get("name") == callee:
                return function_node_id(file_path, callee)

        for cls in parsed.get("classes", []):
            for method in cls.get("methods", []):
                qualified = f"{cls.get('name')}.{method.get('name')}"
                if qualified == callee or method.get("name") == callee:
                    return function_node_id(file_path, qualified)

        for cls in parsed.get("classes", []):
            if cls.get("name") == callee:
                return class_node_id(file_path, callee)

        imported = self._resolve_imported_callee(callee, parsed)
        if imported:
            return imported

        return function_node_id(file_path, callee)


def build_graph(
    project_id: str,
    files: list[str],
    *,
    graph_store: Optional[CodeGraphStore] = None,
    project_root: str | Path | None = None,
) -> dict[str, int]:
    """Parse project files and persist a directed code graph."""
    store = graph_store or NetworkXGraphStore()
    builder = CodeGraphBuilder()
    parsed_entries: list[tuple[str, dict[str, Any]]] = []
    root = Path(project_root).resolve() if project_root else None

    for file_path in files:
        path = Path(file_path).expanduser()
        if not path.is_absolute() and root is not None:
            path = (root / path).resolve()
        else:
            path = path.resolve()
        if not path.is_file():
            continue

        if root is not None:
            try:
                rel_path = path.relative_to(root).as_posix()
            except ValueError:
                rel_path = path.name
        else:
            rel_path = path.as_posix()

        code = path.read_text(encoding="utf-8", errors="replace")
        language = LanguageDetector.detect(filename=rel_path, code=code)
        if not language or language.lower() not in PARSEABLE_LANGUAGES:
            continue

        parsed_entries.append((rel_path, _parse_code(code, language.lower())))

    for rel_path, parsed in parsed_entries:
        builder.add_structure(rel_path, parsed)

    for rel_path, parsed in parsed_entries:
        builder.add_calls(rel_path, parsed)

    store.save_graph(project_id, builder.graph)
    return {
        "nodes": builder.graph.number_of_nodes(),
        "edges": builder.graph.number_of_edges(),
    }


def load_graph(
    project_id: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> Optional[nx.DiGraph]:
    """Load a persisted project graph."""
    store = graph_store or NetworkXGraphStore()
    return store.load_graph(project_id)


def has_graph(
    project_id: str,
    *,
    graph_store: Optional[CodeGraphStore] = None,
) -> bool:
    """Return whether a graph has been built for the project."""
    store = graph_store or NetworkXGraphStore()
    return store.has_graph(project_id)


def graph_edges(
    graph: nx.DiGraph,
    *,
    relation: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return edges with source, target, and metadata."""
    edges: list[dict[str, Any]] = []
    for source, target, data in graph.edges(data=True):
        if relation and data.get("relation") != relation:
            continue
        edges.append({"source": source, "target": target, **data})
    return edges
