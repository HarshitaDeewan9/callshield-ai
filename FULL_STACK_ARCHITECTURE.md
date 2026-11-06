# CallShield full-stack architecture

These diagrams describe the implemented React/Spring/Python extension. The earlier architecture pack describes the original v1 Python service.

```mermaid
flowchart TB
    User[Consenting user] --> UI[React studio / AudioWorklet]
    UI -->|Cookie session + CSRF / HTTPS| Edge[Caddy edge]
    UI -->|PCM16 mono 16kHz / WSS| Edge
    subgraph EC2[Existing EC2 — Docker on Linux]
      Edge -->|Loopback 8081| Java[Spring Boot gateway]
      Java --> Auth[Authentication / ownership / CSRF]
      Java -->|JPA / Flyway| DB[(PostgreSQL persistent volume)]
      Java -->|Private key / loopback 8000| Python[FastAPI orchestration]
      Python --> Gate[Bounded single-request inference gate]
      Gate -->|Loopback 8080 / thinking disabled| Evon[Existing Gnani Evon GGUF / llama.cpp]
    end
    Python <-->|Prisma transcript stream| Gnani[Gnani APIs]
    Python -->|Approved template / Timbre WAV| Gnani
    Python --> Mock[Offline deterministic adapters]
```

```mermaid
sequenceDiagram
    actor U as User
    participant R as React
    participant S as Spring
    participant P as FastAPI
    participant G as Prisma stream
    participant E as Evon
    participant D as PostgreSQL
    U->>R: Consent and Start listening
    R->>S: POST session (cookie + CSRF)
    S->>P: Create session (private key)
    S->>D: Persist owned live record
    S-->>R: Session + gateway socket path
    R->>S: Open WS (cookie + allowed Origin)
    S->>P: Open private WS (key, no browser Origin)
    P->>G: Connect documented STT stream
    P-->>R: audio_ready via Spring
    loop Audio capture
      R->>S: 512 samples / 1024 bytes every 32ms
      S->>P: Serialized bounded binary forwarding
      P->>G: PCM frame
    end
    G-->>P: Completed transcript
    P-->>R: transcript via Spring
    P->>E: Recent whole turns + JSON schema
    E-->>P: Index + concise explanation + evidence
    P->>P: Validate schema and exact quotes
    P-->>S: risk snapshot
    S->>D: Save snapshot, transcript, timeline
    S-->>R: Render actual score/explanation
    opt Threshold crossed and policy armed
      P-->>R: alert + approved warning via Spring
    end
    U->>R: Finish
    R->>P: end through Spring
    P->>G: Commit final utterance
    P->>P: Drain final inference
    P-->>S: closed snapshot
    S->>D: Save final report
    S-->>R: Final result
```

```mermaid
stateDiagram-v2
    [*] --> Waiting: Session created
    Waiting --> Assessing: Completed transcript
    Assessing --> Assessed: Valid structured result
    Assessing --> Undetermined: Timeout / invalid provider output
    Assessed --> Assessing: New conversational evidence
    Undetermined --> Assessing: New evidence / retry checkpoint
    Assessed --> Alerted: Index >= threshold and armed
    Alerted --> Assessed: Show one in-app alert
    Assessed --> Armed: Index < reset and cooldown elapsed
    Armed --> Assessing: New evidence
    Waiting --> Closed: Finish
    Assessed --> Closed: Finish and drain
    Assessing --> Closed: Final checkpoint completes
    Assessed --> Interrupted: Connection lost; saved result marked stale
    Closed --> [*]
    Interrupted --> [*]
```

```mermaid
erDiagram
    ACCOUNT ||--o{ ANALYSIS_RECORD : owns
    ACCOUNT {
      varchar id PK
      varchar email UK
      varchar display_name
      varchar password_hash
      timestamptz created_at
    }
    ANALYSIS_RECORD {
      varchar id PK
      varchar owner_id FK
      varchar kind
      text payload_json
      timestamptz created_at
    }
```

`payload` stores the JSON assessment/transcript and bounded timeline, not raw audio. Session cookies and CSRF tokens are never model inputs. Provider keys remain on servers. Scores are uncalibrated indices; measured vocal amplitude does not imply deception. The no-domain deployment binds Caddy to loopback 8090 and is reached through SSH; public deployment uses a DNS name with HTTPS on 443.
