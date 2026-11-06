from app.core.exceptions import ServiceError
from app.providers.interfaces import NormalizedText


class IdentityTranslator:
    async def normalize(self, text, source_language, target):
        raise ServiceError("UNCONFIGURED_PROVIDER", "Configure Google translation for this input language.")

    async def localize_template(self, template_id, target_language):
        from app.services.warnings import select_warning

        return select_warning(template_id.removesuffix("_GENERIC"), target_language)


def preserve(text, language):
    return NormalizedText(text, language, "identity")
