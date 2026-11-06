import asyncio
import json
from pathlib import Path

from app.core.exceptions import ServiceError
from app.providers.gnani_timbre import GnaniTimbreProvider
from app.services.warnings import select_warning
from scripts.real_common import real_settings


async def main():
    settings = real_settings()
    warning = select_warning("HIGH_RISK", "en-IN")
    provider = GnaniTimbreProvider(settings)
    try:
        audio = await provider.synthesize(warning.text, "en-IN", "Kaveri")
    except ServiceError as exc:
        print(f"{exc.code}: {exc.message}")
        diagnostics = getattr(provider, "last_audio_diagnostics", None)
        if diagnostics:
            print("Audio diagnostics (metadata only): " + json.dumps(diagnostics, sort_keys=True))
        raise SystemExit(1) from None
    Path("warning-smoke.wav").write_bytes(audio.data)
    print(f"Real Timbre wrote warning-smoke.wav ({len(audio.data)} bytes); mock={audio.mock}.")


if __name__ == "__main__":
    asyncio.run(main())
