from language_detector import LanguageDetector


def test_detect_python_from_py_extension():
    assert LanguageDetector.detect("app.py") == "python"
    assert LanguageDetector.detect("src/pkg/module.py") == "python"


def test_detect_javascript_from_js_and_ts():
    assert LanguageDetector.detect("bundle.js") == "javascript"
    assert LanguageDetector.detect("component.ts") == "javascript"
    assert LanguageDetector.detect("App.tsx") == "javascript"


def test_detect_cpp_from_cpp_extension():
    assert LanguageDetector.detect("main.cpp") == "cpp"
    assert LanguageDetector.detect("lib.cc") == "cpp"


def test_detect_c_from_c_extension():
    assert LanguageDetector.detect("driver.c") == "c"


def test_detect_sql_from_sql_extension():
    assert LanguageDetector.detect("schema.sql") == "sql"


def test_detect_universal_languages_by_extension():
    assert LanguageDetector.detect("src/Hello.java") == "java"
    assert LanguageDetector.detect("main.go") == "go"
    assert LanguageDetector.detect("lib.rs") == "rust"


def test_unknown_extension_without_code_returns_none():
    assert LanguageDetector.detect("data.unknown") is None
    assert LanguageDetector.detect_from_extension("file.xyz") is None


def test_unknown_extension_falls_back_to_code_content():
    assert LanguageDetector.detect("data.unknown", "def hello():\n    return 42\n") == "python"
