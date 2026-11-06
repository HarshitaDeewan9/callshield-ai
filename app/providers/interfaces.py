from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Classification:
    code: str
    provider: str
    mock: bool = False


@dataclass
class NormalizedText:
    text: str
    language: str
    provider: str
    applied: bool = False
    mock: bool = False


@dataclass
class Audio:
    data: bytes
    mime: str = "audio/wav"
    provider: str = "gnani-timbre"
    mock: bool = False


class Classifier(Protocol):
    async def classify(self, text: str) -> Classification: ...


class PrismaSTTProvider(Protocol):
    async def transcribe(self, path: Path, language: str) -> dict: ...


class TimbreTTSProvider(Protocol):
    async def synthesize(self, text: str, language: str, voice: str) -> Audio: ...


class Translator(Protocol):
    async def normalize(self, text: str, source_language: str, target: str) -> NormalizedText: ...

    async def localize_template(self, template_id: str, target_language: str): ...
