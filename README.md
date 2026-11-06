# CallShield India AI Service

**Testing real providers and multilingual input:** see [REAL_TESTING.md](REAL_TESTING.md). `scripts/dev.py` always starts mock mode; use `scripts/dev.py --real` for actual Evon/Prisma/Timbre calls. The studio now exposes 11 Evon text languages plus Hinglish, ten Prisma audio locales, separate explanation-language selection and explicit result provenance. Curated warning audio remains English/Hindi.

**Full React + Spring + Python studio is now included.** Start locally in mock mode with `.\.venv\Scripts\python.exe scripts\dev.py`, then open http://localhost:5173 and create an account. See [FULL_STACK.md](FULL_STACK.md) for setup, testing, real providers and EC2 Docker deployment without a domain; [FULL_STACK_ARCHITECTURE.md](FULL_STACK_ARCHITECTURE.md) contains the updated diagrams. The sections below retain the private Python service documentation.

**New: v2 live risk sessions.** Incremental text/PCM audio streaming, model-generated risk indices and evidence-linked summaries, five severity bands, and threshold alerts are implemented alongside the unchanged v1 API. See [LIVE_STREAMING.md](LIVE_STREAMING.md) for the protocol, context upgrade, executable client, and score/tone limitations. v2 indices are uncalibrated assessments, not fraud probabilities; acoustic measurements do not infer deception.

A Python 3.11+ FastAPI service for consented audio clips and pasted transcripts. It orchestrates **Gnani Prisma v2.5**, the existing **Gnani Evon v3.3 GGUF on your private AWS llama.cpp server**, optional Google Cloud Translation NMT, and **Gnani Timbre v2.5**. There is no model training, replacement classifier, local model download, React application, or Java backend in this repository.

**Default: deterministic offline mock mode.** Real mode never silently falls back to mocks. Mock labels demonstrate the API contract, not model accuracy. Mock transcription always returns a documented English scam fixture regardless of audio content; mock TTS returns a playable 0.5-second 440 Hz test tone, **not spoken warning audio**. Every mocked stage identifies its provenance.

## Start locally

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --limit-concurrency 8
```

On PowerShell use `Copy-Item .env.example .env`. If Python is not on PATH, invoke your installed Python executable explicitly. This implementation was exercised with Python 3.12 on Windows. Exact tested direct dependency versions are in `pyproject.toml`; `requirements-tested.txt` records the complete tested environment. The development extra includes the small official Gnani client so its actual HTTP contract is tested. Neither torch nor transformers is needed.

No keys are needed with the default local mock configuration. Set `APP_API_KEY` for a shared development server; send it as `X-API-Key`. All service routes except `/health/live` enforce this key when set. Real mode and production refuse to start without a key of at least 24 characters. Never expose keyless development mode outside loopback.

```bash
python -m scripts.smoke_test_mock
# In another terminal, test the running server:
python -m scripts.smoke_test_mock --base-url http://127.0.0.1:8000
pytest -q
ruff check .
```

The default mock WAV upload needs no system tools. Install **ffmpeg and ffprobe** for MP3 uploads or any real audio upload. Ubuntu: `sudo apt-get update && sudo apt-get install ffmpeg`. On Windows install a trusted FFmpeg distribution, add its `bin` directory to PATH or set `FFMPEG_PATH` and `FFPROBE_PATH`. Docker installs both tools. Mock mode performs no provider network calls, including readiness.

### Windows pytest temporary-directory permission errors

If tests report `PermissionError: [WinError 5]` for `pytest-of-DELL` or warnings about `.pytest_cache`, use the isolated runner:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_tests
```

It runs the same tests in a new temporary directory, disables pytest's persistent cache, and returns pytest's exit code. It does not modify ACLs or reuse/delete the blocked directories. Extra arguments work, for example `python -m scripts.run_tests tests/test_audio_utils.py`. A passing mock smoke test alongside those setup errors indicates the endpoint demonstration succeeded while pytest could not create its test files. The Starlette HTTPX deprecation warning is separate from the permissions issue.

## Try the API

