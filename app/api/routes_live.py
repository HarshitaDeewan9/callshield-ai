import asyncio
import json
import time

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.auth import owner_for_key
from app.core.exceptions import ServiceError
from app.core.rate_limits import limited
from app.providers.evon_assessment import select_window
from app.schemas.live import DetailedRequest, LiveTurn, SessionRequest

router = APIRouter(prefix="/api/v2")


def enabled(state):
    if not state.settings.live_enabled:
        raise ServiceError("UNCONFIGURED_PROVIDER", "Live assessment is disabled.")


def check_turn_ids(turns):
    if len({t.id for t in turns}) != len(turns):
        raise ServiceError("INVALID_INPUT", "Turn IDs must be unique.", 422)


@router.post("/analyze/text")
async def detailed_analysis(body: DetailedRequest, request: Request, owner: str = Depends(limited)):
    enabled(request.app.state)
    check_turn_ids(body.turns)
    result = await request.app.state.risk_assessor.assess(
        [t.model_dump() for t in body.turns], explanation_language=body.explanationLanguage
    )
    return {
        "status": "COMPLETED",
        "assessment": result,
        "mock": result["mock"],
        "inputLanguage": body.inputLanguage,
        "languageSource": "user",
        "translationApplied": False,
    }


@router.post("/sessions", status_code=201)
async def create_session(body: SessionRequest, request: Request, owner: str = Depends(limited)):
    state = request.app.state
    enabled(state)
    if not state.settings.mock_mode:
        select_window([{"id": "probe", "speaker": "unknown", "text": "Hello"}], state.settings)
    if body.inputMode == "audio" and (
        not state.settings.prisma_enabled
        or (not state.settings.mock_mode and not state.settings.gnani_api_key.get_secret_value())
    ):
        raise ServiceError(
            "UNCONFIGURED_PROVIDER", "Enable Prisma and configure its credentials for live audio."
        )
    session = state.live_sessions.create(owner, body)
    return {
        **session.snapshot(),
        "mock": state.settings.mock_mode,
        "websocketPath": f"/api/v2/sessions/{session.id}/stream",
        "audioFormat": {
            "encoding": "pcm_s16le",
            "sampleRate": 16000,
            "channels": 1,
            "frameBytes": 1024,
            "frameIntervalMs": 32,
        }
        if body.inputMode == "audio"
        else None,
    }


@router.get("/sessions/{session_id}")
async def session_status(session_id: str, request: Request, owner: str = Depends(limited)):
    enabled(request.app.state)
    session = request.app.state.live_sessions.get(session_id, owner)
    return {
        **session.snapshot(),
        "history": list(session.history),
        "turns": session.turns,
        "mock": request.app.state.settings.mock_mode,
    }


@router.post("/sessions/{session_id}/turns", status_code=202)
async def append_turn(session_id: str, body: LiveTurn, request: Request, owner: str = Depends(limited)):
    enabled(request.app.state)
    session = request.app.state.live_sessions.get(session_id, owner)
    if session.request.inputMode != "text":
        raise ServiceError("INVALID_INPUT", "Audio sessions accept transcripts only from Prisma.", 409)
    await request.app.state.live_sessions.append(session, body)
    return {"sessionId": session.id, "inputRevision": session.revision, "status": "ACCEPTED"}


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, request: Request, owner: str = Depends(limited)):
    enabled(request.app.state)
    session = request.app.state.live_sessions.get(session_id, owner)
    if session.connected:
        raise ServiceError(
            "INVALID_INPUT", "Send end on the connected WebSocket to drain speech safely.", 409
        )
    await request.app.state.live_sessions.finish(session)
    return session.snapshot()


