# CallShield Intelligence Studio — run, test and host

**Updated multilingual studio:** [REAL_TESTING.md](REAL_TESTING.md) supersedes the narrower language descriptions below: 11 Evon text languages plus Hinglish, ten Prisma audio locales, separate explanation-language selection, and original-script evidence. Warning playback remains curated English/Hindi. The real verification script rejects mock output; changing `.env` alone does not override the launcher's default mock mode.

The repository now contains the complete React → Spring Boot → Python application. The existing Gnani Evon GGUF remains the only real risk LLM. No training or replacement model was added. The earlier Python v1 API remains available privately.

## What you can use

- Original responsive React/TypeScript interface: animated orbital capture area, risk gauge, timeline, evidence cards, history, preferences and account screens. Reduced-motion settings are respected.
- Email/password accounts, BCrypt password hashes, server-side cookie sessions and CSRF protection. No provider/backend credentials in JavaScript or browser storage.
- Text review, consented WAV/MP3 upload, and consented live microphone or typed-turn sessions.
- Streaming transcript, model risk index, five severity bands, short evidence-linked explanation, peak score, assessment age, stale status and threshold-crossing alerts.
- Threshold, re-arm level and cooldown preferences. Advice audio uses approved English/Hindi templates through Timbre; mock playback is explicitly a test tone.
- Owner-scoped saved reports, score timelines, JSON download and permanent deletion from the application database.
- H2 file database locally; PostgreSQL with Flyway migrations on EC2. Docker Compose and Caddy configuration included.

The current index is **not a fraud probability**. Evon can consider conversational context, linguistic urgency, coercion and protective negations. Audio level/clipping are descriptive quality measurements; no acoustic emotion/deception classifier exists. A family identity claim does not establish identity. Browser microphone capture does not intercept cellular phone audio. Scores require completed speech plus inference; one-second status updates do not guarantee one new score per second. See [LIVE_STREAMING.md](LIVE_STREAMING.md).

## Start locally on Windows — mock first

The current workspace already has the dependencies and compiled gateway. From `E:\callshield-ai`:

```powershell
.\.venv\Scripts\python.exe scripts\dev.py
```

Open **http://localhost:5173**. Choose **Create an account**, enter your own account details and a password of at least 12 characters. There are no seeded/default login credentials. Wait for the Spring startup message if the browser opens before Java is ready. Ctrl+C stops the launcher-owned processes.

The launcher starts Python on `127.0.0.1:8123`, Spring on `127.0.0.1:8081`, and Vite on port 5173. It generates a temporary shared backend key in memory, sets `MOCK_MODE=true`, and does not modify your root `.env`. It refuses occupied ports rather than killing existing services. Account/report data persists under `gateway/data/`; authentication sessions expire on Java restart.

### Fresh checkout prerequisites/build

