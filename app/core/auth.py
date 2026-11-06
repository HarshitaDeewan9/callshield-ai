import hashlib
import secrets

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.exceptions import ServiceError

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def authorize(request: Request, api_key: str | None = Depends(api_key_header)):
    return owner_for_key(request.app.state.settings, api_key)


def owner_for_key(settings, api_key):
    expected = settings.app_api_key.get_secret_value()
    if expected and (not api_key or not secrets.compare_digest(api_key.encode(), expected.encode())):
        raise ServiceError("UNAUTHORIZED", "Valid backend API key required.", 401)
    # Single trusted backend principal. Spring must enforce end-user ownership itself.
    return hashlib.sha256((expected or "local-mock-development").encode()).hexdigest()
