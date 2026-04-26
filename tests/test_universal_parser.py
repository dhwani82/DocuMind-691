from universal_parser import (
    UniversalParser,
    detect_language_from_extension,
    should_index_file_by_path,
    is_probably_binary_bytes,
)


def test_detect_lang_java_go():
    assert detect_language_from_extension("src/Foo.java") == "java"
    assert UniversalParser.detect_language_from_extension("main.go") == "go"
    assert detect_language_from_extension("x.rs") == "rust"


def test_never_says_unsupported_by_extension():
    assert detect_language_from_extension("weird.xyz") == "text"


def test_should_skip_node_modules_path():
    assert not should_index_file_by_path("node_modules/lodash/x.js")
    assert should_index_file_by_path("src/main.go")


def test_binary_bytes():
    assert is_probably_binary_bytes(b"\x00" + b"hello" * 10)
    assert not is_probably_binary_bytes(b"package main\nfunc main() {}")


def test_parse_go_functions():
    u = UniversalParser()
    code = "package main\n\nfunc main() {\n}\n\nfunc helper() int {\n  return 1\n}\n"
    d = u.parse(code, "main.go")
    assert d["parser_type"] == "universal_fallback"
    assert d["language"] == "go"
    assert d["line_count"] >= 3
    names = [f.get("name") for f in d["functions"] if isinstance(f, dict)]
    assert "main" in names or "helper" in names
