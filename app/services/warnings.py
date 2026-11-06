from app.schemas.responses import Warning

TEMPLATES = {
    "HIGH_RISK": {
        "en-IN": "Warning: This conversation contains strong scam indicators. Do not share your OTP, PIN or password, "
        "or transfer money under pressure. End the call and verify through your bank's official channel.",
        "hi-IN": "सावधान! इस बातचीत में धोखाधड़ी के गंभीर संकेत हैं। अपना ओटीपी, पिन या पासवर्ड साझा न करें। "
        "दबाव में पैसे न भेजें। कॉल समाप्त करें और बैंक के आधिकारिक माध्यम से पुष्टि करें।",
    },
    "SUSPICIOUS": {
        "en-IN": "Be cautious. Verify the caller independently through an official channel before sharing "
        "information or sending money. Never share your OTP or PIN.",
        "hi-IN": "सावधान रहें। जानकारी साझा करने या पैसे भेजने से पहले आधिकारिक माध्यम से कॉल करने वाले की "
        "पहचान की पुष्टि करें। अपना ओटीपी या पिन कभी साझा न करें।",
    },
    "LOW_RISK": {
        "en-IN": "No significant risk indicators were found in the provided content. This does not certify "
        "the caller as safe. Never share your OTP or PIN.",
        "hi-IN": "दी गई बातचीत में गंभीर जोखिम के संकेत नहीं मिले। इससे कॉल करने वाले की सुरक्षा प्रमाणित "
        "नहीं होती। अपना ओटीपी या पिन कभी साझा न करें।",
    },
    "UNDETERMINED": {
        "en-IN": "Risk could not be determined. Verify independently through an official channel. "
        "Do not share your OTP or PIN.",
        "hi-IN": "जोखिम का निर्धारण नहीं हो सका। आधिकारिक माध्यम से स्वतंत्र पुष्टि करें। अपना ओटीपी या पिन साझा न करें।",
    },
}


def select_warning(level, language):
    actual = language if language in ("en-IN", "hi-IN") else "en-IN"
    return Warning(
        available=level != "LOW_RISK",
        templateId=f"{level}_GENERIC",
        requestedLanguage=language,
        language=actual,
        actualLanguage=actual,
        fallbackApplied=actual != language,
        text=TEMPLATES[level][actual],
    )
