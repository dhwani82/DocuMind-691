"""Tests for MongoDB collection helpers in models.py."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

import models


@pytest.fixture
def mock_collections():
    users = MagicMock()
    projects = MagicMock()
    chats = MagicMock()
    database = {
        models.USERS_COLLECTION: users,
        models.PROJECTS_COLLECTION: projects,
        models.CHAT_HISTORY_COLLECTION: chats,
    }
    with patch("models.get_db", return_value=database):
        yield users, projects, chats


def test_create_user_inserts_normalized_email(mock_collections):
    users, _, _ = mock_collections
    inserted = ObjectId()
    users.insert_one.return_value = MagicMock(inserted_id=inserted)

    doc = models.create_user("Alice@Example.com", "hashed")

    assert doc["email"] == "alice@example.com"
    assert doc["hashed_password"] == "hashed"
    assert doc["_id"] == inserted
    assert isinstance(doc["created_at"], datetime)
    users.insert_one.assert_called_once()
    payload = users.insert_one.call_args.args[0]
    assert payload["email"] == "alice@example.com"


def test_get_user_by_email(mock_collections):
    users, _, _ = mock_collections
    users.find_one.return_value = {"email": "a@b.com"}

    found = models.get_user_by_email("A@B.com")

    users.find_one.assert_called_once_with({"email": "a@b.com"})
    assert found == {"email": "a@b.com"}


def test_get_project_by_owner_and_source(mock_collections):
    _, projects, _ = mock_collections
    owner_id = ObjectId()
    projects.find_one.return_value = {"name": "demo"}

    found = models.get_project_by_owner_and_source(owner_id, "/tmp/demo")

    projects.find_one.assert_called_once_with(
        {"owner_id": owner_id, "source_ref": "/tmp/demo"}
    )
    assert found == {"name": "demo"}


def test_create_project_stores_owner_object_id(mock_collections):
    _, projects, _ = mock_collections
    owner_id = ObjectId()
    inserted = ObjectId()
    projects.insert_one.return_value = MagicMock(inserted_id=inserted)

    doc = models.create_project(
        owner_id,
        " Demo ",
        "folder",
        "/tmp/repo",
        index_status="ready",
        vector_store="pinecone",
    )

    assert doc["_id"] == inserted
    assert doc["owner_id"] == owner_id
    assert doc["name"] == "Demo"
    assert doc["source_type"] == "folder"
    assert doc["source_ref"] == "/tmp/repo"
    assert doc["index_status"] == "ready"
    assert doc["vector_store"] == "pinecone"


def test_list_projects_by_owner(mock_collections):
    _, projects, _ = mock_collections
    owner_id = ObjectId()
    projects.find.return_value.sort.return_value = [{"name": "a"}]

    rows = models.list_projects_by_owner(str(owner_id))

    projects.find.assert_called_once_with({"owner_id": owner_id})
    assert rows == [{"name": "a"}]


def test_update_project_fields_requires_fields(mock_collections):
    with pytest.raises(ValueError, match="at least one field"):
        models.update_project_fields(ObjectId())


def test_create_chat_history_allows_null_project(mock_collections):
    _, _, chats = mock_collections
    user_id = ObjectId()
    inserted = ObjectId()
    chats.insert_one.return_value = MagicMock(inserted_id=inserted)

    doc = models.create_chat_history(
        user_id,
        project_id=None,
        messages=[
            {
                "role": "user",
                "content": "hello",
                "tool_trace": None,
                "citations": [],
            }
        ],
    )

    assert doc["project_id"] is None
    assert doc["user_id"] == user_id
    assert len(doc["messages"]) == 1
    assert doc["messages"][0]["role"] == "user"
    assert doc["messages"][0]["content"] == "hello"
    assert isinstance(doc["messages"][0]["timestamp"], datetime)


def test_append_chat_message_pushes_normalized_message(mock_collections):
    _, _, chats = mock_collections
    chat_id = ObjectId()
    chats.update_one.return_value = MagicMock()

    fixed = datetime(2026, 1, 2, tzinfo=timezone.utc)
    with patch("models._utcnow", return_value=fixed):
        models.append_chat_message(
            chat_id,
            {"role": "assistant", "content": "hi", "citations": ["a.py:1"]},
        )

    chats.update_one.assert_called_once()
    filt, update = chats.update_one.call_args.args
    assert filt == {"_id": chat_id}
    pushed = update["$push"]["messages"]
    assert pushed["role"] == "assistant"
    assert pushed["content"] == "hi"
    assert pushed["citations"] == ["a.py:1"]
    assert pushed["tool_trace"] is None
    assert pushed["timestamp"] == fixed
    assert "updated_at" in update["$set"]


def test_get_or_create_chat_history_reuses_thread(mock_collections):
    _, _, chats = mock_collections
    user_id = ObjectId()
    existing = {"_id": ObjectId(), "thread_id": "default"}
    chats.find_one.return_value = existing

    doc = models.get_or_create_chat_history(user_id, project_id="/tmp/repo")

    assert doc is existing
    chats.insert_one.assert_not_called()
    chats.find_one.assert_called_once()
    query = chats.find_one.call_args.args[0]
    assert query["project_id"] == "/tmp/repo"
    assert query["thread_id"] == "default"


def test_create_chat_history_stores_path_project_id(mock_collections):
    _, _, chats = mock_collections
    user_id = ObjectId()
    inserted = ObjectId()
    chats.insert_one.return_value = MagicMock(inserted_id=inserted)

    doc = models.create_chat_history(
        user_id, project_id="/Users/me/project", thread_id="t1"
    )

    payload = chats.insert_one.call_args.args[0]
    assert payload["project_id"] == "/Users/me/project"
    assert payload["thread_id"] == "t1"
    assert doc["_id"] == inserted
