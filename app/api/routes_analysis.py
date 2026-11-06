from fastapi import APIRouter, Depends, Request

from app.core.rate_limits import limited
from app.schemas.requests import TextRequest
from app.schemas.responses import Report

router = APIRouter(prefix="/api/v1")


@router.post("/analyze/text", response_model=Report)
async def analyze_text(body: TextRequest, request: Request, owner: str = Depends(limited)):
    return await request.app.state.pipeline.analyze(body, owner)


@router.get("/analyses/{analysis_id}", response_model=None)
async def get_analysis(analysis_id: str, request: Request, owner: str = Depends(limited)):
    entry = request.app.state.store.get(analysis_id, owner)
    return (
        entry.report
        if entry.report
        else entry.error
        or {"analysisId": analysis_id, "status": entry.status, "mock": request.app.state.settings.mock_mode}
    )
