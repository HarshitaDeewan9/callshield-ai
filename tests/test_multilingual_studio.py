import json

import httpx
import pytest

from app.languages import AUDIO_LANGUAGES, TEXT_LANGUAGES
from app.providers.evon_assessment import EvonRiskAssessor, parse_assessment
from app.providers.evon_llamacpp import EvonLlamaCppProvider
from app.providers.mock_providers import demo_wav
from app.schemas.live import SessionRequest


def test_catalog_distinguishes_language_features(client):
    catalog = client.get("/api/v1/capabilities").json()["studio"]
    by_code = {language["code"]: language for language in catalog["languages"]}
    assert len(by_code) == 12 and len(AUDIO_LANGUAGES) == 10
    assert by_code["or-IN"]["text"] and not by_code["or-IN"]["audio"]
    assert by_code["ta-IN"]["audio"] and not by_code["ta-IN"]["warningAudio"]
    assert not catalog["automaticLanguageDetection"] and not catalog["translationApplied"]
    assert not any(item["fraudAccuracyValidated"] for item in by_code.values())


@pytest.mark.parametrize("language", TEXT_LANGUAGES)
def test_native_text_metadata_and_mock_provenance(client, language):
    result = client.post(
        "/api/v2/analyze/text",
        json={
            "inputLanguage": language,
            "explanationLanguage": language,
            "turns": [{"id": "t1", "text": "உங்கள் OTP எண்ணை சொல்லுங்கள்."}],
        },
    ).json()
    assert result["inputLanguage"] == language and result["languageSource"] == "user"
    assert result["assessment"]["mock"] and result["assessment"]["explanationLanguage"] == "en-IN"
    assert result["assessment"]["requestedExplanationLanguage"] == language
    assert result["assessment"]["evidence"][0]["quote"] == "உங்கள் OTP எண்ணை சொல்லுங்கள்."


@pytest.mark.parametrize("language", AUDIO_LANGUAGES)
def test_audio_catalog_enabled_end_to_end(client, language):
    result = client.post(
        "/api/v2/analyze/audio",
        files={"file": ("qa.wav", demo_wav(), "audio/wav")},
        data={"consent": "true", "inputLanguage": language, "explanationLanguage": "hi-IN"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["inputLanguage"] == language
    assert result.json()["transcription"]["mock"]


def test_text_only_locale_rejected_for_audio():
    for language in ("hi-Latn", "or-IN"):
        with pytest.raises(ValueError):
            SessionRequest(consent=True, inputMode="audio", inputLanguage=language)
    assert SessionRequest(consent=True, inputMode="audio", inputLanguage="ta-IN").inputLanguage == "ta-IN"


async def test_real_adapter_preserves_script_and_requests_localized_explanation(settings):
    settings.evon_context_tokens = 4096
    text = "உங்கள் OTP எண்ணை சொல்லுங்கள்."
    turns = [{"id": "t1", "speaker": "caller", "text": text}]

    def handler(request):
        body = json.loads(request.content)
        assert "Write explanation in Hindi" in body["messages"][0]["content"]
        assert json.loads(body["messages"][1]["content"])["untrusted_turns"][0]["text"] == text
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 85,
                                    "explanation": "कॉलर ने OTP माँगा।",
                                    "scenario": "credential_theft",
                                    "evidence": [{"turnId": "t1", "quote": text}],
                                },
                                ensure_ascii=False,
                            )
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await EvonRiskAssessor(settings, EvonLlamaCppProvider(settings, http)).assess(
            turns, explanation_language="hi-IN"
        )
    assert not result["mock"] and result["explanationLanguage"] == "hi-IN"
    assert result["evidenceQuotesValidated"] and not result["explanationLanguageVerified"]
    assert result["evidence"][0]["quote"] == text


def test_translated_evidence_rejected():
    payload = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "score": 90,
                            "explanation": "OTP request.",
                            "scenario": "credential_theft",
                            "evidence": [{"turnId": "t1", "quote": "Tell me your OTP"}],
                        }
                    )
                },
            }
        ]
    }
    with pytest.raises(Exception, match="MODEL_OUTPUT_INVALID"):
        parse_assessment(payload, [{"id": "t1", "text": "आपका OTP बताइए।"}])
