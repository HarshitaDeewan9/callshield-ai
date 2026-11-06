import json

import httpx
import pytest

from app.core.exceptions import ServiceError
from app.providers.evon_assessment import EvonRiskAssessor, band, parse_assessment, select_window
from app.providers.evon_llamacpp import EvonLlamaCppProvider

TURNS = [{"id": "t1", "speaker": "caller", "text": "Tell me your OTP now."}]
VALID = {
    "score": 90,
    "explanation": "The caller requests an OTP immediately.",
    "scenario": "credential_theft",
    "evidence": [{"turnId": "t1", "quote": "Tell me your OTP"}],
}


def completion(value, finish="stop"):
    return {
        "choices": [
            {
                "message": {"content": json.dumps(value), "reasoning_content": "ignore this"},
                "finish_reason": finish,
            }
        ]
    }


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "MINIMAL"),
        (19, "MINIMAL"),
        (20, "GUARDED"),
        (39, "GUARDED"),
        (40, "SUSPICIOUS"),
        (59, "SUSPICIOUS"),
        (60, "HIGH"),
        (79, "HIGH"),
        (80, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_severity_bands(score, expected):
    assert band(score) == expected


@pytest.mark.parametrize(
    "change",
    [
        {"score": -1},
        {"score": 101},
        {"score": 0.9},
        {"score": "90"},
        {"score": True},
        {"explanation": ""},
        {"scenario": "invented"},
        {"evidence": []},
        {"evidence": [{"turnId": "missing", "quote": "OTP"}]},
        {"evidence": [{"turnId": "t1", "quote": "made up evidence"}]},
    ],
)
def test_invalid_assessment(change):
    with pytest.raises(ServiceError, match="MODEL_OUTPUT_INVALID"):
        parse_assessment(completion({**VALID, **change}), TURNS)


def test_length_finish_is_not_an_explanation():
    with pytest.raises(ServiceError, match="MODEL_OUTPUT_INVALID"):
        parse_assessment(completion(VALID, "length"), TURNS)


async def test_structured_evon_contract(settings):
    settings.evon_context_tokens = 4096

    def handler(request):
        payload = json.loads(request.content)
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert payload["max_tokens"] == settings.risk_max_tokens
        assert payload["response_format"]["schema"]["properties"]["score"]["maximum"] == 100
        assert json.loads(payload["messages"][1]["content"])["untrusted_turns"] == TURNS
        assert "not probability" in payload["messages"][0]["content"]
        return httpx.Response(200, json=completion(VALID))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assessor = EvonRiskAssessor(settings, EvonLlamaCppProvider(settings, client))
        result = await assessor.assess(TURNS)
    assert result["score"] == 90 and result["band"] == "CRITICAL"
    assert not result["calibrated"] and result["confidence"] is None and not result["mock"]
    assert result["explanationSource"] == "model_generated_summary"


def test_context_window_is_explicit(settings):
    with pytest.raises(ServiceError, match="CONTEXT_LIMIT_EXCEEDED"):
        select_window(TURNS, settings)
    settings.evon_context_tokens = 2048
    turns = [{"id": str(i), "speaker": "caller", "text": "x" * 700} for i in range(5)]
    selected = select_window(turns, settings)
    assert selected[-1] == turns[-1] and len(selected) < len(turns)


def test_v2_endpoint(client):
    response = client.post("/api/v2/analyze/text", json={"turns": TURNS})
    assert response.status_code == 200
    result = response.json()["assessment"]
    assert result["mock"] and result["score"] == 90
    assert not result["acousticInfluence"]
    assert client.post("/api/v2/analyze/text", json={"turns": TURNS * 2}).status_code == 422


def test_context_distinguishes_claimed_parent_and_coercion(client):
    parent = client.post(
        "/api/v2/analyze/text",
        json={"turns": [{"id": "t1", "speaker": "caller", "text": "I am your dad. Please share your OTP."}]},
    ).json()
    coercion = client.post("/api/v2/analyze/text", json={"turns": TURNS}).json()
    assert 0 < parent["assessment"]["score"] < coercion["assessment"]["score"]
    # Mock demonstrations only: real semantic accuracy is a separate evaluation.
