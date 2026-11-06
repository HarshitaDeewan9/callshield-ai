import time

from fastapi import Depends, Request

from app.core.auth import authorize
from app.core.exceptions import ServiceError


async def limited(request: Request, owner: str = Depends(authorize)):
    now = time.monotonic()
    state = request.app.state
    start, count = state.rate.get(owner, (now, 0))
    if now - start >= 60:
        start, count = now, 0
    if count >= state.settings.requests_per_minute:
        raise ServiceError("RATE_LIMITED", "Request limit reached; retry later.", 429, True)
    state.rate[owner] = (start, count + 1)
    return owner
