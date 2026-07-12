"""MongoDB connection helpers for DocuMind.

Reads ``MONGODB_URI`` from the environment and exposes a shared PyMongo client
and database via ``get_client()`` / ``get_db()``. No routes are wired here —
other modules import these helpers when they need persistence.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from pymongo import MongoClient
from pymongo.database import Database

DEFAULT_DB_NAME = "documind"

_client: Optional[MongoClient] = None


def _resolve_uri() -> str:
    uri = (os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise ValueError(
            "Missing MONGODB_URI. Set it in the environment or .env "
            "(e.g. mongodb://localhost:27017/documind)."
        )
    return uri


def _database_name_from_uri(uri: str) -> str:
    """Return the DB name from the URI path, or the default when absent."""
    path = (urlparse(uri).path or "").strip("/")
    if not path:
        return DEFAULT_DB_NAME
    # Ignore extra path segments; MongoDB URIs use a single db name.
    return path.split("/")[0] or DEFAULT_DB_NAME


def get_client() -> MongoClient:
    """Return a process-wide MongoClient, creating it on first use."""
    global _client
    if _client is None:
        _client = MongoClient(_resolve_uri())
    return _client


def get_db(name: Optional[str] = None) -> Database:
    """Return a Database handle for ``name``, or the URI/default database."""
    client = get_client()
    db_name = (name or "").strip() or _database_name_from_uri(_resolve_uri())
    return client[db_name]


def close_client() -> None:
    """Close the shared client (tests / graceful shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
