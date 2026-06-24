"""LangSmith tracing helpers (env-gated, no-op when disabled)."""

from __future__ import annotations

import os
from typing import Any, Callable, Optional, TypeVar

from langchain_core.tools import BaseTool

# Retrieval strategy labels used across eval and tracing.
RETRIEVAL_AGENTIC = "agentic"
RETRIEVAL_VECTOR = "vector"
RETRIEVAL_GRAPH = "graph"
RETRIEVAL_GENERATION = "generation"
RETRIEVAL_AGENT = "agent"

TOOL_RETRIEVAL_STRATEGY: dict[str, str] = {
    "grep_code": RETRIEVAL_AGENTIC,
    "read_file": RETRIEVAL_AGENTIC,
    "list_files": RETRIEVAL_AGENTIC,
    "find_symbol": RETRIEVAL_AGENTIC,
    "get_structure": RETRIEVAL_AGENTIC,
    "vector_search": RETRIEVAL_VECTOR,
    "who_calls": RETRIEVAL_GRAPH,
    "what_calls": RETRIEVAL_GRAPH,
    "impact_of": RETRIEVAL_GRAPH,
    "dependencies_of": RETRIEVAL_GRAPH,
    "generate_docstrings": RETRIEVAL_GENERATION,
    "generate_readme": RETRIEVAL_GENERATION,
    "generate_architecture_doc": RETRIEVAL_GENERATION,
    "generate_diagram": RETRIEVAL_GENERATION,
    "generate_svg_flowchart": RETRIEVAL_GENERATION,
}

F = TypeVar("F", bound=Callable[..., Any])


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_tracing_enabled() -> bool:
    """Return True when LangSmith tracing should be active."""
    if not _truthy(os.getenv("LANGCHAIN_TRACING_V2")):
        return False
    api_key = (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY") or "").strip()
    return bool(api_key)


def configure_tracing() -> bool:
    """Normalize tracing env vars. Returns whether tracing is active."""
    if not is_tracing_enabled():
        return False

    # LangChain reads LANGCHAIN_TRACING_V2 and LANGSMITH_API_KEY / LANGCHAIN_API_KEY.
    # Mirror LANGSMITH_API_KEY into LANGCHAIN_API_KEY when only the former is set.
    if not (os.getenv("LANGCHAIN_API_KEY") or "").strip():
        smith_key = (os.getenv("LANGSMITH_API_KEY") or "").strip()
        if smith_key:
            os.environ["LANGCHAIN_API_KEY"] = smith_key

    if not (os.getenv("LANGCHAIN_TRACING_V2") or "").strip():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    return True


def build_run_config(
    *,
    thread_id: str = "default",
    project_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    retrieval_strategy: Optional[str] = None,
    recursion_limit: Optional[int] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
    extra_tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build a LangGraph/LangChain run config with tracing metadata and tags."""
    metadata: dict[str, Any] = {}
    if project_id:
        metadata["project_id"] = project_id
    if endpoint:
        metadata["endpoint"] = endpoint
    if retrieval_strategy:
        metadata["retrieval_strategy"] = retrieval_strategy
    if extra_metadata:
        metadata.update(extra_metadata)

    tags: list[str] = list(extra_tags or [])
    if project_id:
        tags.append(f"project:{project_id}")
    if endpoint:
        tags.append(f"endpoint:{endpoint}")
    if retrieval_strategy:
        tags.append(f"retrieval:{retrieval_strategy}")

    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if metadata:
        config["metadata"] = metadata
    if tags:
        config["tags"] = tags
    if recursion_limit is not None:
        config["recursion_limit"] = recursion_limit
    return config


def apply_tracing_config(
    runnable: Any,
    *,
    project_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    retrieval_strategy: Optional[str] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
    extra_tags: Optional[list[str]] = None,
) -> Any:
    """Attach tracing metadata to a runnable when tracing is enabled."""
    if not is_tracing_enabled():
        return runnable

    metadata: dict[str, Any] = {}
    tags: list[str] = list(extra_tags or [])
    if project_id:
        metadata["project_id"] = project_id
        tags.append(f"project:{project_id}")
    if endpoint:
        metadata["endpoint"] = endpoint
        tags.append(f"endpoint:{endpoint}")
    if retrieval_strategy:
        metadata["retrieval_strategy"] = retrieval_strategy
        tags.append(f"retrieval:{retrieval_strategy}")
    if extra_metadata:
        metadata.update(extra_metadata)

    config_kwargs: dict[str, Any] = {}
    if metadata:
        config_kwargs["metadata"] = metadata
    if tags:
        config_kwargs["tags"] = tags
    if not config_kwargs:
        return runnable

    return runnable.with_config(**config_kwargs)


def wrap_tools_with_tracing(
    tools: list[BaseTool],
    *,
    project_id: str,
    endpoint: Optional[str] = None,
) -> list[BaseTool]:
    """Tag each tool invocation with project_id and per-tool retrieval strategy."""
    if not is_tracing_enabled():
        return tools

    wrapped: list[BaseTool] = []
    for tool in tools:
        strategy = TOOL_RETRIEVAL_STRATEGY.get(tool.name, "unknown")
        wrapped.append(
            apply_tracing_config(
                tool,
                project_id=project_id,
                endpoint=endpoint or f"tool:{tool.name}",
                retrieval_strategy=strategy,
                extra_tags=[f"tool:{tool.name}"],
            )
        )
    return wrapped


def traceable_call(
    name: str,
    *,
    run_type: str = "chain",
    **default_metadata: Any,
) -> Callable[[F], F]:
    """Decorator that becomes a LangSmith trace only when tracing is enabled."""

    def decorator(func: F) -> F:
        if not is_tracing_enabled():
            return func

        try:
            from langsmith.run_helpers import traceable

            return traceable(name=name, run_type=run_type, metadata=default_metadata)(func)
        except Exception:
            return func

    return decorator


def traced_execution(
    name: str,
    func: Callable[..., Any],
    /,
    *args: Any,
    project_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    retrieval_strategy: Optional[str] = None,
    inputs: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Any:
    """Execute a callable inside a LangSmith trace when tracing is enabled."""
    if not is_tracing_enabled():
        return func(*args, **kwargs)

    metadata = {
        key: value
        for key, value in {
            "project_id": project_id,
            "endpoint": endpoint,
            "retrieval_strategy": retrieval_strategy,
        }.items()
        if value is not None
    }
    tags = [
        tag
        for tag in (
            f"project:{project_id}" if project_id else None,
            f"endpoint:{endpoint}" if endpoint else None,
            f"retrieval:{retrieval_strategy}" if retrieval_strategy else None,
        )
        if tag
    ]

    try:
        from langsmith import trace

        with trace(
            name=name,
            run_type="chain",
            inputs=inputs or {},
            metadata=metadata or None,
            tags=tags or None,
        ):
            return func(*args, **kwargs)
    except Exception:
        return func(*args, **kwargs)
