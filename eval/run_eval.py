#!/usr/bin/env python3
"""Three-way retrieval evaluation harness for DocuMind."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from eval.ragas_compat import patch_ragas_imports

patch_ragas_imports()

from code_graph import NetworkXGraphStore, build_graph, has_graph
from code_tools import create_code_tools
from graph_tools import create_graph_tools
from tracing import RETRIEVAL_AGENTIC, RETRIEVAL_GRAPH, RETRIEVAL_VECTOR, configure_tracing

DEFAULT_PROJECT_ID = "eval-sample"
DEFAULT_GOLDEN_SET = Path(__file__).resolve().parent / "golden_set.jsonl"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent / "reports"

MODE_AGENTIC = "agentic"
MODE_VECTOR = "vector"
MODE_GRAPH = "graph-assisted"

MODE_LABELS = {
    MODE_AGENTIC: "agentic-search-only",
    MODE_VECTOR: "vector-RAG-only",
    MODE_GRAPH: "graph-assisted",
}

ALL_MODES = [MODE_AGENTIC, MODE_VECTOR, MODE_GRAPH]

BASE_GROUNDING = """Answer ONLY from tool results. Cite sources as file:line when possible.
If tools do not provide enough evidence, say "not found in the codebase" instead of guessing."""

MODE_SYSTEM_PROMPTS = {
    MODE_AGENTIC: f"""You are DocuMind in agentic-search-only mode.
Use only grep_code, read_file, list_files, find_symbol, and get_structure.
Do not guess. {BASE_GROUNDING}""",
    MODE_VECTOR: f"""You are DocuMind in vector-RAG-only mode.
Use only vector_search to retrieve relevant code chunks, then answer from those results.
Do not guess. {BASE_GROUNDING}""",
    MODE_GRAPH: f"""You are DocuMind in graph-assisted mode.
