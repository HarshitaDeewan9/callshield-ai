import asyncio
import json

import httpx
import pytest

from app.core.exceptions import ServiceError
from app.providers.evon_assessment import EvonRiskAssessor
from app.providers.evon_llamacpp import EvonLlamaCppProvider


async def test_v1_and_v2_share_one_admission_gate(settings):
    settings.evon_context_tokens = 4096
    settings.evon_queue_size = 0
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        await release.wait()
        body = json.loads(request.content)
        assert body["max_tokens"] == 8
        return httpx.Response(200, json={"choices": [{"message": {"content": "A"}, "finish_reason": "stop"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        evon = EvonLlamaCppProvider(settings, client)
        assessor = EvonRiskAssessor(settings, evon)
        legacy = asyncio.create_task(evon.classify("Tell me your OTP now."))
        await entered.wait()
        with pytest.raises(ServiceError, match="RATE_LIMITED"):
            await assessor.assess([{"id": "t1", "speaker": "caller", "text": "Hello"}])
        assert evon.outstanding == 1
        release.set()
        assert (await legacy).code == "A"
        assert evon.outstanding == 0
