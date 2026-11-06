# Spring Boot / React integration handoff

Python is a private synchronous inference service. Spring owns user authentication, user/report ownership, sessions and durable persistence. React calls Spring, never Python directly. No LLM parsing belongs in Java. Configure a private base URL and `X-API-Key` in Spring's secret configuration.

## Routes

| Method | Path | Request | Success |
|---|---|---|---|
| POST | `/api/v1/analyze/text` | JSON below | 200 `Report` |
| POST | `/api/v1/analyze/audio` | Multipart below | 200 `Report` |
| GET | `/api/v1/analyses/{analysisId}` | No body | 200 `Report`, progress, or saved failure |
| POST | `/api/v1/analyses/{analysisId}/warning-audio` | `{"language":"hi-IN","voice":null}` | 200 raw `audio/wav` |
| GET | `/api/v1/analyses/{analysisId}/warning-audio?language=hi-IN` | Optional `voice` query | 200 cached raw `audio/wav`; 404 if absent/expired |
| GET | `/api/v1/capabilities` | No body | 200 limits/languages/provider configuration |
| GET | `/health/live` | Public, no key required | 200 process alive |
| GET | `/health/ready` | Backend key | 200 ready; 503 components unavailable/unconfigured |
| GET | `/openapi.json` | Backend key | 200 complete OpenAPI schema for DTO generation |

Every route except liveness is authenticated when `APP_API_KEY` is set. For local mock-only development it may be empty. Production/real mode requires a secret of at least 24 characters. CORS is deliberately absent. Treat the Python key as a server credential, not a user credential. Python only knows one trusted backend principal; Spring **must** verify that the logged-in user owns the analysis ID on every read/synthesis call. Knowing a UUID is not authorization.

## Text request and DTO

```json
{
  "transcript": "Caller: Tell me your OTP immediately.",
  "inputLanguage": "en-IN",
  "warningLanguage": "hi-IN",
  "includeRuleIndicators": true
}
```

`inputLanguage` defaults to `auto`; it does not run language detection, so metadata is `und`/`unknown`. English/Hinglish/Hindi are preserved by default. Regional input requires configured translation. `warningLanguage` defaults to `en-IN`; supported warning locales are `en-IN`/`hi-IN`, with explicit English fallback for other valid locale codes. `includeRuleIndicators` defaults true. Optional `turns` is an ordered list of `{id,speaker,text}`; if supplied, newline-joining `speaker + ": " + text` must exactly equal `transcript`, and IDs must be unique. No extra request fields are accepted.

Example **mock** response (IDs and timings vary):

```json
{
  "analysisId": "11111111-1111-4111-8111-111111111111",
  "status": "COMPLETED",
  "inputType": "TEXT",
  "originalTranscript": "Caller: Tell me your OTP immediately.",
  "originalLanguage": "en-IN",
  "detectedLanguage": "en-IN",
  "languageSource": "user",
  "normalizedTranscript": "Caller: Tell me your OTP immediately.",
  "analysisLanguage": "en-IN",
  "normalizationApplied": false,
  "normalizedFromOriginal": false,
  "normalizationProvider": "identity",
  "normalization": {
    "provider": "identity", "mock": false,
    "sourceLanguage": "en-IN", "targetLanguage": "en-IN", "caution": null
  },
  "risk": {
    "code": "A", "level": "HIGH_RISK", "confidence": null,
    "source": "mock", "model": "mock-fixture-v1", "mock": true
  },
  "indicators": [{
    "id": "otp_solicitation", "source": "rule", "type": "CREDENTIAL_REQUEST",
    "evidenceText": "Tell me your OTP", "speaker": null, "turnId": null
  }],
  "warning": {
    "available": true, "templateId": "HIGH_RISK_GENERIC",
    "requestedLanguage": "hi-IN", "language": "hi-IN", "actualLanguage": "hi-IN",
    "text": "सावधान! इस बातचीत में धोखाधड़ी के गंभीर संकेत हैं। अपना ओटीपी, पिन या पासवर्ड साझा न करें। दबाव में पैसे न भेजें। कॉल समाप्त करें और बैंक के आधिकारिक माध्यम से पुष्टि करें।",
    "localizationProvider": "curated", "fallbackApplied": false,
    "audioStatus": "NOT_REQUESTED", "mock": false
  },
  "transcription": null,
  "timingsMs": {"total": 1.0, "prisma": null, "translation": 0.1, "evon": 0.1, "timbre": null},
  "providers": {"stt": null, "translation": "identity", "classification": "mock-evon", "tts": null},
  "mock": true
}
```

In real mode risk provenance is `source=evon`, `model=gnani-evon-v3.3-gguf`, `mock=false`; classification provider is `evon-gguf`. Never display a numeric confidence: it is always null. `A/HIGH_RISK`, `B/SUSPICIOUS`, `C/LOW_RISK` are the only model classes. Show LOW_RISK with its limitation text; do not call it certified safe. Indicators are optional literal rules, not model reasoning or an explanation of the model's decision.