Use grep_code, read_file, list_files, find_symbol, get_structure for file lookups.
Use who_calls, what_calls, impact_of, and dependencies_of for structural call/import questions.
Do not use vector_search. {BASE_GROUNDING}""",
}


@dataclass
class GoldenItem:
    id: str
    category: str
    question: str
    expected_answer: str
    expected_source_file: str
    expected_context: str


@dataclass
class QuestionRun:
    id: str
    question: str
    answer: str
    contexts: list[str]
    sources: list[str]
    tool_trace: list[dict[str, Any]]
    latency_ms: float
    tokens: Optional[dict[str, int]]


def load_golden_set(path: Path, limit: Optional[int] = None) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            items.append(
                GoldenItem(
                    id=payload["id"],
                    category=payload.get("category", "retrieval"),
                    question=payload["question"],
                    expected_answer=payload["expected_answer"],
                    expected_source_file=payload.get("expected_source_file", ""),
                    expected_context=payload.get("expected_context", ""),
                )
            )
            if limit is not None and len(items) >= limit:
                break
    return items


def ensure_eval_project(
    project_root: Path,
    project_id: str,
    *,
    vector_store,
    graph_store: NetworkXGraphStore,
) -> list[str]:
    from chunking import chunk_file
    from vector_index import ingest_project, is_indexed

    from eval.sample_project import ensure_sample_project

    ensure_sample_project(project_root)
    files = sorted(str(path) for path in project_root.glob("*.py"))

    if not is_indexed(project_id, vector_store=vector_store):
        ingest_project(project_id, files, vector_store=vector_store, chunker=chunk_file)
    if not has_graph(project_id, graph_store=graph_store):
        build_graph(project_id, files, graph_store=graph_store)

    return files


def tools_for_mode(
    mode: str,
    project_root: Path,
    project_id: str,
    *,
    vector_store,
    graph_store: NetworkXGraphStore,
):
    if mode == MODE_AGENTIC:
        return create_code_tools(project_root)
    if mode == MODE_VECTOR:
        from vector_search import create_vector_search_tool

        return [create_vector_search_tool(project_id, vector_store=vector_store)]
    if mode == MODE_GRAPH:
        return [
            *create_code_tools(project_root),
            *create_graph_tools(project_id, graph_store=graph_store),
        ]
    raise ValueError(f"Unknown mode: {mode}")


def retrieval_strategy_for_mode(mode: str) -> str:
    if mode == MODE_AGENTIC:
        return RETRIEVAL_AGENTIC
    if mode == MODE_VECTOR:
        return RETRIEVAL_VECTOR
    return RETRIEVAL_GRAPH


def run_mode(
    mode: str,
    items: list[GoldenItem],
    *,
    project_root: Path,
    project_id: str,
    vector_store,
    graph_store: NetworkXGraphStore,
) -> list[QuestionRun]:
    from agent import build_agent, run_agent

    agent = build_agent(
        project_root,
        project_id,
        vector_store=vector_store,
        graph_store=graph_store,
        tools=tools_for_mode(mode, project_root, project_id, vector_store=vector_store, graph_store=graph_store),
        system_prompt=MODE_SYSTEM_PROMPTS[mode],
    )

    strategy = retrieval_strategy_for_mode(mode)
    runs: list[QuestionRun] = []

    for item in items:
        started = time.perf_counter()
        result = run_agent(
            agent,
            item.question,
            thread_id=f"eval-{mode}-{item.id}",
            project_id=project_id,
            endpoint=f"eval/{mode}",
            retrieval_strategy=strategy,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        runs.append(
            QuestionRun(
                id=item.id,
                question=item.question,
                answer=result.answer,
                contexts=result.contexts,
                sources=result.sources,
                tool_trace=result.tool_trace,
                latency_ms=latency_ms,
                tokens=result.tokens,
            )
        )
    return runs


def ragas_metrics_for_runs(
    items: list[GoldenItem],
    runs: list[QuestionRun],
) -> dict[str, float]:
    import asyncio

    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    run_by_id = {run.id: run for run in runs}
    if not items:
        return {}

    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for RAGAS evaluation.")

    client = AsyncOpenAI(api_key=api_key)
    ragas_llm = llm_factory(model_name, client=client)
    ragas_embeddings = embedding_factory("openai", model=embedding_model, client=client)

    faithfulness_metric = Faithfulness(llm=ragas_llm)
    answer_relevancy_metric = AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings)
    context_precision_metric = ContextPrecisionWithReference(llm=ragas_llm)
    context_recall_metric = ContextRecall(llm=ragas_llm)

    async def _score_all() -> dict[str, list[float]]:
        buckets: dict[str, list[float]] = {
            "faithfulness": [],
            "answer_relevancy": [],
            "context_precision": [],
            "context_recall": [],
        }

        for item in items:
            run = run_by_id[item.id]
            contexts = run.contexts or ["(no retrieved context)"]
            answer = run.answer or ""

            faith = await faithfulness_metric.ascore(
                user_input=item.question,
                response=answer,
                retrieved_contexts=contexts,
            )
            buckets["faithfulness"].append(float(faith.value))

            relevancy = await answer_relevancy_metric.ascore(
                user_input=item.question,
                response=answer,
            )
            buckets["answer_relevancy"].append(float(relevancy.value))

            precision = await context_precision_metric.ascore(
                user_input=item.question,
                reference=item.expected_answer,
                retrieved_contexts=contexts,
            )
            buckets["context_precision"].append(float(precision.value))

            recall = await context_recall_metric.ascore(
                user_input=item.question,
                retrieved_contexts=contexts,
                reference=item.expected_answer,
            )
            buckets["context_recall"].append(float(recall.value))

        return buckets

    buckets = asyncio.run(_score_all())
    return {key: sum(values) / len(values) for key, values in buckets.items() if values}


def summarize_operational(runs: list[QuestionRun]) -> dict[str, float]:
    if not runs:
        return {"latency_ms_avg": 0.0, "prompt_tokens_avg": 0.0, "completion_tokens_avg": 0.0, "total_tokens_avg": 0.0}

    latencies = [run.latency_ms for run in runs]
    prompt_tokens: list[int] = []
    completion_tokens: list[int] = []
    total_tokens: list[int] = []
    for run in runs:
        if not run.tokens:
            continue
        prompt_tokens.append(int(run.tokens.get("prompt_tokens", 0)))
        completion_tokens.append(int(run.tokens.get("completion_tokens", 0)))
        total_tokens.append(int(run.tokens.get("total_tokens", 0)))

    def _avg(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0

    return {
        "latency_ms_avg": sum(latencies) / len(latencies),
        "prompt_tokens_avg": _avg(prompt_tokens),
        "completion_tokens_avg": _avg(completion_tokens),
        "total_tokens_avg": _avg(total_tokens),
    }


def build_comparison_table(mode_results: dict[str, dict[str, Any]]) -> str:
    metric_columns = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "latency_ms_avg",
        "total_tokens_avg",
    ]

    header = ["mode", *metric_columns]
    rows = [header]
    for mode in ALL_MODES:
        payload = mode_results[mode]
        ragas = payload.get("ragas", {})
        ops = payload.get("operational", {})
        rows.append(
            [
                MODE_LABELS[mode],
                _fmt(ragas.get("faithfulness")),
                _fmt(ragas.get("answer_relevancy")),
                _fmt(ragas.get("context_precision")),
                _fmt(ragas.get("context_recall")),
                _fmt(ops.get("latency_ms_avg")),
                _fmt(ops.get("total_tokens_avg")),
            ]
        )

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(header))]
    lines = []
    for row_index, row in enumerate(rows):
        line = " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(line)
        if row_index == 0:
            lines.append("-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_report(
    reports_dir: Path,
    *,
    table: str,
    mode_results: dict[str, dict[str, Any]],
    golden_path: Path,
    project_id: str,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports_dir / f"comparison_{stamp}.json"
    payload = {
        "generated_at": stamp,
        "golden_set": str(golden_path),
        "project_id": project_id,
        "table": table,
        "modes": mode_results,
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    markdown_path = reports_dir / f"comparison_{stamp}.md"
    markdown_path.write_text(
        "# DocuMind retrieval comparison\n\n"
        f"- Golden set: `{golden_path}`\n"
        f"- Project id: `{project_id}`\n\n"
        "```text\n"
        f"{table}\n"
        "```\n",
        encoding="utf-8",
    )
    return report_path


def check_thresholds(
    mode_results: dict[str, dict[str, Any]],
    *,
    min_faithfulness: Optional[float],
    min_context_precision: Optional[float],
) -> list[str]:
    failures: list[str] = []
    for mode in ALL_MODES:
        ragas = mode_results[mode].get("ragas", {})
        label = MODE_LABELS[mode]
        if min_faithfulness is not None:
            value = ragas.get("faithfulness")
            if value is None or value < min_faithfulness:
                failures.append(
                    f"{label}: faithfulness {value} < threshold {min_faithfulness}"
                )
        if min_context_precision is not None:
            value = ragas.get("context_precision")
            if value is None or value < min_context_precision:
                failures.append(
                    f"{label}: context_precision {value} < threshold {min_context_precision}"
                )
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DocuMind three-way retrieval evaluation.")
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--project-root", type=Path, default=ROOT / "eval" / "sample_project_data")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N golden questions.")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=ALL_MODES,
        default=ALL_MODES,
        help="Subset of retrieval modes to evaluate.",
    )
    parser.add_argument(
        "--threshold",
        action="store_true",
        help="Exit non-zero when faithfulness or context precision fall below configured minimums.",
    )
    parser.add_argument("--min-faithfulness", type=float, default=0.5)
    parser.add_argument("--min-context-precision", type=float, default=0.3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_tracing()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is required for agent and RAGAS evaluation.", file=sys.stderr)
        return 2

    from vector_index import ChromaVectorStore

    vector_store = ChromaVectorStore(persist_dir=ROOT / ".chroma_eval")
    graph_store = NetworkXGraphStore(persist_dir=ROOT / ".graph_store_eval")

    project_root = args.project_root.resolve()
    ensure_eval_project(
        project_root,
        args.project_id,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    items = load_golden_set(args.golden_set, limit=args.limit)
    if not items:
        print("ERROR: golden set is empty.", file=sys.stderr)
        return 2

    mode_results: dict[str, dict[str, Any]] = {}
    for mode in args.modes:
        print(f"Running mode: {MODE_LABELS[mode]} ({len(items)} questions)...", flush=True)
        runs = run_mode(
            mode,
            items,
            project_root=project_root,
            project_id=args.project_id,
            vector_store=vector_store,
            graph_store=graph_store,
        )
        ragas = ragas_metrics_for_runs(items, runs)
        operational = summarize_operational(runs)
        mode_results[mode] = {
            "label": MODE_LABELS[mode],
            "ragas": ragas,
            "operational": operational,
            "runs": [
                {
                    "id": run.id,
                    "question": run.question,
                    "answer": run.answer,
                    "sources": run.sources,
                    "tool_trace": run.tool_trace,
                    "latency_ms": run.latency_ms,
                    "tokens": run.tokens,
                }
                for run in runs
            ],
        }

    for mode in ALL_MODES:
        if mode not in mode_results:
            mode_results[mode] = {"label": MODE_LABELS[mode], "ragas": {}, "operational": {}, "runs": []}

    table = build_comparison_table(mode_results)
    print("\nDocuMind retrieval comparison\n")
    print(table)

    report_path = write_report(
        args.reports_dir,
        table=table,
        mode_results=mode_results,
        golden_path=args.golden_set,
        project_id=args.project_id,
    )
    print(f"\nReport written to {report_path}")

    if args.threshold:
        failures = check_thresholds(
            mode_results,
            min_faithfulness=args.min_faithfulness,
            min_context_precision=args.min_context_precision,
        )
        if failures:
            print("\nThreshold failures:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
