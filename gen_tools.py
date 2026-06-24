"""LangChain tools for documentation and diagram generation."""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from typing import Any, Literal, Optional

from langchain_core.tools import BaseTool, StructuredTool

from code_parser import CodeParser
from diagram_generator import DiagramGenerator
from doc_generator import DocumentationGenerator
from javascript_parser import JavaScriptParser
from language_detector import LanguageDetector
from sql_parser import SQLParser
from svg_generator import SVGFlowchartGenerator

DiagramKind = Literal["architecture", "sequence", "dependency"]

_DIAGRAM_KIND_METHODS: dict[str, str] = {
    "architecture": "generate_architecture_diagram",
    "sequence": "generate_sequence_diagram",
    "dependency": "generate_dependency_diagram",
}

_SUPPORTED_DIAGRAM_KINDS = ", ".join(sorted(_DIAGRAM_KIND_METHODS))


def _tool_error(message: str) -> str:
    return json.dumps({"error": message}, indent=2)


def _parse_code_for_docs(code: str) -> tuple[dict[str, Any], Optional[str]]:
    """Parse code the same way as /api/generate-docs and /api/generate-svg-flowchart."""
    try:
        return CodeParser().parse(code), None
    except SyntaxError as exc:
        return {}, f"Syntax error: {exc}"
    except Exception as exc:
        return {}, f"Error parsing code: {exc}"


def _parse_code_for_diagram(code: str) -> tuple[dict[str, Any], Optional[str]]:
    """Parse code the same way as /api/parse (diagram branch)."""
    try:
        detected_language = LanguageDetector.detect(code=code)
        lang_normalized = (detected_language or "python").lower()

        if lang_normalized == "python":
            result = CodeParser().parse(code)
        elif lang_normalized == "javascript":
            result = JavaScriptParser().parse(code)
        elif lang_normalized == "sql":
            result = SQLParser().parse(code)
        else:
            return {}, (
                f'Language "{lang_normalized}" is not yet supported. '
                "Supported languages: python, javascript, sql."
            )

        result["language"] = lang_normalized
        return result, None
    except SyntaxError as exc:
        return {}, f"Syntax error: {exc}"
    except Exception as exc:
        return {}, f"Error parsing code: {exc}"


def _documentation_generator(api_key: Optional[str] = None) -> DocumentationGenerator:
    """Match DocumentationGenerator construction in app routes."""
    if api_key is None:
        env_key = os.getenv("OPENAI_API_KEY")
        api_key = env_key.strip() if env_key else None
        if api_key == "":
            api_key = None
    return DocumentationGenerator(api_key=api_key)


def generate_docstrings(code: str, *, api_key: Optional[str] = None) -> str:
    """Generate docstrings for the provided source code."""
    if not code or not code.strip():
        return _tool_error("No code provided.")

    parse_result, error = _parse_code_for_docs(code)
    if error:
        return _tool_error(error)

    try:
        doc_generator = _documentation_generator(api_key)
        documentation = doc_generator.generate_documentation(code, parse_result)
        return documentation["docstrings"]
    except Exception as exc:
        return _tool_error(f"Error generating docstrings: {exc}")


def generate_readme(code: str, *, api_key: Optional[str] = None) -> str:
    """Generate a README for the provided source code."""
    if not code or not code.strip():
        return _tool_error("No code provided.")

    parse_result, error = _parse_code_for_docs(code)
    if error:
        return _tool_error(error)

    try:
        doc_generator = _documentation_generator(api_key)
        documentation = doc_generator.generate_documentation(code, parse_result)
        return documentation["readme"]
    except Exception as exc:
        return _tool_error(f"Error generating README: {exc}")


def generate_architecture_doc(code: str, *, api_key: Optional[str] = None) -> str:
    """Generate architecture documentation for the provided source code."""
    if not code or not code.strip():
        return _tool_error("No code provided.")

    parse_result, error = _parse_code_for_docs(code)
    if error:
        return _tool_error(error)

    try:
        doc_generator = _documentation_generator(api_key)
        documentation = doc_generator.generate_documentation(code, parse_result)
        return documentation["architecture"]
    except Exception as exc:
        return _tool_error(f"Error generating architecture documentation: {exc}")


