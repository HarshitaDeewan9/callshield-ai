from app.core.exceptions import ServiceError
from app.providers.gnani_common import GnaniAdapter
from app.schemas.requests import STT_LANGUAGES


class GnaniPrismaProvider(GnaniAdapter):
    async def transcribe(self, path, language):
        if not self.s.prisma_enabled:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Prisma is disabled.")
        if language not in STT_LANGUAGES:
            raise ServiceError(
                "INVALID_INPUT", "Select a supported explicit STT language; auto/hi-Latn are text only.", 422
            )

        def invoke():
            if self.client is None:
                from gnani.stt import GnaniSTTClient

                self.client = GnaniSTTClient(
                    api_key=self.s.gnani_api_key.get_secret_value(), timeout=self.s.provider_timeout_seconds
                )
            return self.client.transcribe(str(path), language_code=language)

        result = await self.invoke(invoke, "STT")
        if (
            not isinstance(result, dict)
            or result.get("success") is not True
            or not isinstance(result.get("transcript"), str)
        ):
            raise ServiceError("TRANSCRIPTION_FAILED", "Prisma returned an invalid transcript response.", 502)
        if not result["transcript"].strip():
            raise ServiceError("INSUFFICIENT_TRANSCRIPT", "No speech recognized; upload a clearer clip.", 422)
        # REST v3 does not return detected language, alignment, diarization or duration.
        return {
            "text": result["transcript"],
            "detectedLanguage": language,
            "languageSource": "user",
            "segments": [],
            "provider": "gnani-prisma",
            "modelVersion": "prisma-v2.5",
            "durationMs": None,
            "mock": False,
        }