Install Python 3.11+, Node.js 22.12+, JDK 21 and Maven 3.6.3+. Then:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,gnani,google]'
npm.cmd --prefix frontend ci
mvn -f gateway/pom.xml package
.\.venv\Scripts\python.exe scripts\dev.py
```

For the portable Java/Maven tools already downloaded into **this workspace**, build with:

```powershell
$env:JAVA_HOME = 'E:\callshield-ai\.tools\jdk\jdk-21.0.13+9'
$env:DEBUG = 'false'
& .tools\maven\apache-maven-3.10.0\bin\mvn.cmd '-Dmaven.repo.local=E:\callshield-ai\.tools\m2' -f gateway\pom.xml package
```

Stop the running studio before rebuilding the JAR on Windows; Java locks the executable archive. The launcher finds a system Java installation or the portable `.tools/jdk` installation. `.tools` is local tooling, ignored by Git/Docker and unnecessary inside deployment containers.

## Exercise the interface

1. **Transcript:** select Transcript → Try a sample → Read the signals. Mock OTP solicitation returns index 90 / CRITICAL, a mock explanation and an exact transcript quote. Paste a protective sentence such as `Caller: Never share your OTP with anyone.` to compare the mock fixture behavior.
2. **Audio clip:** select Audio clip, choose a consented WAV, tick consent and analyze. Mock transcription is a fixed fixture unrelated to the file's speech. WAV works offline without FFmpeg; MP3 still requires FFmpeg/FFprobe. Files are bounded to 15 MiB / 60 seconds.
3. **Live typed turns:** Live monitor → Turns → consent → Start live review. Choose speaker, send a completed turn and wait for its assessment. Add context in subsequent turns. The mock fixture can rise or fall; it is not semantic model validation.
4. **Live microphone:** Live monitor → Mic → consent → Start listening → grant browser microphone access. Only framed PCM streams through Spring. Mock STT emits a fixed demo OTP transcript after 32 frames, even for silence; the UI labels this limitation.
5. **Alerts:** preferences default to alert at 70, re-arm below 50 and cooldown 30 seconds. A sustained high score does not repeatedly alert. Changes apply to the next session. Alerts appear in the studio, not as SMS/push/background notifications.
6. **Finish session:** waits for final transcription/inference. Review evidence and timeline, play safety advice, download JSON, or open Conversation history and reopen/delete a report.

English/Hindi audio and English/Hindi/Hinglish text are exposed. No speaker diarization is invented: real microphone transcripts use `unknown` speaker; typed turns support explicit caller/customer labels.

## Automated tests

```powershell
# Offline Python suite; overrides real-provider settings safely.
.\.venv\Scripts\python.exe -m scripts.run_tests
.\.venv\Scripts\python.exe -m ruff check app tests scripts/dev.py scripts/smoke_test_stack.py deploy/init_config.py --no-cache
# React component/workflow tests and production bundle.
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
# Spring security, CSRF, ownership and persistence tests (H2 in memory).
mvn -f gateway/pom.xml test
# With the mock launcher running: real HTTP + WS across Spring and Python.
.\.venv\Scripts\python.exe -m scripts.smoke_test_stack
```

The stack smoke test creates disposable local accounts/reports and refuses to proceed with provider calls when capabilities report real mode. It checks authentication, CSRF, text, multipart audio, warning WAV, cross-account isolation, WebSocket risk/alert/final persistence, history and deletion. Tests never prove real model accuracy. Browser microphone permissions/hardware and real Gnani streaming require a consented manual validation.

## Real providers from your laptop

Keep the existing EC2 model and SSH tunnel:

```powershell
ssh -i 'C:\Users\DELL\Downloads\callshield-evon-key.pem' -N -L 18080:127.0.0.1:8080 ubuntu@YOUR_CURRENT_EC2_IP
```

Use your actual EC2 IP; a stopped/restarted instance may receive another address. In the **root** `.env`, configure your existing provider credentials and:

```dotenv
EVON_BASE_URL=http://127.0.0.1:18080/v1
EVON_MODEL=evon
EVON_CONTEXT_TOKENS=4096
PRISMA_ENABLED=true
TIMBRE_ENABLED=true
```

Set `GNANI_API_KEY` to your issued key privately. Start the actual EC2 llama-server with `-c 4096` as described in [LIVE_STREAMING.md](LIVE_STREAMING.md); changing Python alone does not enlarge the model server context. Retain `--parallel 1`, CPU settings appropriate to the existing machine and alias `evon`. Thinking is disabled in requests; the displayed explanation is a brief grounded public summary, not chain-of-thought. Install FFmpeg and FFprobe for real uploads.

Stop mock launcher, then explicitly opt into provider usage:

```powershell
.\.venv\Scripts\python.exe scripts\dev.py --real
```

This can incur Gnani charges. Check REAL PROVIDERS in the interface. Test transcript first, then short consented audio, then live audio. The new structured Evon/streaming provider contracts have transport-level tests; this implementation session did not invoke your paid providers or change EC2. Provider failures remain errors/stale assessments, never silent mock fallbacks.

## EC2 deployment without a domain — your current choice

The deployment targets **Linux EC2**. Host networking lets Python reach the already-running Evon on `127.0.0.1:8080`. Do not use this Compose file as a Windows Docker Desktop recipe.

1. Install Docker Engine and the Compose plugin using the [official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Verify `sudo docker version` and `sudo docker compose version`.
2. Transfer the application source to a directory such as `/home/ubuntu/callshield-ai`, using your Git remote or the included source packager. On Windows run `.\.venv\Scripts\python.exe scripts\package_source.py`, then `scp -i 'C:\Users\DELL\Downloads\callshield-evon-key.pem' dist/callshield-source.tar.gz ubuntu@YOUR_CURRENT_EC2_IP:~/`. On EC2 run `tar -xzf callshield-source.tar.gz` and `cd callshield-ai`. The archive excludes `.env`, `deploy/.env`, `.aws`, `.tools`, `.venv`, `node_modules`, `gateway/target`, databases, key files and model files. Keep the existing GGUF where it is. Never put private keys in an archive.
3. On EC2, from the project root, run:

```bash
python3 deploy/init_config.py
sudo docker compose --env-file deploy/.env -f deploy/compose.yml config --quiet
sudo docker compose --env-file deploy/.env -f deploy/compose.yml up -d --build
sudo docker compose --env-file deploy/.env -f deploy/compose.yml ps
curl -f http://127.0.0.1:8090/api/health
```

`init_config.py` generates strong **application/database** secrets, never provider credentials; it creates `deploy/.env` privately and refuses to overwrite an existing file. The default deployment is MOCK and binds the edge to loopback port 8090. A generated local `deploy/.env` already exists in this workspace; do not transfer it—generate a new one on EC2.

4. On your Windows machine, open a tunnel:

```powershell
ssh -i 'C:\Users\DELL\Downloads\callshield-evon-key.pem' -N -L 8090:127.0.0.1:8090 ubuntu@YOUR_CURRENT_EC2_IP
```

5. Open **http://localhost:8090**, create an account and test. `localhost` supports microphone capture while SSH encrypts the remote connection. Keep port 8090 private; no new inbound EC2 application port is required for this preview. Use the exact localhost origin; a different hostname fails the WebSocket origin check.

The app and GGUF share your EC2 machine. Monitor available RAM/CPU/disk while building and running; the 30B quantized model consumes most resources. Inference remains serialized. The configuration is a single-instance pilot, not autoscaling infrastructure.

## Turn EC2 real mode on

Keep the model API on loopback. In EC2 `deploy/.env`, set `MOCK_MODE=false` and your issued `GNANI_API_KEY`; set `EVON_API_KEY` only if your existing llama-server requires it. `EVON_CONTEXT_TOKENS=4096` must match the actual server. The deployment already uses `EVON_BASE_URL=http://127.0.0.1:8080/v1`; the laptop SSH port 18080 is not used inside EC2.

