import time
from dataclasses import dataclass, field

from app.core.exceptions import ServiceError


@dataclass
class Entry:
    owner: str
    expires: float
    report: object = None
    error: dict | None = None
    audio: dict = field(default_factory=dict)
    status: str = "QUEUED"


class ReportStore:
    """Single-process bounded non-durable store. Never indexed by untrusted tenant headers."""

    def __init__(self, settings, clock=time.monotonic):
        self.s, self.clock, self.entries = settings, clock, {}

    def purge(self):
        now = self.clock()
        for key in list(self.entries):
            entry = self.entries[key]
            if entry.expires <= now:
                del self.entries[key]
            else:
                entry.audio = {k: v for k, v in entry.audio.items() if v[0] > now}

    def create(self, analysis_id, owner):
        self.purge()
        if len(self.entries) >= self.s.max_reports:
            raise ServiceError(
                "RATE_LIMITED", "Result storage is full; retry after results expire.", 429, True
            )
        self.entries[analysis_id] = Entry(owner, self.clock() + self.s.report_ttl_seconds)

    def get(self, analysis_id, owner):
        self.purge()
        entry = self.entries.get(analysis_id)
        if entry is None or entry.owner != owner:
            raise ServiceError("NOT_FOUND", "Analysis not found or expired.", 404)
        return entry

    def cache_audio(self, entry, key, audio):
        self.purge()
        budget = self.s.max_cached_audio_mb * 1024 * 1024
        cached = [
            (value[0], other, other_key, len(value[1].data))
            for other in self.entries.values()
            for other_key, value in other.audio.items()
        ]
        used = sum(item[3] for item in cached)
        # Evict earliest-expiring cached warnings, preserving all classification reports.
        for _, other, other_key, size in sorted(cached, key=lambda item: item[0]):
            if used + len(audio.data) <= budget:
                break
            del other.audio[other_key]
            used -= size
        entry.audio[key] = (self.clock() + self.s.warning_audio_ttl_seconds, audio)
