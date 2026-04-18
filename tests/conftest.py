from app import app
import pytest

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
