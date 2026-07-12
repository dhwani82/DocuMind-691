"""Tests for MongoDB connection helpers."""

from unittest.mock import MagicMock, patch

import pytest

import db


@pytest.fixture(autouse=True)
def _reset_client():
    db.close_client()
    yield
    db.close_client()


def test_get_client_requires_mongodb_uri(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with pytest.raises(ValueError, match="MONGODB_URI"):
        db.get_client()


def test_database_name_from_uri_path():
    assert db._database_name_from_uri("mongodb://localhost:27017/mydb") == "mydb"
    assert db._database_name_from_uri("mongodb://localhost:27017/") == db.DEFAULT_DB_NAME
    assert db._database_name_from_uri("mongodb://localhost:27017") == db.DEFAULT_DB_NAME


def test_get_db_uses_uri_database_name(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/projects")
    fake_client = MagicMock()
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db

    with patch("db.MongoClient", return_value=fake_client) as mock_cls:
        result = db.get_db()

    mock_cls.assert_called_once_with("mongodb://localhost:27017/projects")
    fake_client.__getitem__.assert_called_once_with("projects")
    assert result is fake_db


def test_get_db_explicit_name_overrides_uri(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/projects")
    fake_client = MagicMock()
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db

    with patch("db.MongoClient", return_value=fake_client):
        result = db.get_db("other")

    fake_client.__getitem__.assert_called_once_with("other")
    assert result is fake_db


def test_get_client_reuses_singleton(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/documind")
    fake_client = MagicMock()

    with patch("db.MongoClient", return_value=fake_client) as mock_cls:
        first = db.get_client()
        second = db.get_client()

    mock_cls.assert_called_once()
    assert first is second is fake_client
