"""AST-aware code chunking for vector indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from llama_index.core import Document
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from language_detector import LanguageDetector
from code_parser import CodeParser
from javascript_parser import JavaScriptParser
from java_parser import JavaParser
from sql_parser import SQLParser

PARSEABLE_LANGUAGES = frozenset({"python", "javascript", "java", "sql"})

CODE_SPLITTER_LANGUAGES = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "sql",
        "c",
        "cpp",
        "java",
        "go",
        "rust",
        "ruby",
        "php",
    }
)

LANGUAGE_TO_CODE_SPLITTER = {
    "python": "python",
    "javascript": "javascript",
    "sql": "sql",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
}


@dataclass
class ChunkConfig:
    """Configurable chunking parameters."""

    chunk_lines: int = 40
    chunk_lines_overlap: int = 15
    max_chars: int = 1500


@dataclass
class CodeChunk:
    """A source chunk with grounded metadata for retrieval."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _parse_code(code: str, language: str) -> dict[str, Any]:
    lang = (language or "python").lower()
    if lang == "python":
        return CodeParser().parse(code)
    if lang == "javascript":
        return JavaScriptParser().parse(code)
    if lang == "java":
        return JavaParser().parse(code)
    if lang == "sql":
        return SQLParser().parse(code)
    return {}


def _detect_language(file_path: str, code: str) -> str:
    detected = LanguageDetector.detect(filename=file_path, code=code)
    return (detected or "python").lower()


def _split_with_code_splitter(
    code: str,
    language: str,
    config: ChunkConfig,
) -> list[str]:
    splitter_language = LANGUAGE_TO_CODE_SPLITTER.get(language, language)
    if splitter_language not in CODE_SPLITTER_LANGUAGES:
        raise ValueError(f"Unsupported CodeSplitter language: {language}")

    splitter = CodeSplitter(
        language=splitter_language,
        chunk_lines=config.chunk_lines,
        chunk_lines_overlap=config.chunk_lines_overlap,
        max_chars=config.max_chars,
    )
    document = Document(text=code)
    nodes = splitter.get_nodes_from_documents([document])
    chunks = [node.get_content() for node in nodes if node.get_content().strip()]
    if not chunks:
        raise ValueError("CodeSplitter returned no chunks")
    return chunks


def _split_with_line_overlap(code: str, config: ChunkConfig) -> list[tuple[str, int, int]]:
    lines = code.splitlines()
    if not lines:
        return []

    chunks: list[tuple[str, int, int]] = []
    step = max(1, config.chunk_lines - config.chunk_lines_overlap)
    index = 0

    while index < len(lines):
        end_index = min(len(lines), index + config.chunk_lines)
        chunk_lines = lines[index:end_index]
        chunk_text = "\n".join(chunk_lines)
        if len(chunk_text) > config.max_chars:
            chunk_text = chunk_text[: config.max_chars]
            visible_lines = chunk_text.count("\n") + 1
            end_index = index + visible_lines

        start_line = index + 1
        end_line = end_index
        if chunk_text.strip():
            chunks.append((chunk_text, start_line, end_line))

        if end_index >= len(lines):
            break
        index += step

    return chunks


def _split_with_sentence_fallback(code: str, config: ChunkConfig) -> list[str]:
    splitter = SentenceSplitter(
        chunk_size=config.max_chars,
        chunk_overlap=max(1, config.chunk_lines_overlap * 20),
    )
    document = Document(text=code)
    nodes = splitter.get_nodes_from_documents([document])
    chunks = [node.get_content() for node in nodes if node.get_content().strip()]
    if not chunks:
        return [code]
    return chunks


def _locate_chunk_lines(
    code: str,
    chunk_text: str,
    search_from: int = 0,
) -> tuple[int, int]:
    normalized_chunk = chunk_text.strip()
    if not normalized_chunk:
        return 1, 1

    start_index = code.find(normalized_chunk, search_from)
    if start_index == -1:
        first_line = normalized_chunk.splitlines()[0].strip()
        for line_no, line in enumerate(code.splitlines(), start=1):
            if first_line and first_line in line:
                end_line = line_no + max(0, normalized_chunk.count("\n"))
                return line_no, end_line
        return 1, max(1, normalized_chunk.count("\n") + 1)

    start_line = code.count("\n", 0, start_index) + 1
    end_index = start_index + len(normalized_chunk)
    end_line = code.count("\n", 0, end_index) + 1
    return start_line, end_line


def _symbol_declared_in_chunk(name: str, chunk_text: str) -> bool:
    if f"class {name}" in chunk_text or f"def {name}" in chunk_text:
        return True
    if "." in name:
        method_name = name.split(".", 1)[1]
        return f"def {method_name}" in chunk_text or f"{method_name}(" in chunk_text
    return False


def _symbol_for_chunk(
    parsed: dict[str, Any],
    start_line: int,
    end_line: int,
    chunk_text: str = "",
) -> tuple[str, str]:
    candidates: list[tuple[int, str, str]] = []

    for func in parsed.get("functions", []):
        func_line = func.get("line", 0)
        if func_line and start_line <= func_line <= end_line:
            candidates.append((func_line, func.get("name", ""), "function"))

    for cls in parsed.get("classes", []):
        cls_line = cls.get("line", 0)
        if cls_line and start_line <= cls_line <= end_line:
            candidates.append((cls_line, cls.get("name", ""), "class"))

        for method in cls.get("methods", []):
            method_line = method.get("line", 0)
            if method_line and start_line <= method_line <= end_line:
                candidates.append(
                    (
                        method_line,
                        f"{cls.get('name')}.{method.get('name')}",
                        "method",
                    )
                )

    for table in parsed.get("tables", []):
        table_line = table.get("line", 0)
        if table_line and start_line <= table_line <= end_line:
            candidates.append((table_line, table.get("name", ""), "table"))

    if candidates:
        declared = [
            (line, name, kind)
            for line, name, kind in candidates
            if _symbol_declared_in_chunk(name, chunk_text)
        ]
        if declared:
            declared.sort()
            return declared[0][1], declared[0][2]
        candidates.sort()
        return candidates[0][1], candidates[0][2]

    enclosing = _symbol_enclosing_line(parsed, start_line)
    return enclosing, _kind_for_symbol_name(parsed, enclosing)


