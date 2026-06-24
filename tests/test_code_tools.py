"""Tests for LangChain code-navigation tools."""

import json
from pathlib import Path

import pytest

from code_tools import CodeNavigator, create_code_tools, register_project
from tests.sample_code_for_testing import SAMPLE_MIXED, SAMPLE_SIMPLE_FUNCTIONS


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Materialize parser-grounded sample code into an isolated project directory."""
    project = tmp_path / "sample_project"
    project.mkdir()
    (project / "mixed.py").write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")
    (project / "simple.py").write_text(SAMPLE_SIMPLE_FUNCTIONS.strip() + "\n", encoding="utf-8")
    return project


@pytest.fixture
def navigator(sample_project: Path) -> CodeNavigator:
    return CodeNavigator(sample_project)


@pytest.fixture
def repo_navigator() -> CodeNavigator:
    return CodeNavigator(Path(__file__).resolve().parents[1])


def test_create_code_tools_exposes_five_tools(sample_project: Path):
    tools = create_code_tools(sample_project)
    assert [tool.name for tool in tools] == [
        "grep_code",
        "read_file",
        "list_files",
        "find_symbol",
        "get_structure",
    ]


def test_list_files_includes_materialized_samples(navigator: CodeNavigator):
    files = navigator.list_files("**/*.py")
    assert "mixed.py" in files
    assert "simple.py" in files


def test_grep_code_finds_parser_known_identifier(navigator: CodeNavigator):
    hits = navigator.grep_code(r"def load_config", path_glob="**/*.py")
    assert "mixed.py:" in hits
    assert "def load_config" in hits


def test_grep_code_finds_simple_function(navigator: CodeNavigator):
    hits = navigator.grep_code(r"def test_function", path_glob="simple.py")
    assert hits.startswith("simple.py:")
    assert "def test_function" in hits


def test_read_file_returns_numbered_source(navigator: CodeNavigator):
    content = navigator.read_file("mixed.py", start_line=1, end_line=3)
    assert content.startswith("   1|")
    assert "import os" in content


def test_get_structure_returns_parser_outline(navigator: CodeNavigator):
    outline = json.loads(navigator.get_structure("mixed.py"))

    assert outline["file"] == "mixed.py"
    assert outline["language"] == "python"
    function_names = {func["name"] for func in outline["functions"]}
    assert {"load_config", "save_result"} <= function_names

    classes = {cls["name"] for cls in outline["classes"]}
    assert "DataProcessor" in classes

    method_names = {
        method["name"]
        for cls in outline["classes"]
        if cls["name"] == "DataProcessor"
        for method in cls["methods"]
    }
    assert {"process", "validate"} <= method_names


def test_find_symbol_returns_class_definition(navigator: CodeNavigator):
    results = json.loads(navigator.find_symbol("DataProcessor"))

    assert len(results) == 1
    assert results[0]["file"] == "mixed.py"
    assert results[0]["kind"] == "class"
    assert results[0]["name"] == "DataProcessor"
    assert results[0]["line"] > 0


def test_find_symbol_returns_function_definition(navigator: CodeNavigator):
    results = json.loads(navigator.find_symbol("load_config"))

    assert any(
        hit["file"] == "mixed.py" and hit["kind"] == "function" and hit["line"] > 0
        for hit in results
    )


def test_find_symbol_returns_method_definition(navigator: CodeNavigator):
    results = json.loads(navigator.find_symbol("process"))

    assert any(
        hit["file"] == "mixed.py"
        and hit["kind"] == "method"
        and hit["qualified_name"] == "DataProcessor.process"
        for hit in results
    )


def test_find_symbol_code_parser_in_repo(repo_navigator: CodeNavigator):
    results = json.loads(repo_navigator.find_symbol("CodeParser"))

    code_parser_hits = [hit for hit in results if hit["file"] == "code_parser.py"]
    assert code_parser_hits
    assert code_parser_hits[0]["kind"] == "class"
    assert code_parser_hits[0]["line"] == 5


def test_grep_code_finds_code_parser_class(repo_navigator: CodeNavigator):
    hits = repo_navigator.grep_code(r"class CodeParser", path_glob="code_parser.py")
    assert hits.startswith("code_parser.py:5:")
    assert "class CodeParser" in hits


def test_against_sample_code_for_testing_module_file(repo_navigator: CodeNavigator):
    """Use the real tests/sample_code_for_testing.py file for grounded file operations."""
    sample_path = "tests/sample_code_for_testing.py"

    assert sample_path in repo_navigator.list_files("tests/*.py")

    hits = repo_navigator.grep_code(r"SAMPLE_SIMPLE_FUNCTIONS", path_glob=sample_path)
    assert sample_path in hits
    assert "SAMPLE_SIMPLE_FUNCTIONS" in hits

    content = repo_navigator.read_file(sample_path, start_line=1, end_line=5)
    assert "Sample code snippets" in content


def test_register_project_and_get_code_tools(repo_navigator: CodeNavigator):
    root = register_project(repo_navigator.project_root)
    tools = create_code_tools(root)
    assert len(tools) == 5
