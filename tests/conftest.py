from app import app
import pytest
from bson import ObjectId
from flask_jwt_extended import create_access_token

TEST_USER_ID = str(ObjectId("507f1f77bcf86cd799439011"))


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key-at-least-32-bytes"
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Bearer token for protected routes (identity = Mongo-compatible user id)."""
    with app.app_context():
        token = create_access_token(identity=TEST_USER_ID)
    return {"Authorization": f"Bearer {token}"}
