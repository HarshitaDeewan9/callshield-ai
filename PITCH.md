# 🛡️ CallShield AI — 1-Page Solution Pitch

**Tagline:** Real-Time Conversational Fraud Defense Powered by Gnani Voice AI & Evon 30B  
**Live Production URL:** [https://callshiel.me](https://callshiel.me)  
**GitHub Repository:** [https://github.com/HarshitaDeewan9/callshield-ai](https://github.com/HarshitaDeewan9/callshield-ai)  

---

### 1. The Problem
Every year, Indian citizens lose over **₹1,700 Crores** to conversational telecom scams. Attackers increasingly exploit **fear, digital arrest threats, courier interception, and fake bank KYC suspensions** in native Indian languages. 

Existing solutions fail because:
* **Caller-ID blockers (e.g. Truecaller)** only check reported phone numbers, which spoofed VoIP numbers easily bypass.
* **Regex/Keyword filters** fail against conversational social engineering and generate massive false alarms whenever benign users mention words like "OTP" or "Bank".

### 2. The Solution: CallShield AI
**CallShield AI** is an enterprise-grade, consent-first fraud interception platform that protects users during active calls by listening for *intent and coercion*, not just keywords.

1. **Multilingual Speech Ingestion (Gnani Prisma v2.5):** Captures live audio chunks with explicit user consent and transcribes code-mixed Indian speech across 10+ Indic languages and English with sub-second latency.
2. **Contextual Intent Reasoning (Evon 30B Indian Foundation Model):** Evaluates conversational turns against complex psychological fraud patterns. Evon accurately distinguishes between hostile credential demands and protective advice (e.g. *"Never share your OTP"* is recognized as 100% safe).
3. **Dual Defense Mechanism:**
   * **Real-Time Visual Alerts:** Dynamic risk gauge (0–100), scenario tagging (`credential_theft`, `emergency_scam`, `impersonation`), and exact verbatim evidence quotes.
   * **Immediate Spoken Voice Warnings (Gnani Timbre v2.5):** Synthesizes automated voice alerts through phone speakers in English (`Kaveri`) and Hindi (`Nalini`) to prevent the victim from transferring money or disclosing passwords.

### 3. Production Architecture & Tech Stack
* **Cloud Infrastructure:** Hosted on AWS EC2 (`ap-south-1` Mumbai) with **Caddy v2** managing automated Let's Encrypt SSL/TLS certificates and HTTP/2 WebSocket streaming.
* **Backend Security Gateway:** **Java 21 / Spring Boot 3.5** enforcing BCrypt auth, CSRF tokens, secure HTTP-only sessions, and **PostgreSQL 17** persistence with Flyway migrations for forensic auditing.
* **AI Orchestration Engine:** **Python 3.12 / FastAPI** managing asynchronous LLM admission queues and memory-safe audio buffers (raw audio is never stored unencrypted).
* **Live Foundation Models:** Direct cloud connection to **Gnani Prisma STT**, **Gnani Timbre TTS**, and private EC2 inference on **Evon 30B GGUF**.

### 4. Feasibility, Scalability & Market Impact
* **Zero Barrier to Adoption:** Works instantly as a mobile web application, with native capability to connect to telecom carrier SIP trunks (Jio, Airtel) or mobile dialer apps.
* **Enterprise & Consumer Value:** Scalable to millions of concurrent calls, saving families and seniors from financial ruin while providing banks and law enforcement with tamper-proof evidence logs.

