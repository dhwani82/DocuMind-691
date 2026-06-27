"""Java code parser using regex-based structure extraction."""

from __future__ import annotations

import re
from typing import Any


class JavaParser:
    """Parse Java source to extract classes, methods, imports, and calls."""

    def __init__(self) -> None:
        self.functions: list[dict[str, Any]] = []
        self.classes: list[dict[str, Any]] = []
        self.imports: list[dict[str, Any]] = []
        self.global_vars: list[dict[str, Any]] = []
        self.local_vars: list[dict[str, Any]] = []
        self.execution_scope_vars: list[dict[str, Any]] = []
        self.decorators: list[dict[str, Any]] = []
        self.function_calls: list[dict[str, Any]] = []
        self.method_calls: list[dict[str, Any]] = []
        self.class_instantiations: list[dict[str, Any]] = []
        self.control_flow: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.import_usage: list[dict[str, Any]] = []

    def parse(self, code: str) -> dict[str, Any]:
        """Parse Java code and return a DocuMind-compatible structure dict."""
        self._reset()
        lines = code.split("\n")

        self._extract_imports(code)
        self._extract_classes(code, lines)

        sync_functions = [
            f
            for f in self.functions
            if not f.get("is_async") and not f.get("is_nested")
        ]

        methods: list[dict[str, Any]] = []
        for cls in self.classes:
            methods.extend(cls.get("methods", []))

        class_vars: list[dict[str, Any]] = []
        instance_vars: list[dict[str, Any]] = []
        for cls in self.classes:
            class_vars.extend(cls.get("class_variables", []))
            instance_vars.extend(cls.get("instance_variables", []))

        return {
            "summary": {
                "total_functions": len(self.functions),
                "sync_functions": len(sync_functions),
                "async_functions": 0,
                "nested_functions": 0,
                "total_classes": len(self.classes),
                "total_methods": len(methods),
                "global_variables": len(self.global_vars),
                "local_variables": len(self.local_vars),
                "execution_scope_variables": len(self.execution_scope_vars),
                "class_variables": len(class_vars),
                "instance_variables": len(instance_vars),
                "total_decorators": len(self.decorators),
                "total_imports": len(self.imports),
            },
            "functions": self.functions,
            "classes": self.classes,
            "global_variables": self.global_vars,
            "local_variables": self.local_vars,
            "execution_scope_variables": self.execution_scope_vars,
            "imports": self.imports,
            "decorators": self.decorators,
            "function_calls": self.function_calls,
            "method_calls": self.method_calls,
            "class_instantiations": self.class_instantiations,
            "control_flow": self.control_flow,
            "warnings": self.warnings,
            "import_usage": self.import_usage,
            "language": "java",
        }

    def _reset(self) -> None:
        self.functions = []
        self.classes = []
        self.imports = []
        self.global_vars = []
        self.local_vars = []
        self.execution_scope_vars = []
        self.decorators = []
        self.function_calls = []
        self.method_calls = []
        self.class_instantiations = []
        self.control_flow = []
        self.warnings = []
        self.import_usage = []

    def _extract_imports(self, code: str) -> None:
        import_pattern = r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;"
        for match in re.finditer(import_pattern, code, re.MULTILINE):
            module = match.group(1)
            is_static = "import static" in match.group(0)
            line_num = code[: match.start()].count("\n") + 1
            if module.endswith(".*"):
                self.imports.append(
                    {
                        "type": "import",
                        "module": module[:-2],
                        "name": None,
                        "alias": None,
                        "line": line_num,
                        "is_static": is_static,
                    }
                )
            else:
                package, _, name = module.rpartition(".")
                self.imports.append(
                    {
                        "type": "from_import" if package else "import",
                        "module": package or module,
                        "name": name or module,
                        "alias": None,
                        "line": line_num,
                        "is_static": is_static,
                    }
                )

    def _extract_classes(self, code: str, lines: list[str]) -> None:
        class_pattern = (
            r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?"
            r"class\s+(\w+)(?:\s+extends\s+(\w+))?"
            r"(?:\s+implements\s+([\w,\s]+))?\s*\{"
        )
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            base_class = match.group(2)
            line_num = code[: match.start()].count("\n") + 1
            class_start = match.end()
            class_body = self._extract_block(code, class_start - 1)

            methods = self._extract_methods(class_name, class_body, class_start, code)
            self._extract_calls_in_body(class_name, class_body, class_start, code)

            self.classes.append(
                {
                    "name": class_name,
                    "line": line_num,
                    "bases": [base_class] if base_class else [],
                    "decorators": [],
                    "methods": methods,
                    "class_variables": [],
                    "instance_variables": [],
                }
            )

    def _extract_block(self, code: str, open_brace_index: int) -> str:
        brace_count = 0
        i = open_brace_index
        while i < len(code):
            if code[i] == "{":
                brace_count += 1
            elif code[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    return code[open_brace_index + 1 : i]
            i += 1
        return code[open_brace_index + 1 :]

    def _extract_methods(
        self,
        class_name: str,
        class_body: str,
        class_start: int,
        full_code: str,
    ) -> list[dict[str, Any]]:
        methods: list[dict[str, Any]] = []
        method_pattern = (
            r"(?:public|private|protected|static|\s)+"
            r"[\w<>\[\],\s]+\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w.\s,]+)?\s*\{"
        )
        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            if method_name in {"if", "for", "while", "switch", "catch", "new"}:
                continue

            absolute_start = class_start + match.start()
            line_num = full_code[:absolute_start].count("\n") + 1
            param_str = match.group(2).strip()
            params = [p.strip() for p in param_str.split(",") if p.strip()] if param_str else []

            qualified = f"{class_name}.{method_name}"
            method_info = {
                "name": method_name,
                "parameters": params,
                "line": line_num,
                "class_name": class_name,
            }
            methods.append(method_info)

            if method_name not in {"<init>", "class"}:
                self.functions.append(
                    {
                        "name": qualified,
                        "line": line_num,
                        "parameters": params,
                        "is_async": False,
                        "is_nested": False,
                        "decorators": [],
                        "returns": None,
                        "docstring": None,
                        "class_name": class_name,
                    }
                )

        return methods

    def _extract_calls_in_body(
        self,
        class_name: str,
        body: str,
        body_start: int,
        full_code: str,
    ) -> None:
        current_method = class_name

        method_header_pattern = (
            r"(?:public|private|protected|static|\s)+"
            r"[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w.\s,]+)?\s*\{"
        )
        segments: list[tuple[str, str, int]] = []
        for match in re.finditer(method_header_pattern, body):
            method_name = match.group(1)
            if method_name in {"if", "for", "while", "switch", "catch", "new"}:
                continue
            method_body_start = body_start + match.end() - 1
            method_body = self._extract_block(full_code, method_body_start)
            caller = f"{class_name}.{method_name}"
            segments.append((caller, method_body, method_body_start + 1))

        if not segments:
            segments.append((class_name, body, body_start))

        for caller, method_body, offset in segments:
            self._extract_calls_from_segment(caller, method_body, offset, full_code)

    def _extract_calls_from_segment(
        self,
        caller: str,
        segment: str,
        segment_start: int,
        full_code: str,
    ) -> None:
        call_pattern = r"(?<![\w.])(\w+)\s*\("
        for match in re.finditer(call_pattern, segment):
            callee = match.group(1)
            if callee in {
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "return",
                "new",
                "throw",
                "super",
                "this",
            }:
                continue
            line_num = full_code[: segment_start + match.start()].count("\n") + 1
            self.function_calls.append(
                {"caller": caller, "callee": callee, "line": line_num}
            )

        method_call_pattern = r"(\w+)\.(\w+)\s*\("
        for match in re.finditer(method_call_pattern, segment):
            obj = match.group(1)
            method = match.group(2)
            if obj in {"this", "super"}:
                continue
            line_num = full_code[: segment_start + match.start()].count("\n") + 1
            self.method_calls.append(
                {
                    "caller": caller,
                    "method": method,
                    "class_name": obj,
                    "line": line_num,
                }
            )
            if method[0].isupper():
                self.class_instantiations.append(
                    {"caller": caller, "class_name": method, "line": line_num}
                )

        new_pattern = r"new\s+(\w+)\s*\("
        for match in re.finditer(new_pattern, segment):
            class_name = match.group(1)
            line_num = full_code[: segment_start + match.start()].count("\n") + 1
            self.class_instantiations.append(
                {"caller": caller, "class_name": class_name, "line": line_num}
            )