```bash
sudo docker compose --env-file deploy/.env -f deploy/compose.yml up -d
sudo docker compose --env-file deploy/.env -f deploy/compose.yml logs --tail=80 ai gateway
```

No model download/training/startup is performed by Compose. Keep your existing llama-server running as its own supervised service. Do not expose ports 8000, 8080, 8081 or 5432 in the security group. Starting/restarting the app ends active live sessions; reports and accounts persist in PostgreSQL, but users sign in again after a Java restart.

## Add public HTTPS when you have a domain

Point a DNS A record at the instance's stable public IP/Elastic IP. Allow inbound TCP 80 and 443 in the EC2 security group, retain SSH restricted to your IP, and ensure no other process owns 80/443. Edit the existing private `deploy/.env` without changing its database password:

```dotenv
SITE_ADDRESS=callshield.your-domain.example
PUBLIC_ORIGIN=https://callshield.your-domain.example
EDGE_BIND=0.0.0.0
COOKIE_SECURE=true
```

Replace the example with your domain, then run Compose `up -d` again. Caddy obtains/renews certificates when DNS and inbound connectivity are correct; see [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https). HTTP on an arbitrary EC2 IP does not provide the browser secure context required for microphone capture. The existing no-domain SSH preview remains available until you switch configuration.

## Data, operations and boundaries

