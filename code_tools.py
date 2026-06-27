"""LangChain code-navigation tools backed by existing DocuMind parsers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool

from code_parser import CodeParser
from javascript_parser import JavaScriptParser
from java_parser import JavaParser
from language_detector import LanguageDetector
from project_ignore import DEFAULT_SKIP_DIRS as SKIP_DIRS
from sql_parser import SQLParser

PARSEABLE_LANGUAGES = frozenset({"python", "javascript", "java", "sql"})

SUPPORTED_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyw",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".java",
        ".c",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".hxx",
        ".php",
        ".phtml",
        ".sql",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".html",
        ".css",
    }
)

_registered_project_root: Optional[Path] = None


def register_project(project_dir: str | Path) -> Path:
    """Register the project directory that code tools operate on."""
    global _registered_project_root
    root = Path(project_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project directory does not exist: {root}")
    _registered_project_root = root
    return root


def get_registered_project() -> Path:
    """Return the currently registered project directory."""
    if _registered_project_root is None:
        raise RuntimeError(
            "No project directory registered. Call register_project(path) first."
        )
    return _registered_project_root


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
    raise ValueError(
        f'Language "{lang}" is not supported for structure lookup. '
        f"Supported: {', '.join(sorted(PARSEABLE_LANGUAGES))}"
    )


@dataclass
class CodeNavigator:
    """Code-navigation operations scoped to a single project root."""

    project_root: Path

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project directory does not exist: {self.project_root}")

    def _resolve_path(self, file_path: str) -> Path:
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        resolved = candidate.resolve()
        if resolved != self.project_root and self.project_root not in resolved.parents:
            raise ValueError(f"Path escapes project root: {file_path}")
        return resolved

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()

    def _matches_glob(self, rel_path: str, glob_pattern: str) -> bool:
        if glob_pattern in {"", "*", "**/*"}:
            return True

        path = Path(rel_path)
        if path.match(glob_pattern):
            return True

        # pathlib does not treat **/*.py as matching root-level *.py files.
        if "**/" in glob_pattern:
            suffix_pattern = glob_pattern.split("**/", 1)[1]
            if path.match(suffix_pattern):
                return True

        return path.as_posix() == glob_pattern or path.name == glob_pattern

    def _iter_files(self, path_glob: Optional[str] = None) -> list[Path]:
        matches: list[Path] = []
        glob_pattern = path_glob or "**/*"

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            rel_root = Path(root).relative_to(self.project_root)

            for filename in sorted(files):
                rel_path = (rel_root / filename).as_posix()
                if rel_path == ".":
                    rel_path = filename
                if not self._matches_glob(rel_path, glob_pattern):
                    continue
                full_path = Path(root) / filename
                if full_path.is_file():
                    matches.append(full_path)

        return matches

    def grep_code(self, pattern: str, path_glob: Optional[str] = None) -> str:
        """Ripgrep-style regex search returning file:line:match hits."""
        if not pattern:
            raise ValueError("pattern is required")

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {exc}") from exc

        glob_pattern = path_glob or "**/*"
        hits: list[str] = []

        for file_path in self._iter_files(glob_pattern):
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = self._relative_path(file_path)
            for line_no, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    hits.append(f"{rel_path}:{line_no}:{line.rstrip()}")

        return "\n".join(hits)

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Return exact source with 1-based line numbers."""
        resolved = self._resolve_path(file_path)
        if not resolved.is_file():
            raise ValueError(f"File not found: {file_path}")

        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start_line or 1)
        end = min(len(lines), end_line or len(lines))
        if start > end:
            raise ValueError("start_line must be less than or equal to end_line")

        numbered = [f"{line_no:4d}| {lines[line_no - 1]}" for line_no in range(start, end + 1)]
        return "\n".join(numbered)

    def list_files(self, path_glob: Optional[str] = None) -> str:
        """Return the project file tree as relative paths."""
        paths = [self._relative_path(path) for path in self._iter_files(path_glob or "**/*")]
        return "\n".join(paths)

    def _symbol_definitions_in_file(
        self,
        file_path: Path,
        name: str,
    ) -> list[dict[str, Any]]:
        rel_path = self._relative_path(file_path)
        code = file_path.read_text(encoding="utf-8", errors="replace")
        language = LanguageDetector.detect(filename=rel_path, code=code)
        if not language or language.lower() not in PARSEABLE_LANGUAGES:
            return []

        try:
            parsed = _parse_code(code, language)
        except Exception:
            return []

        matches: list[dict[str, Any]] = []

        def add(kind: str, symbol_name: str, line: int, qualified_name: Optional[str] = None) -> None:
            if symbol_name != name:
                return
            matches.append(
                {
                    "file": rel_path,
                    "line": line,
                    "kind": kind,
                    "name": symbol_name,
                    "qualified_name": qualified_name or symbol_name,
                }
            )

        for func in parsed.get("functions", []):
            add("function", func.get("name", ""), func.get("line", 0))

        for cls in parsed.get("classes", []):
            cls_name = cls.get("name", "")
            add("class", cls_name, cls.get("line", 0))
            for method in cls.get("methods", []):
                method_name = method.get("name", "")
                add(
                    "method",
                    method_name,
                    method.get("line", 0),
                    qualified_name=f"{cls_name}.{method_name}",
                )

        for var in parsed.get("global_variables", []):
            add("variable", var.get("name", ""), var.get("line", 0))

        for table in parsed.get("tables", []):
            add("table", table.get("name", ""), table.get("line", 0))

        return matches

    def find_symbol(self, name: str) -> str:
        """Locate symbol definitions using existing language parsers."""
        if not name:
            raise ValueError("name is required")

        results: list[dict[str, Any]] = []
        for file_path in self._iter_files("**/*"):
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            results.extend(self._symbol_definitions_in_file(file_path, name))

        results.sort(key=lambda item: (item["file"], item["line"], item["qualified_name"]))
        return json.dumps(results, indent=2)

    def get_structure(self, file_path: str) -> str:
        """Return parsed outline for a single file using existing parsers."""
        resolved = self._resolve_path(file_path)
        if not resolved.is_file():
            raise ValueError(f"File not found: {file_path}")

        rel_path = self._relative_path(resolved)
        code = resolved.read_text(encoding="utf-8", errors="replace")
        language = LanguageDetector.detect(filename=rel_path, code=code)
        if not language or language.lower() not in PARSEABLE_LANGUAGES:
            raise ValueError(
                f'File "{rel_path}" is not a supported parseable language. '
                f"Supported: {', '.join(sorted(PARSEABLE_LANGUAGES))}"
            )

        parsed = _parse_code(code, language)
        outline = {
            "file": rel_path,
            "language": language.lower(),
            "functions": [
                {
                    "name": func.get("name"),
                    "line": func.get("line"),
                    "parameters": func.get("parameters", []),
                    "is_async": func.get("is_async", False),
                }
                for func in parsed.get("functions", [])
            ],
            "classes": [
                {
                    "name": cls.get("name"),
                    "line": cls.get("line"),
                    "bases": cls.get("bases", []),
                    "methods": [
                        {
                            "name": method.get("name"),
                            "line": method.get("line"),
                        }
                        for method in cls.get("methods", [])
                    ],
                }
                for cls in parsed.get("classes", [])
            ],
            "imports": parsed.get("imports", []),
            "global_variables": [
                {"name": var.get("name"), "line": var.get("line")}
                for var in parsed.get("global_variables", [])
            ],
            "tables": [
                {"name": table.get("name"), "line": table.get("line")}
                for table in parsed.get("tables", [])
            ],
        }
        return json.dumps(outline, indent=2)


