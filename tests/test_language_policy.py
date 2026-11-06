from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ServiceError
from app.main import create_app
from app.providers.google_translation import GoogleCloudTranslator
from app.providers.identity_translation import IdentityTranslator
from app.services.language_policy import normalize


@pytest.mark.parametrize("language", ["en-IN", "hi-Latn", "hi-IN", "auto"])
async def test_identity(settings, language):
    text = "Bank kabhi OTP nahi maangta"
    result = await normalize(text, language, IdentityTranslator(), settings)
    assert result.text == text and not result.applied and not result.mock


async def test_required_translation_unconfigured(settings):
    with pytest.raises(ServiceError, match="UNCONFIGURED_PROVIDER"):
        await normalize("வணக்கம்", "ta-IN", IdentityTranslator(), settings)


def test_translated_original_retained(settings):
    settings.translation_provider = "google"
    with TestClient(create_app(settings)) as c:
        c.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        result = c.post("/api/v1/analyze/text", json={"transcript": "வணக்கம்", "inputLanguage": "ta-IN"}).json()
    assert result["originalTranscript"] == "வணக்கம்"
    assert result["normalizedTranscript"] != result["originalTranscript"]
    assert result["normalizationApplied"] and result["normalization"]["mock"]


async def test_google_contract(settings):
    settings.google_cloud_project = "test-project"

    class Client:
        def translate_text(self, request, timeout, retry):
            assert request["contents"] == ["OTP मत बताना"]
            assert request["source_language_code"] == "hi"
            assert request["target_language_code"] == "en"
            assert request["model"].endswith("/general/nmt")
            assert retry is None
            return SimpleNamespace(translations=[SimpleNamespace(translated_text="Do not share your OTP")])

    result = await GoogleCloudTranslator(settings, Client()).normalize("OTP मत बताना", "hi-IN", "en-IN")
    assert result.text == "Do not share your OTP" and not result.mock


async def test_google_failure(settings):
    settings.google_cloud_project = "test-project"

    class Client:
        def translate_text(self, **kwargs):
            raise RuntimeError("sensitive")

    with pytest.raises(ServiceError, match="TRANSLATION_FAILED"):
        await GoogleCloudTranslator(settings, Client()).normalize("secret", "ta-IN", "en-IN")
