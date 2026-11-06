from typing import Any, Literal

from pydantic import BaseModel, Field


class Risk(BaseModel):
    code: Literal["A", "B", "C"]
    level: Literal["HIGH_RISK", "SUSPICIOUS", "LOW_RISK"]
    confidence: None = None
    source: str
    model: str
    mock: bool


class Warning(BaseModel):
    available: bool
    templateId: str
    requestedLanguage: str
    language: str
    actualLanguage: str
    text: str
    localizationProvider: str = "curated"
    fallbackApplied: bool = False
    audioStatus: str = "NOT_REQUESTED"
    mock: bool = False


class Report(BaseModel):
    analysisId: str
    status: Literal["COMPLETED"] = "COMPLETED"
    inputType: Literal["TEXT", "AUDIO"] = "TEXT"
    originalTranscript: str
    originalLanguage: str
    detectedLanguage: str
    languageSource: str
    normalizedTranscript: str
    analysisLanguage: str
    normalizationApplied: bool
    normalizedFromOriginal: bool
    normalizationProvider: str
    normalization: dict[str, Any]
    risk: Risk
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    warning: Warning
    transcription: dict[str, Any] | None = None
    timingsMs: dict[str, float | None]
    providers: dict[str, str | None]
    mock: bool


class ErrorResponse(BaseModel):
    error: dict[str, Any]
    analysisId: str | None = None
    status: Literal["FAILED"] = "FAILED"
    mock: bool