Examples below assume the default empty local mock key. If set, add `-H "X-API-Key: YOUR_BACKEND_KEY"`; use `curl.exe` in PowerShell. Do not paste real keys into shared terminals or source files.

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/api/v1/capabilities
curl -X POST http://127.0.0.1:8000/api/v1/analyze/text \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Caller: Tell me your OTP immediately.","inputLanguage":"en-IN","warningLanguage":"hi-IN","includeRuleIndicators":true}'
# Replace ANALYSIS_ID with the actual UUID from that response:
curl http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID
curl -X POST http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/warning-audio \
  -H 'Content-Type: application/json' -d '{"language":"hi-IN","voice":null}' --output warning.wav
curl 'http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/warning-audio?language=hi-IN' --output cached-warning.wav
curl -X POST http://127.0.0.1:8000/api/v1/analyze/audio \
  -F 'file=@consented-clip.wav;type=audio/wav' -F 'consent=true' \
  -F 'inputLanguage=en-IN' -F 'warningLanguage=hi-IN' -F 'includeRuleIndicators=true'
```

For the exact response schema fetch `/openapi.json` using your backend key. `/docs` is public only in keyless local mock mode; when a key is configured, use an HTTP client to fetch the authenticated OpenAPI schema and import it into your API tooling. The Swagger page itself also requires the header; browsers do not attach it automatically. See [SPRING_BOOT_HANDOFF.md](SPRING_BOOT_HANDOFF.md) for Java examples and error handling.

## Architecture and behavior

`app/api` handles transport. `app/services/pipeline.py` is shared by text and audio flows. `app/providers/interfaces.py` defines the replaceable classification, STT, TTS, and translation contracts. Provider adapters own upstream formats; they never leak provider response bodies to Spring. Classification and warning synthesis are separate requests.

Analysis is **synchronous**: a successful POST returns 200 and the completed report. There are no 202 jobs or background inference retries. Results are stored under real UUIDs. GET returns a completed report, a saved failure envelope, or a small progress record if called while that UUID is processing. Progress states are `QUEUED`, `TRANSCRIBING`, `TRANSLATING`, `CLASSIFYING`, `COMPLETED`, `FAILED`. A failure after report allocation includes its retrievable `analysisId`; early validation errors have null IDs. Risk failures contain no successful risk class and must be shown as operationally **UNDETERMINED** by the caller.

The optional literal evidence rules return exact substrings from the original transcript with `source=rule`; they never alter the model label. Unknown speaker/turn attribution stays null. Supplied turns must exactly reconstruct `transcript` as newline-separated `speaker: text`, with unique turn IDs; they are not a second conflicting model input.

## Real Evon on AWS

1. Start the existing EC2 instance. The service does not start/stop EC2 or load model weights.
2. Run the existing quantized Evon v3.3 model with llama-server bound to `127.0.0.1:8080`, model alias `evon`, and `--parallel 1`. Keep the context setting consistent with `EVON_CONTEXT_TOKENS`.
3. Prefer running this service on the same EC2 host. Otherwise use a private network, VPN or authenticated tunnel. **Never open port 8080 publicly.** Loopback on your laptop is not EC2 loopback.
4. Configure:

```dotenv
MOCK_MODE=false
APP_API_KEY=<your randomly generated backend secret, at least 24 characters>
EVON_BASE_URL=http://127.0.0.1:8080/v1
EVON_MODEL=evon
EVON_CONTEXT_TOKENS=512
EVON_TIMEOUT_SECONDS=120
# Set only when your private llama-server requires it:
EVON_API_KEY=
```

For text-only real operation without speech credentials set `PRISMA_ENABLED=false` and `TIMBRE_ENABLED=false`. Enabled but unconfigured speech adapters make readiness 503. A stopped/unreachable Evon makes readiness 503 and classification 503; no fabricated result is returned. Readiness uses `/v1/models` and verifies the configured alias, without running inference. Speech readiness says `configured_not_probed` when credentials and SDK are present; this is not a promise that quota/authentication will succeed.

Every Evon request sends `temperature=0`, `max_tokens=8`, `stream=false` and `chat_template_kwargs.enable_thinking=false`. Only `choices[0].message.content` equal to A/B/C after surrounding whitespace and `finish_reason=stop` is accepted. `reasoning_content` is never substituted. Empty/malformed output becomes `MODEL_OUTPUT_INVALID` (502). Confidence is always null. Numeric token counts and accepted finish reason can be logged as metrics; no raw text or upstream body is logged.

Exactly one request is admitted to Evon at a time. Four additional requests can wait, each for at most five seconds; queue overflow/expiry returns 429. HTTP timeout returns 504. The service deliberately makes **no automatic inference or paid-speech retries**; this avoids ambiguous duplicate work/billing. Each speech adapter allows two running SDK operations and four waiting operations. Run **one Uvicorn worker/one replica per Evon server**: local semaphores and storage are not distributed. llama-server must also retain `--parallel 1`.

### Context limit

The prior server context was only 512 tokens. The v1 service uses a deliberately conservative estimate: UTF-8 bytes of both message contents plus 64 tokens reserved for chat framing and output. This can reject text that a tokenizer would fit, particularly native scripts. It never silently truncates or summarizes. The default permits very short English/Hinglish excerpts; increase the *server and service* context together for larger excerpts/native scripts after checking RAM and latency. `MAX_TRANSCRIPT_CHARS=3000` is a separate input cap, not a promise that 3000 characters fit 512 tokens. Mock classification does not simulate tokenizer limits; real-adapter context tests do. The newer v2 live assessor adds explicit whole-turn windows with omitted-turn metadata; see [LIVE_STREAMING.md](LIVE_STREAMING.md).

The GGUF is a community quantization derived from official Gnani Evon weights, not an official Gnani quantized release. The Python process uses only the HTTP adapter and never downloads any LLM.

## Real Prisma and Timbre

```bash
pip install -e '.[gnani]'
```

Obtain `GNANI_API_KEY` through the [Gnani API dashboard](https://app.gnani.ai/) and put it in your private environment. The chosen integration is **gnani-vachana 0.8.1**, not Hugging Face `trust_remote_code`, and not the separate legacy bearer-auth REST API.

Verified against the official SDK documentation and inspected installed SDK source on 20 October 2026:

| Adapter | SDK call / contract |
|---|---|
| Prisma | `GnaniSTTClient(api_key=..., timeout=...).transcribe(path, language_code=...)` |
| STT transport | `https://api.vachana.ai/stt/v3`, multipart `audio_file`, `language_code`, `format=verbatim`, `X-API-Key-ID` |
| STT response | Requires `success=true` and a non-empty string `transcript`. Language is the **user-selected** language, not provider detection. Alignment/diarization/confidence are not invented. |
| Timbre | `GnaniTTSClient(...).synthesize(text, voice=..., model="timbre-v2.5", language=..., speed=1.0, audio_config=AudioConfig(container="wav",sample_rate=48000,encoding="linear_pcm"))` |
| TTS transport | SDK uses `https://api.vachana.ai/api/v1/tts/inference` and `X-API-Key-ID`. Do not substitute the older `api.gnani.ai` bearer-auth payload. |
| Enabled voices | English `en-IN`: **Kaveri**; Hindi `hi-IN`: **Nalini**, both verified v2.5 catalog entries. |

