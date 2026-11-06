import io
import re
import tempfile
import time
import wave
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from app.core.exceptions import ServiceError
from app.core.rate_limits import limited
from app.providers.gnani_timbre import VOICES
from app.schemas.requests import STT_LANGUAGES, TextRequest, WarningRequest
from app.schemas.responses import Report
from app.services.audio_utils import prepare_audio, sniff, validate_wav
from app.services.warnings import select_warning

router = APIRouter(prefix="/api/v1")


@router.post("/analyze/audio", response_model=Report)
async def analyze_audio(
    request: Request,
    file: UploadFile = File(...),
    consent: bool = Form(False),
    inputLanguage: str = Form("en-IN"),
    warningLanguage: str = Form("en-IN"),
    includeRuleIndicators: bool = Form(True),
    owner: str = Depends(limited),
):
    s, pipeline = request.app.state.settings, request.app.state.pipeline
    try:
        if not consent:
            raise ServiceError("CONSENT_REQUIRED", "Explicit recording consent is required.", 422)
        if not s.prisma_enabled:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Prisma is disabled.")
        if (
            not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", warningLanguage)
            or len(warningLanguage) > 20
        ):
            raise ServiceError("INVALID_INPUT", "Invalid warningLanguage.", 422)
        if inputLanguage not in STT_LANGUAGES:
            raise ServiceError("INVALID_INPUT", "Select an explicit supported STT language.", 422)
        if file.content_type not in ("audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg"):
            raise ServiceError("UNSUPPORTED_MEDIA", "Use WAV or MP3 with an audio MIME type.", 415)
        data = await file.read(s.max_audio_mb * 1024 * 1024 + 1)
        if len(data) > s.max_audio_mb * 1024 * 1024:
            raise ServiceError("UPLOAD_TOO_LARGE", "Audio exceeds the configured size limit.", 413)
        kind = sniff(data)
        if kind is None or (kind == "mp3") != (file.content_type == "audio/mpeg"):
            raise ServiceError("UNSUPPORTED_MEDIA", "Audio signature does not match MIME type.", 415)
        analysis_id = pipeline.begin(owner)
        request.app.state.store.get(analysis_id, owner).status = "TRANSCRIBING"
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="callshield-") as directory:
                if s.mock_mode and kind == "wav":
                    # Offline WAV path needs no system tools; real mode always uses ffprobe/ffmpeg.
                    validate_wav(data)
                    with wave.open(io.BytesIO(data), "rb") as wav:
                        duration_ms = wav.getnframes() / wav.getframerate() * 1000
                    if duration_ms > s.max_audio_seconds * 1000:
                        raise ServiceError("INVALID_INPUT", "Clip exceeds duration limit.", 422)
                    path = Path(directory) / "input.wav"
                    path.write_bytes(data)
                else:
                    path, duration_ms = await prepare_audio(data, directory, s)
                transcription = await pipeline.stt.transcribe(path, inputLanguage)
            if len(transcription["text"]) > s.max_transcript_chars:
                raise ServiceError("INVALID_INPUT", "Recognized transcript exceeds length limit.", 422)
            prisma_ms = (time.perf_counter() - started) * 1000
            transcription["uploadDurationMs"] = duration_ms
            body = TextRequest(
                transcript=transcription["text"],
                inputLanguage=transcription["detectedLanguage"],
                warningLanguage=warningLanguage,
                includeRuleIndicators=includeRuleIndicators,
            )
            return await pipeline.analyze(body, owner, analysis_id, transcription, prisma_ms)
        except ServiceError as exc:
            exc.analysis_id = analysis_id
            request.app.state.store.get(analysis_id, owner).error = exc.body(s.mock_mode)
            request.app.state.store.get(analysis_id, owner).status = "FAILED"
            raise
    finally:
        await file.close()


def audio_response(audio, warning, voice):
    return Response(
        audio.data,
        media_type=audio.mime,
        headers={
            "X-Mock": str(audio.mock).lower(),
            "X-Audio-Provider": audio.provider,
            "X-Template-Id": warning.templateId,
            "X-Requested-Language": warning.requestedLanguage,
            "X-Actual-Language": warning.actualLanguage,
            "X-Voice": voice,
            "X-Audio-Kind": "test-tone" if audio.mock else "speech",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/analyses/{analysis_id}/warning-audio",
    response_class=Response,
    responses={200: {"content": {"audio/wav": {}}}},
)
async def warning_audio(
    analysis_id: str, body: WarningRequest, request: Request, owner: str = Depends(limited)
):
    state = request.app.state
    if not state.settings.timbre_enabled:
        raise ServiceError("UNCONFIGURED_PROVIDER", "Timbre is disabled.")
    entry = state.store.get(analysis_id, owner)
    if entry.report is None:
        raise ServiceError("INVALID_INPUT", "Analysis has no completed risk result.", 409)
    warning = select_warning(entry.report.risk.level, body.language)
    if not warning.available:
        raise ServiceError("WARNING_NOT_AVAILABLE", "No warning audio is offered for low-risk results.", 409)
    voice = body.voice or VOICES[warning.actualLanguage]
    if voice != VOICES[warning.actualLanguage]:
        raise ServiceError("INVALID_INPUT", "Unsupported voice for this language.", 422)
    key = (warning.templateId, warning.actualLanguage, voice)
    cached = entry.audio.get(key)
    if cached and cached[0] > state.store.clock():
        audio = cached[1]
    else:
        started = time.perf_counter()
        try:
            audio = await state.pipeline.tts.synthesize(warning.text, warning.actualLanguage, voice)
        except ServiceError as exc:
            entry.report.warning.audioStatus = "FAILED"
            exc.analysis_id = analysis_id
            raise
        entry.report.timingsMs["timbre"] = (time.perf_counter() - started) * 1000
        state.store.cache_audio(entry, key, audio)
    warning.audioStatus = "READY"
    warning.mock = audio.mock
    entry.report.warning = warning
    entry.report.providers["tts"] = audio.provider
    return audio_response(audio, warning, voice)


@router.get(
    "/analyses/{analysis_id}/warning-audio",
    response_class=Response,
    responses={200: {"content": {"audio/wav": {}}}},
)
async def cached_warning_audio(
    analysis_id: str,
    request: Request,
    language: str = Query("en-IN", max_length=20, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"),
    voice: str | None = None,
    owner: str = Depends(limited),
):
    entry = request.app.state.store.get(analysis_id, owner)
    if entry.report is None:
        raise ServiceError("NOT_FOUND", "No warning audio is cached.", 404)
    warning = select_warning(entry.report.risk.level, language)
    voice = voice or VOICES[warning.actualLanguage]
    cached = entry.audio.get((warning.templateId, warning.actualLanguage, voice))
    if not cached:
        raise ServiceError("NOT_FOUND", "Warning audio is absent or expired; POST to synthesize it.", 404)
    return audio_response(cached[1], warning, voice)
