"""LangGraph agent for project-bound code Q&A and artifact generation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from code_graph import CodeGraphStore, has_graph
from llm_factory import get_chat_model
from tracing import (
    RETRIEVAL_AGENT,
    apply_tracing_config,
    build_run_config,
    configure_tracing,
    wrap_tools_with_tracing,
)
from vector_index import VectorStore, is_indexed
from vector_search import create_all_tools

DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "25"))

STEP_BUDGET_MESSAGE = (
    "I couldn't complete this request within the step budget. "
    "Try a narrower question or increase the agent step limit."
)

AGENT_SYSTEM_PROMPT = """You are DocuMind, a codebase assistant with retrieval and generation tools.

Tool selection:
- Prefer grep_code, read_file, find_symbol, and get_structure for specific lookups (definitions, file contents, structure).
- Use vector_search only for fuzzy or conceptual questions where exact symbols are unknown.
- Use who_calls, what_calls, impact_of, and dependencies_of for structural questions about callers, callees, impact, and imports.

Documentation and diagrams:
- For requests to document or diagram code, FIRST retrieve the relevant source with retrieval tools (read_file, find_symbol, grep_code, or get_structure).
- THEN pass the retrieved code into generate_docstrings, generate_readme, generate_architecture_doc, generate_diagram, or generate_svg_flowchart.
- Never invent or hallucinate code to document. Only generate artifacts from code returned by tools.

