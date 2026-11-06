import anyio

from app.core.exceptions import ServiceError
from app.providers.identity_translation import IdentityTranslator
from app.providers.interfaces import NormalizedText


class GoogleCloudTranslator(IdentityTranslator):
    def __init__(self, settings, client=None):
        self.s, self.client = settings, client
        self.limiter = anyio.CapacityLimiter(2)

    async def normalize(self, text, source_language, target="en-IN"):
        if not self.s.google_cloud_project:
            raise ServiceError(
                "UNCONFIGURED_PROVIDER", "Set GOOGLE_CLOUD_PROJECT and Google ADC credentials."
            )

        def invoke():
            if self.client is None:
                from google.cloud import translate_v3

                self.client = translate_v3.TranslationServiceClient()
            response = self.client.translate_text(
                request={
                    "parent": f"projects/{self.s.google_cloud_project}/locations/global",
                    "contents": [text],
                    "mime_type": "text/plain",
                    "source_language_code": source_language.split("-")[0],
                    "target_language_code": target.split("-")[0],
                    "model": f"projects/{self.s.google_cloud_project}/locations/global/models/general/nmt",
                },
                timeout=self.s.provider_timeout_seconds,
                retry=None,
            )
            return response.translations[0].translated_text

        try:
            result = await anyio.to_thread.run_sync(invoke, limiter=self.limiter)
            if not isinstance(result, str) or not result.strip():
                raise ValueError
            return NormalizedText(result, target, "google-cloud-translation", True)
        except Exception:
            raise ServiceError(
                "TRANSLATION_FAILED", "Translation failed; original text was preserved.", 502
            ) from None
