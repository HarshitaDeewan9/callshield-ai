import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from app.core.exceptions import ServiceError
from app.services.acoustics import AcousticMetrics
from app.services.alerts import ThresholdAlerts
from app.services.warnings import select_warning


@dataclass
class LiveSession:
    id: str
    owner: str
    request: object
    expires: float
    mock: bool = False
    turns: list = field(default_factory=list)
    revision: int = 0
    processed_revision: int = 0
    assessed_revision: int = 0
    result: dict | None = None
    error: dict | None = None
    peak: int | None = None
    closing: bool = False
    closed: bool = False
    connected: bool = False
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    history: object = None
    events: object = None
    alerts: object = None
    task: object = None
    acoustic: object = field(default_factory=AcousticMetrics)
    stt_failed: bool = False
    last_turn_at: float = 0
    assessed_at: float | None = None

    def snapshot(self):
        return {
            "sessionId": self.id,
            "mock": self.mock,
            "status": "CLOSED" if self.closed else "ENDING" if self.closing else "ACTIVE",
            "inputMode": self.request.inputMode,
            "inputLanguage": self.request.inputLanguage,
            "explanationLanguage": self.request.explanationLanguage,
            "languageSource": "user",
            "translationApplied": False,
            "inputRevision": self.revision,
            "assessedRevision": self.assessed_revision,
            "riskStatus": "UNDETERMINED"
            if self.error
            else "ASSESSED"
            if self.result
            else "WAITING_FOR_EVIDENCE",
            "stale": self.assessed_revision != self.revision or self.error is not None,
            "assessmentAgeMs": round((time.monotonic() - self.assessed_at) * 1000)
            if self.assessed_at
            else None,
            "assessment": self.result,
            "peakScore": self.peak,
            "error": self.error,
            "alerts": self.request.alerts.model_dump(),
            "acoustics": self.acoustic.view(),
            "scoreChangesRequireNewEvidence": True,
            "sttFinalization": "best_effort_commit_drain" if self.request.inputMode == "audio" else None,
        }


class LiveSessions:
    def __init__(self, settings, assessor):
        self.s, self.assessor, self.entries = settings, assessor, {}

    def purge(self):
        now = time.monotonic()
        for key in list(self.entries):
            session = self.entries[key]
            if now >= session.expires:
                session.closed = True
                session.task.cancel()
                del self.entries[key]

    def create(self, owner, request):
        self.purge()
        if len(self.entries) >= self.s.live_max_sessions:
            raise ServiceError("RATE_LIMITED", "Live session capacity reached.", 429, True)
        session = LiveSession(
            str(uuid.uuid4()), owner, request, time.monotonic() + self.s.live_session_seconds
        )
        session.history = deque(maxlen=self.s.live_history_size)
        session.mock = self.s.mock_mode
        session.events = asyncio.Queue(maxsize=self.s.live_event_queue_size)
        session.alerts = ThresholdAlerts(request.alerts)
        self.entries[session.id] = session
        session.task = asyncio.create_task(self.worker(session))
        return session

    def get(self, session_id, owner):
        self.purge()
        session = self.entries.get(session_id)
        if session is None or session.owner != owner:
            raise ServiceError("NOT_FOUND", "Live session not found or expired.", 404)
        return session

    def emit(self, session, event):
        event = {**event, "sessionId": session.id}
        if session.events.full():
            session.events.get_nowait()
        session.events.put_nowait(event)

    async def append(self, session, turn, provider="client_transcript"):
        if session.closing or session.closed:
            raise ServiceError("INVALID_INPUT", "Session is closing or closed.", 409)
        for old in session.turns:
            if old["id"] == turn.id:
                if {k: old[k] for k in ("id", "speaker", "text")} == turn.model_dump():
                    return
                raise ServiceError("INVALID_INPUT", "A turn ID cannot be reused with different text.", 409)
        if len(session.turns) >= self.s.live_max_turns:
            raise ServiceError("SESSION_LIMIT", "Live session turn limit reached; finish this session.", 422)
        now = time.monotonic()
        if now - session.last_turn_at < 0.05:
            raise ServiceError("RATE_LIMITED", "Send at most 20 completed turns per second.", 429, True)
        session.last_turn_at = now
        session.turns.append({**turn.model_dump()})
        session.revision += 1
        self.emit(
            session,
            {
                "type": "transcript",
                "turn": turn.model_dump(),
                "revision": session.revision,
                "provider": provider,
                "mock": self.s.mock_mode and provider != "client_transcript",
            },
        )
        session.changed.set()

    async def fail_stt(self, session, error):
        session.stt_failed = True
        session.error = {"code": error.code, "message": error.message, "retryable": error.retryable}
        self.emit(session, {"type": "error", **session.error, "stage": "stt"})

    async def worker(self, session):
        previous_start = float("-inf")
        try:
            while not session.closed:
                await session.changed.wait()
                session.changed.clear()
                if session.processed_revision == session.revision:
                    if session.closing:
                        break
                    continue
                await asyncio.sleep(
                    max(0, self.s.live_checkpoint_seconds - (time.monotonic() - previous_start))
                )
                previous_start = time.monotonic()
                revision, turns = session.revision, list(session.turns)
                self.emit(session, {"type": "classifying", "revision": revision})
                try:
                    result = (
                        await self.assessor.assess(turns)
                        if session.request.explanationLanguage == "en-IN"
                        else await self.assessor.assess(
                            turns, explanation_language=session.request.explanationLanguage
                        )
                    )
                    session.result, session.assessed_revision = result, revision
                    session.assessed_at = time.monotonic()
                    session.peak = max(session.peak or 0, result["score"])
                    if not session.stt_failed:
                        session.error = None
                    checkpoint = {"revision": revision, **result}
                    session.history.append(checkpoint)
                    self.emit(session, {"type": "risk", **session.snapshot()})
                    # Do not alert on an already obsolete window or after STT failure.
                    if revision == session.revision and not session.stt_failed:
                        alert = session.alerts.observe(result["score"])
                        if alert:
                            warning = select_warning(
                                "HIGH_RISK" if result["score"] >= 60 else "SUSPICIOUS",
                                session.request.warningLanguage,
                            )
                            self.emit(
                                session,
                                {
                                    **alert,
                                    "revision": revision,
                                    "band": result["band"],
                                    "warning": warning.model_dump(),
                                    "mock": result["mock"],
                                },
                            )
                except ServiceError as exc:
                    session.error = {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
                    self.emit(
                        session,
                        {"type": "error", **session.error, "stage": "assessment", "revision": revision},
                    )
                except Exception:
                    session.error = {
                        "code": "INTERNAL_ERROR",
                        "message": "Live assessment failed.",
                        "retryable": False,
                    }
                    self.emit(session, {"type": "error", **session.error, "stage": "assessment"})
                session.processed_revision = revision
                if session.closing and revision == session.revision:
                    break
            session.closed = True
            self.emit(session, {"type": "closed", **session.snapshot()})
        except asyncio.CancelledError:
            session.closed = True
            raise

    async def finish(self, session):
        session.closing = True
        session.changed.set()
        try:
            await asyncio.wait_for(asyncio.shield(session.task), self.s.evon_timeout_seconds + 10)
        except TimeoutError:
            session.task.cancel()
            session.closed = True
            raise ServiceError("TIMEOUT", "Final live checkpoint timed out.", 504, True) from None

    async def shutdown(self):
        tasks = [s.task for s in self.entries.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.entries.clear()
