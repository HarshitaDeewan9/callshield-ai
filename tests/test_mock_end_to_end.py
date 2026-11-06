import httpx
import requests

from scripts.smoke_test_mock import exercise


def test_mock_never_contacts_provider(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Mock mode attempted a network call")

    async def forbidden_async(*args, **kwargs):
        raise AssertionError("Mock mode attempted an async network call")

    monkeypatch.setattr(requests, "post", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_async)
    exercise(client)


def test_openapi_and_capabilities(client):
    schema = client.get("/openapi.json").json()
    assert "/api/v1/analyze/audio" in schema["paths"]
    assert {"get", "post"}.issubset(schema["paths"]["/api/v1/analyses/{analysis_id}/warning-audio"])
    assert schema["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
    result = client.get("/api/v1/capabilities").json()
    assert result["mockMode"] and result["simulationEnabled"] is False
    assert "hi-Latn" not in result["sttLanguages"]
