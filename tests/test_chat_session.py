"""Tests for durable chat session helpers."""

from __future__ import annotations

from unittest.mock import patch

from bson import ObjectId

import chat_session


def test_messages_for_model_limits_and_filters():
    chat_doc = {
        "messages": [
            {"role": "user", "content": "u1"},
            {"role": "tool", "content": "skip"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
    }
    assert chat_session.messages_for_model(chat_doc, limit=2) == [
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]


def test_load_or_create_session_noop_without_mongo(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    assert chat_session.load_or_create_session("507f1f77bcf86cd799439011") is None


def test_persist_turn_appends_user_and_assistant(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/documind")
    chat_id = ObjectId()
    chat_doc = {"_id": chat_id, "messages": []}

    with patch("chat_session.models.append_chat_messages") as append:
        result = chat_session.persist_turn(
            chat_doc,
            user_content="q",
            assistant_content="a",
            tool_trace=[{"tool": "grep_code"}],
            citations=[{"file": "a.py", "line": 1}],
        )

    assert result == str(chat_id)
    append.assert_called_once()
    args = append.call_args.args
    assert args[0] == chat_id
    assert args[1][0]["role"] == "user"
    assert args[1][0]["content"] == "q"
    assert args[1][1]["role"] == "assistant"
    assert args[1][1]["tool_trace"] == [{"tool": "grep_code"}]
    assert args[1][1]["citations"] == [{"file": "a.py", "line": 1}]


def test_api_chat_persists_and_resumes(client, auth_headers, monkeypatch):
    from app import CURRENT_PROJECT_FILES, _set_rag_project_files

    chat_id = ObjectId()
    store = {
        "_id": chat_id,
        "user_id": ObjectId("507f1f77bcf86cd799439011"),
        "project_id": None,
        "thread_id": "default",
        "messages": [],
    }

    def fake_load(*_a, **_k):
        return store

    def fake_persist(chat_doc, **kwargs):
        store["messages"].extend(
            [
                {
                    "role": "user",
                    "content": kwargs["user_content"],
                    "tool_trace": None,
                    "citations": None,
                },
                {
                    "role": "assistant",
                    "content": kwargs["assistant_content"],
                    "tool_trace": kwargs.get("tool_trace"),
                    "citations": kwargs.get("citations"),
                },
            ]
        )
        return str(chat_id)

    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/documind")
    monkeypatch.setattr(
        "app.answer_question",
        lambda question, chunks, history: f"hist={len(history)}::{question}",
    )
    monkeypatch.setattr(
        "app.rag_engine.retrieve",
        lambda question, top_k=5: [
            {
                "file": "demo.py",
                "start_line": 1,
                "end_line": 2,
                "content": "def add(a, b):\n    return a + b\n",
            }
        ],
    )

    import chat_session as cs_mod

    monkeypatch.setattr(cs_mod, "load_or_create_session", fake_load)
    monkeypatch.setattr(cs_mod, "persist_turn", fake_persist)

    _set_rag_project_files(
        [{"path": "demo.py", "content": "def add(a, b):\n    return a + b\n"}]
    )

    first = client.post(
        "/api/chat",
        json={"question": "What is add?"},
        headers=auth_headers,
    )
    assert first.status_code == 200, first.get_json()
    first_data = first.get_json()
    assert first_data["chat_id"] == str(chat_id)
    assert first_data["answer"].startswith("hist=0::")
    assert len(store["messages"]) == 2

    second = client.post(
        "/api/chat",
        json={"question": "and subtract?", "chat_id": str(chat_id)},
        headers=auth_headers,
    )
    assert second.status_code == 200, second.get_json()
    second_data = second.get_json()
    assert second_data["answer"].startswith("hist=2::")
    assert len(store["messages"]) == 4

    _set_rag_project_files([])
    assert CURRENT_PROJECT_FILES == []
