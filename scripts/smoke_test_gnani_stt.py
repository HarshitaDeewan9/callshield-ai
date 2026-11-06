import argparse
import asyncio
import tempfile
from pathlib import Path

from app.providers.gnani_prisma import GnaniPrismaProvider
from app.services.audio_utils import prepare_audio
from scripts.real_common import real_settings


async def main():
    settings = real_settings()
    parser = argparse.ArgumentParser(description="Use only an audio clip you have consent to process.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--language", default="en-IN")
    parser.add_argument("--consent", action="store_true", required=True)
    args = parser.parse_args()
    if args.path.stat().st_size > settings.max_audio_mb * 1024 * 1024:
        raise SystemExit("Clip exceeds upload limit")
    with tempfile.TemporaryDirectory(prefix="callshield-smoke-") as directory:
        path, _ = await prepare_audio(args.path.read_bytes(), directory, settings)
        result = await GnaniPrismaProvider(settings).transcribe(path, args.language)
    print(f"Real Prisma succeeded; transcript characters={len(result['text'])}; mock={result['mock']}.")


if __name__ == "__main__":
    asyncio.run(main())
