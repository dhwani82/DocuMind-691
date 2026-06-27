"""Tests for the Java parser."""

from java_parser import JavaParser
from eval.sample_java_project import SAMPLE_CALCULATOR, SAMPLE_CALLS, SAMPLE_INHERITANCE


def test_parse_calculator_class_and_methods():
    result = JavaParser().parse(SAMPLE_CALCULATOR)

    assert result["language"] == "java"
    assert result["summary"]["total_classes"] == 1
    assert any(cls["name"] == "Calculator" for cls in result["classes"])

    calculator = next(cls for cls in result["classes"] if cls["name"] == "Calculator")
    method_names = {method["name"] for method in calculator["methods"]}
    assert {"add", "subtract", "reset"}.issubset(method_names)


def test_parse_calls_extracts_helper_call():
    result = JavaParser().parse(SAMPLE_CALLS)

    assert any(
        call["caller"] == "Calls.mainFlow" and call["callee"] == "helper"
        for call in result["function_calls"]
    )


def test_parse_inheritance_bases():
    result = JavaParser().parse(SAMPLE_INHERITANCE)

    class_names = {cls["name"] for cls in result["classes"]}
    assert "Animal" in class_names
    assert "Dog" in class_names
    assert "Cat" in class_names

    dog = next(cls for cls in result["classes"] if cls["name"] == "Dog")
    assert dog["bases"] == ["Animal"]


def test_parse_java_via_api(client):
    response = client.post(
        "/api/parse",
        json={
            "code": SAMPLE_CALCULATOR,
            "filename": "Calculator.java",
            "language": "java",
        },
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data.get("language") == "java"
    assert data["summary"]["total_classes"] == 1
