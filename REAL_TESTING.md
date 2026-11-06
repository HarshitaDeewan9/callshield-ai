# Real Gnani testing and multilingual verification

## Why the previous preview looked fake

`python scripts/dev.py` explicitly starts **MOCK** providers. It does so even if the root `.env` says `MOCK_MODE=false`; the command-line launcher deliberately overrides that setting. No Evon inference, Prisma transcription or Timbre synthesis occurs in this mode. Its transcript, score and explanation are development fixtures. Mock quotes are taken from the supplied text or **fixed mock audio transcript**, not from the speech in your recording. Historical mock reports remain mock after you change modes.

Use **`python scripts/dev.py --real`** to start the complete studio with your configured real providers. There is no automatic fallback from real failures to mock responses.

## 1. Start the existing Evon model on EC2

Connect to the instance using your actual current public address:

```powershell
ssh -i 'C:\Users\DELL\Downloads\callshield-evon-key.pem' ubuntu@YOUR_CURRENT_EC2_IP
```

On EC2, first check the existing process and its command:

```bash
pgrep -af llama-server
ss -ltnp | grep ':8080'
```

If it is still using the old `-c 512`, stop that specific foreground process with Ctrl+C or restart its existing supervised service. Use the same executable/model, increasing context to match the application:

```bash
LLAMA_SERVER="$(find "$HOME" -type f -path '*/build/bin/llama-server' -print -quit 2>/dev/null)"
test -n "$LLAMA_SERVER" || { echo 'Locate your existing llama-server executable first'; exit 1; }
"$LLAMA_SERVER" \
  -m "$HOME/evon-model/gnani-evon-v3.3-30B-A3B-Q3_K_S.gguf" \
  --alias evon --host 127.0.0.1 --port 8080 \
  -ngl 0 -c 4096 -t 4 --parallel 1
```

Wait for the model to finish loading. In another EC2 shell, `curl -f http://127.0.0.1:8080/health` should succeed. Retain any authentication flags your existing server requires. There is no new model download, training or replacement. Python requests still disable thinking with `enable_thinking=false`; the UI gets a short assessment summary.

## 2. Open the private model tunnel from Windows

Keep this command running in a separate PowerShell window:

```powershell
ssh -i 'C:\Users\DELL\Downloads\callshield-evon-key.pem' -N -L 18080:127.0.0.1:8080 ubuntu@YOUR_CURRENT_EC2_IP
```

In a different window:

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```

If the server has an API key, use its configured authentication header privately. Connection refused means the remote model listener is unavailable; an SSH timeout is an EC2/SSH networking issue. Do not open model port 8080 publicly.

## 3. Configure the root application `.env`

Edit `E:\callshield-ai\.env` privately. Keep your existing issued Gnani credential and set:

```dotenv
EVON_BASE_URL=http://127.0.0.1:18080/v1
EVON_MODEL=evon
EVON_CONTEXT_TOKENS=4096
RISK_MAX_TOKENS=512
EVON_TIMEOUT_SECONDS=180
PRISMA_ENABLED=true
TIMBRE_ENABLED=true
```

`GNANI_API_KEY` must contain **your issued key**. `EVON_API_KEY` is needed only if your llama-server requires one. Do not paste secrets into screenshots/chat/frontend configuration. FFmpeg and FFprobe must be on PATH or configured through `FFMPEG_PATH` / `FFPROBE_PATH` for real audio uploads.

The studio launcher generates its own temporary Python↔Spring backend key; you do not type that key into React. The root `.env` is for the native launcher; `deploy/.env` is separate and is only used by EC2 Compose. Changing one does not change the other.

## 4. Start all three services in real mode

Stop the previous mock launcher with Ctrl+C. Rebuild the gateway once after this update, while Java is stopped:

```powershell
cd E:\callshield-ai
$env:JAVA_HOME = 'E:\callshield-ai\.tools\jdk\jdk-21.0.13+9'
$env:DEBUG = 'false'
& .tools\maven\apache-maven-3.10.0\bin\mvn.cmd '-Dmaven.repo.local=E:\callshield-ai\.tools\m2' -f gateway\pom.xml package
.\.venv\Scripts\python.exe scripts\dev.py --real
```

The gateway has already been built in this workspace. For future builds use installed Java 21/Maven or the portable paths above. Open **http://localhost:5173**, sign in or create an account, and start a **new review**. The top badge must say **REAL PROVIDERS** and the persistent demo banner must be absent. Mode indicates configuration, not successful model inference—check the new report's provenance too.

### First: test real text classification

Choose Transcript, choose a conversation language and an explanation language, then submit a short controlled example. For Hindi:

```text
Caller: मैं बैंक से बोल रहा हूँ। खाता बंद होने से बचाने के लिए अपना OTP अभी बताइए।
Customer: मैं पहले बैंक के आधिकारिक नंबर पर पुष्टि करूँगा।
```

Then start another review with a protective sentence:

```text
Caller: अपना OTP किसी के साथ साझा न करें। बैंक कभी आपका OTP नहीं माँगता।
```

Inspect the response/provenance. A real completed report must contain:

```json
{
  "mock": false,
  "assessment": {
    "source": "evon",
    "mock": false,
    "model": "gnani-evon-v3.3-gguf",
    "explanationSource": "model_generated_summary",
    "evidenceSource": "evon_selected_original_quote",
    "evidenceQuotesValidated": true
  }
}
```

This is a **required metadata shape**, not a fabricated provider result. Evidence quotes must appear exactly in your submitted transcript. Python rejects invented/transformed quotes with `MODEL_OUTPUT_INVALID`. Exact quote validation proves textual grounding, not correctness of the model's fraud judgment. Do not require a particular numeric score to pass an integration check; the model can be wrong. View the actual llama-server request activity on EC2 while submitting a new review to confirm traffic reaches your instance. No thinking trace is displayed.

### Next: test real audio and warning playback

Record a short consented clip in the selected language, upload it and verify that the transcript actually follows what was spoken. Real audio reports must show `transcription.provider=gnani-prisma`, `transcription.mock=false`, and an Evon assessment with `mock=false`. Upload a different clip with clearly different words; a constant demo transcript is a failure, not a success. Only send non-sensitive test content.

For an eligible report (risk >=20), select English or Hindi safety advice and click Play safety advice. Real Timbre should return intelligible speech, not the mock test tone. Advice is an approved template, not an LLM-generated explanation spoken aloud.

### Finally: test live microphone capture

Choose Live monitor → Mic → explicit conversation language → consent → Start listening. Grant browser microphone access. Speak a short sentence, pause, then add context. Check completed transcripts against your speech. New scores require speech completion and successful Evon inference; CPU inference and STT segmentation prevent a guaranteed one-second new score. Finish to drain final speech and save the report.

This captures the selected browser microphone. It does not automatically access the audio of an active cellular call. Use consented microphone/speaker test setup or a supported audio input device.

## Optional executable verification through the complete studio

Create a studio account first. With `scripts/dev.py --real` running:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_real_stack --confirm-real --live
```