PostgreSQL lives in the named `callshield_postgres_data` Docker volume. Caddy certificate state has separate volumes. `down` preserves volumes; **do not use `down -v`** unless intentionally deleting data. Back up the database and encrypted deployment settings before migrations. A database dump can be taken on EC2 with:

```bash
umask 077
sudo docker compose --env-file deploy/.env -f deploy/compose.yml exec -T database pg_dump -U callshield -d callshield > callshield-backup.sql
```

Treat the dump as sensitive. Use encrypted EBS/backups and restrict access. Reports contain transcript/evidence in the database until deleted; there is no automatic durable report TTL. Python live sessions remain bounded in-memory and expire. Deletion removes the active database row, not external backups or provider-side retention. Raw live PCM is not stored by this app; Gnani still receives consented audio in real mode. Avoid debug logging or logging request bodies.

Accounts currently support registration/login/logout, not email verification, password reset, invitations or administrator workflows. Browser notifications are in-app only. The gateway lists the latest 100 reports. Authentication sessions are process-local; horizontal scaling would require shared sessions, shared AI session routing and revised rate limits. Alert events are not durable delivery receipts. Real provider accuracy and latency need representative evaluation before relying on the system.

## Architecture and contracts

See [FULL_STACK_ARCHITECTURE.md](FULL_STACK_ARCHITECTURE.md) for shareable diagrams. Spring's endpoints are:

| Method | Browser route | Purpose |
|---|---|---|
| GET | `/api/auth/csrf` | CSRF token and header name |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Account/session lifecycle |
| GET | `/api/auth/me` | Current account |
| GET | `/api/health`, `/api/capabilities`, `/api/ready` | Process/configuration/readiness |
| POST | `/api/analyze/text` | `{transcript,inputLanguage}` → persisted report envelope |
| POST | `/api/analyze/audio` | multipart `file,consent,inputLanguage` → persisted report |
| GET | `/api/records`, `/api/records/{id}` | Own summaries/report |
| DELETE | `/api/records/{id}` | Delete own report |
| POST | `/api/records/{id}/warning-audio` | `{language}` → approved WAV derived from saved risk |
| POST | `/api/live/sessions` | Python v2 session fields → owned session/socket path |
| GET | `/api/live/sessions/{id}` | Owned active Python snapshot |
| WS | `/ws/live/{id}` | Cookie-authenticated bidirectional live bridge |

Every browser mutation needs the CSRF header returned by `/api/auth/csrf`. Browser sockets use the authenticated session cookie and exact approved Origin. Spring forwards only its own private key to Python and does not forward the browser Origin. The Python v2 routes `/analyze/audio` and `/warnings/synthesize` are new private contracts; warning text cannot be supplied by the browser. The edge blocks direct Python `/api/v1` and `/api/v2` access.

## Validation performed

After the multilingual update: Python offline suite: 221 passing. Spring security/locale suite: 6 passing. React workflow/component suite: 8 passing; production bundle built successfully. Full mock stack exercised through actual HTTP/WebSocket connections, including Tamil input metadata and a Hindi explanation request through multipart upload. Compose interpolation validated. Local Docker image execution/PostgreSQL smoke testing was not possible because Docker Engine is not running on this Windows environment. Chrome visual inspection was unavailable because computer-use access was not approved. No production deployment is claimed.

Technical references: [Spring Boot 3.5 requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html), [Gnani streaming STT](https://docs.gnani.ai/api/STT/stt-websocket), [Gnani SDK](https://github.com/Gnani-AI-Mintlify/gnani-vachana), [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Design direction was informed by [Dribbble cybersecurity dashboard references](https://dribbble.com/shots/27376069-Cybersecurity-Dashboard-Design-Dark-UI-Data-Visualization); the shipped composition and assets are original code/SVG, not copied designs.
