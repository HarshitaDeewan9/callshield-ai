import asyncio

import anyio

from app.core.exceptions import ServiceError


class GnaniAdapter:
    def __init__(self, settings, client=None):
        self.s, self.client = settings, client
        self.limiter = anyio.CapacityLimiter(2)
        self.slots = asyncio.Semaphore(2)
        self.pending = 0

    async def invoke(self, callback, stage):
        if not self.s.gnani_api_key.get_secret_value() and self.client is None:
            raise ServiceError(
                "UNCONFIGURED_PROVIDER", "Set GNANI_API_KEY and install the gnani dependency extra."
            )
        if self.pending >= 6:
            raise ServiceError("RATE_LIMITED", "Speech provider queue is full.", 429, True)
        self.pending += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(self.slots.acquire(), 5)
                acquired = True
            except TimeoutError:
                raise ServiceError("RATE_LIMITED", "Speech queue wait expired.", 429, True) from None
            return await anyio.to_thread.run_sync(callback, limiter=self.limiter)
        except ImportError:
            raise ServiceError("UNCONFIGURED_PROVIDER", "Install callshield-ai[gnani].") from None
        except ServiceError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status == 429:
                raise ServiceError("RATE_LIMITED", "Speech provider quota exceeded.", 429, True) from None
            if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
                raise ServiceError("TIMEOUT", "Speech provider timed out.", 504, True) from None
            raise ServiceError(
                f"{stage}_UNAVAILABLE",
                "Speech provider request failed.",
                503,
                status not in (400, 401, 403, 422),
            ) from None
        finally:
            if acquired:
                self.slots.release()
            self.pending -= 1
