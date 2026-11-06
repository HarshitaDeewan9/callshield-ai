import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.exceptions import ServiceError
from app.main import create_app
from app.providers.evon_assessment import MockRiskAssessor
from app.schemas.live import AlertPolicy, LiveTurn, SessionRequest
from app.services.alerts import ThresholdAlerts
from app.services.live_sessions import LiveSessions


def create(client, mode="text", **kwargs):
    response = client.post("/api/v2/sessions", json={"consent": True, "inputMode": mode, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


def receive_until(ws, event_type):
    for _ in range(30):
        value = ws.receive_json()
        if value["type"] == event_type:
            return value
    raise AssertionError(f"Did not receive {event_type}")


def test_text_websocket_risk_and_alert(client):
    session = create(client)
    with client.websocket_connect(session["websocketPath"]) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "turn", "id": "t1", "speaker": "caller", "text": "Tell me your OTP now."})
        risk = receive_until(ws, "risk")
        assert risk["assessment"]["score"] == 90 and risk["inputRevision"] == 1
        alert = receive_until(ws, "alert")
        assert alert["threshold"] == 70 and alert["warning"]["available"]
        ws.send_json({"type": "end"})
        assert receive_until(ws, "closed")["status"] == "CLOSED"
    saved = client.get(f"/api/v2/sessions/{session['sessionId']}").json()
    assert saved["peakScore"] == 90 and len(saved["history"]) == 1


def test_no_evidence_heartbeat_does_not_fabricate_score(client):
    session = create(client)
    with client.websocket_connect(session["websocketPath"]) as ws:
        ws.receive_json()
        value = receive_until(ws, "status")
        assert value["assessment"] is None and value["riskStatus"] == "WAITING_FOR_EVIDENCE"
        ws.send_json({"type": "end"})
        receive_until(ws, "closed")


def test_rest_incremental_and_score_can_drop(client):
    session = create(client)
    url = f"/api/v2/sessions/{session['sessionId']}"
    body = {"id": "t1", "speaker": "caller", "text": "Tell me your OTP now."}
    assert client.post(url + "/turns", json=body).status_code == 202
    # Idempotent replay does not introduce extra turns or scores.
    assert client.post(url + "/turns", json=body).json()["inputRevision"] == 1
    client.post(url + "/end")
    assert client.get(url).json()["assessment"]["score"] == 90
    assert client.post(url + "/turns", json={**body, "id": "t2"}).status_code == 409


def test_policy_hysteresis_cooldown():
    now = [0]
    alerts = ThresholdAlerts(AlertPolicy(threshold=70, resetBelow=50, cooldownSeconds=30), lambda: now[0])
    assert alerts.observe(60) is None
    assert alerts.observe(80)
    assert alerts.observe(90) is None
    alerts.observe(40)
    assert alerts.observe(85) is None
    now[0] = 31
    assert alerts.observe(85)
    assert alerts.observe(99) is None


def test_policy_validation():
    with pytest.raises(ValidationError):
        AlertPolicy(threshold=40, resetBelow=50)


@pytest.mark.parametrize(
    "body", [{"consent": False}, {"consent": True, "inputMode": "audio", "inputLanguage": "hi-Latn"}]
)
def test_invalid_creation(client, body):
    assert client.post("/api/v2/sessions", json=body).status_code == 422


def test_unauthorized_socket(client):
    session = create(client)
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(session["websocketPath"], headers={"X-API-Key": "wrong"}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(session["websocketPath"], headers={"Origin": "https://evil.test"}):
            pass


def test_bad_audio_frame(client):
    session = create(client, "audio")
    with client.websocket_connect(session["websocketPath"]) as ws:
        receive_until(ws, "audio_ready")
        ws.send_bytes(b"RIFF not raw pcm")
        assert receive_until(ws, "error")["code"] == "INVALID_INPUT"


def test_mock_live_audio_end_to_end(client):
    session = create(client, "audio")
    with client.websocket_connect(session["websocketPath"]) as ws:
        receive_until(ws, "audio_ready")
        for _ in range(32):
            ws.send_bytes(b"\0" * 1024)
            time.sleep(0.033)
        risk = receive_until(ws, "risk")
        assert risk["assessment"]["mock"] and risk["assessment"]["score"] == 90
        assert risk["acoustics"]["samples"] == 32 * 512
        assert not risk["acoustics"]["usedByRiskModel"]
        ws.send_json({"type": "end"})
        receive_until(ws, "closed")


def test_audio_burst_backpressure(client):
    session = create(client, "audio")
    with client.websocket_connect(session["websocketPath"]) as ws:
        receive_until(ws, "audio_ready")
        for _ in range(10):
            ws.send_bytes(b"\0" * 1024)
        assert receive_until(ws, "error")["code"] == "RATE_LIMITED"


def test_disabled_live(settings):
    settings.live_enabled = False
    with TestClient(create_app(settings)) as client:
        client.headers["X-API-Key"] = settings.app_api_key.get_secret_value()
        assert client.post("/api/v2/sessions", json={"consent": True}).status_code == 503


async def test_worker_failure_keeps_operational_state(settings):
    class Failing:
        async def assess(self, turns):
            raise ServiceError("MODEL_OUTPUT_INVALID", "Invalid output.", 502)

    manager = LiveSessions(settings, Failing())
    session = manager.create("owner", SessionRequest(consent=True))
    await manager.append(session, LiveTurn(id="1", text="Hello"))
    await manager.finish(session)
    assert session.snapshot()["riskStatus"] == "UNDETERMINED"
    assert session.result is None and session.peak is None
    await manager.shutdown()


async def test_latest_pending_input_is_coalesced(settings):
    settings.live_checkpoint_seconds = 0.1
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Slow:
        async def assess(self, turns):
            calls.append(len(turns))
            entered.set()
            await release.wait()
            return await MockRiskAssessor().assess(turns)

    manager = LiveSessions(settings, Slow())
    session = manager.create("owner", SessionRequest(consent=True))
    await manager.append(session, LiveTurn(id="1", text="Hello"))
    await entered.wait()
    session.last_turn_at = 0
    await manager.append(session, LiveTurn(id="2", text="Tell me your OTP now."))
    session.last_turn_at = 0
    await manager.append(session, LiveTurn(id="3", text="Do not share your OTP."))
    release.set()
    await manager.finish(session)
    assert calls == [1, 3]
    assert session.result["score"] == 10 and session.assessed_revision == 3
    assert not session.snapshot()["stale"]
    await manager.shutdown()


async def test_limits_ownership_and_expiry(settings):
    settings.live_max_sessions = 1
    manager = LiveSessions(settings, MockRiskAssessor())
    session = manager.create("one", SessionRequest(consent=True))
    with pytest.raises(ServiceError, match="NOT_FOUND"):
        manager.get(session.id, "two")
    with pytest.raises(ServiceError, match="RATE_LIMITED"):
        manager.create("one", SessionRequest(consent=True))
    session.expires = 0
    with pytest.raises(ServiceError, match="NOT_FOUND"):
        manager.get(session.id, "one")
    await asyncio.gather(session.task, return_exceptions=True)
    await manager.shutdown()
