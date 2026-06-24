"""Tests for LangSmith tracing helpers."""

from unittest.mock import MagicMock

import pytest
from langchain_core.tools import tool

from tracing import (
    RETRIEVAL_GRAPH,
    RETRIEVAL_VECTOR,
    TOOL_RETRIEVAL_STRATEGY,
    apply_tracing_config,
    build_run_config,
    configure_tracing,
    is_tracing_enabled,
    wrap_tools_with_tracing,
)


@pytest.fixture(autouse=True)
def tracing_env_off(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)


def test_is_tracing_enabled_false_by_default():
    assert is_tracing_enabled() is False
    assert configure_tracing() is False


def test_is_tracing_enabled_true_when_env_set(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

    assert is_tracing_enabled() is True
    assert configure_tracing() is True

    import os

    assert os.environ.get("LANGCHAIN_API_KEY") == "test-key"


def test_build_run_config_includes_metadata_and_tags():
    config = build_run_config(
        thread_id="t-1",
        project_id="documind",
        endpoint="api/agent",
        retrieval_strategy="agent",
        recursion_limit=10,
    )

    assert config["configurable"]["thread_id"] == "t-1"
    assert config["recursion_limit"] == 10
    assert config["metadata"]["project_id"] == "documind"
    assert config["metadata"]["endpoint"] == "api/agent"
    assert config["metadata"]["retrieval_strategy"] == "agent"
    assert "project:documind" in config["tags"]
    assert "endpoint:api/agent" in config["tags"]
    assert "retrieval:agent" in config["tags"]


def test_apply_tracing_config_noop_when_disabled():
    runnable = MagicMock()
    runnable.with_config = MagicMock(return_value="wrapped")

    result = apply_tracing_config(
        runnable,
        project_id="demo",
        endpoint="test",
        retrieval_strategy=RETRIEVAL_VECTOR,
    )

    assert result is runnable
    runnable.with_config.assert_not_called()


def test_apply_tracing_config_wraps_when_enabled(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

    runnable = MagicMock()
    runnable.with_config = MagicMock(return_value="wrapped")

    result = apply_tracing_config(
        runnable,
        project_id="demo",
        endpoint="test",
        retrieval_strategy=RETRIEVAL_VECTOR,
    )

    assert result == "wrapped"
    runnable.with_config.assert_called_once()
    kwargs = runnable.with_config.call_args.kwargs
    assert kwargs["metadata"]["project_id"] == "demo"
    assert kwargs["metadata"]["retrieval_strategy"] == RETRIEVAL_VECTOR
    assert "retrieval:vector" in kwargs["tags"]


def test_wrap_tools_with_tracing_noop_when_disabled():
    @tool
    def sample_tool(query: str) -> str:
        """Sample tool."""
        return query

    wrapped = wrap_tools_with_tracing([sample_tool], project_id="demo")
    assert wrapped[0] is sample_tool


def test_wrap_tools_with_tracing_tags_tools_when_enabled(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

    @tool
    def sample_tool(query: str) -> str:
        """Sample tool."""
        return query

    wrapped = wrap_tools_with_tracing(
        [sample_tool],
        project_id="demo",
        endpoint="agent.tools",
    )

    assert wrapped[0] is not sample_tool
    assert TOOL_RETRIEVAL_STRATEGY["vector_search"] == RETRIEVAL_VECTOR
    assert TOOL_RETRIEVAL_STRATEGY["who_calls"] == RETRIEVAL_GRAPH
