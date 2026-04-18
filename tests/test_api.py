import pytest


@pytest.fixture
def no_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# --- /api/parse ---


def test_parse_valid_python_returns_200(client):
    response = client.post(
        "/api/parse",
        json={"code": "def add(a, b):\n    return a + b"},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data.get("language") == "python"
    assert "functions" in data
    assert any(f.get("name") == "add" for f in data["functions"])
    assert "diagrams" in data
    assert isinstance(data.get("diagrams", {}).get("flowchart", ""), str)


def test_parse_simple_function_returns_200(client):
    response = client.post("/api/parse", json={"code": "def hello(): return 'hi'"})
    data = response.get_json()

    assert response.status_code == 200
    assert "functions" in data
    assert len(data["functions"]) == 1
    assert data["functions"][0]["name"] == "hello"


def test_parse_empty_code_returns_400(client):
    response = client.post("/api/parse", json={"code": ""})
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data
    assert "code" in data["error"].lower()


def test_parse_invalid_syntax_returns_400(client):
    response = client.post("/api/parse", json={"code": "def broken(\n"})
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data


def test_parse_class_with_method_returns_200(client):
    code = (
        "class Greeter:\n"
        "    def greet(self):\n"
        "        return 'hi'\n"
    )
    response = client.post("/api/parse", json={"code": code})
    data = response.get_json()

    assert response.status_code == 200
    assert "classes" in data
    assert len(data["classes"]) == 1
    assert data["classes"][0]["name"] == "Greeter"
    assert len(data["classes"][0].get("methods", [])) == 1
    assert data["classes"][0]["methods"][0]["name"] == "greet"
    assert "functions" in data


# --- /api/generate-docs ---


def test_generate_docs_valid_without_api_key_returns_200(client, no_openai_key):
    response = client.post(
        "/api/generate-docs",
        json={"code": "def ok():\n    return 42"},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data.get("success") is True
    assert data.get("used_llm") is False
    assert "documentation" in data
    docs = data["documentation"]
    assert "readme" in docs and len(docs["readme"]) > 0
    assert "docstrings" in docs and len(docs["docstrings"]) > 0
    assert "architecture" in docs and len(docs["architecture"]) > 0


def test_generate_docs_missing_code_field_returns_400(client, no_openai_key):
    response = client.post("/api/generate-docs", json={"note": "no code key"})
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data
    assert "code" in data["error"].lower()


def test_generate_docs_empty_code_returns_400(client, no_openai_key):
    response = client.post("/api/generate-docs", json={"code": ""})
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data


# --- /api/generate-svg-flowchart ---


def test_svg_flowchart_valid_code_with_branches_returns_svg(client):
    code = (
        "def branchy(x):\n"
        "    if x > 0:\n"
        "        for i in range(3):\n"
        "            pass\n"
        "    return x\n"
    )
    response = client.post("/api/generate-svg-flowchart", json={"code": code})

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert len(response.data) > 100
    body = response.data.decode("utf-8", errors="replace")
    assert "<svg" in body
    assert "branchy" in body


def test_svg_flowchart_empty_code_returns_400(client):
    response = client.post("/api/generate-svg-flowchart", json={"code": ""})
    data = response.get_json()

    assert response.status_code == 400
    assert data and "error" in data


def test_svg_flowchart_no_control_flow_returns_fallback_svg(client):
    """Parsable code with no recorded control flow → small informational SVG."""
    response = client.post(
        "/api/generate-svg-flowchart",
        json={"code": "def only_pass():\n    pass\n"},
    )

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    body = response.data.decode("utf-8", errors="replace")
    assert "<svg" in body
    assert "only_pass" in body
    assert "no control flow" in body.lower()


# --- / ---


def test_index_returns_200_html(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in (response.mimetype or "")
    assert len(response.data) > 0
    assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data.lower()