Prisma REST supports up to 60 seconds. This service exposes the narrower **WAV/MP3** input set. It checks MIME and magic bytes, then ffprobe duration/streams and ffmpeg decoding in real mode. It converts accepted clips to mono 16-bit PCM WAV at 16 kHz as a **service choice**; the REST documentation accepts WAV and does not impose a universal 16 kHz requirement. Never confuse this with the realtime PCM contract. Filenames from clients are ignored, external protocols are disabled, subprocesses have a 20-second timeout, and temporary inputs/conversions are removed even on provider failure. Raw inputs are never retained; there is no audio-retention switch. Returned Timbre WAVs must contain complete frames, have a valid channel/rate configuration and be at most 10 MiB; invalid payloads fail explicitly.

The API enables ten explicit Prisma locales listed by `/capabilities`. `auto` and `hi-Latn` are **text metadata only** and are rejected for speech input. Uploaded audio defaults to `en-IN`; select the actual recording language explicitly. Reports distinguish provider inference timings from measured upload duration (`uploadDurationMs`). STT `durationMs` remains null because this SDK REST response does not report it.

Timbre can return a streaming WAV header with RIFF/data sizes both set to `0xFFFFFFFF`. After the SDK receives the HTTP body, the adapter finalizes those two lengths from the received bytes, only for the observed canonical 44-byte mono 48 kHz, 16-bit PCM layout. Samples are unchanged. Empty/partial frames, unexpected streaming formats, oversized responses and truncated WAVs with finite declared lengths remain errors. This handling is restricted to Timbre responses; uploaded WAV validation remains strict. Unknown-length streams cannot prove that the provider produced every intended spoken word, so listening remains part of the live smoke test.

