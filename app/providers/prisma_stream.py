import asyncio
import hashlib
import json

from app.core.exceptions import ServiceError
from app.schemas.live import LiveTurn


class GnaniPrismaStream:
    """Verified Gnani v2.5 WS protocol. Distinct from legacy REST and SDK private internals."""

    def __init__(self, settings, language, on_turn, on_error):
        self.s, self.language = settings, language
        self.on_turn, self.on_error = on_turn, on_error
        self.ws = self.task = None
        self.ending = False

    async def start(self):
        if not self.s.prisma_enabled or not self.s.gnani_api_key.get_secret_value():
            raise ServiceError("UNCONFIGURED_PROVIDER", "Enable Prisma and configure GNANI_API_KEY.")
        try:
            import websockets

            self.ws = await websockets.connect(
                "wss://api.vachana.ai/stt/v3/stream",
                additional_headers={
                    "x-api-key-id": self.s.gnani_api_key.get_secret_value(),
                    "language_code": self.language,
                    "model": "prisma-v2.5",
                    "format": "verbatim",
                    "x-sample-rate": "16000",
                    "x-min-silence-ms": "400",
                    "x-max-speech-s": str(self.s.live_stt_max_speech_seconds),
                },
                open_timeout=10,
                close_timeout=3,
                max_size=65536,
                max_queue=8,
            )
            first = json.loads(await asyncio.wait_for(self.ws.recv(), 10))
            if first.get("type") != "connected":
                raise ValueError
            self.task = asyncio.create_task(self.receive())
        except ImportError:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Install the gnani dependency extra.") from None
        except Exception:
            await self.close()
            raise ServiceError("STT_UNAVAILABLE", "Prisma streaming connection failed.", 503, True) from None

    async def send(self, frame):
        try:
            await asyncio.wait_for(self.ws.send(frame), 5)
        except Exception:
            raise ServiceError("STT_UNAVAILABLE", "Prisma streaming send failed.", 503, True) from None

    async def receive(self):
        try:
            async for raw in self.ws:
                if not isinstance(raw, str):
                    raise ValueError
                event = json.loads(raw)
                if event.get("type") == "error":
                    raise ValueError
                if event.get("type") == "transcript":
                    text, segment_id = event.get("text"), event.get("segment_id")
                    if not isinstance(text, str) or not text.strip() or not isinstance(segment_id, str):
                        raise ValueError
                    turn_id = "stt_" + hashlib.sha256(segment_id.encode()).hexdigest()[:24]
                    await self.on_turn(LiveTurn(id=turn_id, speaker="unknown", text=text))
            if not self.ending:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.on_error(
                ServiceError(
                    "STT_UNAVAILABLE", "Prisma stream stopped or returned invalid speech data.", 503, True
                )
            )

    async def drain(self):
        # Documented commit closes the utterance. No final-commit acknowledgement exists in v2.5.
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.send('{"type":"commit"}'), 5)
                await asyncio.sleep(3)
            except Exception:
                raise ServiceError(
                    "STT_UNAVAILABLE", "Could not commit final speech segment.", 503, True
                ) from None

    async def close(self):
        self.ending = True
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.close(), 5)
            except Exception:
                pass


class MockPrismaStream:
    def __init__(self, settings, language, on_turn, on_error):
        self.on_turn, self.frames, self.issued = on_turn, 0, False

    async def start(self):
        pass

    async def send(self, frame):
        self.frames += 1
        if self.frames >= 32 and not self.issued:
            self.issued = True
            await self.on_turn(LiveTurn(id="mock_segment_1", speaker="unknown", text="Tell me your OTP now."))

    async def drain(self):
        pass

    async def close(self):
        pass
