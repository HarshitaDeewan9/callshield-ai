# CallShield India: architecture and technical diagrams

Source snapshot: **20 October 2026**. These diagrams describe the implementation in this repository. React and Spring Boot are separate teammate projects; the EC2 deployment is the recommended topology, not an assertion that EC2 is running. Real provider adapters exist; cloud execution requires credentials and connectivity. M6 simulations/window aggregation are not implemented.

Share the PDF for review, individual PNGs for chat/slides, and SVGs for scalable editing. Mermaid blocks below can be edited in a Mermaid-compatible Markdown viewer. Diagrams use the default configuration unless noted. This documentation makes no provider network calls and contains no credentials.

## 1. System context and ownership

```mermaid
flowchart TB
    React["React client<br/>Separate teammate project"] -->|HTTPS| Spring["Spring Boot backend<br/>User auth, ownership, durable persistence"]
    Spring -->|"Private HTTP / X-API-Key"| AI["CallShield FastAPI<br/>Implemented in this repository"]
    AI --> Prisma["Gnani Prisma v2.5<br/>Hosted STT / official SDK"]
    AI --> Translation["Optional Google v3 NMT<br/>Otherwise identity where allowed"]
    AI --> Evon["Gnani Evon v3.3 GGUF<br/>Private EC2 / llama.cpp"]
    AI --> Timbre["Gnani Timbre v2.5<br/>On-demand warning speech"]
    classDef built fill:#E7F5F2,stroke:#14806E,color:#142D42;
    classDef external fill:#FFF3E5,stroke:#C77B27,color:#142D42;
    classDef provider fill:#F0ECFB,stroke:#7660AF,color:#142D42;
    class AI built;
    class React,Spring external;
    class Prisma,Translation,Evon,Timbre provider;
```

Python owns orchestration, not user accounts or durable storage. Spring must enforce per-user report ownership before forwarding any analysis ID. The service uses one trusted backend principal; user identity headers are not an authorization mechanism.

Code: `app/main.py`, `app/core/auth.py`, `app/services/pipeline.py`.

## 2. Python components and adapter seams

```mermaid
flowchart TB
    Boundary["Request boundary<br/>Body/time caps, backend key, rate limits, schemas"]
    Boundary --> Routes["app/api<br/>Analysis, audio, health, capabilities"]
    Routes --> Pipeline["Pipeline service<br/>Normalize, classify, rules, warning, report"]
    Pipeline --> Store["ReportStore<br/>Progress, reports, failures, warning cache"]
    Routes --> Store
    Routes --> STT["PrismaSTTProvider<br/>GnaniPrismaProvider / MockPrismaProvider"]
    Pipeline --> Translator["Translator<br/>Identity / GoogleCloud / Mock"]
    Pipeline --> Classifier["Classifier<br/>EvonLlamaCppProvider / MockEvonProvider"]
    Routes --> TTS["TimbreTTSProvider<br/>GnaniTimbreProvider / MockTimbreProvider"]
    Factory["create_app + lifespan<br/>Settings select adapters at startup"] -.-> Routes
    Factory -.-> Pipeline
    Factory -.-> Store
```

The interface contracts use Python protocols and small result dataclasses. `Prisma` refers to Gnani speech recognition, not the Prisma database ORM. Report storage is an in-memory implementation, with no database included.

Code: `app/providers/interfaces.py`, `app/services/*`, `app/api/*`, `app/main.py`.

## 3. Text request sequence

```mermaid
sequenceDiagram
    participant Spring
    participant API as API / security
    participant Pipeline
    participant Translator
    participant Evon
    participant Store as ReportStore
    Spring->>API: POST /api/v1/analyze/text + X-API-Key
    API->>API: Validate body, authorize, rate-limit
    API->>Pipeline: Analyze validated request
    Pipeline->>Store: Allocate UUID, QUEUED
    Pipeline->>Store: TRANSLATING
    Pipeline->>Translator: Preserve or normalize transcript
    Translator-->>Pipeline: NormalizedText + provenance
    Pipeline->>Store: CLASSIFYING
    Pipeline->>Evon: Bounded non-thinking chat request
    Evon-->>Pipeline: Exact A/B/C, finish_reason=stop
    Pipeline->>Pipeline: Grounded rules + approved warning
    Pipeline->>Store: Save COMPLETED Report
    Pipeline-->>Spring: 200 Report JSON
    Note over Pipeline,Evon: Invalid output -> 502; unavailable -> 503; timeout -> 504; busy -> 429
    Note over Pipeline,Store: A ServiceError is saved as FAILED after UUID allocation
```

Identity policy preserves English/Hinglish and Hindi by default. `auto` preserves the text and reports `und` / `unknown`; it does not detect language. Regional inputs, and Hindi when explicitly configured for translation, require translation. Both original and normalized text remain in the report.

