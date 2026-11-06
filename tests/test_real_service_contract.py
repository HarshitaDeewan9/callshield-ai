import json
from pathlib import Path

import httpx
import pytest
import requests
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.mock_providers import demo_wav


@pytest.mark.parametrize("code,level", [("A", "HIGH_RISK"), ("B", "SUSPICIOUS"), ("C", "LOW_RISK")])
def test_real_text_contract(settings, code, level):
    settings.mock_mode = False
    settings.prisma_enabled = settings.timbre_enabled = False
    settings.evon_api_key = "test-evon-secret"

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-evon-secret"
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "evon"}]})
        assert json.loads(request.content)["chat_template_kwargs"]["enable_thinking"] is False
        return httpx.Response(
            200, json={"choices": [{"message": {"content": code}, "finish_reason": "stop"}]}
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(create_app(settings, upstream)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        assert client.get("/health/ready").status_code == 200
        result = client.post("/api/v1/analyze/text", json={"transcript": "Caller: Hello"}).json()
        assert result["risk"]["code"] == code and result["risk"]["level"] == level
        assert result["risk"]["source"] == "evon" and not result["mock"]


@pytest.mark.parametrize("bad_output", ["", "A because ...", "D"])
def test_invalid_model_output_is_failed_report(settings, bad_output):
    settings.mock_mode = False
    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": bad_output, "reasoning_content": "C"},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )
        )
    )
    with TestClient(create_app(settings, upstream)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        result = client.post("/api/v1/analyze/text", json={"transcript": "Caller: Hello"})
        assert result.status_code == 502
        failure = result.json()
        assert failure["error"]["code"] == "MODEL_OUTPUT_INVALID" and "risk" not in failure
        assert client.get("/api/v1/analyses/" + failure["analysisId"]).json() == failure


def test_real_audio_to_warning_contract_and_temp_cleanup(settings, monkeypatch):
    settings.mock_mode = False
    settings.gnani_api_key = "test-gnani-key"
    paths = []

    async def process(*args):
        if args[0] == settings.ffprobe_path:
            paths.append(Path(args[-1]))
            return b'{"format":{"duration":"0.5"},"streams":[{"codec_type":"audio"}]}'
        Path(args[-1]).write_bytes(demo_wav())
        return b""

    class SDKResponse:
        status_code = 200
        content = demo_wav()

        def json(self):
            return {"success": True, "transcript": "Tell me your OTP now."}

    monkeypatch.setattr("app.services.audio_utils.command", process)
    monkeypatch.setattr(requests, "post", lambda *a, **k: SDKResponse())
    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"choices": [{"message": {"content": "A"}, "finish_reason": "stop"}]}
            )
        )
    )
    with TestClient(create_app(settings, upstream)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        response = client.post(
            "/api/v1/analyze/audio",
            files={"file": ("call.wav", demo_wav(), "audio/wav")},
            data={"consent": "true", "inputLanguage": "hi-IN"},
        )
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["risk"]["code"] == "A" and not report["mock"]
        assert report["transcription"]["provider"] == "gnani-prisma"
        assert paths and all(not path.exists() and not path.parent.exists() for path in paths)
        audio = client.post(
            f"/api/v1/analyses/{report['analysisId']}/warning-audio", json={"language": "hi-IN"}
        )
        assert audio.status_code == 200 and audio.headers["x-mock"] == "false"
        assert audio.headers["x-audio-kind"] == "speech" and audio.content == demo_wav()
