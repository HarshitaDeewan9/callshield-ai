import io
import math
import re
import struct
import wave

from app.providers.identity_translation import IdentityTranslator
from app.providers.interfaces import Audio, Classification, NormalizedText


def demo_wav():
    """Audible test tone, deliberately not fabricated speech."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(
            b"".join(
                struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(8000)
            )
        )
    return output.getvalue()


class MockEvonProvider:
    async def ready(self):
        return True

    async def classify(self, text):
        # Offline demonstration only: sentence-level negation prevents basic warning false positives.
        dangerous = False
        for sentence in re.split(r"[.!?।\n]", text.lower()):
            secret = re.search(r"otp|pin|password|ओटीपी|पिन", sentence)
            negated = re.search(r"never|don't|do not|not share|nahi|mat |नहीं|मत ", sentence)
            solicitation = re.search(r"tell|share|give|bata|बताइ|बताओ|दीजिए", sentence)
            dangerous |= bool(secret and solicitation and not negated)
        if dangerous or re.search(r"safe account|सुरक्षित खाते", text.lower()):
            code = "A"
        elif re.search(r"verification pending|verify|verification|blocked|block|सत्यापन", text.lower()):
            code = "B"
        else:
            code = "C"
        return Classification(code, "mock-evon", True)


class MockPrismaProvider:
    async def transcribe(self, path, language):
        return {
            "text": "Caller: Your account will be blocked. Tell me your OTP immediately.",
            "detectedLanguage": "en-IN",
            "languageSource": "provider",
            "segments": [],
            "provider": "mock-prisma",
            "modelVersion": "fixture-v1",
            "durationMs": None,
            "mock": True,
        }


class MockTimbreProvider:
    async def synthesize(self, text, language, voice):
        return Audio(demo_wav(), provider="mock-timbre-test-tone", mock=True)


class MockTranslator(IdentityTranslator):
    async def normalize(self, text, source_language, target):
        return NormalizedText(
            "Caller: Verification is pending; I will explain the details.",
            target,
            "mock-translation-fixed-fixture",
            True,
            True,
        )
