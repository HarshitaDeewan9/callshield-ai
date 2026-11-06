import importlib.util
import shutil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.auth import authorize

router = APIRouter()


def sdk_available():
    return importlib.util.find_spec("gnani") is not None


@router.get("/health/live")
async def live():
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request, owner: str = Depends(authorize)):
    state, components = request.app.state, {}
    s = state.settings
    components["evon"] = "ready" if await state.pipeline.classifier.ready() else "unavailable"
    for name, enabled in (("prisma", s.prisma_enabled), ("timbre", s.timbre_enabled)):
        components[name] = (
            "disabled"
            if not enabled
            else "mock"
            if s.mock_mode
            else "configured_not_probed"
            if s.gnani_api_key.get_secret_value() and sdk_available()
            else "unconfigured"
        )
    components["audio_tools"] = (
        "ready"
        if all(shutil.which(p) for p in (s.ffmpeg_path, s.ffprobe_path))
        else ("mock_wav_only" if s.mock_mode else "unavailable" if s.prisma_enabled else "disabled")
    )
    components["translation"] = (
        "identity"
        if s.translation_provider == "identity"
        else (
            "mock" if s.mock_mode else "configured_not_probed" if s.google_cloud_project else "unconfigured"
        )
    )
    ok = not any(v in ("unavailable", "unconfigured") for v in components.values())
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "components": components, "mock": s.mock_mode},
        status_code=200 if ok else 503,
    )
