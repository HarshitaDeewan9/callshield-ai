from app.providers.mock_providers import demo_wav


def test_studio_audio_score(client):
    result = client.post(
        "/api/v2/analyze/audio",
        files={"file": ("clip.wav", demo_wav(), "audio/wav")},
        data={"consent": "true", "inputLanguage": "en-IN"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["assessment"]["score"] == 90
    assert result.json()["transcription"]["mock"]


def test_studio_audio_consent(client):
    result = client.post(
        "/api/v2/analyze/audio",
        files={"file": ("clip.wav", demo_wav(), "audio/wav")},
        data={"consent": "false"},
    )
    assert result.status_code == 422


def test_trusted_warning_only_templates(client):
    result = client.post("/api/v2/warnings/synthesize", json={"level": "HIGH_RISK", "language": "en-IN"})
    assert result.status_code == 200 and result.headers["x-mock"] == "true"
    assert (
        client.post(
            "/api/v2/warnings/synthesize", json={"level": "HIGH_RISK", "text": "arbitrary"}
        ).status_code
        == 422
    )
