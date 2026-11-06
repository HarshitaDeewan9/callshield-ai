import re


def indicators(text):
    found = []
    for match in re.finditer(
        r"\bOTP\s+bata(?:iye|o)|\b(?:tell me|share|give me)\s+(?:your\s+)?(?:OTP|PIN)\b", text, re.I
    ):
        prefix = text[max(0, match.start() - 40) : match.start()].lower()
        if re.search(r"do not|don't|never|mat|nahi", prefix):
            continue
        found.append(
            {
                "id": "otp_solicitation",
                "source": "rule",
                "type": "CREDENTIAL_REQUEST",
                "evidenceText": match.group(),
                "speaker": None,
                "turnId": None,
            }
        )
    return found
