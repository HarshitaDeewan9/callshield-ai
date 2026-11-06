"""Exercise live text or paced PCM audio against a running server; real calls require opt-in."""

import argparse
import asyncio
import json
import os
import wave
from pathlib import Path

import httpx
import websockets

from app.config import Settings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--language", default="en-IN", choices=["en-IN", "hi-IN", "hi-Latn"])
    args = parser.parse_args()
    settings = Settings()
    headers = {"X-API-Key": settings.app_api_key.get_secret_value()}
    base = args.base_url.rstrip("/")
    async with httpx.AsyncClient(base_url=base, headers=headers, trust_env=False, timeout=30) as client:
        response = await client.get("/api/v1/capabilities")
        response.raise_for_status()
        mock = response.json()["mockMode"]
        if not mock and os.getenv("RUN_REAL_INTEGRATION", "").lower() != "true":
            raise SystemExit("Set RUN_REAL_INTEGRATION=true to permit live provider requests.")
        audio = None
        if args.audio:
            audio = wave.open(str(args.audio), "rb")
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                audio.close()
                raise SystemExit("Use mono 16-bit PCM WAV at 16000 Hz; convert the clip with ffmpeg first.")
            if not 0 < audio.getnframes() / 16000 <= 900:
                audio.close()
                raise SystemExit("Use a nonempty clip no longer than 15 minutes.")
        response = await client.post(
            "/api/v2/sessions",
            json={
                "consent": True,
                "inputMode": "audio" if audio else "text",
                "inputLanguage": args.language,
                "alerts": {"threshold": 70, "resetBelow": 50, "cooldownSeconds": 30},
            },
        )
        if response.status_code != 201:
            if audio:
                audio.close()
            print(response.text)
            raise SystemExit(1)
        session = response.json()
        print(f"Session {session['sessionId']}; mock={mock}")
        url = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + session["websocketPath"]
        async with websockets.connect(url, additional_headers=headers, max_size=65536) as ws:
            first = json.loads(await ws.recv())
            if first["type"] != "ready":
                raise SystemExit("Expected ready event")
            if audio:
                first = json.loads(await ws.recv())
                if first["type"] != "audio_ready":
                    print(first.get("code", "STT_UNAVAILABLE"))
                    audio.close()
                    raise SystemExit(1)
            state = {"revision": 0, "error": None}
            changed = asyncio.Condition()

            async def receive():
                async for raw in ws:
                    event = json.loads(raw)
                    kind = event["type"]
                    if kind == "risk":
                        result = event["assessment"]
                        print(
                            f"risk revision={event['assessedRevision']} score={result['score']} "
                            f"band={result['band']} stale={event['stale']} mock={result['mock']}"
                        )
                        async with changed:
                            state["revision"] = event["assessedRevision"]
                            changed.notify_all()
                    elif kind == "alert":
                        print(f"ALERT: threshold {event['threshold']} crossed at score {event['score']}")
                    elif kind == "error":
                        print(f"ERROR: {event['code']}: {event['message']}")
                        async with changed:
                            state["error"] = event["code"]
                            changed.notify_all()
                    elif kind == "closed":
                        print("Session closed")
                        return

            listener = asyncio.create_task(receive())
            try:
                if audio:
                    try:
                        deadline = asyncio.get_running_loop().time()
                        while chunk := audio.readframes(512):
                            await ws.send(chunk.ljust(1024, b"\0"))
                            deadline += 0.032
                            await asyncio.sleep(max(0, deadline - asyncio.get_running_loop().time()))
                    finally:
                        audio.close()
                else:
                    demo = [
                        "Hello, how are you?",
                        "Bank verification pending; I will explain.",
                        "Tell me your OTP now.",
                        "Do not share your OTP with anyone.",
                    ]
                    for revision, text in enumerate(demo, 1):
                        await asyncio.sleep(0.06)
                        await ws.send(
                            json.dumps(
                                {"type": "turn", "id": f"t{revision}", "speaker": "caller", "text": text}
                            )
                        )
                        async with changed:
                            await asyncio.wait_for(
                                changed.wait_for(
                                    lambda target=revision: state["revision"] >= target or state["error"]
                                ),
                                150,
                            )
                        if state["error"]:
                            raise SystemExit(1)
                await ws.send('{"type":"end"}')
                await asyncio.wait_for(listener, 150)
                if state["error"]:
                    raise SystemExit(1)
            finally:
                if not listener.done():
                    listener.cancel()
                    await asyncio.gather(listener, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