@router.websocket("/sessions/{session_id}/stream")
async def stream(session_id: str, ws: WebSocket):
    state, tasks, provider, session = ws.app.state, [], None, None
    try:
        enabled(state)
        # Browser clients must go through Spring. No query-string credentials, no cross-origin sockets.
        if ws.headers.get("origin"):
            raise ServiceError("UNAUTHORIZED", "Use the authenticated Spring WebSocket proxy.", 403)
        owner = owner_for_key(state.settings, ws.headers.get("x-api-key"))
        session = state.live_sessions.get(session_id, owner)
        if session.connected or session.closed or session.closing:
            raise ServiceError("INVALID_INPUT", "Session is already connected or closed.", 409)
    except ServiceError:
        await ws.close(code=1008)
        return
    session.connected = True
    await ws.accept()

    async def on_turn(turn):
        await state.live_sessions.append(
            session, turn, "mock-prisma-stream" if state.settings.mock_mode else "gnani-prisma-stream"
        )

    async def on_error(error):
        await state.live_sessions.fail_stt(session, error)

    async def sender():
        while True:
            state.live_sessions.purge()
            try:
                event = await asyncio.wait_for(session.events.get(), 1)
            except TimeoutError:
                event = {"type": "closed" if session.closed else "status", **session.snapshot()}
            await asyncio.wait_for(ws.send_json(event), 5)
            if event["type"] == "closed":
                await ws.close(code=1000)
                return

    async def receiver():
        started, sent_bytes = time.monotonic(), 0
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                frame = message["bytes"]
                if session.request.inputMode != "audio" or len(frame) != 1024:
                    raise ServiceError(
                        "INVALID_INPUT", "Audio frames must be exactly 1024 bytes of mono 16 kHz PCM16.", 422
                    )
                sent_bytes += len(frame)
                if sent_bytes > (time.monotonic() - started) * 32000 + 8192:
                    raise ServiceError(
                        "RATE_LIMITED", "Send audio at real-time cadence (32 ms per frame).", 429, True
                    )
                if session.stt_failed:
                    raise ServiceError(
                        "STT_UNAVAILABLE", "Reconnect using a new session after speech failure."
                    )
                session.acoustic.add(frame)
                await provider.send(frame)
                continue
            raw = message.get("text", "")
            if len(raw.encode("utf-8")) > 8192:
                raise ServiceError("UPLOAD_TOO_LARGE", "Live control message is too large.", 413)
            try:
                command = json.loads(raw)
                if not isinstance(command, dict):
                    raise ValueError
                kind = command.get("type")
                if kind == "turn" and session.request.inputMode == "text":
                    turn = LiveTurn.model_validate({k: v for k, v in command.items() if k != "type"})
                    await state.live_sessions.append(session, turn)
                elif kind == "end" and set(command) == {"type"}:
                    if provider:
                        await provider.drain()
                        await provider.close()
                    await state.live_sessions.finish(session)
                    return
                else:
                    raise ValueError
            except (ValueError, ValidationError, UnicodeError):
                raise ServiceError(
                    "INVALID_INPUT", "Use a valid turn message or an end control message.", 422
                ) from None

    try:
        await ws.send_json({"type": "ready", **session.snapshot(), "mock": state.settings.mock_mode})
        if session.request.inputMode == "audio":
            provider = state.prisma_stream_factory(
                state.settings, session.request.inputLanguage, on_turn, on_error
            )
            await provider.start()
            await ws.send_json(
                {"type": "audio_ready", "sessionId": session.id, "mock": state.settings.mock_mode}
            )
        tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        # Normal end: give the sender a chance to deliver final risk + closed.
        if session.closed and not tasks[0].done():
            await asyncio.wait_for(asyncio.shield(tasks[0]), 5)
    except (WebSocketDisconnect, OSError, TimeoutError):
        pass
    except ServiceError as exc:
        try:
            await ws.send_json(
                {
                    "type": "error",
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "sessionId": session.id,
                }
            )
            await ws.close(code=1011)
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if provider:
            await provider.close()
        session.connected = False
        if not session.closed:
            session.task.cancel()
            await asyncio.gather(session.task, return_exceptions=True)
        session.closed = True
        try:
            await asyncio.wait_for(ws.close(code=1000), 3)
        except (RuntimeError, OSError, TimeoutError):
            pass
