"""Tests for the LangGraph DocuMind agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver

from agent import (
    STEP_BUDGET_MESSAGE,
    AgentRunResult,
    build_agent,
    is_project_ready,
    run_agent,
)
from chunking import ChunkConfig, chunk_file
from code_graph import NetworkXGraphStore, build_graph
from tests.sample_code_for_testing import SAMPLE_MIXED
from vector_index import ChromaVectorStore, ingest_project


class DummyEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class ScriptedChatModel(BaseChatModel):
    """Deterministic chat model for agent tests."""

    responses: list[AIMessage]
    call_count: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        index = min(self.call_count, len(self.responses) - 1)
        message = self.responses[index]
        self.call_count += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "scripted"


class LoopingToolChatModel(BaseChatModel):
    """Always requests the same tool call to trigger the recursion limit."""

    tool_name: str
    tool_args: dict
    call_count: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": self.tool_name,
                    "args": self.tool_args,
                    "id": f"loop-{self.call_count}",
                    "type": "tool_call",
                }
            ],
        )
        self.call_count += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "looping-tool"


@pytest.fixture
def graph_store(tmp_path: Path) -> NetworkXGraphStore:
    return NetworkXGraphStore(persist_dir=tmp_path / "graphs")


@pytest.fixture
def vector_store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(
        persist_dir=tmp_path / "chroma",
        embedding_model=DummyEmbeddings(),
    )


@pytest.fixture
def indexed_project(tmp_path: Path, vector_store: ChromaVectorStore, graph_store: NetworkXGraphStore) -> tuple[Path, str]:
    project = tmp_path / "sample_project"
    project.mkdir()
    mixed_path = project / "mixed.py"
    mixed_path.write_text(SAMPLE_MIXED.strip() + "\n", encoding="utf-8")

    project_id = str(project.resolve())
    chunk_config = ChunkConfig(chunk_lines=8, chunk_lines_overlap=1, max_chars=100)
    ingest_project(
        project_id,
        [str(mixed_path)],
        vector_store=vector_store,
        chunker=lambda _file_path: chunk_file(mixed_path, config=chunk_config),
    )
    build_graph(project_id, [str(mixed_path)], graph_store=graph_store)
    assert is_project_ready(project_id, vector_store=vector_store, graph_store=graph_store)
    return project, project_id


def _build_scripted_agent(
    project: Path,
    project_id: str,
    responses: list[AIMessage],
    *,
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    return build_agent(
        project,
        project_id,
        llm=ScriptedChatModel(responses=responses),
        checkpointer=MemorySaver(),
        vector_store=vector_store,
        graph_store=graph_store,
    )


def test_structural_question_invokes_graph_tool(
    indexed_project: tuple[Path, str],
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    project, project_id = indexed_project
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "who_calls",
                    "args": {"symbol": "load_config"},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="middle calls load_config per graph results."),
    ]
    agent = _build_scripted_agent(
        project,
        project_id,
        responses,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    result = run_agent(agent, "What calls load_config?")

    assert result.tool_trace
    assert result.tool_trace[0]["tool"] == "who_calls"
    assert "load_config" in result.answer


def test_specific_lookup_uses_find_symbol_not_vector_search(
    indexed_project: tuple[Path, str],
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    project, project_id = indexed_project
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "find_symbol",
                    "args": {"name": "DataProcessor"},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="DataProcessor is defined in mixed.py:11."),
    ]
    agent = _build_scripted_agent(
        project,
        project_id,
        responses,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    result = run_agent(agent, "Where is DataProcessor defined?")

    tool_names = [entry["tool"] for entry in result.tool_trace]
    assert "find_symbol" in tool_names
    assert "vector_search" not in tool_names


def test_document_request_retrieves_before_generation(
    indexed_project: tuple[Path, str],
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    project, project_id = indexed_project
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_file",
                    "args": {"file_path": "mixed.py"},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "generate_docstrings",
                    "args": {"code": "def load_config(path):\n    pass"},
                    "id": "2",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Generated docstrings for load_config."),
    ]
    agent = _build_scripted_agent(
        project,
        project_id,
        responses,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    result = run_agent(agent, "Document the load_config function.")

    tool_names = [entry["tool"] for entry in result.tool_trace]
    assert tool_names.index("read_file") < tool_names.index("generate_docstrings")


def test_unanswerable_question_refuses_without_guessing(
    indexed_project: tuple[Path, str],
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    project, project_id = indexed_project
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "grep_code",
                    "args": {"pattern": "TotallyMissingSymbolXYZ"},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="not found in the codebase"),
    ]
    agent = _build_scripted_agent(
        project,
        project_id,
        responses,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    result = run_agent(agent, "Where is TotallyMissingSymbolXYZ defined?")

    assert "grep_code" in [entry["tool"] for entry in result.tool_trace]
    assert "not found in the codebase" in result.answer.lower()


def test_step_limit_returns_graceful_message(
    indexed_project: tuple[Path, str],
    vector_store: ChromaVectorStore,
    graph_store: NetworkXGraphStore,
):
    project, project_id = indexed_project
    agent = build_agent(
        project,
        project_id,
        llm=LoopingToolChatModel(tool_name="grep_code", tool_args={"pattern": "x"}),
        checkpointer=MemorySaver(),
        vector_store=vector_store,
        graph_store=graph_store,
    )

    result = run_agent(agent, "Keep searching forever.", recursion_limit=4)

    assert result.answer == STEP_BUDGET_MESSAGE
    assert result.tool_trace == []


def test_agent_api_requires_indexed_project(tmp_path: Path, monkeypatch):
    from app import app as flask_app

    ready = tmp_path / "ready"
    ready.mkdir()
    unindexed = tmp_path / "unindexed"
    unindexed.mkdir()

    def fake_resolve(project_id: str) -> Path:
        path = Path(project_id).expanduser().resolve()
        if path.is_dir():
            return path
        raise ValueError(f"Project directory not found for project_id '{project_id}'")

    def fake_ready(project_id: str, **kwargs) -> bool:
        return Path(project_id).expanduser().resolve() == ready.resolve()

    monkeypatch.setattr("agent.resolve_project_root", fake_resolve)
    monkeypatch.setattr("agent.is_project_ready", fake_ready)
    monkeypatch.setattr("agent.get_agent", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "agent.run_agent",
        lambda *_args, **_kwargs: AgentRunResult(
            answer="ok",
            sources=[],
            tool_trace=[],
            tokens=None,
            contexts=[],
        ),
    )

    client = flask_app.test_client()
    ready_response = client.post(
        "/api/agent",
        json={
            "project_id": str(ready),
            "message": "hello",
            "thread_id": "t1",
        },
    )
    assert ready_response.status_code == 200
    assert ready_response.get_json()["answer"] == "ok"

    missing_response = client.post(
        "/api/agent",
        json={
            "project_id": str(tmp_path / "missing"),
            "message": "hello",
        },
    )
    assert missing_response.status_code == 404

    unindexed_response = client.post(
        "/api/agent",
        json={
            "project_id": str(unindexed),
            "message": "hello",
        },
    )
    assert unindexed_response.status_code == 409