It prompts for your existing studio email/password without printing the password. It signs in through Spring and rejects mock mode **before inference**. It verifies real Evon metadata and exact quote matches, then tests incremental text through the actual frontend→Spring→Python WebSocket route. It saves real reports to your account.

For real Prisma plus optional Timbre:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_real_stack --confirm-real `
  --language hi-IN --explanation-language hi-IN `
  --text 'अपना OTP अभी बताइए।' `
  --audio 'C:\path\consented-hindi.wav' --consent --tts
```

`--confirm-real` explicitly permits provider requests/possible charges. No credential/provider response is invented. `--tts` is skipped if the selected report has a minimal score. The script prints result metadata, not transcript/audio contents. Live microphone hardware/permissions still need the UI test above. Use `--base-url http://localhost:8090` through the EC2 preview tunnel, or your exact HTTPS public origin, when testing the deployed gateway.

## What multilingual support now means in this application

| Feature | Enabled languages / behavior |
|---|---|
| Evon original-script text | English, Hindi, Bengali, Telugu, Tamil, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi |
| Hinglish text | Additional Roman Hindi/English text option; not an STT locale |
| Prisma clip/live audio | The same list except Odia; explicit locale selection |
| Explanation language | Choose separately from conversation language; Evon is prompted in the requested language |
| Evidence quotes | Always copied from the original input/STT transcript; never translated |
| Timbre warnings | Curated English and Hindi templates only in this app |
| Auto language detection | Not enabled on the retained Prisma v2.5 integration |
| Translation | None on the studio v2 path; Evon reads original multilingual text directly |
| Fraud accuracy | Not established by the provider language catalog or mock tests; evaluate separately |

The backend publishes this per-language catalog in `/api/v1/capabilities` → `studio` (browser route `/api/capabilities`). React uses it to populate options and display the multilingual feature panel. Spring validates/forwards the input and explanation locales; Python validates supported combinations and preserves Unicode. Odia and Hinglish are explicitly text-only. The new catalog applies to studio v2; the legacy v1 normalization policy is unchanged.

`explanationLanguage` describes the requested model output language. `explanationLanguageVerified=false` explicitly records that the server does not run a language detector to certify compliance. Mock summaries stay English even if another language is requested. Real quote validation checks the exact original script. Model fields/scenario enum remain stable for Java/React even when the explanation is localized.

Provider sources checked: [Evon model card](https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B), [Prisma streaming language catalog](https://docs.gnani.ai/api/STT/stt-websocket), [official Gnani SDK](https://github.com/Gnani-AI-Mintlify/gnani-vachana). Current docs also offer opt-in Prisma v3.0 auto-detection/code-mix; this change deliberately retains the installed v2.5 integration. Enabling v3 would be a separate versioned adapter upgrade with SDK/contract tests, not a dropdown claim.

## A useful multilingual evaluation

Build paired suspicious/protective/ambiguous conversations in each target language. Include negation, legitimate family help, impersonation, urgent transfer demands, dialects, code-switching and adversarial instructions. Have native speakers label them. Measure STT transcript quality separately from Evon false alerts/missed scams and explanation grounding. Compare equivalent meanings across languages without demanding identical numerical scores. Test incremental corrections, threshold crossing, context-window omissions and inference latency. Do not infer risk from accent, loudness or identity stereotypes.

Real integrations need live credentials/connectivity. This update is tested offline with intercepted provider transports and a running mock stack; it does not claim that paid Gnani calls were executed by the agent.
