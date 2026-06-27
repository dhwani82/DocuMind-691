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
    QuestionRun,
    append_mode_result,
    average_ragas,
    build_comparison_table,
    build_metric_timeouts,
    check_thresholds,
    completed_question_ids,
    format_progress_line,
    load_golden_set,
    load_mode_results,
    mode_results_path,
    run_mode,
    summarize_operational,
    tools_for_mode,
)
from code_graph import NetworkXGraphStore


def test_load_golden_set_has_expected_entries():
    items = load_golden_set(DEFAULT_GOLDEN_SET)
    assert 20 <= len(items) <= 32
    assert {item.category for item in items} >= {
        "retrieval",
        "structural",
        "documentation",
        "refusal",
        "limitation",
    }


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
    runs = [
        QuestionRun("1", "q", "a", [], [], [], 100.0, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        QuestionRun("2", "q", "a", [], [], [], 300.0, {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}),
    ]
    summary = summarize_operational(runs)
    assert summary["latency_ms_avg"] == 200.0
    assert summary["total_tokens_avg"] == 22.5


def test_failed_question_recorded_as_nan_and_run_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    graph_store = NetworkXGraphStore(persist_dir=tmp_path / "graphs")

    items = [
        GoldenItem("gs001", "retrieval", "Where is x defined?", "in a.py", "a.py", "def x"),
        GoldenItem("gs002", "retrieval", "Trigger failure", "n/a", "", ""),
        GoldenItem("gs003", "retrieval", "What does x return?", "1", "a.py", "return 1"),
    ]

    class FakeResult:
        def __init__(self, answer: str):
            self.answer = answer
            self.sources = ["a.py:1"]
            self.tool_trace = [{"tool": "grep_code"}]
            self.tokens = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            self.contexts = ["def x():\n    return 1\n"]

    def fake_run_agent(_agent, question, **kwargs):
        if question == "Trigger failure":
            raise RuntimeError("deliberate agent failure")
        return FakeResult("ok answer")

    def fake_build_agent(*_args, **_kwargs):
        return object()

    def fake_score_ragas(item, run, *, metric_timeouts, judge=None):
        return (
            {
                "faithfulness": 1.0,
                "answer_relevancy": 0.9,
                "context_precision": 1.0,
                "context_recall": 1.0,
            },
            [],
        )

    monkeypatch.setattr("agent.build_agent", fake_build_agent)

    records = run_mode(
        MODE_AGENTIC,
        items,
        reports_dir=reports_dir,
        project_root=project_root,
        project_id="demo",
        vector_store=None,
        graph_store=graph_store,
        agent_timeout_s=5,
        ragas_metric_timeout_s=5,
        run_agent_fn=fake_run_agent,
        score_ragas_fn=fake_score_ragas,
    )

    assert len(records) == 3
    failed = next(record for record in records if record["id"] == "gs002")
    assert "deliberate agent failure" in failed["error"]
    assert failed["ragas"]["faithfulness"] is None

    success = next(record for record in records if record["id"] == "gs001")
    assert success["error"] is None
    assert success["ragas"]["faithfulness"] == 1.0

    results_path = mode_results_path(reports_dir, MODE_AGENTIC)
    assert results_path.exists()
    assert len(load_mode_results(results_path)) == 3


def test_resume_skips_completed_questions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports_dir = tmp_path / "reports"
    project_root = tmp_path / "project"
    project_root.mkdir()
    graph_store = NetworkXGraphStore(persist_dir=tmp_path / "graphs")
    results_path = mode_results_path(reports_dir, MODE_AGENTIC)
    append_mode_result(
        results_path,
        {
            "id": "gs001",
            "question": "already done",
            "answer": "cached",
            "contexts": [],
            "sources": [],
            "tool_trace": [],
            "latency_ms": 1.0,
            "tokens": None,
            "ragas": {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5, "context_recall": 0.5},
            "error": None,
        },
    )

    items = [
        GoldenItem("gs001", "retrieval", "already done", "cached", "", ""),
        GoldenItem("gs002", "retrieval", "new question", "answer", "", ""),
    ]

    calls: list[str] = []

    class FakeResult:
        answer = "new answer"
        sources = []
        tool_trace = []
        tokens = None
        contexts = ["ctx"]

    def fake_run_agent(_agent, question, **kwargs):
        calls.append(question)
        return FakeResult()

    monkeypatch.setattr("agent.build_agent", lambda *_a, **_k: object())

    records = run_mode(
        MODE_AGENTIC,
        items,
        reports_dir=reports_dir,
        project_root=project_root,
        project_id="demo",
        vector_store=None,
        graph_store=graph_store,
        run_agent_fn=fake_run_agent,
        score_ragas_fn=lambda *_a, **_k: (
            {"faithfulness": 1.0, "answer_relevancy": 1.0, "context_precision": 1.0, "context_recall": 1.0},
            [],
        ),
    )

    assert calls == ["new question"]
    assert completed_question_ids(results_path) == {"gs001", "gs002"}
    assert len(records) == 2


def test_format_progress_line_shows_error():
    record = {
        "error": "agent timeout after 120s",
        "ragas": {"faithfulness": None},
    }
    line = format_progress_line(MODE_AGENTIC, 2, 30, "gs002", record)
    assert "question 2/30: gs002" in line
    assert "ERROR: agent timeout after 120s" in line


def test_average_ragas_ignores_missing_scores():
    records = [
        {"ragas": {"faithfulness": 1.0, "answer_relevancy": 0.8, "context_precision": 1.0, "context_recall": 1.0}},
        {"ragas": {"faithfulness": None, "answer_relevancy": None, "context_precision": None, "context_recall": None}},
    ]
    averages = average_ragas(records)
    assert averages["faithfulness"] == 1.0


def test_build_metric_timeouts_gives_answer_relevancy_more_time():
    timeouts = build_metric_timeouts(
        ragas_metric_timeout_s=120.0,
        answer_relevancy_timeout_s=200.0,
    )
    assert timeouts["faithfulness"] == 120.0
    assert timeouts["answer_relevancy"] == 200.0
