from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.languages import AUDIO_LANGUAGES, InputLanguage


class AlertPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threshold: int = Field(70, ge=1, le=100)
    resetBelow: int = Field(50, ge=0, le=99)
    cooldownSeconds: float = Field(30, ge=0, le=3600)

    @model_validator(mode="after")
    def hysteresis(self):
        if self.resetBelow >= self.threshold:
            raise ValueError("resetBelow must be less than threshold")
        return self


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: Literal[True]
    inputMode: Literal["text", "audio"] = "text"
    inputLanguage: InputLanguage = "en-IN"
    explanationLanguage: InputLanguage = "en-IN"
    warningLanguage: Literal["en-IN", "hi-IN"] = "en-IN"
    alerts: AlertPolicy = Field(default_factory=AlertPolicy)

    @model_validator(mode="after")
    def audio_language(self):
        if self.inputMode == "audio" and self.inputLanguage not in AUDIO_LANGUAGES:
            raise ValueError("Select a supported Prisma audio language; Odia/Hinglish are text-only")
        return self


class LiveTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    speaker: Literal["caller", "customer", "unknown"] = "unknown"
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def meaningful(cls, value):
        value.encode("utf-8", errors="strict")
        if not any(c.isalpha() for c in value) or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Provide meaningful Unicode speech text")
        return value


class DetailedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputLanguage: InputLanguage = "en-IN"
    explanationLanguage: InputLanguage = "en-IN"
    turns: list[LiveTurn] = Field(min_length=1, max_length=200)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turnId: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=180)


class ModelAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: StrictInt = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=300)
    scenario: Literal[
        "credential_theft",
        "impersonation",
        "financial_coercion",
        "emergency_scam",
        "remote_access",
        "investment_scam",
        "other",
        "none",
        "unclear",
    ]
    evidence: list[Evidence] = Field(min_length=1, max_length=3)
