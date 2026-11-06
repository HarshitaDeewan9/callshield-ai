import io
import tempfile
import time
import wave
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from app.api.routes_audio import audio_response
from app.core.exceptions import ServiceError
from app.core.rate_limits import limited
from app.languages import AUDIO_LANGUAGES, InputLanguage
from app.providers.gnani_timbre import VOICES
from app.schemas.live import LiveTurn
from app.services.audio_utils import prepare_audio, sniff, validate_wav
from app.services.warnings import select_warning

router = APIRouter(prefix="/api/v2")


@router.post("/analyze/audio")
async def structured_audio(
    request: Request,
    file: UploadFile = File(...),
    consent: bool = Form(False),
    inputLanguage: str = Form("en-IN"),
    explanationLanguage: InputLanguage = Form("en-IN"),
    owner: str = Depends(limited),
):
    state, started = request.app.state, time.perf_counter()
    s = state.settings
    try:
        if not consent:
            raise ServiceError("CONSENT_REQUIRED", "Recording consent is required.", 422)
        if not s.prisma_enabled:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Prisma is disabled.")
        if inputLanguage not in AUDIO_LANGUAGES:
            raise ServiceError("INVALID_INPUT", "Select a supported Prisma audio language.", 422)
        data = await file.read(s.max_audio_mb * 1024 * 1024 + 1)
        if len(data) > s.max_audio_mb * 1024 * 1024:
            raise ServiceError("UPLOAD_TOO_LARGE", "Audio exceeds the configured size limit.", 413)
        kind = sniff(data)
        if (
            file.content_type not in ("audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg")
            or not kind
            or ((kind == "mp3") != (file.content_type == "audio/mpeg"))
        ):
            raise ServiceError("UNSUPPORTED_MEDIA", "Choose valid WAV or MP3 audio.", 415)
        with tempfile.TemporaryDirectory(prefix="callshield-") as directory:
            if s.mock_mode and kind == "wav":
                validate_wav(data)
                with wave.open(io.BytesIO(data), "rb") as audio:
                    duration = audio.getnframes() / audio.getframerate()
                if duration > s.max_audio_seconds:
                    raise ServiceError("INVALID_INPUT", "Clip exceeds the duration limit.", 422)
                path = Path(directory) / "input.wav"
                path.write_bytes(data)
            else:
                path, _ = await prepare_audio(data, directory, s)
            transcription = await state.pipeline.stt.transcribe(path, inputLanguage)
        text = transcription["text"]
        if len(text) > s.max_transcript_chars:
            raise ServiceError("INVALID_INPUT", "Transcript exceeds the configured character limit.", 422)
        # Whole text is preserved; explicit turn slices never discard recognized words.
        turns = [
            LiveTurn(id=f"stt_{i // 1000}", speaker="unknown", text=text[i : i + 1000]).model_dump()
            for i in range(0, len(text), 1000)
        ]
        result = await state.risk_assessor.assess(turns, explanation_language=explanationLanguage)
        return {
            "status": "COMPLETED",
            "inputType": "AUDIO",
            "originalTranscript": text,
            "inputLanguage": inputLanguage,
            "languageSource": "user",
            "translationApplied": False,
            "transcription": transcription,
            "assessment": result,
            "mock": result["mock"] or transcription["mock"],
            "timingsMs": {"total": round((time.perf_counter() - started) * 1000)},
        }
    finally:
        await file.close()


class TrustedWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["HIGH_RISK", "SUSPICIOUS", "UNDETERMINED"]
    language: Literal["en-IN", "hi-IN"] = "en-IN"


@router.post("/warnings/synthesize", response_class=Response, responses={200: {"content": {"audio/wav": {}}}})
async def trusted_warning(body: TrustedWarning, request: Request, owner: str = Depends(limited)):
    """Private authenticated Spring contract: level must come from its owner-scoped persisted report."""
    if not request.app.state.settings.timbre_enabled:
        raise ServiceError("UNCONFIGURED_PROVIDER", "Timbre is disabled.")
    warning = select_warning(body.level, body.language)
    voice = VOICES[warning.actualLanguage]
    audio = await request.app.state.pipeline.tts.synthesize(warning.text, warning.actualLanguage, voice)
    return audio_response(audio, warning, voice)
