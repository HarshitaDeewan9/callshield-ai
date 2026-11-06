import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.interfaces import Audio
from app.services.report_store import ReportStore


def test_cache_memory_budget_preserves_reports(settings):
    settings.max_cached_audio_mb = 10
    store = ReportStore(settings)
    store.create("one", "owner")
    store.create("two", "owner")
    first, second = store.get("one", "owner"), store.get("two", "owner")
    audio = Audio(b"x" * (6 * 1024 * 1024))
    store.cache_audio(first, "warning", audio)
    store.cache_audio(second, "warning", audio)
    assert not first.audio and second.audio
    assert store.get("one", "owner") is first


def test_queued_progress_record(client):
    owner = next(iter(client.app.state.rate), None)
    assert owner is None
    # Obtain the authenticated backend principal through a normal request, then register pending work.
    client.get("/api/v1/analyses/missing")
    owner = next(iter(client.app.state.rate))
    client.app.state.store.create("pending", owner)
    result = client.get("/api/v1/analyses/pending")
    assert result.json() == {"analysisId": "pending", "status": "QUEUED", "mock": True}


def test_disabled_speech_and_capabilities(settings):
    settings.prisma_enabled = settings.timbre_enabled = False
    with TestClient(create_app(settings)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        caps = client.get("/api/v1/capabilities").json()
        assert not caps["sttAvailable"] and not caps["ttsAvailable"]
        assert "ta-IN" not in caps["inputLanguages"]
        assert "ta-IN" in caps["supportedInputLanguages"]


@pytest.mark.parametrize("language", ["नमस्ते", "en\r\nInjected", "z" * 21])
def test_invalid_warning_locale(client, scam, language):
    analysis_id = client.post("/api/v1/analyze/text", json=scam).json()["analysisId"]
    url = f"/api/v1/analyses/{analysis_id}/warning-audio"
    assert client.post(url, json={"language": language}).status_code == 422
    assert client.get(url, params={"language": language}).status_code == 422


def test_standard_route_error(client):
    response = client.get("/missing-route")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
