"""
Regex/text-based fallback parser for languages without deep AST support.
Used when CodeParser, JavaScriptParser, and SQLParser do not apply.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Union

# --- Extension → language id (lowercase) for heuristics & labeling ---
EXT_TO_LANG: Dict[str, str] = {
    # Deep-parser languages still appear here for labeling when detection falls through
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".sql": "sql",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vb",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".phtml": "php",
    ".rb": "ruby",
    ".rake": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".clj": "clojure",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".pl": "perl",
    ".pm": "perl",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".jsonc": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".md": "markdown",
    ".mdx": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".vue": "vue",
    ".svelte": "svelte",
    ".dart": "dart",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
}

# Also match Dockerfile / Makefile with no or odd extension
SPECIAL_NAME_TO_LANG: Dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "make",
    "gnumakefile": "make",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "vagrantfile": "ruby",
    "jenkinsfile": "groovy",
    "justfile": "just",
}

# Per extension: skip in project scan (images, video, common binaries, large vendor blobs)
SCAN_SKIP_EXTS: Set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tiff",
    ".tif",
    ".svg",  # text XML — still skip for parse noise? User said skip images. SVG is code-like; allow .svg
    ".heic",
    ".psd",
    ".mp4",
    ".webm",
    ".avi",
    ".mkv",
    ".mov",
    ".mp3",
    ".wav",
    ".flac",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pdb",
    ".o",
    ".a",
    ".lib",
    ".class",
    ".pyc",
    ".pyo",
    ".pyd",
    ".wasm",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# Allow SVG as text
SCAN_SKIP_EXTS.discard(".svg")

# All extensions we should try to read as text when walking projects
# (union: known text + any non-SCAN_SKIP: handled by logic below)
TEXT_CODE_EXTS: Set[str] = set(EXT_TO_LANG.keys()) | {
    ".svelte",  # already
    ".elm",
    ".ex",
    ".exs",
    ".erl",
    ".hcl",
    ".tf",
    ".tfvars",
    ".ipynb",  # JSON inside — still text
    ".properties",
    ".env",
    ".env.example",
    ".editorconfig",
    ".gitignore",
    ".gitattributes",
    ".sql",
    ".prisma",
    ".log",
    ".adoc",
}


def is_probably_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:12288]
    if b"\x00" in sample:
        return True
    # Heuristic: if very few printable ASCII / common UTF-8, treat as binary
    printable = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126)
    if len(sample) > 200 and printable / len(sample) < 0.45:
        return True
    return False


def detect_language_from_extension(filename: str) -> str:
    """Best-effort language id from path or basename."""
    if not filename:
        return "text"
    name = filename.split("/")[-1].split("\\")[-1]
    base_lower = name.lower()
    for ext in sorted(EXT_TO_LANG.keys(), key=len, reverse=True):
        if base_lower.endswith(ext):
            return EXT_TO_LANG[ext]
    # strip for Special names
    stem = re.sub(r"\.[^.\\/]+$", "", name)
    if not stem and "." in name:
        stem = name.split(".")[0]
    special_key = re.sub(r"[^a-z0-9]", "", base_lower)
    if special_key in SPECIAL_NAME_TO_LANG:
        return SPECIAL_NAME_TO_LANG[special_key]
    if base_lower in ("dockerfile",) or "dockerfile." in base_lower:
        return "dockerfile"
    if base_lower in ("makefile", "gnumakefile"):
        return "make"
    if not name.lower().rpartition(".")[2] or name.count(".") == 0:
        return "text"
    return "text"  # unknown extension: still analyze as generic text


def should_index_file_by_path(
    relpath: str,
) -> bool:
    """True if a file path is worth reading for project analysis (not binary by extension)."""
    if not relpath:
        return False
    parts = relpath.replace("\\", "/").split("/")
    for p in parts:
        if p in (
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            "target",
            "coverage",
        ):
            return False
    name = parts[-1].lower()
    if name in SPECIAL_NAME_TO_LANG or "dockerfile" in name or name in ("makefile", "gnumakefile"):
        return True
    ext = re.sub(r"^.*\.", ".", name) if "." in name else ""
    if not ext or ext == name:
        return True
    if ext in SCAN_SKIP_EXTS:
        return False
    return True  # try unknown ext as text; binary check in reader


class UniversalParser:
    """Heuristic parser for non–deep-parser languages."""

    @staticmethod
    def detect_language_from_extension(filename: str) -> str:
        """Map filename or path extension to a language id for heuristics."""
        return detect_language_from_extension(filename)

    def parse(self, content: str, filename: str) -> Dict[str, Any]:
        line_count = len(content.splitlines()) if content is not None else 0
        language = detect_language_from_extension(filename or "")

        try:
            imp = self.extract_imports(content, language)
            cls_ = self.extract_classes(content, language)
            funcs = self.extract_functions(content, language)
            vars_ = self.extract_variables(content, language)
            ep = self.extract_endpoints(content, language)
        except Exception as exc:
            return {
                "language": language,
                "filename": filename or "",
                "summary": f"Universal fallback: limited analysis ({exc})",
                "imports": [],
                "classes": [],
                "functions": [],
                "variables": [],
                "endpoints": [],
                "line_count": line_count,
                "parser_type": "universal_fallback",
            }

        narrative = self._narrative_summary(
            language, line_count, imp, cls_, funcs, vars_, ep, filename
        )
        return {
            "language": language,
            "filename": filename or "",
            "summary": narrative,
            "imports": imp,
            "classes": cls_,
            "functions": funcs,
            "variables": vars_,
            "endpoints": ep,
            "line_count": line_count,
            "parser_type": "universal_fallback",
        }

    def to_app_parse_result(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map universal parse() output to the app/diagram-expected structure."""
        functions: List[Dict[str, Any]] = []
        for f in raw.get("functions") or []:
            if isinstance(f, dict):
                fn = f.copy()
                fn.setdefault("name", "")
                fn.setdefault("line", 0)
                fn.setdefault("parameters", [])
                fn.setdefault("is_async", False)
                fn.setdefault("is_nested", False)
                fn.setdefault("decorators", [])
                functions.append(fn)
            else:
                functions.append(
                    {
                        "name": str(f),
                        "line": 0,
                        "parameters": [],
                        "is_async": False,
                        "is_nested": False,
                        "decorators": [],
                    }
                )

        classes: List[Dict[str, Any]] = []
        for c in raw.get("classes") or []:
            if isinstance(c, dict):
                co = c.copy()
                co.setdefault("name", "")
                co.setdefault("line", 0)
                co.setdefault("methods", [])
                co.setdefault("bases", [])
                co.setdefault("class_variables", [])
                co.setdefault("instance_variables", [])
                classes.append(co)
            else:
                classes.append(
                    {
                        "name": str(c),
                        "line": 0,
                        "methods": [],
                        "bases": [],
                    }
                )

        raw_imports = raw.get("imports") or []
        imports: List[Dict[str, Any]] = []
        for i, it in enumerate(raw_imports):
            if isinstance(it, dict):
                itc = {
                    "type": it.get("type", "import"),
                    "module": it.get("module", it.get("name", "")),
                    "name": it.get("name"),
                    "alias": it.get("alias"),
                    "line": it.get("line", 0),
                }
                imports.append(itc)
            else:
                imports.append(
                    {
                        "type": "import",
                        "module": str(it),
                        "name": None,
                        "alias": None,
                        "line": 0,
                    }
                )

        gvs: List[Dict[str, Any]] = []
        for v in raw.get("variables") or []:
            if isinstance(v, dict):
                gvs.append(
                    {
                        "name": v.get("name", ""),
                        "type": v.get("type", "unknown"),
                        "line": v.get("line", 0),
                        "source": "global",
                    }
                )
            else:
                gvs.append(
                    {
                        "name": str(v),
                        "type": "unknown",
                        "line": 0,
                        "source": "global",
                    }
                )

        sfn = len(functions)
        n_classes = len(classes)
        t_imp = len(imports)
        n_vars = len(gvs)
        sum_dict = {
            "total_functions": sfn,
            "sync_functions": sfn,  # universal does not split
            "async_functions": 0,
            "nested_functions": 0,
            "total_classes": n_classes,
            "total_methods": 0,
            "global_variables": n_vars,
            "local_variables": 0,
            "execution_scope_variables": 0,
            "class_variables": 0,
            "instance_variables": 0,
            "total_decorators": 0,
            "total_imports": t_imp,
            "total_tables": 0,
            "total_relationships": 0,
        }

        info_msg = (raw.get("summary") or "")[:2000]
        warnings: List[Dict[str, str]] = []
        if info_msg:
            warnings.append({"type": "info", "message": f"Universal fallback: {info_msg}"})

        out: Dict[str, Any] = {
            "summary": sum_dict,
            "functions": functions,
            "classes": classes,
            "global_variables": gvs,
            "local_variables": [],
            "execution_scope_variables": [],
            "imports": imports,
            "decorators": [],
            "function_calls": [],
            "method_calls": [],
            "class_instantiations": [],
            "control_flow": [],
            "warnings": warnings,
            "import_usage": [],
            "tables": [],
            "relationships": [],
            "language": raw.get("language", "text"),
            "parser_type": "universal_fallback",
            "universal_endpoints": raw.get("endpoints", []),
        }
        return out

    def _narrative_summary(
        self,
        language: str,
        line_count: int,
        imports: list,
        classes: list,
        functions: list,
        variables: list,
        endpoints: list,
        filename: str,
    ) -> str:
        base = f"File {filename or 'snippet'}: language={language}, {line_count} lines (universal heuristics)."
        return (
            f"{base} Found ~{len(functions)} functions, {len(classes)} types/classes, "
            f"{len(imports)} imports, ~{len(variables)} variables, {len(endpoints)} possible endpoints or routes."
        )

    def extract_imports(
        self, content: str, language: str
    ) -> List[Union[str, Dict[str, Any]]]:
        out: List[Union[str, Dict[str, Any]]] = []
        lines = content.splitlines()

        def add_line(text: str, line_no: int) -> None:
            out.append(
                {
                    "type": "import",
                    "module": text,
                    "name": None,
                    "alias": None,
                    "line": line_no,
                }
            )

        if language in ("c", "cpp"):
            for i, line in enumerate(lines, 1):
                m = re.search(r'#\s*include\s*[<"]([^>"]+)[>"]', line)
                if m:
                    add_line(m.group(1), i)
        elif language == "go":
            in_import = False
            for i, line in enumerate(lines, 1):
                t = line.strip()
                if t.startswith("import "):
                    if "(" in t and ")" not in t:
                        in_import = True
                    m2 = re.search(r'"([^"]+)"', t)
                    if m2:
                        add_line(m2.group(1), i)
                elif in_import:
                    m2 = re.search(r'"([^"]+)"', t)
                    if m2:
                        add_line(m2.group(1), i)
                    if ")" in t and "(" not in t:
                        in_import = False
        elif language == "rust":
            for i, line in enumerate(lines, 1):
                if re.match(r"^\s*use\s+", line):
                    m = re.search(r"use\s+([^;]+);", line)
                    if m:
                        add_line(m.group(1).strip(), i)
        elif language in ("php", "ruby"):
            for i, line in enumerate(lines, 1):
                if re.search(r"^\s*(?:require|require_once|include|include_once)\s*[\(]?\s*['\"]([^'\"]+)['\"]", line):
                    m = re.search(
                        r"['\"]([^'\"]+)['\"]", line
                    )
                    if m:
                        add_line(m.group(1), i)
        elif language in ("java", "kotlin", "csharp", "scala", "groovy", "dart", "swift"):
            for i, line in enumerate(lines, 1):
                if re.match(
                    r"^\s*import\s+(?:static\s+)?(?:[\w.]+\*|[\w.]+);", line.strip()
                ):
                    m = re.search(
                        r"import\s+(?:static\s+)?(.+?);", line
                    )
                    if m:
                        add_line(m.group(1).strip(), i)
        else:
            # generic: C-style #include, import lines
            for i, line in enumerate(lines, 1):
                m = re.search(r'#\s*include\s*[<"]([^>"]+)[>"]', line)
                if m:
                    add_line(m.group(1), i)
                if re.match(r"^\s*import\s+", line) and "import" in line and language not in (
                    "javascript",
                    "text",
                ):
                    s = line.strip()[:200]
                    if s.endswith(";") or " from " in line or s.startswith("import "):
                        add_line(s, i)
        return out

    def extract_classes(
        self, content: str, language: str
    ) -> List[Union[str, Dict[str, Any]]]:
        out: List[Dict[str, Any]] = []
        for m in re.finditer(
            r"^\s*(?:public|private|protected|internal|sealed|abstract|open|data)?\s*(?:class|interface|struct|enum|trait)\s+(\w+)",
            content,
            re.MULTILINE,
        ):
            line = content[: m.start()].count("\n") + 1
            out.append({"name": m.group(1), "line": line, "methods": []})
        if language in ("c", "cpp") and not out:
            for m in re.finditer(
                r"^(?:struct|union|enum|class)\s+(\w+)", content, re.MULTILINE
            ):
                line = content[: m.start()].count("\n") + 1
                out.append({"name": m.group(1), "line": line, "methods": []})
        if language == "go":
            for m in re.finditer(
                r"^type\s+(\w+)\s+struct", content, re.MULTILINE
            ):
                line = content[: m.start()].count("\n") + 1
                out.append({"name": m.group(1), "line": line, "methods": []})
        if language == "rust":
            for m in re.finditer(
                r"^(?:pub\s+)?struct\s+(\w+)", content, re.MULTILINE
            ):
                line = content[: m.start()].count("\n") + 1
                out.append({"name": m.group(1), "line": line, "methods": []})
        if language in ("html", "vue", "svelte") and not out:
            for m in re.finditer(
                r"<(script|style|div|table|form|a)\b[^>]*\bid=['\"]([^'\"]+)['\"]", content, re.IGNORECASE
            ):
                line = content[: m.start()].count("\n") + 1
                out.append({"name": f"{m.group(1)}#{m.group(2)}", "line": line, "methods": []})
        if language == "json":
            m = re.search(r"{\s*\"(\w+)\"", content[:2000])
            if m:
                out.append(
                    {
                        "name": f"root key: {m.group(1)}",
                        "line": 1,
                        "methods": [],
                    }
                )
        return out

    def extract_functions(
        self, content: str, language: str
    ) -> List[Union[Dict[str, Any], str]]:
        res: List[Dict[str, Any]] = []
        if language in ("html", "css", "json", "yaml", "xml", "text", "markdown", "ini"):
            return res

        patterns: List[tuple] = []
        if language == "go":
            patterns.append(
                (r"^\s*func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", 1)
            )
        elif language == "rust":
            patterns.append((r"^\s*(?:pub\s+)?fn\s+(\w+)\s*\(", 1))
        elif language == "ruby":
            patterns.append((r"^\s*def\s+(\w+)[\s!(]", 1))
        elif language in ("php", "hack"):
            patterns.append((r"function\s+(\w+)\s*\(", 1))
        elif language in ("java", "kotlin", "csharp", "scala", "groovy", "swift", "dart"):
            patterns.append(
                (
                    r"(?:^|\n)\s*(?:public|private|protected|static|async|override|open|suspend)?\s*[\w<>,\s\[\].]+\s+(\w+)\s*\(",
                    1,
                )
            )
            patterns.append(
                (r"^\s*fun\s+(\w+)\s*\(", 1)
            )  # kotlin
            patterns.append((r"^\s*def\s+(\w+)\s*\(", 1))  # kotlin script / scala
        else:
            # c/c++ / generic
            patterns.append(
                (r"^\s*(?:static|inline|extern)?\s*[\w\s\*]+\b(\w+)\s*\([^;]*\)\s*\{", 1)
            )

        seen: Set[str] = set()
        for pat, grp in patterns:
            for m in re.finditer(pat, content, re.MULTILINE):
                name = m.group(grp)
                if not name or len(name) > 200 or not name[0].isalpha():
                    continue
                if name in ("if", "for", "while", "switch", "return", "new", "case"):
                    continue
                key = f"{name}:{m.start()}"
                if key in seen:
                    continue
                seen.add(key)
                line = content[: m.start()].count("\n") + 1
                res.append(
                    {
                        "name": name,
                        "line": line,
                        "parameters": [],
                        "is_async": "async" in m.group(0).lower()
                        or "suspend" in m.group(0).lower(),
                        "is_nested": False,
                        "decorators": [],
                    }
                )
        return res[:500]  # cap

    def extract_variables(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if language in ("json", "html", "css"):
            return out
        for m in re.finditer(
            r"^\s*(?:const|let|var|val)\s+(\w+)\s*[:=]", content, re.MULTILINE
        ):
            line = content[: m.start()].count("\n") + 1
            out.append({"name": m.group(1), "line": line, "type": "inferred"})
        for m in re.finditer(
            r"^\s*(\w+(?:<[^>]+>)?)\s+(\w+)\s*=\s*[^;]+;", content, re.MULTILINE
        ):
            if m.group(1) not in (
                "if",
                "for",
                "while",
                "return",
                "import",
            ) and m.group(1) not in ("struct", "class"):
                line = content[: m.start()].count("\n") + 1
                out.append(
                    {
                        "name": m.group(2),
                        "line": line,
                        "type": m.group(1),
                    }
                )
        return out[:300]

    def extract_endpoints(
        self, content: str, language: str
    ) -> List[Union[str, Dict[str, Any]]]:
        out: List[Dict[str, Any]] = []
        patterns = [
            (r"@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*[\"']([^\"']+)[\"']", "spring"),
            (r"@app\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "flask"),
            (r"router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "express"),
            (r"\.(?:get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "generic"),
            (r"HttpGet\s*\(\s*[\"']([^\"']+)[\"']", "csharp"),
            (r"http\.(HandleFunc|Handle)\s*\(\s*[\"']([^\"']+)[\"']", "go"),
            (r"#\[(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "rust"),
        ]
        for pat, kind in patterns:
            for m in re.finditer(pat, content, re.IGNORECASE):
                line = content[: m.start()].count("\n") + 1
                g = m.groups()
                path_ = g[-1] if g else ""
                if isinstance(path_, str) and path_:
                    out.append(
                        {
                            "framework": kind,
                            "path": path_,
                            "line": line,
                        }
                    )
        return out[:200]


# ---- helpers for app / scanner ----
def resolve_language_label(
    filename: Optional[str], code: Optional[str]
) -> str:
    """
    When LanguageDetector has no match, return extension-based label for universal path.
    """
    return detect_language_from_extension(filename or "")