def generate_diagram(code: str, kind: str) -> str:
    """Generate a Mermaid diagram for the provided source code."""
    if not code or not code.strip():
        return _tool_error("No code provided.")

    normalized_kind = (kind or "").strip().lower()
    method_name = _DIAGRAM_KIND_METHODS.get(normalized_kind)
    if method_name is None:
        return _tool_error(
            f"Unknown diagram kind '{kind}'. Supported kinds: {_SUPPORTED_DIAGRAM_KINDS}."
        )

    parse_result, error = _parse_code_for_diagram(code)
    if error:
        return _tool_error(error)

    try:
        diagram_gen = DiagramGenerator(parse_result)
        diagram = getattr(diagram_gen, method_name)()
        return diagram
    except Exception as exc:
        traceback.print_exc()
        return _tool_error(f"Error generating {normalized_kind} diagram: {exc}")


def generate_svg_flowchart(code: str, function_name: Optional[str] = None) -> str:
    """Generate an SVG flowchart for the provided source code."""
    if not code or not code.strip():
        return _tool_error("No code provided.")

    parse_result, error = _parse_code_for_docs(code)
    if error:
        return _tool_error(error)

    try:
        svg_generator = SVGFlowchartGenerator(parse_result)
        return svg_generator.generate_svg_flowchart(function_name=function_name)
    except Exception as exc:
        return _tool_error(f"Error generating SVG flowchart: {exc}")


@dataclass
class GenerationTools:
    """LangChain generation tools."""

    api_key: Optional[str] = None

    def generate_docstrings(self, code: str) -> str:
        return generate_docstrings(code, api_key=self.api_key)

    def generate_readme(self, code: str) -> str:
        return generate_readme(code, api_key=self.api_key)

    def generate_architecture_doc(self, code: str) -> str:
        return generate_architecture_doc(code, api_key=self.api_key)

    def generate_diagram(self, code: str, kind: str) -> str:
        return generate_diagram(code, kind)

    def generate_svg_flowchart(self, code: str) -> str:
        return generate_svg_flowchart(code)


def create_generation_tools(*, api_key: Optional[str] = None) -> list[BaseTool]:
    """Create LangChain tools for documentation and diagram generation."""
    tools = GenerationTools(api_key=api_key)

    return [
        StructuredTool.from_function(
            func=tools.generate_docstrings,
            name="generate_docstrings",
            description=(
                "Generate PEP 257-style docstrings for Python source code. "
                "Use when the user wants inline function/class documentation added to code. "
                "Returns documented source code as a string."
            ),
        ),
        StructuredTool.from_function(
            func=tools.generate_readme,
            name="generate_readme",
            description=(
                "Generate a README.md for a code snippet or module. "
                "Use when the user wants project overview documentation. "
                "Returns markdown text."
            ),
        ),
        StructuredTool.from_function(
            func=tools.generate_architecture_doc,
            name="generate_architecture_doc",
            description=(
                "Generate architecture documentation describing functions, classes, and structure. "
                "Use when the user asks how a codebase is organized. "
                "Returns markdown text."
            ),
        ),
        StructuredTool.from_function(
            func=tools.generate_diagram,
            name="generate_diagram",
            description=(
                "Generate a Mermaid diagram from source code. "
                "kind must be one of: architecture, sequence, dependency. "
                "Use for visual structure, call flow, or import relationships."
            ),
        ),
        StructuredTool.from_function(
            func=tools.generate_svg_flowchart,
            name="generate_svg_flowchart",
            description=(
                "Generate an SVG control-flow flowchart from Python source code. "
                "Use when the user wants a visual execution path for functions. "
                "Returns SVG markup as a string."
            ),
        ),
    ]
