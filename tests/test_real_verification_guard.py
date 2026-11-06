import pytest

from scripts.verify_real_stack import verify_report


def test_real_verifier_rejects_mock_report():
    with pytest.raises(ValueError, match="Not a real Evon"):
        verify_report({"result": {"mock": True, "assessment": {"mock": True, "source": "mock"}}})


def test_real_verifier_checks_exact_quote_and_prisma_provenance():
    report = {
        "id": "qa",
        "result": {
            "mock": False,
            "originalTranscript": "आपका OTP बताइए।",
            "assessment": {
                "mock": False,
                "source": "evon",
                "explanationSource": "model_generated_summary",
                "score": 90,
                "band": "CRITICAL",
                "evidence": [{"quote": "आपका OTP"}],
            },
        },
    }
    assert verify_report(report)["originalQuoteMatches"]
    with pytest.raises(ValueError, match="Prisma"):
        verify_report(report, require_stt=True)
    report["result"]["assessment"]["evidence"][0]["quote"] = "invented"
    with pytest.raises(ValueError, match="Evidence"):
        verify_report(report)