def _kind_for_symbol_name(parsed: dict[str, Any], name: str) -> str:
    if not name:
        return ""
    if "." in name:
        return "method"
    for cls in parsed.get("classes", []):
        if cls.get("name") == name:
            return "class"
    for table in parsed.get("tables", []):
        if table.get("name") == name:
            return "table"
    return "function"


def _symbol_enclosing_line(parsed: dict[str, Any], line: int) -> str:
    best_name = ""
    best_line = -1

    for cls in parsed.get("classes", []):
        cls_line = cls.get("line", 0)
        if cls_line and cls_line <= line and cls_line >= best_line:
            best_name = cls.get("name", "")
            best_line = cls_line

        for method in cls.get("methods", []):
            method_line = method.get("line", 0)
            if method_line and method_line <= line and method_line >= best_line:
                best_name = f"{cls.get('name')}.{method.get('name')}"
                best_line = method_line

    for func in parsed.get("functions", []):
        func_line = func.get("line", 0)
        if func_line and func_line <= line and func_line >= best_line:
            best_name = func.get("name", "")
            best_line = func_line

    for table in parsed.get("tables", []):
        table_line = table.get("line", 0)
        if table_line and table_line <= line and table_line >= best_line:
            best_name = table.get("name", "")
            best_line = table_line

    return best_name


def _build_chunk_metadata(
    *,
    file_path: str,
    language: str,
    start_line: int,
    end_line: int,
    parsed: dict[str, Any],
    chunker: str,
    chunk_text: str,
) -> dict[str, Any]:
    symbol_name, symbol_kind = _symbol_for_chunk(parsed, start_line, end_line, chunk_text)
    metadata = {
        "file_path": file_path,
        "language": language,
        "start_line": start_line,
        "end_line": end_line,
        "chunker": chunker,
    }
    if symbol_name:
        metadata["symbol_name"] = symbol_name
    if symbol_kind:
        metadata["symbol_kind"] = symbol_kind
    return metadata


def chunk_source(
    *,
    file_path: str,
    code: str,
    config: Optional[ChunkConfig] = None,
    language: Optional[str] = None,
) -> list[CodeChunk]:
    """Chunk a single source file with AST-first splitting and parser metadata."""
    cfg = config or ChunkConfig()
    resolved_language = (language or _detect_language(file_path, code)).lower()
    parsed = _parse_code(code, resolved_language) if resolved_language in PARSEABLE_LANGUAGES else {}

    raw_chunks: list[tuple[str, int, int, str]] = []
    chunker_used = "fallback_lines"

    try:
        if resolved_language in LANGUAGE_TO_CODE_SPLITTER:
            text_chunks = _split_with_code_splitter(code, resolved_language, cfg)
            chunker_used = "code_splitter"
            search_from = 0
            for chunk_text in text_chunks:
                start_line, end_line = _locate_chunk_lines(code, chunk_text, search_from)
                raw_chunks.append((chunk_text, start_line, end_line, chunker_used))
                search_from = max(0, code.find(chunk_text.strip(), search_from))
        else:
            raise ValueError(f"No CodeSplitter mapping for language: {resolved_language}")
    except Exception:
        line_chunks = _split_with_line_overlap(code, cfg)
        if line_chunks:
            raw_chunks = [(text, start, end, "fallback_lines") for text, start, end in line_chunks]
        else:
            sentence_chunks = _split_with_sentence_fallback(code, cfg)
            search_from = 0
            for chunk_text in sentence_chunks:
                start_line, end_line = _locate_chunk_lines(code, chunk_text, search_from)
                raw_chunks.append((chunk_text, start_line, end_line, "fallback_sentences"))
                search_from = max(0, code.find(chunk_text.strip(), search_from))

    if not raw_chunks:
        raw_chunks = [(code, 1, max(1, code.count("\n") + 1), "fallback_whole_file")]

    return [
        CodeChunk(
            text=chunk_text,
            metadata=_build_chunk_metadata(
                file_path=file_path,
                language=resolved_language,
                start_line=start_line,
                end_line=end_line,
                parsed=parsed,
                chunker=chunker_name,
                chunk_text=chunk_text,
            ),
        )
        for chunk_text, start_line, end_line, chunker_name in raw_chunks
    ]


def chunk_file(
    file_path: str | Path,
    config: Optional[ChunkConfig] = None,
) -> list[CodeChunk]:
    """Chunk a file from disk using a path-relative file_path in metadata."""
    path = Path(file_path)
    code = path.read_text(encoding="utf-8", errors="replace")
    return chunk_source(file_path=path.as_posix(), code=code, config=config)


def lines_are_tiled(chunks: list[CodeChunk], total_lines: int) -> bool:
    """Return True when every 1-based line number is covered by at least one chunk."""
    if total_lines <= 0:
        return True

    covered = set()
    for chunk in chunks:
        start_line = int(chunk.metadata.get("start_line", 0))
        end_line = int(chunk.metadata.get("end_line", 0))
        if start_line <= 0 or end_line <= 0:
            continue
        covered.update(range(start_line, end_line + 1))

    return all(line_no in covered for line_no in range(1, total_lines + 1))
