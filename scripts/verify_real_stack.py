"""Opt-in verification of real providers through the authenticated studio gateway.

No default credentials. Prompts for an existing studio account. Never accepts mock results.
"""

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import websockets


def verify_report(report, require_stt=False):
    result = report.get("result", report)
    assessment = result.get("assessment") or {}
    if (
        result.get("mock") is not False
        or assessment.get("mock") is not False
        or assessment.get("source") != "evon"
    ):
        raise ValueError("Not a real Evon result. Mock/undetermined output is rejected.")
    if assessment.get("explanationSource") != "model_generated_summary":
        raise ValueError("Expected a model-generated explanation.")
    transcript = result.get("originalTranscript", "")
    if not assessment.get("evidence") or any(
        item["quote"] not in transcript for item in assessment["evidence"]
    ):
        raise ValueError("Evidence is missing or does not match the original transcript.")
    if require_stt:
        stt = result.get("transcription") or {}
        if stt.get("mock") is not False or stt.get("provider") != "gnani-prisma":
            raise ValueError("Expected real Prisma transcription.")
    return {
        "recordId": report.get("id"),
        "model": assessment.get("model"),
        "source": assessment["source"],
        "mock": False,
        "score": assessment["score"],
        "band": assessment["band"],
        "originalQuoteMatches": True,
        "evidenceQuotes": len(assessment["evidence"]),
        "inputLanguage": result.get("inputLanguage"),
        "requestedExplanationLanguage": assessment.get("requestedExplanationLanguage"),
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-real", action="store_true", help="Explicitly allow provider requests/charges"
    )
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--email", help="Existing studio account; prompts if omitted")
    parser.add_argument("--language", default="hi-IN")
    parser.add_argument("--explanation-language", default="en-IN")
    parser.add_argument("--text", default="कृपया अपना OTP किसी के साथ साझा न करें।")
    parser.add_argument("--audio", type=Path, help="Optional consented clip, <=60 seconds")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument(
        "--tts", action="store_true", help="Also synthesize approved warning audio for an eligible report"
    )
    parser.add_argument(
        "--live", action="store_true", help="Also test incremental text through the live socket"
    )
    args = parser.parse_args()
    if not args.confirm_real:
        parser.error("Pass --confirm-real to explicitly allow real provider calls and possible charges.")
    parsed = urlsplit(args.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        parser.error("Use a valid gateway origin without credentials.")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("Use HTTPS for a remote server or a localhost SSH tunnel.")
    if args.audio and not args.consent:
        parser.error("Audio requires --consent from everyone involved.")
    from app.languages import AUDIO_LANGUAGES, TEXT_LANGUAGES

    if args.language not in TEXT_LANGUAGES or args.explanation_language not in TEXT_LANGUAGES:
        parser.error("Choose supported input and explanation locales from the studio catalog.")
    if not args.text.strip() or len(args.text) > (1000 if args.live else 3000):
        parser.error("Provide a nonempty transcript up to 1000 characters for live, or 3000 for review.")
    if args.audio:
        if args.language not in AUDIO_LANGUAGES:
            parser.error("Choose a Prisma audio locale; Odia/Hinglish are text-only.")
        if (
            not args.audio.is_file()
            or args.audio.suffix.lower() not in (".wav", ".mp3")
            or args.audio.stat().st_size > 15 * 1024 * 1024
        ):
            parser.error("Choose an existing WAV/MP3 clip under 15 MiB.")
    email = args.email or input("Studio email: ").strip()
    password = os.getenv("CALLSHIELD_TEST_PASSWORD") or getpass.getpass("Studio password: ")
    base = args.base_url.rstrip("/")
    async with httpx.AsyncClient(base_url=base, timeout=330, trust_env=False) as client:

        async def post(path, **kwargs):
            csrf = (await client.get("/api/auth/csrf")).json()
            response = await client.post(path, headers={csrf["headerName"]: csrf["token"]}, **kwargs)
            if response.is_error:
                try:
                    error = response.json().get("error", {})
                except ValueError:
                    error = {}
                raise RuntimeError(
                    f"{response.status_code}: {error.get('code', 'REQUEST_FAILED')} {error.get('message', 'Check service readiness.')}"
                )
            return response

        await post("/api/auth/login", json={"email": email, "password": password})
        capabilities = await client.get("/api/capabilities")
        capabilities.raise_for_status()
        if capabilities.json().get("mockMode") is not False:
            raise RuntimeError(
                "Server is MOCK. Stop the mock launcher and start scripts/dev.py --real. No inference was requested."
            )
        ready = await client.get("/api/ready")
        if ready.is_error:
            raise RuntimeError(
                "Provider readiness failed. Check Evon tunnel, SDK, credentials and audio tools. No inference was requested."
            )
        text_report = (
            await post(
                "/api/analyze/text",
                json={
                    "transcript": args.text,
                    "inputLanguage": args.language,
                    "explanationLanguage": args.explanation_language,
                },
            )
        ).json()
        print("TEXT", json.dumps(verify_report(text_report), ensure_ascii=True))
        selected = text_report
        if args.audio:
            if (
                args.audio.suffix.lower() not in (".wav", ".mp3")
                or args.audio.stat().st_size > 15 * 1024 * 1024
            ):
                raise ValueError("Choose a WAV/MP3 clip under 15 MiB.")
            with args.audio.open("rb") as stream:
                selected = (
                    await post(
                        "/api/analyze/audio",
                        files={
                            "file": (
                                "clip" + args.audio.suffix.lower(),
                                stream,
                                "audio/wav" if args.audio.suffix.lower() == ".wav" else "audio/mpeg",
                            )
                        },
                        data={
                            "consent": "true",
                            "inputLanguage": args.language,
                            "explanationLanguage": args.explanation_language,
                        },
                    )
                ).json()
            print("AUDIO", json.dumps(verify_report(selected, require_stt=True)))
        if args.tts:
            if selected["result"]["assessment"]["score"] < 20:
                print(
                    "TTS skipped: this report has minimal risk. Use an eligible suspicious test conversation."
                )
            else:
                audio = await post(
                    "/api/records/" + selected["id"] + "/warning-audio", json={"language": "hi-IN"}
                )
                if audio.headers.get("x-mock") != "false" or audio.content[:4] != b"RIFF":
                    raise ValueError("Expected real Timbre WAV, not a mock tone.")
                print("TTS: real Timbre returned WAV bytes=", len(audio.content))
        if args.live:
            session = (
                await post(
                    "/api/live/sessions",
                    json={
                        "consent": True,
                        "inputMode": "text",
                        "inputLanguage": args.language,
                        "explanationLanguage": args.explanation_language,
                    },
                )
            ).json()
            cookie = "; ".join(f"{c.name}={c.value}" for c in client.cookies.jar)
            socket_url = (
                base.replace("http://", "ws://").replace("https://", "wss://") + session["websocketPath"]
            )
            async with websockets.connect(
                socket_url, origin=base, additional_headers={"Cookie": cookie}
            ) as ws:
                assert json.loads(await asyncio.wait_for(ws.recv(), 15))["type"] == "ready"
                await ws.send(
                    json.dumps({"type": "turn", "id": "verify_1", "speaker": "unknown", "text": args.text})
                )
                while True:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 180))
                    if event["type"] == "error":
                        raise RuntimeError(event.get("code", "LIVE_FAILED"))
                    if event["type"] == "risk":
                        break
                await ws.send('{"type":"end"}')
                while json.loads(await asyncio.wait_for(ws.recv(), 180))["type"] != "closed":
                    pass
            persisted = await client.get("/api/records/" + session["recordId"])
            persisted.raise_for_status()
            print("LIVE", json.dumps(verify_report(persisted.json())))
        print(
            "Verification completed with real provider results. This checks integration, not fraud accuracy."
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, RuntimeError, httpx.HTTPError) as error:
        raise SystemExit(str(error)) from None
