import pytest

from doc_generator import DocumentationGenerator
from code_parser import CodeParser


@pytest.fixture
def template_doc_gen(monkeypatch):
    """Force template path (no LLM) regardless of host environment."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gen = DocumentationGenerator(api_key=None)
    assert gen.use_llm is False
    return gen


def test_readme_generation(template_doc_gen):
    code = "def test(): return 1"

    parser = CodeParser()
    parsed = parser.parse(code)

    docs = template_doc_gen.generate_documentation(code, parsed)

    assert "readme" in docs
    assert "1 functions" in docs["readme"]


def test_docstrings_template_for_simple_function(template_doc_gen):
    code = "def double(x):\n    return x * 2\n"
    parsed = CodeParser().parse(code)
    out = template_doc_gen.generate_documentation(code, parsed)["docstrings"]

    assert "double" in out
    assert '"""' in out
    assert "Args:" in out
    assert "x:" in out


def test_readme_one_function_name_and_counts(template_doc_gen):
    code = "def compute(n):\n    return n + 1\n"
    parsed = CodeParser().parse(code)
    readme = template_doc_gen.generate_documentation(code, parsed)["readme"]

    assert "# Project Documentation" in readme
    assert "1 functions" in readme
    assert "0 classes" in readme or "and 0 classes" in readme
    assert "`compute`" in readme


def test_readme_one_class_with_one_method(template_doc_gen):
    code = (
        "class Box:\n"
        "    def size(self):\n"
        "        return 1\n"
    )
    parsed = CodeParser().parse(code)
    assert parsed["summary"]["total_classes"] == 1
    assert parsed["summary"]["total_methods"] == 1

    readme = template_doc_gen.generate_documentation(code, parsed)["readme"]

    assert "# Project Documentation" in readme
    assert "`Box`" in readme
    assert "**Methods**: 1" in readme
    assert "0 functions" in readme
    assert "1 classes" in readme


def test_architecture_functions_only(template_doc_gen):
    code = (
        "def alpha():\n"
        "    pass\n"
        "\n"
        "def beta():\n"
        "    pass\n"
    )
    parsed = CodeParser().parse(code)
    arch = template_doc_gen.generate_documentation(code, parsed)["architecture"]

    assert "# Architecture Documentation" in arch
    assert "### Functions" in arch
    assert "Total top-level functions: 2" in arch
    assert "`alpha`" in arch
    assert "`beta`" in arch


def test_architecture_class_and_method(template_doc_gen):
    code = (
        "class Vehicle:\n"
        "    def drive(self):\n"
        "        return 'go'\n"
    )
    parsed = CodeParser().parse(code)
    arch = template_doc_gen.generate_documentation(code, parsed)["architecture"]

    assert "# Architecture Documentation" in arch
    assert "### Classes" in arch
    assert "Vehicle" in arch
    assert "`drive`" in arch
    assert "### Functions" in arch
    assert "Total top-level functions: 0" in arch


def test_template_mode_without_api_key(template_doc_gen):
    """Explicit template mode: no LLM client active."""
    code = "def tiny():\n    return 0\n"
    parsed = CodeParser().parse(code)
    docs = template_doc_gen.generate_documentation(code, parsed)

    assert template_doc_gen.use_llm is False
    assert set(docs.keys()) == {"docstrings", "readme", "architecture"}
    assert "# Project Documentation" in docs["readme"]


def test_empty_code_template_fallback(template_doc_gen):
    code = ""
    parsed = CodeParser().parse(code)

    docs = template_doc_gen.generate_documentation(code, parsed)

    assert docs["docstrings"].strip() == ""
    assert "# Project Documentation" in docs["readme"]
    assert "0 functions" in docs["readme"]
    assert "0 classes" in docs["readme"]
    assert "# Architecture Documentation" in docs["architecture"]
    assert "Total top-level functions: 0" in docs["architecture"]
    assert "No top-level functions were detected" in docs["architecture"]
