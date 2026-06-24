"""Compatibility shims so RAGAS can import without optional Vertex AI integrations."""

from __future__ import annotations

import sys
import types


def patch_ragas_imports() -> None:
    """Stub optional langchain-community Vertex modules required by ragas imports."""
    stubs = {
        "langchain_community.chat_models.vertexai": {"ChatVertexAI": type("ChatVertexAI", (), {})},
        "langchain_community.llms": {"VertexAI": type("VertexAI", (), {})},
    }
    for module_name, attrs in stubs.items():
        if module_name in sys.modules:
            continue
        module = types.ModuleType(module_name)
        for attr_name, attr_value in attrs.items():
            setattr(module, attr_name, attr_value)
        sys.modules[module_name] = module
