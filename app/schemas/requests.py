from pydantic import BaseModel, ConfigDict, Field

INPUT_LANGUAGES = [
    "auto",
    "en-IN",
    "hi-IN",
    "hi-Latn",
    "ta-IN",
    "te-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "bn-IN",
    "gu-IN",
    "pa-IN",
]
STT_LANGUAGES = [x for x in INPUT_LANGUAGES if x not in ("auto", "hi-Latn")]


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=64)
    speaker: str = Field(max_length=64)
    text: str = Field(max_length=3000)


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript: str = Field(min_length=1, max_length=3000)
    inputLanguage: str = Field("auto", max_length=20)
    warningLanguage: str = Field("en-IN", max_length=20, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    includeRuleIndicators: bool = True
    turns: list[Turn] = Field(default_factory=list, max_length=100)


class WarningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field("en-IN", max_length=20, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    voice: str | None = Field(None, max_length=64)
