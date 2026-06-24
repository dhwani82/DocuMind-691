"""Tests for the evaluation harness (offline / mocked)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.run_eval import (
    DEFAULT_GOLDEN_SET,
    MODE_AGENTIC,
    MODE_GRAPH,
    MODE_VECTOR,
    GoldenItem,
    build_comparison_table,
    check_thresholds,
    load_golden_set,
    summarize_operational,
    tools_for_mode,
)
from code_graph import NetworkXGraphStore


def test_load_golden_set_has_expected_entries():
    items = load_golden_set(DEFAULT_GOLDEN_SET)
    assert 20 <= len(items) <= 30
    assert {item.category for item in items} >= {"retrieval", "structural", "documentation", "refusal"}


def test_load_golden_set_respects_limit():
    items = load_golden_set(DEFAULT_GOLDEN_SET, limit=3)
    assert len(items) == 3


def test_build_comparison_table_renders_three_modes():
    mode_results = {
        MODE_AGENTIC: {
            "ragas": {
                "faithfulness": 0.9,
                "answer_relevancy": 0.8,
                "context_precision": 0.7,
                "context_recall": 0.6,
            },
            "operational": {"latency_ms_avg": 1200.0, "total_tokens_avg": 300.0},
        },
        MODE_VECTOR: {
            "ragas": {
                "faithfulness": 0.7,
                "answer_relevancy": 0.75,
                "context_precision": 0.5,
                "context_recall": 0.55,
            },
            "operational": {"latency_ms_avg": 900.0, "total_tokens_avg": 250.0},
        },
        MODE_GRAPH: {
            "ragas": {
                "faithfulness": 0.85,
                "answer_relevancy": 0.82,
                "context_precision": 0.65,
                "context_recall": 0.7,
            },
            "operational": {"latency_ms_avg": 1100.0, "total_tokens_avg": 280.0},
        },
    }

    table = build_comparison_table(mode_results)
    assert "agentic-search-only" in table
    assert "vector-RAG-only" in table
    assert "graph-assisted" in table
    assert "faithfulness" in table


def test_check_thresholds_detects_failures():
    mode_results = {
        MODE_AGENTIC: {"ragas": {"faithfulness": 0.2, "context_precision": 0.1}},
        MODE_VECTOR: {"ragas": {"faithfulness": 0.9, "context_precision": 0.8}},
        MODE_GRAPH: {"ragas": {"faithfulness": 0.9, "context_precision": 0.8}},
    }
    failures = check_thresholds(
        mode_results,
        min_faithfulness=0.5,
        min_context_precision=0.3,
    )
    assert any("agentic-search-only" in failure for failure in failures)


def test_tools_for_mode_selects_expected_tool_names(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    graph_store = NetworkXGraphStore(persist_dir=tmp_path / "graphs")

    agentic_names = [tool.name for tool in tools_for_mode(MODE_AGENTIC, project, "demo", vector_store=None, graph_store=graph_store)]
    vector_names = [tool.name for tool in tools_for_mode(MODE_VECTOR, project, "demo", vector_store=None, graph_store=graph_store)]
    graph_names = [tool.name for tool in tools_for_mode(MODE_GRAPH, project, "demo", vector_store=None, graph_store=graph_store)]

    assert agentic_names == [
        "grep_code",
        "read_file",
        "list_files",
        "find_symbol",
        "get_structure",
    ]
    assert vector_names == ["vector_search"]
    assert "who_calls" in graph_names
    assert "find_symbol" in graph_names
    assert "vector_search" not in graph_names


def test_summarize_operational_averages_tokens():
    from eval.run_eval import QuestionRun

    runs = [
        QuestionRun("1", "q", "a", [], [], [], 100.0, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        QuestionRun("2", "q", "a", [], [], [], 300.0, {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}),
    ]
    summary = summarize_operational(runs)
    assert summary["latency_ms_avg"] == 200.0
    assert summary["total_tokens_avg"] == 22.5
