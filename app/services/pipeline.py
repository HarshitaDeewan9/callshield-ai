import time
import uuid

from app.core.exceptions import ServiceError
from app.schemas.responses import Report, Risk
from app.services.evidence_rules import indicators
from app.services.language_policy import normalize
from app.services.warnings import select_warning

LEVELS = {"A": "HIGH_RISK", "B": "SUSPICIOUS", "C": "LOW_RISK"}


class Pipeline:
    def __init__(self, settings, store, classifier, translator, stt, tts):
        self.s, self.store = settings, store
        self.classifier, self.translator, self.stt, self.tts = classifier, translator, stt, tts

    def begin(self, owner):
        analysis_id = str(uuid.uuid4())
        self.store.create(analysis_id, owner)
        return analysis_id

    async def analyze(self, request, owner, analysis_id=None, transcription=None, prisma_ms=None):
        started = time.perf_counter()
        analysis_id = analysis_id or self.begin(owner)
        entry = self.store.get(analysis_id, owner)
        try:
            text = request.transcript
            try:
                text.encode("utf-8", errors="strict")
            except UnicodeError:
                raise ServiceError("INVALID_INPUT", "Transcript must be valid Unicode.", 422) from None
            if (
                not any(c.isalpha() for c in text)
                or len(text) > self.s.max_transcript_chars
                or any(ord(c) < 32 and c not in "\n\r\t" for c in text)
            ):
                raise ServiceError(
                    "INVALID_INPUT", "Provide meaningful text within the configured length limit.", 422
                )
            if request.turns:
                if "\n".join(f"{t.speaker}: {t.text}" for t in request.turns) != text:
                    raise ServiceError(
                        "INVALID_INPUT", "Transcript must match the supplied ordered turns.", 422
                    )
                if len({t.id for t in request.turns}) != len(request.turns):
                    raise ServiceError("INVALID_INPUT", "Turn IDs must be unique.", 422)
            translation_start = time.perf_counter()
            entry.status = "TRANSLATING"
            normalized = await normalize(text, request.inputLanguage, self.translator, self.s)
            translation_ms = (time.perf_counter() - translation_start) * 1000
            if not normalized.text.strip() or len(normalized.text) > self.s.max_transcript_chars:
                raise ServiceError("TRANSLATION_FAILED", "Normalized transcript exceeds input limits.", 502)
            evon_start = time.perf_counter()
            entry.status = "CLASSIFYING"
            classification = await self.classifier.classify(normalized.text)
            evon_ms = (time.perf_counter() - evon_start) * 1000
            level = LEVELS[classification.code]
            language = "und" if request.inputLanguage == "auto" else request.inputLanguage
            source = "unknown" if language == "und" else "user"
            if transcription:
                language, source = transcription["detectedLanguage"], transcription["languageSource"]
            report = Report(
                analysisId=analysis_id,
                inputType="AUDIO" if transcription else "TEXT",
                originalTranscript=text,
                originalLanguage=language,
                detectedLanguage=language,
                languageSource=source,
                normalizedTranscript=normalized.text,
                analysisLanguage=normalized.language,
                normalizationApplied=normalized.applied,
                normalizedFromOriginal=normalized.applied,
                normalizationProvider=normalized.provider,
                normalization={
                    "provider": normalized.provider,
                    "mock": normalized.mock,
                    "sourceLanguage": language,
                    "targetLanguage": normalized.language,
                    "caution": "Translation can alter intent or negation." if normalized.applied else None,
                },
                risk=Risk(
                    code=classification.code,
                    level=level,
                    source="mock" if classification.mock else "evon",
                    model="mock-fixture-v1" if classification.mock else "gnani-evon-v3.3-gguf",
                    mock=classification.mock,
                ),
                indicators=indicators(text) if request.includeRuleIndicators else [],
                warning=select_warning(level, request.warningLanguage),
                transcription=transcription,
                timingsMs={
                    "total": (time.perf_counter() - started) * 1000 + (prisma_ms or 0),
                    "prisma": prisma_ms,
                    "translation": translation_ms,
                    "evon": evon_ms,
                    "timbre": None,
                },
                providers={
                    "stt": transcription["provider"] if transcription else None,
                    "translation": normalized.provider,
                    "classification": classification.provider,
                    "tts": None,
                },
                mock=classification.mock or normalized.mock or bool(transcription and transcription["mock"]),
            )
            entry.report = report
            entry.status = "COMPLETED"
            entry.expires = self.store.clock() + self.s.report_ttl_seconds
            return report
        except ServiceError as exc:
            exc.analysis_id = analysis_id
            entry.error = exc.body(self.s.mock_mode)
            entry.status = "FAILED"
            raise
