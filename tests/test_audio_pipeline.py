import io
import wave

import pytest

from app.providers.mock_providers import demo_wav


def upload(client, data=None, consent="true", mime="audio/wav", **fields):
    return client.post(
        "/api/v1/analyze/audio",
        files={"file": ("../../untrusted.wav", data or demo_wav(), mime)},
        data={"consent": consent, **fields},
    )


def test_mock_audio(client):
    response = upload(client)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["inputType"] == "AUDIO" and report["risk"]["code"] == "A"
    assert report["transcription"]["mock"] and report["transcription"]["segments"] == []
    assert report["transcription"]["durationMs"] is None
    assert report["transcription"]["uploadDurationMs"] == 500


@pytest.mark.parametrize(
    "kwargs,status,code",
    [
        ({"consent": "false"}, 422, "CONSENT_REQUIRED"),
        ({"data": b"not audio"}, 415, "UNSUPPORTED_MEDIA"),
        ({"data": b"\xff\xfeinvalid UTF8"}, 415, "UNSUPPORTED_MEDIA"),
        ({"mime": "text/plain"}, 415, "UNSUPPORTED_MEDIA"),
        ({"mime": "audio/mpeg"}, 415, "UNSUPPORTED_MEDIA"),
        ({"inputLanguage": "hi-Latn"}, 422, "INVALID_INPUT"),
        ({"inputLanguage": "auto"}, 422, "INVALID_INPUT"),
        ({"data": demo_wav()[:50]}, 415, "UNSUPPORTED_MEDIA"),
    ],
)
def test_rejections(client, kwargs, status, code):
    response = upload(client, **kwargs)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_oversize_and_duration(client):
    response = upload(client, data=b"x" * (16 * 1024 * 1024))
    assert response.status_code == 413
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", ""))
        wav.writeframes(b"\0\0" * 8000 * 61)
    assert upload(client, output.getvalue()).status_code == 422