Grounding:
- Answer ONLY from tool results.
- Cite sources as file:line whenever possible.
- If tools do not provide enough evidence, say "not found in the codebase" instead of guessing.
"""


@dataclass(frozen=True)
class AgentRunResult:
    """Structured agent response."""

    answer: str
    sources: list[str]
    tool_trace: list[dict[str, Any]]
    tokens: Optional[dict[str, int]]
    contexts: list[str]


def resolve_project_root(project_id: str) -> Path:
    """Resolve a project_id to an on-disk project directory."""
    from project_indexing import resolve_project_folder

    return resolve_project_folder(project_id)


def is_project_ready(
    project_id: str,
    *,
    vector_store: Optional[VectorStore] = None,
    graph_store: Optional[CodeGraphStore] = None,
) -> bool:
    """Return True when both vector index and code graph exist for the project."""
    return is_indexed(project_id, vector_store=vector_store) and has_graph(
        project_id,
        graph_store=graph_store,
    )


def build_agent(
    project_root: str | Path,
    project_id: str,
    *,
    llm: Optional[BaseChatModel] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    vector_store: Optional[VectorStore] = None,
    graph_store: Optional[CodeGraphStore] = None,
    tools: Optional[list[Any]] = None,
    system_prompt: Optional[str] = None,
) -> CompiledStateGraph:
    """Build a LangGraph ReAct agent bound to a project."""
    if tools is None:
        tools = create_all_tools(
            str(project_root),
            project_id,
            vector_store=vector_store,
            graph_store=graph_store,
        )
    tools = wrap_tools_with_tracing(
        tools,
        project_id=project_id,
        endpoint="agent.tools",
    )
    model = llm or get_chat_model()
    model = apply_tracing_config(
        model,
        project_id=project_id,
        endpoint="agent.model",
        retrieval_strategy=RETRIEVAL_AGENT,
    )
    memory = checkpointer or MemorySaver()

    return create_agent(
        model,
        tools=tools,
        system_prompt=system_prompt or AGENT_SYSTEM_PROMPT,
        checkpointer=memory,
    )


@lru_cache(maxsize=32)
def _cached_agent(project_root: str, project_id: str) -> CompiledStateGraph:
    return build_agent(project_root, project_id)


def get_agent(project_root: str | Path, project_id: str) -> CompiledStateGraph:
    """Return a cached compiled agent for a project."""
    return _cached_agent(str(Path(project_root).resolve()), project_id)


def run_agent(
    agent: CompiledStateGraph,
    message: str,
    *,
    thread_id: str = "default",
    recursion_limit: Optional[int] = None,
    project_id: Optional[str] = None,
    endpoint: str = "agent.run",
    retrieval_strategy: str = RETRIEVAL_AGENT,
) -> AgentRunResult:
    """Invoke the agent and return a structured response."""
    configure_tracing()
    limit = recursion_limit or DEFAULT_RECURSION_LIMIT
    config = build_run_config(
        thread_id=thread_id,
        project_id=project_id,
        endpoint=endpoint,
        retrieval_strategy=retrieval_strategy,
        recursion_limit=limit,
        extra_metadata={"message_preview": message[:200]},
    )

    try:
        state = agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )
    except GraphRecursionError:
        return AgentRunResult(
            answer=STEP_BUDGET_MESSAGE,
            sources=[],
            tool_trace=[],
            tokens=None,
            contexts=[],
        )

    messages: Sequence[BaseMessage] = state.get("messages", [])
    answer = _final_answer(messages)
    return AgentRunResult(
        answer=answer,
        sources=_collect_sources(messages),
        tool_trace=_collect_tool_trace(messages),
        tokens=_collect_token_usage(messages),
        contexts=_collect_contexts(messages),
    )


def _final_answer(messages: Sequence[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                return "".join(text_parts)
    return ""


def _collect_tool_trace(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            trace.append(
                {
                    "tool": tool_call.get("name"),
                    "args": tool_call.get("args", {}),
                    "tool_call_id": tool_call.get("id"),
                }
            )
    return trace


def _collect_contexts(messages: Sequence[BaseMessage]) -> list[str]:
    contexts: list[str] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content.strip():
            contexts.append(content)
    return contexts


def _collect_sources(messages: Sequence[BaseMessage]) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []

    def add_source(file_path: Any, line: Any) -> None:
        if not file_path or line is None:
            return
        try:
            line_no = int(line)
        except (TypeError, ValueError):
            return
        label = f"{file_path}:{line_no}"
        if label not in seen:
            seen.add(label)
            sources.append(label)

    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            for match in re.finditer(
                r'"(?:file|file_path)"\s*:\s*"([^"]+)"[^}\]]*"(?:line|start_line)"\s*:\s*(\d+)',
                content,
            ):
                add_source(match.group(1), match.group(2))
            continue
        _walk_payload_for_sources(payload, add_source)

    return sources


def _walk_payload_for_sources(payload: Any, add_source) -> None:
    if isinstance(payload, list):
        for item in payload:
            _walk_payload_for_sources(item, add_source)
        return

    if not isinstance(payload, dict):
        return

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        add_source(
            metadata.get("file_path") or metadata.get("file"),
            metadata.get("start_line") or metadata.get("line"),
        )

    file_path = payload.get("file") or payload.get("file_path")
    line = payload.get("line") or payload.get("start_line")
    if file_path is not None:
        add_source(file_path, line)

    for nested_key in ("caller", "callee", "file", "module"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            _walk_payload_for_sources(nested, add_source)


def _collect_token_usage(messages: Sequence[BaseMessage]) -> Optional[dict[str, int]]:
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    found = False

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        usage = _usage_from_message(msg)
        if not usage:
            continue
        found = True
        for key in totals:
            totals[key] += int(usage.get(key, 0) or 0)

    return totals if found else None


def _usage_from_message(msg: AIMessage) -> Optional[dict[str, int]]:
    usage_metadata = msg.usage_metadata
    if usage_metadata:
        prompt = usage_metadata.get("input_tokens", usage_metadata.get("prompt_tokens", 0))
        completion = usage_metadata.get(
            "output_tokens",
            usage_metadata.get("completion_tokens", 0),
        )
        total = usage_metadata.get("total_tokens")
        if total is None:
            total = int(prompt or 0) + int(completion or 0)
        return {
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "total_tokens": int(total or 0),
        }

    token_usage = (msg.response_metadata or {}).get("token_usage")
    if isinstance(token_usage, dict):
        return {
            "prompt_tokens": int(token_usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(token_usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(token_usage.get("total_tokens", 0) or 0),
        }

    return None
