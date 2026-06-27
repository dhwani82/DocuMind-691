#!/usr/bin/env python3
"""Three-way retrieval evaluation harness for DocuMind."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from eval.ragas_compat import patch_ragas_imports

patch_ragas_imports()

from code_graph import NetworkXGraphStore, build_graph
from code_tools import create_code_tools
from graph_tools import create_graph_tools
from tracing import RETRIEVAL_AGENTIC, RETRIEVAL_GRAPH, RETRIEVAL_VECTOR, configure_tracing

DEFAULT_PROJECT_ID = "eval-sample"
DEFAULT_GOLDEN_SET = Path(__file__).resolve().parent / "golden_set.jsonl"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent / "reports"

DEFAULT_AGENT_TIMEOUT_S = 120.0
DEFAULT_RAGAS_METRIC_TIMEOUT_S = 120.0
DEFAULT_RAGAS_ANSWER_RELEVANCY_TIMEOUT_S = 200.0
DEFAULT_PREFLIGHT_EMBED_TIMEOUT_S = 45.0
DEFAULT_PREFLIGHT_LLM_TIMEOUT_S = 45.0
DEFAULT_PREFLIGHT_ANSWER_RELEVANCY_TIMEOUT_S = 120.0

# Pinned RAGAS judge models (separate from the agent answer model).
DEFAULT_RAGAS_JUDGE_MODEL = "gpt-4o-mini"
DEFAULT_RAGAS_JUDGE_EMBEDDING_MODEL = "text-embedding-3-small"

MODE_AGENTIC = "agentic"
MODE_VECTOR = "vector"
MODE_GRAPH = "graph-assisted"

MODE_LABELS = {
    MODE_AGENTIC: "agentic-search-only",
    MODE_VECTOR: "vector-RAG-only",
    MODE_GRAPH: "graph-assisted",
}

ALL_MODES = [MODE_AGENTIC, MODE_VECTOR, MODE_GRAPH]

RAGAS_METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)

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


@dataclass
class RagasJudge:
    """RAGAS judge LLM + embeddings with dedicated async OpenAI clients."""

    judge_model: str
    embedding_model: str
    llm: Any
    embeddings: Any
    metrics: dict[str, Any]
    llm_client: Any
    embedding_client: Any


def build_metric_timeouts(
    *,
    ragas_metric_timeout_s: float,
    answer_relevancy_timeout_s: float,
) -> dict[str, float]:
    return {
        "faithfulness": ragas_metric_timeout_s,
        "answer_relevancy": answer_relevancy_timeout_s,
        "context_precision": ragas_metric_timeout_s,
        "context_recall": ragas_metric_timeout_s,
    }


def build_ragas_judge() -> RagasJudge:
    """Construct RAGAS 0.4 judge LLM and embeddings with separate async clients."""
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    judge_model = os.getenv("RAGAS_JUDGE_MODEL", DEFAULT_RAGAS_JUDGE_MODEL)
    embedding_model = os.getenv(
        "RAGAS_JUDGE_EMBEDDING_MODEL",
        DEFAULT_RAGAS_JUDGE_EMBEDDING_MODEL,
    )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for RAGAS evaluation.")

    llm_client = AsyncOpenAI(api_key=api_key)
    embedding_client = AsyncOpenAI(api_key=api_key)

    ragas_llm = llm_factory(judge_model, client=llm_client)
    ragas_embeddings = embedding_factory(
        provider="openai",
        model=embedding_model,
        client=embedding_client,
        interface="modern",
    )

    return RagasJudge(
        judge_model=judge_model,
        embedding_model=embedding_model,
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        metrics={
            "faithfulness": Faithfulness(llm=ragas_llm),
            "answer_relevancy": AnswerRelevancy(
                llm=ragas_llm,
                embeddings=ragas_embeddings,
            ),
            "context_precision": ContextPrecisionWithReference(llm=ragas_llm),
            "context_recall": ContextRecall(llm=ragas_llm),
        },
        llm_client=llm_client,
        embedding_client=embedding_client,
    )


async def close_ragas_judge(judge: RagasJudge) -> None:
    """Close async OpenAI clients before tearing down the event loop."""
    for client in (judge.llm_client, judge.embedding_client):
        close = getattr(client, "close", None)
        if close is None:
            continue
        result = close()
        if asyncio.iscoroutine(result):
            await result


class RagasScoringSession:
    """Reuse one event loop and judge clients for all questions in a mode run."""

    def __init__(self, metric_timeouts: dict[str, float]):
        self.metric_timeouts = metric_timeouts
        self.judge = build_ragas_judge()
        self._loop = asyncio.new_event_loop()

    def score(
        self,
        item: GoldenItem,
        run: QuestionRun,
    ) -> tuple[dict[str, Optional[float]], list[str]]:
        return self._loop.run_until_complete(
            _score_ragas_metrics_async(
                item,
                run,
                self.judge,
                metric_timeouts=self.metric_timeouts,
            )
        )

    def close(self) -> None:
        try:
            self._loop.run_until_complete(close_ragas_judge(self.judge))
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        finally:
            self._loop.close()


def _build_ragas_metrics() -> dict[str, Any]:
    """Backward-compatible accessor used by older tests."""
    return build_ragas_judge().metrics


async def _preflight_ragas_judge_async(
    judge: RagasJudge,
    *,
    embed_timeout_s: float,
    llm_timeout_s: float,
    answer_relevancy_timeout_s: float,
) -> None:
    try:
        vector = await asyncio.wait_for(
            judge.embeddings.aembed_text("ragas preflight"),
            timeout=embed_timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"RAGAS judge embeddings preflight timed out after {embed_timeout_s:.0f}s "
            f"(model={judge.embedding_model}). Check OPENAI_API_KEY and embedding access."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"RAGAS judge embeddings preflight failed (model={judge.embedding_model}): {exc}"
        ) from exc

    if not vector:
        raise RuntimeError(
            f"RAGAS judge embeddings returned an empty vector on preflight "
            f"(model={judge.embedding_model})."
        )

    try:
        batch = await asyncio.wait_for(
            judge.embeddings.aembed_texts(["ragas preflight one", "ragas preflight two"]),
            timeout=embed_timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"RAGAS judge batch embeddings preflight timed out after {embed_timeout_s:.0f}s "
            f"(model={judge.embedding_model})."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"RAGAS judge batch embeddings preflight failed (model={judge.embedding_model}): {exc}"
        ) from exc

    if len(batch) != 2:
        raise RuntimeError(
            f"RAGAS judge batch embeddings preflight returned {len(batch)} vectors, expected 2."
        )

    try:
        await asyncio.wait_for(
            judge.metrics["faithfulness"].ascore(
                user_input="What is 2+2?",
                response="4",
                retrieved_contexts=["2+2 equals 4"],
            ),
            timeout=llm_timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"RAGAS judge LLM preflight timed out after {llm_timeout_s:.0f}s "
            f"(model={judge.judge_model})."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"RAGAS judge LLM preflight failed (model={judge.judge_model}): {exc}"
        ) from exc

    try:
        preflight_relevancy = judge.metrics["answer_relevancy"].__class__(
            llm=judge.llm,
            embeddings=judge.embeddings,
            strictness=1,
        )
        relevancy = await asyncio.wait_for(
            preflight_relevancy.ascore(
                user_input="What is 2+2?",
                response="The answer is 4.",
            ),
            timeout=answer_relevancy_timeout_s,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"RAGAS answer_relevancy preflight timed out after {answer_relevancy_timeout_s:.0f}s "
            f"(judge={judge.judge_model}, embeddings={judge.embedding_model}). "
            "answer_relevancy needs both LLM and embedding calls; increase "
            "--ragas-answer-relevancy-timeout if needed."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"RAGAS answer_relevancy preflight failed "
            f"(judge={judge.judge_model}, embeddings={judge.embedding_model}): {exc}"
        ) from exc

    if relevancy.value is None:
        raise RuntimeError("RAGAS answer_relevancy preflight returned no score.")


def preflight_ragas_judge(
    *,
    embed_timeout_s: float = DEFAULT_PREFLIGHT_EMBED_TIMEOUT_S,
    llm_timeout_s: float = DEFAULT_PREFLIGHT_LLM_TIMEOUT_S,
    answer_relevancy_timeout_s: float = DEFAULT_PREFLIGHT_ANSWER_RELEVANCY_TIMEOUT_S,
) -> None:
    """Verify judge embeddings and LLM before scoring questions."""
    judge = build_ragas_judge()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _preflight_ragas_judge_async(
                judge,
                embed_timeout_s=embed_timeout_s,
                llm_timeout_s=llm_timeout_s,
                answer_relevancy_timeout_s=answer_relevancy_timeout_s,
            )
        )
        loop.run_until_complete(close_ragas_judge(judge))
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()


def mode_results_path(reports_dir: Path, mode: str) -> Path:
    """Path to the incremental per-mode JSONL results file."""
    return reports_dir / f"{mode}_results.jsonl"


def load_mode_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def completed_question_ids(path: Path) -> set[str]:
    return {record["id"] for record in load_mode_results(path)}


def append_mode_result(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


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
    from vector_index import ingest_project

    from eval.sample_project import ensure_sample_project

    ensure_sample_project(project_root)
    files = sorted(str(path) for path in project_root.glob("*.py"))

    ingest_project(project_id, files, vector_store=vector_store, chunker=chunk_file)
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


def _empty_agent_result() -> Any:
    from agent import AgentRunResult

    return AgentRunResult(
        answer="",
        sources=[],
        tool_trace=[],
        tokens=None,
        contexts=[],
    )


def run_agent_with_timeout(
    agent: Any,
    question: str,
    *,
    timeout_s: float,
    thread_id: str,
    project_id: str,
    endpoint: str,
    retrieval_strategy: str,
    run_agent_fn: Optional[Callable[..., Any]] = None,
) -> tuple[Any, Optional[str]]:
    from agent import run_agent

    invoke = run_agent_fn or run_agent
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            invoke,
            agent,
            question,
            thread_id=thread_id,
            project_id=project_id,
            endpoint=endpoint,
            retrieval_strategy=retrieval_strategy,
        )
        try:
            return future.result(timeout=timeout_s), None
        except FuturesTimeoutError:
            return _empty_agent_result(), f"agent timeout after {timeout_s:.0f}s"
        except Exception as exc:
            return _empty_agent_result(), f"agent error: {exc}"


async def _score_ragas_metrics_async(
    item: GoldenItem,
    run: QuestionRun,
    judge: RagasJudge,
    *,
    metric_timeouts: dict[str, float],
) -> tuple[dict[str, Optional[float]], list[str]]:
    scores: dict[str, Optional[float]] = {key: None for key in RAGAS_METRIC_KEYS}
    errors: list[str] = []
    contexts = run.contexts or ["(no retrieved context)"]
    answer = run.answer or ""

    metric_calls: list[tuple[str, Any]] = [
        (
            "faithfulness",
            judge.metrics["faithfulness"].ascore(
                user_input=item.question,
                response=answer,
                retrieved_contexts=contexts,
            ),
        ),
        (
            "answer_relevancy",
            judge.metrics["answer_relevancy"].ascore(
                user_input=item.question,
                response=answer,
            ),
        ),
        (
            "context_precision",
            judge.metrics["context_precision"].ascore(
                user_input=item.question,
                reference=item.expected_answer,
                retrieved_contexts=contexts,
            ),
        ),
        (
            "context_recall",
            judge.metrics["context_recall"].ascore(
                user_input=item.question,
                retrieved_contexts=contexts,
                reference=item.expected_answer,
            ),
        ),
    ]

    for name, coro in metric_calls:
        timeout_s = metric_timeouts.get(name, DEFAULT_RAGAS_METRIC_TIMEOUT_S)
        task = asyncio.create_task(coro)
        try:
            result = await asyncio.wait_for(task, timeout=timeout_s)
            scores[name] = float(result.value)
        except asyncio.TimeoutError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            errors.append(f"{name}: timeout after {timeout_s:.0f}s")
        except Exception as exc:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            errors.append(f"{name}: {exc}")

    return scores, errors


def score_ragas_for_item(
    item: GoldenItem,
    run: QuestionRun,
    *,
    metric_timeouts: dict[str, float],
    judge: Optional[RagasJudge] = None,
) -> tuple[dict[str, Optional[float]], list[str]]:
    if judge is not None:
        return asyncio.run(
            _score_ragas_metrics_async(
                item,
                run,
                judge,
                metric_timeouts=metric_timeouts,
            )
        )
    session = RagasScoringSession(metric_timeouts)
    try:
        return session.score(item, run)
    finally:
        session.close()


def record_from_run(
    item: GoldenItem,
    run: QuestionRun,
    *,
    ragas: dict[str, Optional[float]],
    error: Optional[str],
) -> dict[str, Any]:
    return {
        "id": item.id,
        "category": item.category,
        "question": item.question,
        "expected_answer": item.expected_answer,
        "answer": run.answer,
        "contexts": run.contexts,
        "sources": run.sources,
        "tool_trace": run.tool_trace,
        "latency_ms": run.latency_ms,
        "tokens": run.tokens,
        "ragas": ragas,
        "error": error,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


def record_to_question_run(record: dict[str, Any]) -> QuestionRun:
    return QuestionRun(
        id=record["id"],
        question=record.get("question", ""),
        answer=record.get("answer", ""),
        contexts=record.get("contexts") or [],
        sources=record.get("sources") or [],
        tool_trace=record.get("tool_trace") or [],
        latency_ms=float(record.get("latency_ms") or 0.0),
        tokens=record.get("tokens"),
    )


def format_progress_line(
    mode: str,
    index: int,
    total: int,
    item_id: str,
    record: dict[str, Any],
) -> str:
    label = MODE_LABELS[mode]
    prefix = f"[{label}] question {index}/{total}: {item_id} ->"
    if record.get("error"):
        return f"{prefix} ERROR: {record['error']}"
    faith = (record.get("ragas") or {}).get("faithfulness")
    if faith is None:
        return f"{prefix} faithfulness=nan"
    return f"{prefix} faithfulness={faith:.3f}"


def average_ragas(records: list[dict[str, Any]]) -> dict[str, float]:
    averages: dict[str, float] = {}
    for key in RAGAS_METRIC_KEYS:
        values = [
            float(record["ragas"][key])
            for record in records
            if record.get("ragas", {}).get(key) is not None
        ]
        averages[key] = sum(values) / len(values) if values else float("nan")
    return averages


def aggregate_mode_payload(mode: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [record_to_question_run(record) for record in records]
    return {
        "label": MODE_LABELS[mode],
        "ragas": average_ragas(records),
        "operational": summarize_operational(runs),
        "runs": [
            {
                "id": record["id"],
                "question": record.get("question", ""),
                "answer": record.get("answer", ""),
                "sources": record.get("sources") or [],
                "tool_trace": record.get("tool_trace") or [],
                "latency_ms": record.get("latency_ms"),
                "tokens": record.get("tokens"),
                "ragas": record.get("ragas") or {},
                "error": record.get("error"),
            }
            for record in records
        ],
    }


def run_mode(
    mode: str,
    items: list[GoldenItem],
    *,
    reports_dir: Path,
    project_root: Path,
    project_id: str,
    vector_store,
    graph_store: NetworkXGraphStore,
    agent_timeout_s: float = DEFAULT_AGENT_TIMEOUT_S,
    ragas_metric_timeout_s: float = DEFAULT_RAGAS_METRIC_TIMEOUT_S,
    ragas_answer_relevancy_timeout_s: float = DEFAULT_RAGAS_ANSWER_RELEVANCY_TIMEOUT_S,
    run_agent_fn: Optional[Callable[..., Any]] = None,
    score_ragas_fn: Optional[Callable[..., tuple[dict[str, Optional[float]], list[str]]]] = None,
) -> list[dict[str, Any]]:
    """Evaluate one mode with incremental writes, resume, and per-question isolation."""
    from agent import build_agent

    results_path = mode_results_path(reports_dir, mode)
    done_ids = completed_question_ids(results_path)
    if done_ids:
        print(
            f"Resuming {MODE_LABELS[mode]}: skipping {len(done_ids)} completed question(s).",
            flush=True,
        )

    agent = build_agent(
        project_root,
        project_id,
        vector_store=vector_store,
        graph_store=graph_store,
        tools=tools_for_mode(mode, project_root, project_id, vector_store=vector_store, graph_store=graph_store),
        system_prompt=MODE_SYSTEM_PROMPTS[mode],
    )

    strategy = retrieval_strategy_for_mode(mode)
    metric_timeouts = build_metric_timeouts(
        ragas_metric_timeout_s=ragas_metric_timeout_s,
        answer_relevancy_timeout_s=ragas_answer_relevancy_timeout_s,
    )
    score_one = score_ragas_fn
    ragas_session: Optional[RagasScoringSession] = None
    if score_one is None:
        ragas_session = RagasScoringSession(metric_timeouts)
    total = len(items)

    try:
        for index, item in enumerate(items, start=1):
            if item.id in done_ids:
                continue

            started = time.perf_counter()
            result, agent_error = run_agent_with_timeout(
                agent,
                item.question,
                timeout_s=agent_timeout_s,
                thread_id=f"eval-{mode}-{item.id}",
                project_id=project_id,
                endpoint=f"eval/{mode}",
                retrieval_strategy=strategy,
                run_agent_fn=run_agent_fn,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            run = QuestionRun(
                id=item.id,
                question=item.question,
                answer=result.answer,
                contexts=result.contexts,
                sources=result.sources,
                tool_trace=result.tool_trace,
                latency_ms=latency_ms,
                tokens=result.tokens,
            )

            ragas_scores: dict[str, Optional[float]] = {key: None for key in RAGAS_METRIC_KEYS}
            metric_errors: list[str] = []
            if agent_error is None:
                try:
                    if ragas_session is not None:
                        ragas_scores, metric_errors = ragas_session.score(item, run)
                    else:
                        ragas_scores, metric_errors = score_one(
                            item,
                            run,
                            metric_timeouts=metric_timeouts,
                        )
                except Exception as exc:
                    metric_errors.append(f"ragas scoring error: {exc}")

            errors = [agent_error] if agent_error else []
            errors.extend(metric_errors)
            error = "; ".join(error for error in errors if error) or None

            record = record_from_run(item, run, ragas=ragas_scores, error=error)
            append_mode_result(results_path, record)
            print(format_progress_line(mode, index, total, item.id, record), flush=True)
    finally:
        if ragas_session is not None:
            ragas_session.close()

    return load_mode_results(results_path)


def ragas_metrics_for_runs(
    items: list[GoldenItem],
    runs: list[QuestionRun],
) -> dict[str, float]:
    """Aggregate RAGAS metrics from in-memory runs (legacy helper for tests)."""
    records = [
        record_from_run(
            item,
            run,
            ragas={key: 0.0 for key in RAGAS_METRIC_KEYS},
            error=None,
        )
        for item, run in zip(items, runs, strict=False)
    ]
    for record in records:
        run = next(run for run in runs if run.id == record["id"])
        item = next(item for item in items if item.id == record["id"])
        scores, errors = score_ragas_for_item(
            item,
            run,
            metric_timeouts=build_metric_timeouts(
                ragas_metric_timeout_s=DEFAULT_RAGAS_METRIC_TIMEOUT_S,
                answer_relevancy_timeout_s=DEFAULT_RAGAS_ANSWER_RELEVANCY_TIMEOUT_S,
            ),
        )
        record["ragas"] = scores
        record["error"] = "; ".join(errors) if errors else None
    return average_ragas(records)


def summarize_operational(runs: list[QuestionRun]) -> dict[str, float]:
    if not runs:
        return {
            "latency_ms_avg": 0.0,
            "prompt_tokens_avg": 0.0,
            "completion_tokens_avg": 0.0,
            "total_tokens_avg": 0.0,
        }

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
    if isinstance(value, float) and math.isnan(value):
        return "nan"
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
            if value is None or (isinstance(value, float) and math.isnan(value)) or value < min_faithfulness:
                failures.append(
                    f"{label}: faithfulness {value} < threshold {min_faithfulness}"
                )
        if min_context_precision is not None:
            value = ragas.get("context_precision")
            if value is None or (isinstance(value, float) and math.isnan(value)) or value < min_context_precision:
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
        "--agent-timeout",
        type=float,
        default=DEFAULT_AGENT_TIMEOUT_S,
        help="Per-question agent timeout in seconds.",
    )
    parser.add_argument(
        "--ragas-metric-timeout",
        type=float,
        default=DEFAULT_RAGAS_METRIC_TIMEOUT_S,
        help="Per-metric RAGAS timeout in seconds for LLM metrics (default 120s).",
    )
    parser.add_argument(
        "--ragas-answer-relevancy-timeout",
        type=float,
        default=DEFAULT_RAGAS_ANSWER_RELEVANCY_TIMEOUT_S,
        help="Timeout for answer_relevancy (uses LLM + embeddings; default 180s).",
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

    judge_model = os.getenv("RAGAS_JUDGE_MODEL", DEFAULT_RAGAS_JUDGE_MODEL)
    agent_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    print(
        f"Evaluating {len(items)} questions × {len(args.modes)} modes "
        f"(agent={agent_model}, ragas_judge={judge_model}, "
        f"agent_timeout={args.agent_timeout:.0f}s, "
        f"ragas_metric_timeout={args.ragas_metric_timeout:.0f}s, "
        f"ragas_answer_relevancy_timeout={args.ragas_answer_relevancy_timeout:.0f}s)",
        flush=True,
    )

    print("Preflight: checking RAGAS judge LLM and embeddings...", flush=True)
    try:
        preflight_ragas_judge()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("Preflight OK.", flush=True)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    mode_results: dict[str, dict[str, Any]] = {}
    for mode in args.modes:
        print(f"Running mode: {MODE_LABELS[mode]} ({len(items)} questions)...", flush=True)
        records = run_mode(
            mode,
            items,
            reports_dir=args.reports_dir,
            project_root=project_root,
            project_id=args.project_id,
            vector_store=vector_store,
            graph_store=graph_store,
            agent_timeout_s=args.agent_timeout,
            ragas_metric_timeout_s=args.ragas_metric_timeout,
            ragas_answer_relevancy_timeout_s=args.ragas_answer_relevancy_timeout,
        )
        mode_results[mode] = aggregate_mode_payload(mode, records)
        print(
            f"Finished {MODE_LABELS[mode]}: {len(records)} result(s) in "
            f"{mode_results_path(args.reports_dir, mode)}",
            flush=True,
        )

    for mode in ALL_MODES:
        if mode not in mode_results:
            existing = load_mode_results(mode_results_path(args.reports_dir, mode))
            if existing:
                mode_results[mode] = aggregate_mode_payload(mode, existing)
            else:
                mode_results[mode] = {
                    "label": MODE_LABELS[mode],
                    "ragas": {},
                    "operational": {},
                    "runs": [],
                }

    table = build_comparison_table(mode_results)
    print("\nDocuMind retrieval comparison\n", flush=True)
    print(table, flush=True)

    report_path = write_report(
        args.reports_dir,
        table=table,
        mode_results=mode_results,
        golden_path=args.golden_set,
        project_id=args.project_id,
    )
    print(f"\nReport written to {report_path}", flush=True)

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