Evon has one active request, four waiting slots, five-second queue wait, and a 120-second upstream timeout by default. Its context guard counts message UTF-8 bytes plus 64 reserved tokens against the configured budget (512 default). It rejects over-budget input without truncation. `chat_template_kwargs.enable_thinking=false` is mandatory; confidence remains null. Mock classification does not simulate the real tokenizer budget.

Code: `app/api/routes_analysis.py`, `app/services/pipeline.py`, `app/services/language_policy.py`, `app/providers/evon_llamacpp.py`.

## 4. Audio upload pipeline

```mermaid
flowchart LR
    Upload["Multipart audio upload"] --> Gate["Consent=true<br/>WAV/MP3 MIME + signature<br/>15 MiB default file cap"]
    Gate --> Inspect["Real: ffprobe + ffmpeg<br/>0 &lt; duration &lt;= 60 seconds<br/>Bounded subprocesses"]
    Inspect --> WAV["Temporary mono PCM WAV<br/>16-bit / 16 kHz service choice"]
    WAV --> Prisma["Official Prisma SDK<br/>Explicit supported language"]
    Prisma --> Check{"success=true and<br/>non-empty transcript?"}
    Check -->|Yes| Shared["Shared text pipeline"]
    Shared --> Report["AUDIO Report + STT provenance"]
    Check -->|No| Error["Typed STT failure<br/>Never LOW_RISK by default"]
    WAV -.-> Cleanup["Delete temporary files on exit<br/>Success or provider failure"]
    Gate -.-> Mock["Mock WAV: stdlib validation<br/>Fixed labeled transcript"]
    Mock -.-> Shared
```

Mock WAV uploads do not require FFmpeg; MP3 needs FFmpeg in either mode. Real uploads always use ffprobe/ffmpeg. `auto` and `hi-Latn` are rejected as STT language inputs. Prisma REST metadata does not fabricate diarization, alignment, duration or confidence. `uploadDurationMs` is separately measured by this service. Client filenames are ignored and subprocess commands disable external protocols.

Code: `app/api/routes_audio.py`, `app/services/audio_utils.py`, `app/providers/gnani_prisma.py`.

## 5. Warning synthesis and caching

```mermaid
flowchart TB
    Request["POST /api/v1/analyses/{id}/warning-audio<br/>language + optional voice only"] --> Lookup["Authorize and load completed report"]
    Lookup --> Low{"LOW_RISK?"}
    Low -->|Yes| NoAudio["409 WARNING_NOT_AVAILABLE"]
    Low -->|No| Template["Approved HIGH_RISK / SUSPICIOUS template"]
    Template --> Locale["Curated en-IN / hi-IN<br/>Other locales fall back to English"]
    Locale --> Voice["Validate voice<br/>Kaveri: en-IN / Nalini: hi-IN"]
    Voice --> Cache{"Cached for this analysis?<br/>templateId + locale + voice"}
    Cache -->|Hit| Output["200 raw audio/wav<br/>Provenance and locale headers"]
    Cache -->|Miss| Timbre["Timbre v2.5 SDK<br/>Or labeled mock test tone"]
    Timbre --> Valid["Validate complete WAV frames<br/>At most 10 MiB"]
    Valid --> Save["Cache with TTL and memory budget"]
    Save --> Output
    Timbre -.-> Failure["On failure: warning.audioStatus=FAILED<br/>Existing classification stays COMPLETED"]
```

Cache is per report; the aggregate audio budget is 32 MiB. Earlier-expiring warning blobs are evicted first without deleting risk reports. Audio TTL is one hour but cannot outlive report retention or eviction. GET on the same warning-audio route serves cached bytes using `language` and optional `voice` query parameters, or 404. Template localization is curated in the active synthesis path; Google warning translation is not enabled.

Code: `app/api/routes_audio.py`, `app/services/warnings.py`, `app/providers/gnani_timbre.py`, `app/services/report_store.py`.

## 6. Mock and real provider selection

```mermaid
flowchart TB
    Settings["Settings + application lifespan"] --> Mode{"MOCK_MODE?"}
    Mode -->|true default| Mock["Mock providers<br/>No provider network calls"]
    Mode -->|false| Real["Real adapters<br/>Missing configuration is an explicit error"]
    Mock --> ME["MockEvon: deterministic demo rules"]
    Mock --> MP["MockPrisma: fixed English transcript"]
    Mock --> MT["MockTimbre: 0.5-second 440 Hz tone"]
    Mock --> MX["Identity, or fixed mock translation fixture"]
    Real --> RE["Evon HTTP<br/>Private /v1/chat/completions"]
    Real --> RP["Gnani SDK 0.8.1<br/>Prisma + Timbre"]
    Real --> RX["Identity or Google v3 general/nmt"]
```

All mocked stages return explicit provenance. Curated warning text and identity preservation are not themselves fabricated provider output. Real mode never falls back to mock predictions. Speech adapters use the official SDK with `GNANI_API_KEY`; Evon can use its separately configured key. Speech work is bounded to two running and four waiting operations per adapter; Google uses a two-thread limiter. SDKs execute away from the FastAPI event loop.

