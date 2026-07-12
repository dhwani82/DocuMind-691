"""Tests for JWT register/login and @require_auth."""

from unittest.mock import patch

import pytest
from bson import ObjectId
from flask_jwt_extended import decode_token

from auth import hash_password


def test_register_returns_token(client, monkeypatch):
    user_id = ObjectId()

    def fake_create(email, hashed_password):
        return {
            "_id": user_id,
            "email": email,
            "hashed_password": hashed_password,
        }

    monkeypatch.setattr("auth.models.get_user_by_email", lambda _email: None)
    monkeypatch.setattr("auth.models.create_user", fake_create)

    response = client.post(
        "/api/register",
        json={"email": "New@Example.com", "password": "password123"},
    )
    data = response.get_json()

    assert response.status_code == 201
    assert data["success"] is True
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["id"] == str(user_id)
    assert data["access_token"]
    claims = decode_token(data["access_token"])
    assert claims["sub"] == str(user_id)


def test_register_rejects_duplicate_email(client, monkeypatch):
    monkeypatch.setattr(
        "auth.models.get_user_by_email",
        lambda _email: {"_id": ObjectId(), "email": "taken@example.com"},
    )

    response = client.post(
        "/api/register",
        json={"email": "taken@example.com", "password": "password123"},
    )
    data = response.get_json()

    assert response.status_code == 400
    assert "already exists" in data["error"].lower()


def test_login_returns_token(client, monkeypatch):
    user_id = ObjectId()
    password = "password123"
    monkeypatch.setattr(
        "auth.models.get_user_by_email",
        lambda _email: {
            "_id": user_id,
            "email": "user@example.com",
            "hashed_password": hash_password(password),
        },
    )

    response = client.post(
        "/api/login",
        json={"email": "user@example.com", "password": password},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["access_token"]
    assert data["user"]["id"] == str(user_id)


def test_login_rejects_bad_password(client, monkeypatch):
    monkeypatch.setattr(
        "auth.models.get_user_by_email",
        lambda _email: {
            "_id": ObjectId(),
            "email": "user@example.com",
            "hashed_password": hash_password("password123"),
        },
    )

    response = client.post(
        "/api/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    data = response.get_json()

    assert response.status_code == 401
    assert "invalid" in data["error"].lower()


def test_require_auth_accepts_bearer_token(client, auth_headers):
    """Protected routes run after JWT validation (400 = auth passed, body invalid)."""
    response = client.post("/api/index-project", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert "folder_path" in (response.get_json() or {}).get("error", "").lower()


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/chat", {"question": "hi"}),
        ("/api/index-project", {"folder_path": "/tmp"}),
        ("/api/agent", {"project_id": "/tmp", "message": "hi"}),
    ],
)
def test_protected_routes_require_jwt(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 401
