from diagram_generator import DiagramGenerator
from code_parser import CodeParser


def test_architecture_diagram():
    code = "def test(): pass"

    parser = CodeParser()
    result = parser.parse(code)

    diagram = DiagramGenerator(result).generate_architecture_diagram()

    assert "test" in diagram
    assert len(diagram.strip()) > 0
    assert "mermaid" in diagram


def test_architecture_one_top_level_function():
    """Architecture shows a single top-level function name."""
    code = "def compute_total(items):\n    return sum(items)"
    result = CodeParser().parse(code)
    diagram = DiagramGenerator(result).generate_architecture_diagram()

    assert "compute_total" in diagram
    assert "MODULE" in diagram
    assert "```mermaid" in diagram


def test_architecture_one_class_with_one_method():
    """Architecture shows the class; method count is reflected in the label."""
    code = (
        "class Vehicle:\n"
        "    def drive_miles(self, n):\n"
        "        return n\n"
    )
    result = CodeParser().parse(code)
    assert len(result["classes"]) == 1
    assert result["classes"][0]["methods"][0]["name"] == "drive_miles"

    diagram = DiagramGenerator(result).generate_architecture_diagram()

    assert "Vehicle" in diagram
    assert "MODULE" in diagram
    assert "method" in diagram.lower()
    assert len(diagram.strip()) > 0


def test_sequence_diagram_two_functions_one_calls_another():
    code = (
        "def helper():\n"
        "    return 1\n"
        "\n"
        "def main():\n"
        "    return helper()\n"
    )
    result = CodeParser().parse(code)
    assert any(
        c.get("caller") == "main" and c.get("callee") == "helper"
        for c in result.get("function_calls", [])
    )

    diagram = DiagramGenerator(result).generate_sequence_diagram()

    assert "sequenceDiagram" in diagram
    assert "main" in diagram
    assert "helper" in diagram
    assert len(diagram.strip()) > 0


def test_dependency_diagram_shows_imported_modules():
    code = (
        "import os\n"
        "import json\n"
        "\n"
        "def run():\n"
        "    return json.dumps({'ok': True})\n"
    )
    result = CodeParser().parse(code)
    assert any(i.get("module") == "os" for i in result.get("imports", []))
    assert any(i.get("module") == "json" for i in result.get("imports", []))

    diagram = DiagramGenerator(result).generate_dependency_diagram()

    assert "os" in diagram
    assert "json" in diagram
    assert "CurrentModule" in diagram or "Your Code" in diagram
    assert "imports" in diagram.lower()
    assert len(diagram.strip()) > 0


def test_empty_parse_result_diagram_fallbacks():
    """Empty parse: minimal architecture, structure-based sequence, no-import dependency."""
    result = CodeParser().parse("")
    gen = DiagramGenerator(result)

    arch = gen.generate_architecture_diagram()
    assert "MODULE" in arch
    assert "```mermaid" in arch
    assert len(arch.strip()) > 0

    seq = gen.generate_sequence_diagram()
    assert "sequenceDiagram" in seq
    assert "No code structure detected" in seq
    assert len(seq.strip()) > 0

    dep = gen.generate_dependency_diagram()
    assert "No Imports Found" in dep
    assert len(dep.strip()) > 0