Keep `originalTranscript` and `normalizedTranscript` separate. If `normalizationApplied=true`, surface the translation caution. Never infer language from script in the frontend; use `languageSource`. JSON text is UTF-8. Preserve Devanagari correctly throughout database storage and UI rendering.

Generate full DTOs from authenticated `/openapi.json`, or use a minimal integration record while retaining the full JSON:

```java
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AnalyzeTextRequest(String transcript, String inputLanguage,
                                 String warningLanguage, boolean includeRuleIndicators) {}

@JsonIgnoreProperties(ignoreUnknown = true)
public record Risk(String code, String level, Double confidence,
                   String source, String model, boolean mock) {}

@JsonIgnoreProperties(ignoreUnknown = true)
public record AnalysisReport(String analysisId, String status, String inputType,
                             String originalTranscript, String normalizedTranscript,
                             Risk risk, boolean mock) {}
```

Records shown belong in separate files. This minimal response record intentionally omits warning/provenance fields; use generated full DTOs for the complete UI. Construct the request explicitly: Java primitive false differs from the Python default true if you omit the field in your own DTO logic.

## Spring WebClient examples

```java
import java.time.Duration;
import org.springframework.web.reactive.function.client.WebClient;

WebClient ai = WebClient.builder()
    .baseUrl(aiBaseUrl)                       // application configuration, private URL
    .defaultHeader("X-API-Key", aiApiKey)     // secret configuration
    .codecs(c -> c.defaultCodecs().maxInMemorySize(11 * 1024 * 1024))
    .build();

AnalysisReport report = ai.post().uri("/api/v1/analyze/text")
    .bodyValue(new AnalyzeTextRequest(
        "Caller: Tell me your OTP immediately.", "en-IN", "hi-IN", true))
    .retrieve()
    .bodyToMono(AnalysisReport.class)
    .timeout(Duration.ofSeconds(210))
    .block();
```

This snippet assumes WebFlux's `WebClient` dependency. In a WebFlux request handler return the `Mono` instead of blocking. Configure connect timeout around 5 seconds and response timeout around 210 seconds for text / 300 seconds for audio at the HTTP connector and ingress. `retrieve()` turns HTTP errors into `WebClientResponseException`; parse the bounded standard error JSON below with Jackson and propagate its status/code/retryable flag. Do not log request/response bodies, the key, or transcripts. Do not add automatic retries to analysis or paid synthesis: requests are not idempotency-keyed.

Multipart audio:

```java
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;

MultipartBodyBuilder parts = new MultipartBodyBuilder();
parts.part("file", new FileSystemResource(consentedAudioPath))
     .contentType(MediaType.parseMediaType("audio/wav"));
parts.part("consent", "true");
parts.part("inputLanguage", "hi-IN");
parts.part("warningLanguage", "hi-IN");
parts.part("includeRuleIndicators", "true");

AnalysisReport report = ai.post().uri("/api/v1/analyze/audio")
    .contentType(MediaType.MULTIPART_FORM_DATA).bodyValue(parts.build())
    .retrieve().bodyToMono(AnalysisReport.class)
    .timeout(Duration.ofSeconds(300)).block();
```

Only submit recordings with explicit user consent. UI must collect that consent before Spring forwards `consent=true`. Enabled uploads are WAV (`audio/wav`, `audio/x-wav`, `audio/wave`) and MP3 (`audio/mpeg`); extension alone is insufficient. The clip cap is **15 MiB and 60 seconds**, configurable downward, and recognized text is still subject to transcript/context limits. Multipart requests should be limited to roughly **16 MiB** in Spring/ingress. Python caps the body before multipart parsing and deletes temporary inputs automatically. STT defaults `inputLanguage=en-IN`; use an explicit supported BCP-47 locale. `hi-Latn` and `auto` are rejected for audio. Real STT reports the user-selected locale and no invented diarization/timestamps.

Warning audio:

```java
import java.util.Map;
import org.springframework.http.ResponseEntity;

ResponseEntity<byte[]> warning = ai.post()
    .uri("/api/v1/analyses/{id}/warning-audio", report.analysisId())
    .bodyValue(Map.of("language", "hi-IN"))   // omit voice to select the enabled default
    .retrieve().toEntity(byte[].class)
    .timeout(Duration.ofSeconds(90)).block();
```

Forward bytes with the provider's validated `Content-Type: audio/wav`. Retain the metadata headers or expose them in a separate Spring DTO. Do not JSON-decode this body, and do not require base64. In React, fetch Spring's authenticated audio route into a Blob, use `URL.createObjectURL(blob)` for playback, and revoke the object URL on disposal. Keep transcripts out of URL/query strings.

| Response header | Meaning |
|---|---|
| `X-Mock` | `true` for offline test tone |
| `X-Audio-Kind` | `test-tone` or `speech` |
| `X-Audio-Provider` | `mock-timbre-test-tone` or `gnani-timbre` |
| `X-Template-Id` | Server-selected approved template |
| `X-Requested-Language` | Locale the caller requested |
| `X-Actual-Language` | Actual enabled locale, including fallback |
| `X-Voice` | Kaveri (`en-IN`) or Nalini (`hi-IN`) |

