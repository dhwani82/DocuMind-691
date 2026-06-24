"""Tests for generation LangChain tools."""

import json

import pytest

from code_parser import CodeParser
from diagram_generator import DiagramGenerator
from doc_generator import DocumentationGenerator
from gen_tools import (
    create_generation_tools,
    generate_architecture_doc,
    generate_diagram,
    generate_docstrings,
    generate_readme,
    generate_svg_flowchart,
)
from svg_generator import SVGFlowchartGenerator
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_search import create_all_tools


@pytest.fixture
def sample_code() -> str:
    return SAMPLE_MIXED.strip()


@pytest.fixture
def template_doc_gen(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gen = DocumentationGenerator(api_key=None)
    assert gen.use_llm is False
    return gen


@pytest.fixture
def parsed_sample(sample_code: str) -> dict:
    return CodeParser().parse(sample_code)


def test_generate_docstrings_matches_module_output(
    sample_code: str,
    parsed_sample: dict,
    template_doc_gen: DocumentationGenerator,
    monkeypatch,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    expected = template_doc_gen.generate_documentation(sample_code, parsed_sample)["docstrings"]

    actual = generate_docstrings(sample_code, api_key=None)

    assert actual == expected
    assert '"""' in actual or "load_config" in actual


def test_generate_readme_matches_module_output(
    sample_code: str,
    parsed_sample: dict,
    template_doc_gen: DocumentationGenerator,
    monkeypatch,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    expected = template_doc_gen.generate_documentation(sample_code, parsed_sample)["readme"]

    actual = generate_readme(sample_code, api_key=None)

    assert actual == expected
    assert "# Project Documentation" in actual
    assert "`DataProcessor`" in actual


def test_generate_architecture_doc_matches_module_output(
    sample_code: str,
    parsed_sample: dict,
    template_doc_gen: DocumentationGenerator,
    monkeypatch,
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    expected = template_doc_gen.generate_documentation(sample_code, parsed_sample)["architecture"]

    actual = generate_architecture_doc(sample_code, api_key=None)

    assert actual == expected
    assert "# Architecture Documentation" in actual
    assert "DataProcessor" in actual


def test_generate_diagram_matches_module_output(sample_code: str, parsed_sample: dict):
    diagram_gen = DiagramGenerator(parsed_sample)

    for kind, method_name in {
        "architecture": "generate_architecture_diagram",
        "sequence": "generate_sequence_diagram",
        "dependency": "generate_dependency_diagram",
    }.items():
        expected = getattr(diagram_gen, method_name)()
        actual = generate_diagram(sample_code, kind)
        assert actual == expected
        assert "```mermaid" in actual


def test_generate_svg_flowchart_matches_module_output(sample_code: str, parsed_sample: dict):
    expected = SVGFlowchartGenerator(parsed_sample).generate_svg_flowchart()

    actual = generate_svg_flowchart(sample_code)

    assert actual == expected
    assert actual.startswith("<svg") or "No functions found" in actual


def test_generate_diagram_rejects_unknown_kind(sample_code: str):
    result = generate_diagram(sample_code, "flowchart")

    payload = json.loads(result)
    assert "error" in payload
    assert "Unknown diagram kind" in payload["error"]
    assert "architecture" in payload["error"]
    assert "sequence" in payload["error"]
    assert "dependency" in payload["error"]


def test_create_generation_tools_exposes_five_tools():
    tools = create_generation_tools(api_key=None)
    assert [tool.name for tool in tools] == [
        "generate_docstrings",
        "generate_readme",
        "generate_architecture_doc",
        "generate_diagram",
        "generate_svg_flowchart",
    ]


def test_create_all_tools_returns_full_tool_count():
    tools = create_all_tools(project_root=".", project_id="demo", api_key=None)
    tool_names = [tool.name for tool in tools]

    assert len(tools) == 15
    assert tool_names[:6] == [
        "grep_code",
        "read_file",
        "list_files",
        "find_symbol",
        "get_structure",
        "vector_search",
    ]
    assert tool_names[6:10] == [
        "who_calls",
        "what_calls",
        "impact_of",
        "dependencies_of",
    ]
    assert tool_names[10:] == [
        "generate_docstrings",
        "generate_readme",
        "generate_architecture_doc",
        "generate_diagram",
        "generate_svg_flowchart",
    ]
