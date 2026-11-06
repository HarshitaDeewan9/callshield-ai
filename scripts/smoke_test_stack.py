"""Exercise running LOCAL mock Spring/Python services; never runs against real providers."""

import asyncio
import io
import json
import secrets
import wave

import httpx
import websockets

BASE = "http://127.0.0.1:5173"


async def write(client, path, **kwargs):
    csrf = (await client.get("/api/auth/csrf")).json()
    response = await client.post(path, headers={csrf["headerName"]: csrf["token"]}, **kwargs)
    response.raise_for_status()
    return response


async def account(client):
    token = secrets.token_hex(8)
    await write(
        client,
        "/api/auth/register",
        json={
            "email": f"qa-{token}@example.test",
            "name": "Studio QA",
            "password": secrets.token_urlsafe(24),
        },
    )


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        page = await client.get("/")
        assert page.status_code == 200 and 'id="root"' in page.text
        assert (await client.get("/api/records")).status_code == 401
        await account(client)
        assert (await client.get("/api/capabilities")).json()["mockMode"], (
            "Stop: this smoke test requires MOCK_MODE=true."
        )
        assert (await client.post("/api/analyze/text", json={"transcript": "Hello"})).status_code == 403
        report = (
            await write(
                client,
                "/api/analyze/text",
                json={"transcript": "Caller: Tell me your OTP now.", "inputLanguage": "en-IN"},
            )
        ).json()
        assert report["result"]["assessment"]["score"] == 90 and report["result"]["mock"]
        warning = await write(
            client, f"/api/records/{report['id']}/warning-audio", json={"language": "en-IN"}
        )
        assert warning.content[:4] == b"RIFF" and warning.headers["x-mock"] == "true"
        audio = io.BytesIO()
        with wave.open(audio, "wb") as out:
            out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            out.writeframes(b"\0\0" * 16000)
        uploaded = (
            await write(
                client,
                "/api/analyze/audio",
                files={"file": ("qa.wav", audio.getvalue(), "audio/wav")},
                data={"consent": "true", "inputLanguage": "ta-IN", "explanationLanguage": "hi-IN"},
            )
        ).json()
        assert uploaded["result"]["assessment"]["score"] == 90
        assert uploaded["result"]["inputLanguage"] == "ta-IN"
        assert uploaded["result"]["assessment"]["requestedExplanationLanguage"] == "hi-IN"
        assert uploaded["result"]["assessment"]["explanationLanguage"] == "en-IN"
        async with httpx.AsyncClient(base_url=BASE) as other:
            await account(other)
            assert (await other.get(f"/api/records/{report['id']}")).status_code == 404
        live = (await write(client, "/api/live/sessions", json={"consent": True, "inputMode": "text"})).json()
        cookie = "; ".join(f"{item.name}={item.value}" for item in client.cookies.jar)
        events = []
        async with websockets.connect(
            BASE.replace("http://", "ws://") + live["websocketPath"],
            origin="http://localhost:5173",
            additional_headers={"Cookie": cookie},
        ) as ws:
            assert json.loads(await asyncio.wait_for(ws.recv(), 10))["type"] == "ready"
            csrf = (await client.get("/api/auth/csrf")).json()
            assert (
                await client.delete(
                    "/api/records/" + live["recordId"], headers={csrf["headerName"]: csrf["token"]}
                )
            ).status_code == 409
            await ws.send(
                json.dumps({"type": "turn", "id": "t1", "speaker": "caller", "text": "Tell me your OTP now."})
            )
            while "alert" not in events:
                event = json.loads(await asyncio.wait_for(ws.recv(), 10))
                events.append(event["type"])
                if event["type"] == "error":
                    raise AssertionError(event)
            await ws.send(json.dumps({"type": "end"}))
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), 10))
                if event["type"] == "closed":
                    assert event["assessment"]["score"] == 90
                    break
        persisted = (await client.get("/api/records/" + live["recordId"])).json()
        assert persisted["result"]["assessment"]["score"] == 90
        assert persisted["result"]["history"][0]["score"] == 90
        assert not persisted["result"]["stale"]
        audio_live = (
            await write(client, "/api/live/sessions", json={"consent": True, "inputMode": "audio"})
        ).json()
        async with websockets.connect(
            BASE.replace("http://", "ws://") + audio_live["websocketPath"],
            origin="http://localhost:5173",
            additional_headers={"Cookie": cookie},
        ) as ws:
            while json.loads(await asyncio.wait_for(ws.recv(), 10))["type"] != "audio_ready":
                pass
            for _ in range(40):
                await ws.send(b"\0" * 1024)
                await asyncio.sleep(0.032)
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), 10))
                if event["type"] == "error":
                    raise AssertionError(event)
                if event["type"] == "risk":
                    assert event["assessment"]["score"] == 90
                    break
            await ws.send('{"type":"end"}')
            while json.loads(await asyncio.wait_for(ws.recv(), 10))["type"] != "closed":
                pass
        assert len((await client.get("/api/records")).json()) == 4
        csrf = (await client.get("/api/auth/csrf")).json()
        assert (
            await client.delete("/api/records/" + report["id"], headers={csrf["headerName"]: csrf["token"]})
        ).status_code == 204
        assert (await client.get("/api/records/" + report["id"])).status_code == 404
        print(
            "PASS: authentication, CSRF, text, upload, warning WAV, ownership, live text + paced PCM risk/alert/final persistence, history and deletion. MOCK only."
        )


if __name__ == "__main__":
    asyncio.run(main())
