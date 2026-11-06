"""Studio catalog checked against Gnani's Evon model card and Prisma v2.5 docs.

Provider support is not an evaluation of fraud accuracy on our quantized model.
Odia is Evon text-only; Hinglish is a text variant, not an auto-detection claim.
"""

from typing import Literal

InputLanguage = Literal[
    "en-IN",
    "hi-IN",
    "bn-IN",
    "te-IN",
    "ta-IN",
    "mr-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "or-IN",
    "pa-IN",
    "hi-Latn",
]
LANGUAGES = [
    ("en-IN", "English", "English"),
    ("hi-IN", "Hindi", "हिन्दी"),
    ("bn-IN", "Bengali", "বাংলা"),
    ("te-IN", "Telugu", "తెలుగు"),
    ("ta-IN", "Tamil", "தமிழ்"),
    ("mr-IN", "Marathi", "मराठी"),
    ("gu-IN", "Gujarati", "ગુજરાતી"),
    ("kn-IN", "Kannada", "ಕನ್ನಡ"),
    ("ml-IN", "Malayalam", "മലയാളം"),
    ("or-IN", "Odia", "ଓଡ଼ିଆ"),
    ("pa-IN", "Punjabi", "ਪੰਜਾਬੀ"),
    ("hi-Latn", "Hinglish", "Roman Hindi + English"),
]
TEXT_LANGUAGES = [row[0] for row in LANGUAGES]
AUDIO_LANGUAGES = [code for code in TEXT_LANGUAGES if code not in ("or-IN", "hi-Latn")]
LANGUAGE_NAMES = {code: name for code, name, _ in LANGUAGES}


def studio_catalog():
    return {
        "languages": [
            {
                "code": code,
                "name": name,
                "nativeName": native,
                "text": True,
                "audio": code in AUDIO_LANGUAGES,
                "warningAudio": code in ("en-IN", "hi-IN"),
                "fraudAccuracyValidated": False,
            }
            for code, name, native in LANGUAGES
        ],
        "speechModel": "prisma-v2.5",
        "riskModel": "gnani-evon-v3.3-gguf",
        "warningModel": "timbre-v2.5",
        "automaticLanguageDetection": False,
        "translationApplied": False,
        "evidencePolicy": "exact_original_quote",
        "warningLanguages": ["en-IN", "hi-IN"],
    }
