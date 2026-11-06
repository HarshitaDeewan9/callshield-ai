# M0–M5 delivery and verification

The complete specification was read before implementation. Milestones are delivered together in this repository; the checks below record final integrated validation of each area. M6 is excluded from scope.

## M0 — Foundation

- Added installable Python package, validated settings, API schemas, sanitized errors/logging, backend key authentication and mock providers.
- Default mock mode needs no API keys, EC2, GPU or model weights; WAV development also needs no FFmpeg installation.
- Validated startup configuration, Unicode/input limits, authentication, no-secret validation errors and network-free mock operation.

## M1 — Evon text

- Added private llama.cpp HTTP adapter and synchronous text API, strict A/B/C + stop parsing, non-thinking requests and null confidence.
- Added conservative context rejection, one active request, bounded queue/wait, cancellation cleanup and typed HTTP/timeout failures.
- Verified actual request JSON, prompt evidence delimiting, invalid/reasoning-only output, availability errors and concurrent backpressure with HTTP fixtures.

## M2 — Language

- Preserves English/Hinglish and optionally Hindi; unknown input remains `und`, without claiming detection.
- Added optional official Google v3 NMT translation, original/normalized text separation, cost/intent caveats and explicit missing-configuration failures.
- Verified identity preservation, regional configuration errors, translation request contract, provenance and failed translations.

## M3 — Prisma

- Added official `gnani-vachana==0.8.1` adapter with inspected constructor/schema; no remote-code model loading.
- Added consented uploads, byte/MIME/size/duration validation, bounded ffprobe/ffmpeg processing and temporary-file cleanup.
- Verified SDK-generated multipart/auth and response fields, malformed/empty STT, upstream errors, corrupt uploads, audio preprocessing command contract and integrated cleanup.

## M4 — Warnings / Timbre

- Added server-owned English/Hindi warnings, transparent locale fallback, verified v2.5 Kaveri/Nalini catalog, on-demand WAV synthesis and cache.
- Mock output is a labeled audible tone; real output is validated for complete WAV frames, type and size. No arbitrary client synthesis text is accepted.
- Verified actual SDK-generated TTS HTTP calls, supported voice rules, audio bytes, fallback headers, quota/auth/timeouts and TTS failure independence.

## M5 — Integration

- Added result/progress/failure retrieval, backend ownership, TTL/periodic purge, bounded warning cache, rate/body limits, capabilities and readiness.
- Added Docker/compose/CI, mock and guarded real smoke scripts, complete README and Spring Boot DTO/route/error/timeout handoff.
- Ran the full offline suite (**118 passed**) and lint, dependency consistency check, in-process smoke and HTTP smoke against a local Uvicorn process. Live cloud calls remain explicitly gated because no real provider credentials/private running EC2 endpoint were supplied.

## External validation boundary

Provider contracts were checked against official documentation and the installed official SDK; HTTP/provider replies in tests are fixtures, not claimed cloud results. Real EC2 label accuracy, native-language review of templates, paid API authorization/credits, Docker image build and Linux CI execution require their respective runtime/account environments. No models were fine-tuned or substituted.
