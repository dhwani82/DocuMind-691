"""Thin MongoDB collection helpers for DocuMind persistence.

Collections (no ORM — plain PyMongo dicts):

- ``users``: email, hashed_password, created_at
- ``projects``: owner_id, name, source_type, source_ref, index_status,
  vector_store, created_at
- ``chat_history``: user_id, project_id (nullable), messages
  (list of {role, content, tool_trace, citations, timestamp})
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult

from db import get_db

USERS_COLLECTION = "users"
PROJECTS_COLLECTION = "projects"
CHAT_HISTORY_COLLECTION = "chat_history"

DEFAULT_INDEX_STATUS = "pending"
DEFAULT_VECTOR_STORE = "chroma"

INDEX_STATUS_PENDING = "pending"
INDEX_STATUS_INDEXING = "indexing"
INDEX_STATUS_READY = "ready"
INDEX_STATUS_FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))


def _is_object_id_string(value: str) -> bool:
    return len(value) == 24 and ObjectId.is_valid(value)


def _project_ref(project_id: Any) -> Any:
    """Store Mongo ObjectIds as ObjectId; filesystem paths / keys as strings; else None."""
    if project_id is None:
        return None
    if isinstance(project_id, ObjectId):
        return project_id
    text = str(project_id).strip()
    if not text:
        return None
    if _is_object_id_string(text):
        return ObjectId(text)
    return text


def users_collection() -> Collection:
    return get_db()[USERS_COLLECTION]


def projects_collection() -> Collection:
    return get_db()[PROJECTS_COLLECTION]


def chat_history_collection() -> Collection:
    return get_db()[CHAT_HISTORY_COLLECTION]


# --- users -----------------------------------------------------------------


def create_user(email: str, hashed_password: str) -> dict[str, Any]:
    """Insert a user and return the stored document (including ``_id``)."""
    doc: dict[str, Any] = {
        "email": email.strip().lower(),
        "hashed_password": hashed_password,
        "created_at": _utcnow(),
    }
    result: InsertOneResult = users_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_user_by_id(user_id: Any) -> Optional[dict[str, Any]]:
    return users_collection().find_one({"_id": _as_object_id(user_id)})


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    return users_collection().find_one({"email": email.strip().lower()})


# --- projects --------------------------------------------------------------


def create_project(
    owner_id: Any,
    name: str,
    source_type: str,
    source_ref: str,
    *,
    index_status: str = DEFAULT_INDEX_STATUS,
    vector_store: str = DEFAULT_VECTOR_STORE,
) -> dict[str, Any]:
    """Insert a project owned by ``owner_id`` and return the stored document."""
    doc: dict[str, Any] = {
        "owner_id": _as_object_id(owner_id),
        "name": name.strip(),
        "source_type": source_type.strip(),
        "source_ref": source_ref,
        "index_status": index_status,
        "vector_store": vector_store,
        "created_at": _utcnow(),
    }
    result: InsertOneResult = projects_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_project_by_id(project_id: Any) -> Optional[dict[str, Any]]:
    return projects_collection().find_one({"_id": _as_object_id(project_id)})


def get_project_by_owner_and_source(
    owner_id: Any,
    source_ref: str,
) -> Optional[dict[str, Any]]:
    """Return the owner's project for a given source path/ref, if any."""
    return projects_collection().find_one(
        {
            "owner_id": _as_object_id(owner_id),
            "source_ref": source_ref,
        }
    )


def list_projects_by_owner(owner_id: Any) -> list[dict[str, Any]]:
    cursor = projects_collection().find({"owner_id": _as_object_id(owner_id)}).sort(
        "created_at", -1
    )
    return list(cursor)


def update_project_fields(project_id: Any, **fields: Any) -> UpdateResult:
    """Patch arbitrary project fields (e.g. ``index_status``, ``vector_store``)."""
    if not fields:
        raise ValueError("update_project_fields requires at least one field")
    return projects_collection().update_one(
        {"_id": _as_object_id(project_id)},
        {"$set": fields},
    )


def set_project_index_status(project_id: Any, index_status: str, **extra: Any) -> UpdateResult:
    """Update ``index_status`` (and optional extra fields) on a project."""
    return update_project_fields(project_id, index_status=index_status, **extra)


# --- chat_history ----------------------------------------------------------


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": message["role"],
        "content": message.get("content", ""),
        "tool_trace": message.get("tool_trace"),
        "citations": message.get("citations"),
        "timestamp": message.get("timestamp") or _utcnow(),
    }


def create_chat_history(
    user_id: Any,
    *,
    project_id: Any = None,
    thread_id: str = "default",
    messages: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Insert a chat thread; ``project_id`` may be ``None`` for session-only chats."""
    normalized = [_normalize_message(m) for m in (messages or [])]
    doc: dict[str, Any] = {
        "user_id": _as_object_id(user_id),
        "project_id": _project_ref(project_id),
        "thread_id": (thread_id or "default").strip() or "default",
        "messages": normalized,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    result: InsertOneResult = chat_history_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_chat_history_by_id(chat_id: Any) -> Optional[dict[str, Any]]:
    return chat_history_collection().find_one({"_id": _as_object_id(chat_id)})


def find_chat_history(
    user_id: Any,
    *,
    project_id: Any = None,
    thread_id: str = "default",
) -> Optional[dict[str, Any]]:
    """Find a chat thread for user + project scope + thread_id."""
    query: dict[str, Any] = {
        "user_id": _as_object_id(user_id),
        "project_id": _project_ref(project_id),
        "thread_id": (thread_id or "default").strip() or "default",
    }
    return chat_history_collection().find_one(query)


def get_or_create_chat_history(
    user_id: Any,
    *,
    project_id: Any = None,
    thread_id: str = "default",
    chat_id: Any = None,
) -> dict[str, Any]:
    """Load a chat by id (ownership-checked) or by user/project/thread; create if missing."""
    if chat_id is not None and str(chat_id).strip():
        doc = get_chat_history_by_id(chat_id)
        if doc is None:
            raise ValueError("chat_id not found")
        if doc.get("user_id") != _as_object_id(user_id):
            raise ValueError("chat_id does not belong to the current user")
        return doc

    existing = find_chat_history(
        user_id, project_id=project_id, thread_id=thread_id
    )
    if existing is not None:
        return existing
    return create_chat_history(
        user_id, project_id=project_id, thread_id=thread_id, messages=[]
    )


def list_chat_histories_by_user(
    user_id: Any,
    *,
    project_id: Any = None,
    include_null_project: bool = False,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"user_id": _as_object_id(user_id)}
    if project_id is not None:
        query["project_id"] = _project_ref(project_id)
    elif include_null_project:
        query["project_id"] = None
    cursor = chat_history_collection().find(query).sort("updated_at", -1)
    return list(cursor)


def append_chat_message(chat_id: Any, message: dict[str, Any]) -> UpdateResult:
    """Append one message dict to an existing chat_history document."""
    return chat_history_collection().update_one(
        {"_id": _as_object_id(chat_id)},
        {
            "$push": {"messages": _normalize_message(message)},
            "$set": {"updated_at": _utcnow()},
        },
    )


def append_chat_messages(chat_id: Any, messages: list[dict[str, Any]]) -> UpdateResult:
    """Append multiple messages in order to a chat_history document."""
    if not messages:
        raise ValueError("append_chat_messages requires at least one message")
    normalized = [_normalize_message(m) for m in messages]
    return chat_history_collection().update_one(
        {"_id": _as_object_id(chat_id)},
        {
            "$push": {"messages": {"$each": normalized}},
            "$set": {"updated_at": _utcnow()},
        },
    )