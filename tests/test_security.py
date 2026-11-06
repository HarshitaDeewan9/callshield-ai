import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    "path", ["/api/v1/capabilities", "/api/v1/analyses/missing", "/health/ready", "/openapi.json", "/docs"]
)
def test_authenticated(client, path):
    assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401


def test_liveness_is_public(client):
    assert client.get("/health/live", headers={"X-API-Key": ""}).json() == {"status": "alive"}


@pytest.mark.parametrize("transcript", ["", " ", "123456", "\0hidden", "x" * 3001, "\ud800"])
def test_bad_text(client, transcript):
    response = (
        client.post("/api/v1/analyze/text", json={"transcript": transcript})
        if transcript != "\ud800"
        else (
            client.post(
                "/api/v1/analyze/text",
                content=b'{"transcript":"\\ud800"}',
                headers={"Content-Type": "application/json"},
            )
        )
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_no_input_or_secret_leak(client, caplog):
    secret = "otp=secret123456"
    response = client.post("/api/v1/analyze/text", json={"transcript": {"private": secret}})
    assert secret not in response.text and secret not in caplog.text
    health = client.get("/health/ready").text
    assert "127.0.0.1" not in health and "test-backend" not in health


def test_cors_disabled(client):
    assert (
        "access-control-allow-origin"
        not in client.get("/health/live", headers={"Origin": "https://evil.test"}).headers
    )


def test_secure_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mock_mode=False, app_api_key="")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", app_api_key="short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, evon_max_concurrent=2)


def test_real_mode_never_falls_back(settings, scam):
    settings.mock_mode = False

    def handler(request):
        return httpx.Response(503, text="secret infrastructure error")

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(create_app(settings, upstream)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        response = client.post("/api/v1/analyze/text", json=scam)
        assert response.status_code == 503, response.text
        data = response.json()
        assert data["error"]["code"] == "EVON_UNAVAILABLE" and not data["mock"]
        assert "risk" not in data
        assert client.get("/api/v1/analyses/" + data["analysisId"]).json() == data
        ready = client.get("/health/ready")
        assert ready.status_code == 503 and ready.json()["components"]["evon"] == "unavailable"


def test_request_rate_limit(settings):
    settings.requests_per_minute = 1
    with TestClient(create_app(settings)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        assert client.get("/api/v1/analyses/unknown").status_code == 404
        assert client.get("/api/v1/analyses/unknown").status_code == 429


def test_body_limit(client):
    response = client.post("/api/v1/analyze/text", content=b"x" * 65537)
    assert response.status_code == 413