Provider SDK calls execute in bounded worker threads, with configured socket timeouts, without blocking the event loop. Their 401/403 failures are non-retryable; 429 is explicit; timeouts become 504. An absent key/SDK or disabled adapter gives `UNCONFIGURED_PROVIDER` (503), never mock speech. Startup in real text-only mode needs no Gnani key if speech is disabled.

## Language and warning policy

English and Roman-script Hinglish are preserved. Hindi native script is preserved by default; set `TRANSLATE_HINDI=true` to request English normalization. `auto` does no heuristic detection: it preserves input with `detectedLanguage=und`, `languageSource=unknown`. Other listed input languages require translation; identity mode returns `UNCONFIGURED_PROVIDER` rather than claiming translation occurred.

```bash
pip install -e '.[google]'
```

Enable the Cloud Translation API, set `GOOGLE_CLOUD_PROJECT`, and configure Google Application Default Credentials (`GOOGLE_APPLICATION_CREDENTIALS` may point to a private service-account file). Set `TRANSLATION_PROVIDER=google`. The adapter uses the official v3 client with `general/nmt` explicitly; it does not select Google's translation LLM. It preserves the original transcript separately, records source/target/provider/applied flags and warns that translation can alter intent and negation. No translation confidence is invented. In mock mode this setting selects a labeled fixed translation fixture, not Google.

Warning output language is independent of transcript language. Templates in `app/services/warnings.py` are server-owned English/Hindi localizations; they should receive native-language/product review before deployment. Unsupported requested locales fall back to English with `fallbackApplied=true`, `requestedLanguage` and `actualLanguage`. `hi-Latn` also falls back; it is not silently passed to Timbre. There is no machine translation of warnings in the enabled path. The translator interface exposes template localization for future adapters; the current policy always favors the enabled curated catalog.

LOW_RISK means only that no significant risk indicators were found in the supplied excerpt; it does not certify safety. It has `warning.available=false` and synthesis returns 409. Operational failures can use the generic `UNDETERMINED` template in the UI; failed analyses do not synthesize through the result-bound endpoint. TTS accepts only an existing completed analysis and a language/voice, never arbitrary client text. TTS failure updates `warning.audioStatus=FAILED`, retaining the successful classification.

## Storage, privacy, and deployment

Storage is in memory, non-durable, process-local, bounded to 500 reports, with a default 30-minute result TTL and periodic cleanup (at most 30 seconds after expiration). Cached warning audio expires after one hour **or when its report expires**, whichever comes first. `MAX_CACHED_AUDIO_MB=32` caps the aggregate warning cache; earlier-expiring audio is evicted without deleting risk reports. Report IDs are attached to the authenticated backend principal; another key is unauthorized. This is a **single trusted Spring backend** contract: Spring must authenticate users, persist ownership mappings, and authorize every access to a UUID before proxying it. User identity headers are not trusted by Python. Never give this service key directly to React.

Default application logging never records transcripts, audio, raw validation inputs, secrets or upstream error bodies. Launch with `--no-access-log` as shown to avoid IPs/URLs in Uvicorn access logs. Restrict infrastructure logs similarly. API responses use `Cache-Control: no-store`. CORS is disabled; Spring calls the service server-to-server. Use TLS at the private ingress, encrypted storage if adding persistence, appropriate consent/lawful handling, and explicit deletion policies for Spring's own data. Do not persist raw transcripts in observability tools. There are no hardcoded production credentials.