def create_code_tools(project_root: str | Path) -> list[BaseTool]:
    """Create LangChain tools bound to a project directory."""
    navigator = CodeNavigator(project_root)

    return [
        StructuredTool.from_function(
            func=navigator.grep_code,
            name="grep_code",
            description=(
                "Search files in the registered project with a Python regex pattern. "
                "Returns newline-separated file:line:match hits."
            ),
        ),
        StructuredTool.from_function(
            func=navigator.read_file,
            name="read_file",
            description=(
                "Read a project file and return exact source with 1-based line numbers. "
                "Optional start_line and end_line limit the returned range."
            ),
        ),
        StructuredTool.from_function(
            func=navigator.list_files,
            name="list_files",
            description=(
                "List project files as relative paths. Optional path_glob filters results "
                "(for example **/*.py)."
            ),
        ),
        StructuredTool.from_function(
            func=navigator.find_symbol,
            name="find_symbol",
            description=(
                "Find where a function, class, method, global variable, or SQL table is "
                "defined using existing DocuMind parsers. Returns JSON with file, line, "
                "kind, and qualified_name."
            ),
        ),
        StructuredTool.from_function(
            func=navigator.get_structure,
            name="get_structure",
            description=(
                "Return a parsed outline for one file: functions, classes, imports, "
                "global variables, and SQL tables."
            ),
        ),
    ]


def get_code_tools(project_root: Optional[str | Path] = None) -> list[BaseTool]:
    """Return code tools for an explicit or previously registered project root."""
    root = Path(project_root).expanduser().resolve() if project_root else get_registered_project()
    return create_code_tools(root)
