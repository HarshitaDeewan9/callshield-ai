import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api import (
    routes_analysis,
    routes_audio,
    routes_capabilities,
    routes_health,
    routes_live,
    routes_studio,
)
from app.config import Settings
from app.core.auth import authorize
from app.core.exceptions import ServiceError
from app.core.logging import configure_logging
from app.providers.evon_assessment import EvonRiskAssessor, MockRiskAssessor
from app.providers.evon_llamacpp import EvonLlamaCppProvider
from app.providers.gnani_prisma import GnaniPrismaProvider
from app.providers.gnani_timbre import GnaniTimbreProvider
from app.providers.google_translation import GoogleCloudTranslator
from app.providers.identity_translation import IdentityTranslator
from app.providers.mock_providers import (
    MockEvonProvider,
    MockPrismaProvider,
    MockTimbreProvider,
    MockTranslator,
)
from app.providers.prisma_stream import GnaniPrismaStream, MockPrismaStream
from app.schemas.responses import ErrorResponse
from app.services.live_sessions import LiveSessions
from app.services.pipeline import Pipeline
from app.services.report_store import ReportStore


class BodyLimitMiddleware:
    """Bound streamed request bodies before multipart parsing/spooling."""

    def __init__(self, app, settings):
        self.app, self.s = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = (
            self.s.max_audio_mb * 1024 * 1024 + 65536 if scope["path"].endswith("/analyze/audio") else 65536
        )
        chunks, total = [], 0
        deadline = asyncio.get_running_loop().time() + 120
        # Buffer only the bounded body; unknown/chunked lengths cannot bypass the cap.
        while True:
            try:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                message = await asyncio.wait_for(receive(), min(30, remaining))
            except TimeoutError:
                response = JSONResponse(
                    ServiceError("TIMEOUT", "Request upload stalled.", 504).body(self.s.mock_mode),
                    status_code=504,
                )
                return await response(scope, receive, send)
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > limit:
                response = JSONResponse(
                    ServiceError("UPLOAD_TOO_LARGE", "Request body exceeds limit.", 413).body(
                        self.s.mock_mode
                    ),
                    status_code=413,
                )
                return await response(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def bounded_receive():
            nonlocal index
            if index < len(chunks):
                msg = chunks[index]
                index += 1
                return msg
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(settings=None, http_client=None):
    s = settings or Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(application):
        client = http_client or httpx.AsyncClient(
            follow_redirects=False, trust_env=False, limits=httpx.Limits(max_connections=8)
        )
        store = ReportStore(s)
        if s.mock_mode:
            classifier, stt, tts = MockEvonProvider(), MockPrismaProvider(), MockTimbreProvider()
            translator = MockTranslator() if s.translation_provider == "google" else IdentityTranslator()
        else:
            classifier, stt, tts = (
                EvonLlamaCppProvider(s, client),
                GnaniPrismaProvider(s),
                GnaniTimbreProvider(s),
            )
            translator = (
                GoogleCloudTranslator(s) if s.translation_provider == "google" else IdentityTranslator()
            )
        application.state.pipeline = Pipeline(s, store, classifier, translator, stt, tts)
        application.state.store = store
        application.state.rate = {}
        application.state.risk_assessor = (
            MockRiskAssessor() if s.mock_mode else EvonRiskAssessor(s, classifier)
        )
        application.state.live_sessions = LiveSessions(s, application.state.risk_assessor)
        application.state.prisma_stream_factory = MockPrismaStream if s.mock_mode else GnaniPrismaStream

        async def expire_results():
            while True:
                await asyncio.sleep(min(30, s.report_ttl_seconds, s.warning_audio_ttl_seconds))
                store.purge()
                application.state.live_sessions.purge()

        cleanup = asyncio.create_task(expire_results())
        try:
            yield
        finally:
            cleanup.cancel()
            try:
                await cleanup
            except asyncio.CancelledError:
                pass
            store.entries.clear()
            await application.state.live_sessions.shutdown()
            if http_client is None:
                await client.aclose()
            if isinstance(translator, GoogleCloudTranslator) and translator.client is not None:
                translator.client.transport.close()

    app = FastAPI(
        title="CallShield India AI Service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        responses={
            code: {"model": ErrorResponse} for code in (401, 404, 409, 413, 415, 422, 429, 502, 503, 504)
        },
    )
    app.state.settings = s
    app.add_middleware(BodyLimitMiddleware, settings=s)

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse(
            exc.body(s.mock_mode), status_code=exc.status, headers={"Cache-Control": "no-store"}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic errors include user input; never serialize those into errors/logs.
        error = ServiceError("INVALID_INPUT", "Request fields are missing or invalid.", 422)
        return JSONResponse(error.body(s.mock_mode), status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        error = ServiceError(
            "NOT_FOUND" if exc.status_code == 404 else "INVALID_INPUT",
            "Route not found." if exc.status_code == 404 else "HTTP request rejected.",
            exc.status_code,
        )
        return JSONResponse(error.body(s.mock_mode), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse(
            ServiceError("INTERNAL_ERROR", "Unexpected service failure.", 500).body(s.mock_mode),
            status_code=500,
        )

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/openapi.json", include_in_schema=False)
    async def schema(owner: str = Depends(authorize)):
        return app.openapi()

    @app.get("/docs", include_in_schema=False)
    async def docs(owner: str = Depends(authorize)):
        return get_swagger_ui_html(openapi_url="/openapi.json", title=app.title)

    for router in (
        routes_analysis.router,
        routes_audio.router,
        routes_health.router,
        routes_capabilities.router,
        routes_live.router,
        routes_studio.router,
    ):
        app.include_router(router)
    return app


app = create_app()
