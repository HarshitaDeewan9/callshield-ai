import asyncio

import httpx

from app.providers.evon_llamacpp import EvonLlamaCppProvider
from scripts.real_common import real_settings


async def main():
    settings = real_settings()
    async with httpx.AsyncClient(trust_env=False) as client:
        provider = EvonLlamaCppProvider(settings, client)
        if not await provider.ready():
            raise SystemExit("Evon unavailable: start EC2 and verify private connectivity/model alias.")
        result = await provider.classify("Caller: Tell me your OTP now.")
        print(f"Real Evon parsed code={result.code}; mock={result.mock}. This is not an accuracy evaluation.")


if __name__ == "__main__":
    asyncio.run(main())
