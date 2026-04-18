from code_parser import CodeParser


def test_detect_functions():
    code = "def add(a,b): return a+b"
    parser = CodeParser()
    result = parser.parse(code)

    assert len(result["functions"]) == 1
    assert result["functions"][0]["name"] == "add"


def test_detect_multiple_functions():
    code = "def a(): pass\ndef b(): pass"
    parser = CodeParser()
    result = parser.parse(code)

    assert len(result["functions"]) == 2


def test_empty_code():
    parser = CodeParser()
    result = parser.parse("")

    assert result["functions"] == []
    assert result["classes"] == []
