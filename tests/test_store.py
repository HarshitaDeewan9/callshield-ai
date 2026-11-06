import pytest

from app.core.exceptions import ServiceError
from app.services.report_store import ReportStore


def test_ttl_ownership_and_capacity(settings):
    settings.max_reports = 1
    clock = [0]
    store = ReportStore(settings, lambda: clock[0])
    store.create("id", "backend-one")
    with pytest.raises(ServiceError, match="NOT_FOUND"):
        store.get("id", "backend-two")
    with pytest.raises(ServiceError, match="RATE_LIMITED"):
        store.create("new", "backend-one")
    clock[0] = settings.report_ttl_seconds + 1
    with pytest.raises(ServiceError, match="NOT_FOUND"):
        store.get("id", "backend-one")
    store.create("new", "backend-one")


def test_audio_expiry(settings):
    clock = [0]
    store = ReportStore(settings, lambda: clock[0])
    store.create("id", "owner")
    entry = store.get("id", "owner")
    entry.audio["key"] = (1, b"audio")
    clock[0] = 2
    assert not store.get("id", "owner").audio
