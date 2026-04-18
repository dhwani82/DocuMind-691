from javascript_parser import JavaScriptParser


def test_parse_one_function():
    code = "function add(a, b) {\n  return a + b;\n}\n"
    result = JavaScriptParser().parse(code)

    assert result["language"] == "javascript"
    assert result["summary"]["total_functions"] >= 1
    assert any(f["name"] == "add" for f in result["functions"])


def test_parse_one_class_with_one_method():
    code = "class Greeter {\n  greet() {\n    return 'hi';\n  }\n}\n"
    result = JavaScriptParser().parse(code)

    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "Greeter"
    methods = result["classes"][0].get("methods", [])
    assert len(methods) == 1
    assert methods[0]["name"] == "greet"


def test_parse_import_statements():
    code = "import { useState } from 'react';\nimport axios from 'axios';\n"
    result = JavaScriptParser().parse(code)

    assert result["summary"]["total_imports"] >= 2
    modules = {imp["module"] for imp in result["imports"]}
    assert "react" in modules
    assert "axios" in modules


def test_parse_empty_input():
    result = JavaScriptParser().parse("")

    assert result["language"] == "javascript"
    assert result["summary"]["total_functions"] == 0
    assert result["summary"]["total_classes"] == 0
    assert result["functions"] == []
    assert result["classes"] == []
