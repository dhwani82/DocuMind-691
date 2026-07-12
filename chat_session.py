"""Persist and resume chat turns in MongoDB for /api/chat and /api/agent."""

from __future__ import annotations

import os
from typing import Any, Optional

import models

DEFAULT_CONTEXT_LIMIT = 12


def mongo_persistence_enabled() -> bool:
    return bool((os.getenv("MONGODB_URI") or "").strip())


def messages_for_model(
    chat_doc: Optional[dict[str, Any]],
    *,
    limit: int = DEFAULT_CONTEXT_LIMIT,
) -> list[dict[str, str]]:
    """Return recent ``{role, content}`` pairs for LLM context."""
    if not chat_doc:
        return []
    raw = list(chat_doc.get("messages") or [])
    if limit > 0:
        raw = raw[-limit:]
    out: list[dict[str, str]] = []
    for item in raw:
        role = str(item.get("role") or "").strip()
        if role not in {"user", "assistant", "system"}:
            continue
        out.append({"role": role, "content": str(item.get("content") or "")})
    return out


def load_or_create_session(
    user_id: Any,
    *,
    project_id: Any = None,
    thread_id: str = "default",
    chat_id: Any = None,
) -> Optional[dict[str, Any]]:
    """Load/create a chat_history doc, or ``None`` when Mongo is not configured."""
    if not mongo_persistence_enabled():
        return None
    return models.get_or_create_chat_history(
        user_id,
        project_id=project_id,
        thread_id=thread_id,
        chat_id=chat_id,
    )


def persist_turn(
    chat_doc: Optional[dict[str, Any]],
    *,
    user_content: str,
    assistant_content: str,
    tool_trace: Any = None,
    citations: Any = None,
) -> Optional[str]:
    """Append user + assistant messages after a turn. Returns chat_id or None."""
    if not chat_doc or not mongo_persistence_enabled():
        return None
    chat_id = chat_doc["_id"]
    models.append_chat_messages(
        chat_id,
        [
            {
                "role": "user",
                "content": user_content,
                "tool_trace": None,
                "citations": None,
            },
            {
                "role": "assistant",
                "content": assistant_content,
                "tool_trace": tool_trace,
                "citations": citations,
            },
        ],
    )
    return str(chat_id)
