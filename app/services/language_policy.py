from app.core.exceptions import ServiceError
from app.providers.identity_translation import preserve
from app.schemas.requests import INPUT_LANGUAGES


async def normalize(text, language, translator, settings):
    if language not in INPUT_LANGUAGES:
        raise ServiceError("INVALID_INPUT", "Unsupported inputLanguage.", 422)
    if language in ("auto", "en-IN", "hi-Latn") or (language == "hi-IN" and not settings.translate_hindi):
        return preserve(text, "und" if language == "auto" else language)
    return await translator.normalize(text, language, "en-IN")
