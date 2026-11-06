"""Offline smoke, or exercise a running mock server with --base-url."""

import argparse
import os

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.mock_providers import demo_wav


def exercise(client):
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/v1/capabilities").json()["mockMode"] is True
    response = client.post(
        "/api/v1/analyze/text",
        json={
            "transcript": "Caller: Tell me your OTP immediately.",
            "inputLanguage": "en-IN",
            "warningLanguage": "hi-IN",
        },
    )
    response.raise_for_status()
    result = response.json()
    assert result["mock"] and result["risk"]["code"] == "A"
    analysis_id = result["analysisId"]
    assert client.get(f"/api/v1/analyses/{analysis_id}").status_code == 200
    audio = client.post(f"/api/v1/analyses/{analysis_id}/warning-audio", json={"language": "hi-IN"})
    assert audio.status_code == 200 and audio.headers["x-mock"] == "true"
    assert audio.content[:4] == b"RIFF"
    response = client.post(
        "/api/v1/analyze/audio",
        files={"file": ("demo.wav", demo_wav(), "audio/wav")},
        data={"consent": "true", "inputLanguage": "en-IN"},
    )
    response.raise_for_status()
    assert response.json()["transcription"]["mock"]
    print("PASS: mock text, stored result, Hindi warning tone, WAV upload; all without provider calls.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    args = parser.parse_args()
    if args.base_url:
        with httpx.Client(
            base_url=args.base_url,
            headers={"X-API-Key": os.getenv("APP_API_KEY", "")},
            timeout=30,
            trust_env=False,
        ) as client:
            exercise(client)
    else:
        with TestClient(create_app(Settings(_env_file=None, mock_mode=True, app_api_key=""))) as client:
            exercise(client)


if __name__ == "__main__":
    main()
