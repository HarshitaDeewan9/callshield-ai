from app.core.exceptions import ServiceError
from app.providers.gnani_common import GnaniAdapter
from app.providers.interfaces import Audio
from app.services.audio_utils import finalize_timbre_wav, wav_diagnostics

# Narrow enabled catalog, checked against the official v2.5 SDK catalog.
VOICES = {"en-IN": "Kaveri", "hi-IN": "Nalini"}


class GnaniTimbreProvider(GnaniAdapter):
    async def synthesize(self, text, language, voice):
        if not self.s.timbre_enabled:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Timbre is disabled.")
        if VOICES.get(language) != voice:
            raise ServiceError("INVALID_INPUT", "Voice is not enabled for the selected language.", 422)

        def invoke():
            from gnani.tts import AudioConfig, GnaniTTSClient

            if self.client is None:
                self.client = GnaniTTSClient(
                    api_key=self.s.gnani_api_key.get_secret_value(), timeout=self.s.provider_timeout_seconds
                )
            return self.client.synthesize(
                text,
                voice=voice,
                model=self.s.timbre_model,
                language=language,
                speed=1.0,
                audio_config=AudioConfig(container="wav", sample_rate=48000, encoding="linear_pcm"),
            )

        data = await self.invoke(invoke, "TTS")
        try:
            data = finalize_timbre_wav(data)
        except ServiceError:
            # Useful for opt-in smoke diagnosis; not added to REST errors or transcript logs.
            self.last_audio_diagnostics = wav_diagnostics(data)
            raise
        return Audio(data)