Code: `app/main.py`, `app/config.py`, `app/providers/mock_providers.py`, `app/providers/gnani_common.py`.

## 7. Deployment and security boundaries

```mermaid
flowchart LR
    Spring["Spring Boot server<br/>User ownership / backend credential"] -->|"Private TLS ingress + X-API-Key"| Python
    subgraph EC2["Recommended private EC2 host"]
        Python["FastAPI / Uvicorn<br/>Single worker / replica<br/>Typical private port 8000"]
        Python -->|"Loopback HTTP"| Llama["llama.cpp + existing Evon GGUF<br/>127.0.0.1:8080<br/>alias evon / parallel 1"]
        Python --> Memory["Process-local reports + audio cache"]
    end
    Python -->|"Private outbound HTTPS"| Gnani["Gnani hosted STT / TTS"]
    Python -->|"Optional HTTPS + ADC"| Google["Google Cloud Translation NMT"]
    Monitor["Service health caller"] -->|"Public liveness only"| Live["GET /health/live"]
    Monitor -->|"Backend key"| Ready["GET /health/ready"]
    Ready -.->|"GET /v1/models; alias check"| Llama
```

Do not expose llama-server port 8080 publicly. If Python is elsewhere, use a private network, VPN or authenticated tunnel. Container loopback is the container, not the EC2 host. Compose is local mock development: loopback binding, non-root image, read-only root and bounded temporary storage. All service routes except `/health/live` authenticate when a key is set; real/production mode requires a key of at least 24 characters. CORS is disabled. API responses disable caching; transcript logging is absent by default.

An unavailable Evon produces readiness and classification 503. Speech readiness is `configured_not_probed`, not proof of valid quota/authentication. No database/distributed lock/queue is implemented; multiple workers would break shared result retrieval and global Evon admission control.

Code: `Dockerfile`, `docker-compose.yml`, `app/core/auth.py`, `app/api/routes_health.py`, `app/main.py`.

## 8. Result states and integration contract

```mermaid
stateDiagram-v2
    [*] --> QUEUED: Allocate in-memory UUID
    QUEUED --> TRANSCRIBING: Audio path
    QUEUED --> TRANSLATING: Text path
    TRANSCRIBING --> TRANSLATING: Valid transcript
    TRANSLATING --> CLASSIFYING: Preserve or normalize
    CLASSIFYING --> COMPLETED: Strict A/B/C + report
    QUEUED --> FAILED: ServiceError after allocation
    TRANSCRIBING --> FAILED: STT / media failure
    TRANSLATING --> FAILED: Language / translation failure
    CLASSIFYING --> FAILED: Provider / context / output failure
    COMPLETED --> [*]: Report expires or process restarts
    FAILED --> [*]: Entry expires or process restarts
```

POST is synchronous: success is HTTP 200, failures carry a typed HTTP status and error envelope. No 202 job API exists. A known ID can be retrieved while processing; GET returns progress, a completed report, or a saved failure. Saved failure retrieval uses HTTP 200 with `status=FAILED`; callers must check body status. Missing/expired IDs return 404.

Default store: 500 reports, 30-minute TTL, periodic cleanup within at most 30 seconds of expiry. Successful completion refreshes report TTL. Early validation errors can have `analysisId=null`. The service's `UNDETERMINED` is operational, not a fourth model class. TTS failure changes warning state, not the COMPLETED risk state.

| Boundary | Teammate handling |
|---|---|
| Successful report | Preserve original and normalized text, warning, provider provenance and mock flags |
| Risk code A / B / C | HIGH_RISK / SUSPICIOUS / LOW_RISK; confidence is always null |
| Classification error | Show UNDETERMINED, never assume LOW_RISK |
| TTS response | Raw WAV bytes, not JSON/base64; honor locale and mock headers |
| Retry | Do not automatically replay paid analysis/synthesis requests |
| Ownership | Spring checks logged-in user ownership of each UUID before proxying |
| Persistence | Spring saves durable results; Python entries disappear on restart |
| Capabilities | Enable supported UI features from the current service configuration |

Code: `app/services/report_store.py`, `app/services/pipeline.py`, `app/api/routes_analysis.py`, `app/schemas/responses.py`.

## Rebuild the visual pack

Install the authoring dependency separately from service dependencies: `pip install reportlab`.

```powershell
python scripts/generate_architecture_diagrams.py
# Optional PNG export when Poppler is on PATH:
pdftoppm -scale-to 1600 -png output/architecture/CallShield_Architecture_and_Technical_Diagrams.pdf output/architecture/page
```

The generator draws editable SVGs and a vector PDF. The Markdown/Mermaid file is the conceptual editing source; the Python generator controls the composed visual layout. Keep both in sync when architecture changes. Application code was not changed for this documentation task.