No arbitrary warning text is accepted. LOW_RISK has `warning.available=false` and returns `WARNING_NOT_AVAILABLE` (409) on synthesis. A TTS failure leaves the successful risk report intact; allow retry only on explicit user action if `retryable=true`. GET cached audio uses `language` and optional `voice` query parameters; the last synthesized language is not an implicit default. Unsupported output locales fall back to English. Unsupported explicit voices are rejected with 422.

## Status and errors

There is no 202 job contract. POST completes synchronously or returns an error. After receiving an ID, GET returns the report or saved error. If queried while a known ID is still processing, progress is:

```json
{"analysisId":"11111111-1111-4111-8111-111111111111","status":"CLASSIFYING","mock":false}
```

Progress states: `QUEUED`, `TRANSCRIBING`, `TRANSLATING`, `CLASSIFYING`; terminal states: `COMPLETED`, `FAILED`. A saved failure is returned by GET with HTTP 200 and `status=FAILED`; the original POST carries its failure HTTP status. Check both the HTTP status **and the body status**. Missing/expired/foreign IDs return 404. Store results durably in Spring after the POST succeeds: Python storage is process-local, expires after 30 minutes, and disappears on restart. Run one worker; do not load-balance retrieval across independent Python replicas.

Standard error envelope:

```json
{
  "error": {
    "code": "EVON_UNAVAILABLE",
    "message": "Risk analysis is temporarily unavailable.",
    "retryable": true
  },
  "analysisId": "11111111-1111-4111-8111-111111111111",
  "status": "FAILED",
  "mock": false
}
```

The ID is null when validation fails before allocation. Treat all failed risk analyses as operationally **UNDETERMINED**, never C/LOW_RISK. Do not use empty or missing `risk` as a benign decision.

| HTTP | Codes / handling |
|---|---|
| 401 | `UNAUTHORIZED`: fix server key; do not retry with a user's token |
| 404 | `NOT_FOUND`: missing/expired result or audio cache |
| 409 | `WARNING_NOT_AVAILABLE`, or `INVALID_INPUT` if analysis never completed |
| 413 | `UPLOAD_TOO_LARGE`: reduce request size |
| 415 | `UNSUPPORTED_MEDIA`: wrong MIME/signature, corrupt or undecodable audio |
| 422 | `INVALID_INPUT`, `CONSENT_REQUIRED`, `INSUFFICIENT_TRANSCRIPT`, `CONTEXT_LIMIT_EXCEEDED` |
| 429 | `RATE_LIMITED`: local admission/queue/rate cap or provider quota |
| 502 | `MODEL_OUTPUT_INVALID`, `TRANSCRIPTION_FAILED`, `TRANSLATION_FAILED`, invalid TTS audio (`TTS_UNAVAILABLE`) |
| 503 | `UNCONFIGURED_PROVIDER`, `EVON_UNAVAILABLE`, `STT_UNAVAILABLE`, `TTS_UNAVAILABLE` |
| 504 | `TIMEOUT`: upstream, audio subprocess or stalled upload |
| 500 | `INTERNAL_ERROR`: generic failure without sensitive details |

Read `retryable`; 401/403 upstream provider failures are represented by non-retryable stage errors rather than exposing the upstream response. No confidence is fabricated. No provider keys/URLs appear in error envelopes or readiness. Retrying an uncertain POST can create another analysis and bill the provider again.

## Limits, mock UI, and go-live

- Fetch `/api/v1/capabilities` before enabling audio/TTS controls. `inputLanguages` and `sttLanguages` reflect the enabled translation policy; `supportedInputLanguages` and `providerSttLanguages` show the broader implemented/provider catalog. `audioToolsAvailable`/`mp3Available` distinguish offline WAV support from FFmpeg-dependent input. Availability reflects configuration, not live provider credits or accuracy. Native Hindi translation is optional.
- The previous Evon context is 512 tokens; Python's conservative UTF-8 byte estimate plus prompt/framing may reject even short native-script text. Do not blindly split transcripts in React. The service rejects rather than truncates. Coordinate higher server/service context with the AI operator.
- Default queue: one active Evon request, four waiting, five-second queue wait. Default service rate cap: 60 requests/minute per backend key. Use 429 to show a retry action and avoid concurrent retry loops.
- Mock UI must visibly say **demo/mock**. Mock audio upload is a fixed English fixture and mock warning audio is a test tone; neither is a real transcription/speech result. Identity preservation and curated warning text are not mocked stages.
- Python retains no uploaded audio. It stores transcripts/results temporarily; Spring must apply its own lawful retention/deletion and ownership rules. Never log transcript payloads or send them into browser analytics.
- Check `/health/ready` before going live. Start EC2 and verify private connectivity, set real Gnani credentials, set `MOCK_MODE=false`, and execute the explicit opt-in smoke scripts from README. No live cloud validation was possible without those external credentials/endpoints.
- No real-time telephony, streaming SSE, window aggregation, fine-tuning, or model confidence is implemented. This is the upload/text M0–M5 contract.