Before handling significant traffic, add a shared result repository and distributed queue, enforce an authenticated end-user ownership model if bypassing Spring, and cap requests at the reverse proxy. The MVP's per-backend rate limit is 60 requests/minute with 429 responses. Uploaded bodies are capped before multipart parsing; stalled reads stop after 30 seconds and total upload time is capped at 120 seconds. Limit public ingress to Spring and bound concurrent connections. Provider SDKs buffer their responses; deploy within a process memory limit and trusted provider egress. Evon context and CPU latency remain workload-dependent; this service does not guarantee classification accuracy.

```bash
docker compose up --build
# Or deploy an image built from a reviewed GitHub checkout:
git clone <your-repository-url>
cd <your-checkout-directory>
docker build -t callshield-ai:0.1.0 .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 callshield-ai:0.1.0
```

The compose file runs mock mode, binds loopback, uses a read-only root filesystem and bounded tmpfs. The Docker image runs as a non-root user. For a same-host Evon deployment, container `127.0.0.1` is the container itself: deploy Python directly on EC2, or use Linux host networking with carefully scoped loopback binding. Do not expose Evon to make container networking easier. Never bake `.env`, AWS credentials, GGUFs or private keys into the image. `.dockerignore` and `.gitignore` exclude them. CI only executes offline tests and mock smoke; it contains no real integration secrets.

## Explicit live smoke tests

These are never run automatically. They call real providers and can spend AWS/Gnani credits. Use a consented clip only. Export real settings above, then:

```bash
export RUN_REAL_INTEGRATION=true
python -m scripts.smoke_test_evon
python -m scripts.smoke_test_gnani_stt consented-clip.wav --language hi-IN --consent
python -m scripts.smoke_test_gnani_tts
```

PowerShell: `$env:RUN_REAL_INTEGRATION='true'`. Output prints label/status/character counts rather than private transcripts. TTS writes the approved warning to `warning-smoke.wav` (ignored by Git). Live execution requires your actual active EC2/private endpoint and valid provider credentials; no credentials or provider successes are asserted by this repository's offline tests.

Operating costs include running EC2 CPU/RAM, EBS even while the instance is stopped, network transfer, Gnani STT/TTS quotas, and Google translation usage. Disable speech and translation when unnecessary. Warning speech is on-demand and cached by approved template/language/voice within a report; repeated uncached requests may be billed. Translation can send sensitive transcripts to Google; enable only with the intended consent and data policy.

## Verification and references

Tests cover mock end-to-end flows with network calls prohibited, strict Evon parsing and non-thinking payloads, prompt delimiters, context rejection, concurrency/backpressure, actual Gnani SDK HTTP construction, malformed STT, authentication/quota/timeout errors, audio validation, translation provenance, storage TTL/ownership, and TTS failure independence. Fixture target labels are demonstration/acceptance targets; no live accuracy evaluation has been performed. See [MILESTONES.md](MILESTONES.md).

Original M0-M5 local validation: **118 tests passed**, `ruff check .` passed, `pip check` passed, and both in-process and live local-Uvicorn mock smoke tests passed. Later fixes and v2 add regression coverage; run `python -m scripts.run_tests` for the current suite. The installed Starlette TestClient emits one upstream deprecation warning about its HTTPX test transport; it does not affect the service or test outcomes. Docker/Linux CI execution was not verified in this Windows session. Subsequent user-run real smoke tests verified v1 Evon, Prisma and Timbre; v2 real streaming/structured accuracy still needs opt-in validation.

Provider contracts checked during implementation:

- [Official Gnani Python SDK](https://github.com/Gnani-AI-Mintlify/gnani-vachana) and installed `gnani-vachana==0.8.1` source (`gnani/stt/client.py`, `gnani/tts/client.py`).
- [Prisma REST v3: formats, 60-second cap, request/response and language list](https://docs.gnani.ai/api/STT/speech-to-text).
- [llama.cpp server: OpenAI-compatible chat and template parameters](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- [Google Cloud Translation v3 Python request and ADC setup](https://docs.cloud.google.com/translate/docs/translate-text).
- [Gnani Hugging Face hosted wrapper](https://huggingface.co/gnani/gnani) and [alternate Gnani product REST sample](https://www.gnani.ai/text-to-speech/english), reviewed but **not used** as the integration contract.
