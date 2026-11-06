import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        mock_mode=True,
        app_api_key="test-backend-secret-at-least-24",
        requests_per_minute=1000,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        c.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        yield c


@pytest.fixture
def scam():
    return {"transcript": "Caller: Tell me your OTP immediately.", "inputLanguage": "en-IN"}
