import asyncio
import json

import pytest
import websockets

from app.core.exceptions import ServiceError
from app.providers.prisma_stream import GnaniPrismaStream, MockPrismaStream
from app.services.acoustics import AcousticMetrics


class FakeSocket:
    def __init__(self, events=()):
        self.queue = asyncio.Queue()
        for event in events:
            self.queue.put_nowait(json.dumps(event))
        self.sent = []
        self.closed = False

    async def recv(self):
        return '{"type":"connected","config":{"language_code":"en-IN"}}'

    async def send(self, data):
        self.sent.append(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.queue.get()

    async def close(self):
        self.closed = True


async def test_official_websocket_contract(settings, monkeypatch):
    settings.gnani_api_key = "fixture-provider-secret"
    ready = asyncio.Event()
    transcript = {"type": "transcript", "text": "Tell me your OTP now.", "segment_id": "req-1-seg-1"}
    socket = FakeSocket([transcript])
    turns = []

    async def connect(url, **kwargs):
        assert url == "wss://api.vachana.ai/stt/v3/stream"
        headers = kwargs["additional_headers"]
        assert headers["x-api-key-id"] == "fixture-provider-secret"
        assert headers["model"] == "prisma-v2.5" and headers["language_code"] == "en-IN"
        assert headers["x-sample-rate"] == "16000" and headers["x-max-speech-s"] == "5.0"
        assert kwargs["max_queue"] == 8
        return socket

    async def on_turn(turn):
        turns.append(turn)
        ready.set()

    async def on_error(error):
        raise AssertionError(error.code)

    monkeypatch.setattr(websockets, "connect", connect)
    stream = GnaniPrismaStream(settings, "en-IN", on_turn, on_error)
    await stream.start()
    await asyncio.wait_for(ready.wait(), 1)
    await stream.send(b"\0" * 1024)
    assert turns[0].text == transcript["text"] and turns[0].speaker == "unknown"
    assert turns[0].id.startswith("stt_")
    assert socket.sent == [b"\0" * 1024]
    await stream.close()
    assert socket.closed and stream.task.done()


async def test_stream_error_sanitized(settings, monkeypatch):
    settings.gnani_api_key = "fixture-provider-secret"
    received = []
    ready = asyncio.Event()

    async def connect(*a, **k):
        return FakeSocket([{"type": "error", "message": "private URL or secret"}])

    async def on_error(error):
        received.append(error)
        ready.set()

    monkeypatch.setattr(websockets, "connect", connect)
    stream = GnaniPrismaStream(settings, "en-IN", None, on_error)
    await stream.start()
    await asyncio.wait_for(ready.wait(), 1)
    assert received[0].code == "STT_UNAVAILABLE" and "private" not in received[0].message
    await stream.close()


async def test_commit_and_bounded_drain(settings, monkeypatch):
    stream = GnaniPrismaStream(settings, "en-IN", None, None)
    stream.ws = FakeSocket()
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("app.providers.prisma_stream.asyncio.sleep", sleep)
    await stream.drain()
    assert json.loads(stream.ws.sent[0]) == {"type": "commit"}
    assert sleeps == [3]
    await stream.close()


async def test_missing_credentials(settings):
    with pytest.raises(ServiceError, match="UNCONFIGURED_PROVIDER"):
        await GnaniPrismaStream(settings, "en-IN", None, None).start()


async def test_mock_audio_emits_one_labeled_fixture(settings):
    turns = []

    async def on_turn(turn):
        turns.append(turn)

    stream = MockPrismaStream(settings, "en-IN", on_turn, None)
    for _ in range(64):
        await stream.send(b"\0" * 1024)
    assert len(turns) == 1


def test_acoustic_measurements_are_not_fraud_scores():
    metrics = AcousticMetrics()
    metrics.add(b"\0" * 1024)
    value = metrics.view()
    assert value["durationMs"] == 32 and value["rmsDbfs"] is None
    assert not value["usedByRiskModel"] and not value["fraudInference"]
    assert value["toneInference"] == "not_available"
