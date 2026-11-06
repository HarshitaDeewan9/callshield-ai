import io
import wave

from app.core.exceptions import ServiceError


def analyze(client, scam):
    return client.post("/api/v1/analyze/text", json=scam).json()["analysisId"]


def test_warning_and_cache(client, scam):
    analysis_id = analyze(client, scam)
    url = f"/api/v1/analyses/{analysis_id}/warning-audio"
    response = client.post(url, json={"language": "hi-IN", "voice": None})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-mock"] == "true" and response.headers["x-audio-kind"] == "test-tone"
    assert response.headers["x-voice"] == "Nalini"
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        assert audio.getnframes() == 8000
    assert client.get(url + "?language=hi-IN").content == response.content
    report = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert report["warning"]["audioStatus"] == "READY"


def test_warning_fallback_and_reject_arbitrary_text(client, scam):
    analysis_id = analyze(client, scam)
    url = f"/api/v1/analyses/{analysis_id}/warning-audio"
    response = client.post(url, json={"language": "ta-IN"})
    assert response.headers["x-requested-language"] == "ta-IN"
    assert response.headers["x-actual-language"] == "en-IN"
    assert client.post(url, json={"text": "Unapproved text"}).status_code == 422
    assert client.post(url, json={"language": "hi-IN", "voice": "Kaveri"}).status_code == 422


def test_low_risk_no_warning_audio(client):
    analysis_id = analyze(client, {"transcript": "Have a nice day"})
    response = client.post(f"/api/v1/analyses/{analysis_id}/warning-audio", json={})
    assert response.status_code == 409 and response.json()["error"]["code"] == "WARNING_NOT_AVAILABLE"


def test_tts_failure_independent(client, scam):
    analysis_id = analyze(client, scam)

    class Fail:
        async def synthesize(self, *args):
            raise ServiceError("TTS_UNAVAILABLE", "Speech unavailable.", 503, True)

    client.app.state.pipeline.tts = Fail()
    response = client.post(f"/api/v1/analyses/{analysis_id}/warning-audio", json={})
    assert response.status_code == 503
    report = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert report["status"] == "COMPLETED" and report["risk"]["code"] == "A"
    assert report["warning"]["audioStatus"] == "FAILED"
