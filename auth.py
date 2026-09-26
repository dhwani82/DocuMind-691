"""JWT auth helpers for DocuMind (flask-jwt-extended).

Provides register/login against the ``users`` collection, token creation,
and a ``@require_auth`` decorator that injects ``g.user_id`` from the JWT.
"""

from __future__ import annotations

import os
import re
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from flask import Flask, g
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

import models

F = TypeVar("F", bound=Callable[..., Any])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8

jwt_manager = JWTManager()


def init_auth(app: Flask) -> JWTManager:
    """Configure JWT on the Flask app. Call once at startup."""
    secret = (
        (os.getenv("JWT_SECRET_KEY") or "").strip()
        or (os.getenv("SECRET_KEY") or "").strip()
        or "documind-dev-jwt-secret-change-me"
    )
    app.config.setdefault("JWT_SECRET_KEY", secret)
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers"])
    jwt_manager.init_app(app)
    return jwt_manager


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def _validate_credentials(email: str, password: str) -> Optional[str]:
    email = (email or "").strip()
    if not email or not EMAIL_RE.match(email):
        return "A valid email is required."
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def _user_public(doc: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
    }


def issue_access_token(user_id: Any) -> str:
    """Create a JWT whose identity is the string user id."""
    return create_access_token(identity=str(user_id))


def register_user(email: str, password: str) -> dict[str, Any]:
    """Create a user and return ``access_token`` + public user fields.

    Raises:
        ValueError: invalid input or email already registered.
    """
    error = _validate_credentials(email, password)
    if error:
        raise ValueError(error)

    normalized = email.strip().lower()
    if models.get_user_by_email(normalized) is not None:
        raise ValueError("An account with this email already exists.")

    user = models.create_user(normalized, hash_password(password))
    token = issue_access_token(user["_id"])
    return {"access_token": token, "user": _user_public(user)}


def login_user(email: str, password: str) -> dict[str, Any]:
    """Verify credentials and return ``access_token`` + public user fields.

    Raises:
        ValueError: invalid input or bad credentials.
    """
    error = _validate_credentials(email, password)
    if error:
        raise ValueError(error)

    user = models.get_user_by_email(email.strip().lower())
    if user is None or not verify_password(password, user.get("hashed_password", "")):
        raise ValueError("Invalid email or password.")

    token = issue_access_token(user["_id"])
    return {"access_token": token, "user": _user_public(user)}


GUEST_USER_ID = "000000000000000000000001"


def auth_required_enabled() -> bool:
    """When false (default), Ask routes allow unauthenticated local/demo use."""
    return (os.getenv("AUTH_REQUIRED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def require_auth(view: F) -> F:
    """Protect a route and set ``g.user_id`` from the JWT identity.

    If ``AUTH_REQUIRED`` is unset/false, JWT is optional and a guest user id is used.
    """

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        from flask_jwt_extended import verify_jwt_in_request

        if auth_required_enabled():
            verify_jwt_in_request()
            g.user_id = get_jwt_identity()
        else:
            verify_jwt_in_request(optional=True)
            g.user_id = get_jwt_identity() or GUEST_USER_ID
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def get_current_user_id() -> Optional[str]:
    """Return the authenticated user id from ``g`` or the active JWT."""
    user_id = getattr(g, "user_id", None)
    if user_id:
        return str(user_id)
    try:
        identity = get_jwt_identity()
    except RuntimeError:
        return GUEST_USER_ID if not auth_required_enabled() else None
    if identity:
        return str(identity)
    return GUEST_USER_ID if not auth_required_enabled() else None
