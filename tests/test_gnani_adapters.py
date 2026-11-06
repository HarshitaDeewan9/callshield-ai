from pathlib import Path

import pytest
import requests

from app.core.exceptions import ServiceError
from app.providers.gnani_prisma import GnaniPrismaProvider
from app.providers.gnani_timbre import VOICES, GnaniTimbreProvider
from app.providers.mock_providers import demo_wav


@pytest.fixture
def gnani_settings(settings):
    settings.gnani_api_key = "test-provider-key"
    return settings


def response(status=200, json=None, content=b""):
    class Response:
        status_code = status
        text = "upstream secret response"

        def __init__(self):
            self.content = content

        def json(self):
            return json

    return Response()


async def test_prisma_sdk_http_contract(gnani_settings, monkeypatch, tmp_path):
    path = tmp_path / "input.wav"
    path.write_bytes(demo_wav())

    def post(url, headers, files, data, timeout):
        assert url == "https://api.vachana.ai/stt/v3"
        assert headers["X-API-Key-ID"] == "test-provider-key"
        assert data == {"language_code": "hi-IN", "format": "verbatim"}
        assert files["audio_file"].read() == demo_wav()
        assert timeout == gnani_settings.provider_timeout_seconds
        return response(json={"success": True, "transcript": "ओटीपी मत बताना"})

    monkeypatch.setattr(requests, "post", post)
    result = await GnaniPrismaProvider(gnani_settings).transcribe(path, "hi-IN")
    assert result["text"] == "ओटीपी मत बताना" and not result["mock"]
    assert result["languageSource"] == "user" and result["segments"] == []


@pytest.mark.parametrize(
    "payload,code",
    [
        ({}, "TRANSCRIPTION_FAILED"),
        ({"text": "wrong field"}, "TRANSCRIPTION_FAILED"),
        ({"success": True, "transcript": ""}, "INSUFFICIENT_TRANSCRIPT"),
        ({"success": False, "transcript": "x"}, "TRANSCRIPTION_FAILED"),
        ({"success": True, "transcript": []}, "TRANSCRIPTION_FAILED"),
    ],
)
async def test_prisma_invalid(gnani_settings, monkeypatch, tmp_path, payload, code):
    path = tmp_path / "input.wav"
    path.write_bytes(demo_wav())
    monkeypatch.setattr(requests, "post", lambda *a, **k: response(json=payload))
    with pytest.raises(ServiceError, match=code):
        await GnaniPrismaProvider(gnani_settings).transcribe(path, "en-IN")


async def test_timbre_sdk_http_contract(gnani_settings, monkeypatch):
    from gnani.tts import GnaniTTSClient

    assert set(VOICES.values()).issubset(GnaniTTSClient.supported_voices(model="timbre-v2.5"))

    def post(url, headers, json, timeout):
        assert url == "https://api.vachana.ai/api/v1/tts/inference"
        assert headers["X-API-Key-ID"] == "test-provider-key"
        assert json["model"] == "timbre-v2.5"
        assert json["language"] == "hi-IN" and json["voice"] == "Nalini"
        assert json["text"] == "सावधान रहें"
        assert json["audio_config"]["container"] == "wav"
        return response(content=demo_wav())

    monkeypatch.setattr(requests, "post", post)
    audio = await GnaniTimbreProvider(gnani_settings).synthesize("सावधान रहें", "hi-IN", "Nalini")
    assert audio.mime == "audio/wav" and not audio.mock


@pytest.mark.parametrize("stage", ["stt", "tts"])
@pytest.mark.parametrize(
    "status,code,retry",
    [(401, None, False), (403, None, False), (429, "RATE_LIMITED", True), (500, None, True)],
)
async def test_provider_http_failure(gnani_settings, monkeypatch, tmp_path, stage, status, code, retry):
    calls = []

    def post(*args, **kwargs):
        calls.append(True)
        return response(status=status)

    monkeypatch.setattr(requests, "post", post)
    path = tmp_path / "input.wav"
    path.write_bytes(demo_wav())
    with pytest.raises(ServiceError) as error:
        if stage == "stt":
            await GnaniPrismaProvider(gnani_settings).transcribe(path, "en-IN")
        else:
            await GnaniTimbreProvider(gnani_settings).synthesize("Warning", "en-IN", "Kaveri")
    assert error.value.code == (code or f"{stage.upper()}_UNAVAILABLE")
    assert error.value.retryable == retry and len(calls) == 1
    assert "secret" not in error.value.message


@pytest.mark.parametrize("stage", ["stt", "tts"])
async def test_missing_credentials(settings, stage):
    with pytest.raises(ServiceError, match="UNCONFIGURED_PROVIDER"):
        if stage == "stt":
            await GnaniPrismaProvider(settings).transcribe(Path("unused"), "en-IN")
        else:
            await GnaniTimbreProvider(settings).synthesize("Warning", "en-IN", "Kaveri")


async def test_tts_timeout_and_bad_audio(gnani_settings, monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("secret")

    monkeypatch.setattr(requests, "post", timeout)
    with pytest.raises(ServiceError, match="TIMEOUT"):
        await GnaniTimbreProvider(gnani_settings).synthesize("Warning", "en-IN", "Kaveri")
    monkeypatch.setattr(requests, "post", lambda *a, **k: response(content=b"<html>error</html>"))
    with pytest.raises(ServiceError, match="TTS_UNAVAILABLE"):
        await GnaniTimbreProvider(gnani_settings).synthesize("Warning", "en-IN", "Kaveri")
