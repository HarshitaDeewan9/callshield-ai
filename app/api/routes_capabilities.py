import shutil

from fastapi import APIRouter, Depends, Request

from app.api.routes_health import sdk_available
from app.core.auth import authorize
from app.languages import AUDIO_LANGUAGES, TEXT_LANGUAGES, studio_catalog
from app.providers.gnani_timbre import VOICES
from app.schemas.requests import INPUT_LANGUAGES, STT_LANGUAGES

router = APIRouter()


@router.get("/api/v1/capabilities")
async def capabilities(request: Request, owner: str = Depends(authorize)):
    s = request.app.state.settings
    speech = s.mock_mode or bool(s.gnani_api_key.get_secret_value() and sdk_available())
    tools = all(shutil.which(p) for p in (s.ffmpeg_path, s.ffprobe_path))
    translation = s.translation_provider == "google" and (s.mock_mode or bool(s.google_cloud_project))
    enabled_inputs = (
        INPUT_LANGUAGES
        if translation
        else [
            language
            for language in ("auto", "en-IN", "hi-Latn", "hi-IN")
            if language != "hi-IN" or not s.translate_hindi
        ]
    )
    return {
        "mockMode": s.mock_mode,
        "studio": studio_catalog(),
        "inputLanguages": enabled_inputs,
        "supportedInputLanguages": INPUT_LANGUAGES,
        "sttLanguages": [language for language in STT_LANGUAGES if language in enabled_inputs],
        "providerSttLanguages": STT_LANGUAGES,
        "translationAvailable": translation,
        "translationProvider": s.translation_provider,
        "outputLanguages": list(VOICES),
        "voices": VOICES,
        "supportedMimeFormats": ["audio/wav", "audio/mpeg"],
        "maxAudioMB": s.max_audio_mb,
        "maxAudioSeconds": s.max_audio_seconds,
        "maxTranscriptChars": s.max_transcript_chars,
        "evonContextTokens": s.evon_context_tokens,
        "audioAvailable": s.prisma_enabled and speech and (s.mock_mode or tools),
        "sttAvailable": s.prisma_enabled and speech and (s.mock_mode or tools),
        "audioToolsAvailable": tools,
        "mp3Available": s.prisma_enabled and speech and tools,
        "ttsAvailable": s.timbre_enabled and speech,
        "simulationEnabled": False,
        "live": {
            "enabled": s.live_enabled,
            "audioAvailable": s.live_enabled and s.prisma_enabled and speech,
            "transport": "websocket",
            "statusIntervalSeconds": 1,
            "checkpointIntervalSeconds": s.live_checkpoint_seconds,
            "newScoresEverySecondGuaranteed": False,
            "inputLanguages": TEXT_LANGUAGES,
            "audioLanguages": AUDIO_LANGUAGES,
            "audioSampleRate": 16000,
            "scoreType": "uncalibrated_model_risk_index",
            "bands": ["MINIMAL", "GUARDED", "SUSPICIOUS", "HIGH", "CRITICAL"],
            "toneFraudInference": False,
            "structuredContextReady": s.mock_mode or s.evon_context_tokens >= 2048,
        },
        "executionMode": "synchronous",
        "storage": "in_memory_single_process",
        "mockAudioKind": "test-tone" if s.mock_mode else None,
    }
