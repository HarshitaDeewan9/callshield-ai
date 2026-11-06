"""Generate vector PDF/SVG architecture diagrams. Requires reportlab (authoring only)."""

import math
from pathlib import Path

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "architecture"
W, H = 1600, 1000
INK = "#142D42"
MUTED = "#52697A"
PALETTE = {
    "built": ("#E7F5F2", "#14806E"),
    "provider": ("#F0ECFB", "#7660AF"),
    "external": ("#FFF3E5", "#C77B27"),
    "store": ("#EDF2F7", "#627C94"),
    "error": ("#FCEEEE", "#B95959"),
}


def color(value):
    return colors.HexColor(value)


class Page:
    def __init__(self, number, slug, title, subtitle, source):
        self.number, self.slug = number, slug
        self.d = Drawing(W, H)
        self.d.add(Rect(0, 0, W, H, fillColor=color("#FAFCFD"), strokeColor=None))
        self.d.add(Rect(0, H - 14, W, 14, fillColor=color("#14806E"), strokeColor=None))
        self.text(56, 51, "CALLSHIELD INDIA  /  ENGINEERING HANDOFF", 16, "#14806E", bold=True)
        self.text(56, 101, title, 37, bold=True)
        self.text(56, 140, subtitle, 19, MUTED)
        self.line([(56, 922), (1544, 922)], "#D9E3EB", arrow=False)
        self.text(56, 950, source, 13, MUTED)
        self.text(
            56,
            977,
            "Source snapshot: 20 October 2026 | M0-M5 implemented | External clients are separate projects",
            13,
            MUTED,
        )
        self.text(1485, 969, f"{number:02d} / 08", 16, MUTED, bold=True)

    def text(self, x, top, value, size=20, fill=INK, bold=False, center=False):
        self.d.add(
            String(
                x,
                H - top,
                value,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                fontSize=size,
                fillColor=color(fill),
                textAnchor="middle" if center else "start",
            )
        )

    def wrap(self, text, width, size, bold=False):
        font = "Helvetica-Bold" if bold else "Helvetica"
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = (current + " " + word).strip()
                if stringWidth(candidate, font, size) > width:
                    if not current:
                        raise ValueError(f"Unbreakable diagram text: {word}")
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        return lines

    def box(self, x, y, w, h, title, body="", kind="built", size=19):
        bg, border = PALETTE[kind]
        self.d.add(
            Rect(
                x,
                H - y - h,
                w,
                h,
                rx=14,
                ry=14,
                fillColor=color(bg),
                strokeColor=color(border),
                strokeWidth=1.8,
            )
        )
        titles = self.wrap(title, w - 40, 22, True)
        top = y + 34
        for label in titles:
            self.text(x + 20, top, label, 22, border, bold=True)
            top += 27
        top += 7
        for label in self.wrap(body, w - 40, size):
            self.text(x + 20, top, label, size)
            top += size + 7
        if top - (size + 7) > y + h - 15:
            raise ValueError(f"Text overflow in {self.slug}: {title}")

    def line(self, points, stroke=INK, arrow=True, dashed=False):
        for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
            self.d.add(
                Line(
                    x1,
                    H - y1,
                    x2,
                    H - y2,
                    strokeColor=color(stroke),
                    strokeWidth=2,
                    strokeDashArray=[7, 5] if dashed else None,
                )
            )
        if arrow:
            (x1, y1), (x2, y2) = points[-2:]
            angle = math.atan2(y2 - y1, x2 - x1)
            points2 = [x2, H - y2]
            for delta in (-0.45, 0.45):
                points2 += [x2 - 12 * math.cos(angle + delta), H - y2 + 12 * math.sin(angle + delta)]
            self.d.add(Polygon(points2, fillColor=color(stroke), strokeColor=color(stroke)))

    def note(self, y, title, body, kind="store", h=110):
        self.box(56, y, 1488, h, title, body, kind, size=19)


def build_pages():
    pages = []
    p = Page(
        1,
        "01-system-context",
        "System context & ownership",
        "The Python service is the implemented product in this repository. Spring owns the end-user boundary.",
        "Sources: app/main.py | app/core/auth.py | app/services/pipeline.py | SPRING_BOOT_HANDOFF.md",
    )
    p.box(
        56,
        230,
        300,
        190,
        "React client",
        "Teammate project\nText/audio submission\nRisk display + playback",
        "external",
    )
    p.box(
        456,
        230,
        360,
        190,
        "Spring Boot backend",
        "Teammate project\nUser auth + ownership\nDurable persistence",
        "external",
    )
    p.box(
        916,
        215,
        628,
        225,
        "CallShield FastAPI service",
        "Implemented here: /api/v1\nConsented uploads + shared text pipeline\nApproved warnings + optional WAV response\nSynchronous reports + expiring in-memory state",
    )
    p.line([(356, 325), (456, 325)])
    p.text(406, 300, "HTTPS", 16, center=True)
    p.line([(816, 325), (916, 325)])
    p.text(866, 290, "Private HTTP", 14, center=True)
    p.text(866, 310, "X-API-Key", 14, center=True)
    p.box(
        56,
        585,
        310,
        180,
        "Gnani Prisma",
        "Hosted STT v2.5\nOfficial Python SDK\nAudio -> transcript",
        "provider",
    )
    p.box(
        446,
        585,
        310,
        180,
        "Google translation",
        "Optional v3 NMT\nRegional input -> English\nIdentity when preserved",
        "provider",
    )
    p.box(
        836,
        585,
        310,
        180,
        "Gnani Evon",
        "Existing private EC2\nv3.3 GGUF / llama.cpp\nTranscript -> A/B/C",
        "provider",
    )
    p.box(
        1226,
        585,
        318,
        180,
        "Gnani Timbre",
        "Hosted TTS v2.5\nEnglish / Hindi warnings\nOn demand, not analysis",
        "provider",
    )
    p.line([(1230, 440), (1230, 510), (211, 510)], arrow=False)
    for x in (211, 601, 991, 1385):
        if x > 1230:
            p.line([(1230, 510), (x, 510)], arrow=False)
        p.line([(x, 510), (x, 585)])
    p.text(56, 845, "Legend", 18, bold=True)
    for x, kind, label in [
        (155, "built", "Implemented Python"),
        (530, "provider", "Real provider boundary"),
        (950, "external", "Separate teammate project"),
    ]:
        p.d.add(
            Rect(x, H - 849, 18, 18, fillColor=color(PALETTE[kind][0]), strokeColor=color(PALETTE[kind][1]))
        )
        p.text(x + 30, 845, label, 18)
    pages.append(p)

    p = Page(
        2,
        "02-components",
        "Python components & adapter seams",
        "Routes orchestrate services; provider details remain behind small, replaceable contracts.",
        "Sources: app/api/* | app/services/* | app/providers/interfaces.py | app/main.py",
    )
    p.box(
        56,
        200,
        1488,
        110,
        "Request boundary",
        "Body/time caps -> X-API-Key -> per-backend rate limit -> validated request schema",
    )
    p.box(
        56,
        365,
        440,
        190,
        "API routers",
        "routes_analysis: text + retrieval\nroutes_audio: upload + warning audio\nhealth + capabilities",
        size=18,
    )
    p.box(
        576,
        365,
        440,
        190,
        "Pipeline service",
        "language_policy -> classifier\nevidence_rules + warning selection\nReport + provider provenance",
        size=18,
    )
    p.box(
        1096,
        365,
        448,
        190,
        "ReportStore",
        "Owner-bound entries + progress\nReports: 500 max / 30 min TTL\nWarning cache + periodic purge",
        "store",
        size=18,
    )
    for x in (276, 796, 1320):
        p.line([(x, 310), (x, 365)])
    p.line([(496, 460), (576, 460)])
    p.line([(1016, 460), (1096, 460)])
    p.box(
        56, 650, 330, 160, "PrismaSTTProvider", "GnaniPrismaProvider\nMockPrismaProvider", "provider", size=18
    )
    p.box(442, 650, 330, 160, "Translator", "Identity / GoogleCloud\nMockTranslator", "provider", size=18)
    p.box(828, 650, 330, 160, "Classifier", "EvonLlamaCppProvider\nMockEvonProvider", "provider", size=18)
    p.box(
        1214,
        650,
        330,
        160,
        "TimbreTTSProvider",
        "GnaniTimbreProvider\nMockTimbreProvider",
        "provider",
        size=18,
    )
    p.line([(276, 555), (276, 605), (221, 605), (221, 650)])
    p.line([(796, 555), (796, 605), (607, 605), (607, 650)])
    p.line([(796, 605), (993, 605), (993, 650)])
    p.line([(496, 510), (536, 510), (536, 580), (1379, 580), (1379, 650)])
    p.text(
        56,
        871,
        "Composition: create_app() selects mock or real providers at startup; shared contracts keep the REST API stable.",
        20,
    )
    pages.append(p)

    p = Page(
        3,
        "03-text-sequence",
        "Text analysis: synchronous sequence",
        "POST /api/v1/analyze/text returns a completed report or an honest operational failure.",
        "Sources: app/api/routes_analysis.py | app/services/pipeline.py | app/providers/evon_llamacpp.py",
    )
    lanes = [
        (150, "Spring"),
        (450, "API / security"),
        (780, "Pipeline"),
        (1130, "Translator / Evon"),
        (1450, "ReportStore"),
    ]
    for x, title in lanes:
        p.text(x, 218, title, 20, bold=True, center=True)
        p.line([(x, 240), (x, 770)], "#B8C8D4", arrow=False, dashed=True)

    def seq(x1, x2, y, label, dashed=False):
        p.line([(x1, y), (x2, y)], dashed=dashed)
        p.text((x1 + x2) / 2, y - 12, label, 17, center=True)

    seq(150, 450, 285, "1  JSON + backend key")
    seq(450, 780, 350, "2  Validate / authorize")
    seq(780, 1450, 415, "3  Create UUID; status QUEUED")
    seq(780, 1130, 480, "4  Preserve or normalize")
    seq(780, 1130, 545, "5  Bounded Evon request")
    seq(1130, 780, 610, "6  Strict A/B/C + stop", True)
    seq(780, 1450, 675, "7  Rules + approved warning; save COMPLETED")
    seq(780, 150, 740, "8  200 Report: original + normalized text, risk, warning, timings, mock flags", True)
    p.note(
        805,
        "Failure contract",
        "Invalid/empty model output -> 502; unavailable Evon -> 503; timeout -> 504; queue pressure -> 429. No false LOW_RISK result.",
        "error",
        h=100,
    )
    pages.append(p)

    p = Page(
        4,
        "04-audio-flow",
        "Consented audio -> shared analysis",
        "POST /api/v1/analyze/audio adds safe media handling before the same text pipeline.",
        "Sources: app/api/routes_audio.py | app/services/audio_utils.py | app/providers/gnani_prisma.py",
    )
    p.box(
        56,
        220,
        405,
        170,
        "1  Upload gate",
        "Explicit consent=true\nWAV/MP3 MIME + magic bytes\n15 MiB file cap by default",
        size=19,
    )
    p.box(
        596,
        220,
        405,
        170,
        "2  Inspect & decode",
        "Real mode: ffprobe + ffmpeg\nDuration > 0 and <= 60 seconds\n20-second subprocess limits",
        size=19,
    )
    p.box(
        1136,
        220,
        408,
        170,
        "3  Temporary WAV",
        "Mono PCM, 16-bit, 16 kHz\nService normalization choice\nClient filenames ignored",
        size=19,
    )
    p.line([(461, 305), (596, 305)])
    p.line([(1001, 305), (1136, 305)])
    p.box(
        1136,
        500,
        408,
        180,
        "4  Prisma STT",
        "Official GnaniSTTClient\nExplicit supported input locale\nRequire success + transcript",
        "provider",
        size=19,
    )
    p.line([(1340, 390), (1340, 500)])
    p.box(
        596,
        500,
        405,
        180,
        "5  Shared pipeline",
        "Original + normalized transcript\nEvon label + rules + warning\nSame semantics as text input",
        size=19,
    )
    p.line([(1136, 590), (1001, 590)])
    p.box(
        56,
        500,
        405,
        180,
        "6  Report JSON",
        "inputType=AUDIO\nSTT provider + mock provenance\nNo invented diarization",
        size=19,
    )
    p.line([(596, 590), (461, 590)])
    p.note(
        760,
        "Temporary inputs are deleted on success and failure",
        "Mock WAV validation uses the standard library; mock STT returns a labeled fixed fixture. Real input always uses the media tools. MP3 needs FFmpeg in either mode.",
        h=135,
    )
    pages.append(p)

    p = Page(
        5,
        "05-warning-flow",
        "Warning audio is a separate operation",
        "POST /api/v1/analyses/{id}/warning-audio accepts language/voice, never arbitrary speech text.",
        "Sources: app/api/routes_audio.py | app/services/warnings.py | app/providers/gnani_timbre.py | report_store.py",
    )
    p.box(
        56,
        215,
        380,
        175,
        "1  Resolve saved result",
        "Backend key + owner lookup\nCompleted risk required\nLOW_RISK -> 409, no audio",
        size=19,
    )
    p.box(
        586,
        215,
        380,
        175,
        "2  Approved template",
        "HIGH_RISK / SUSPICIOUS\nCurated English or Hindi\nOther locales -> English",
        size=19,
    )
    p.box(
        1116,
        215,
        428,
        175,
        "3  Voice + cache key",
        "en-IN: Kaveri / hi-IN: Nalini\n(templateId, locale, voice)\nLookup within this analysis",
        size=19,
    )
    p.line([(436, 300), (586, 300)])
    p.line([(966, 300), (1116, 300)])
    p.box(
        1116,
        510,
        428,
        175,
        "4  Timbre on cache miss",
        "Official GnaniTTSClient\nModel: timbre-v2.5\nComplete WAV bytes validated",
        "provider",
        size=19,
    )
    p.line([(1330, 390), (1330, 510)])
    p.text(1347, 459, "Miss", 17)
    p.box(
        586,
        510,
        380,
        175,
        "5  Cache + metadata",
        "32 MiB aggregate budget\n1-hour audio TTL, bounded by\nreport lifetime / eviction",
        "store",
        size=19,
    )
    p.line([(1116, 600), (966, 600)])
    p.line([(1330, 390), (1330, 445), (776, 445), (776, 510)])
    p.text(940, 433, "Cache hit bypasses provider", 17)
    p.box(
        56,
        510,
        380,
        175,
        "6  Raw audio response",
        "Content-Type: audio/wav\nX-Mock / X-Audio-Kind\nRequested + actual locale",
        size=19,
    )
    p.line([(586, 600), (436, 600)])
    p.note(
        765,
        "TTS failure never discards classification",
        "The report remains COMPLETED with its existing risk; warning.audioStatus becomes FAILED. Mock output is a labeled 440 Hz tone, not synthesized speech.",
        "error",
        h=130,
    )
    pages.append(p)

    p = Page(
        6,
        "06-provider-modes",
        "Mock mode & real integration contracts",
        "The same REST contract is served by different startup-selected adapters. No silent fallback exists.",
        "Sources: app/main.py | app/providers/mock_providers.py | gnani_prisma.py | gnani_timbre.py | google_translation.py",
    )
    p.box(
        56,
        205,
        1488,
        105,
        "Startup configuration",
        "MOCK_MODE=true by default | Real/production mode requires a backend API key with at least 24 characters",
    )
    p.box(
        56,
        370,
        700,
        385,
        "MOCK_MODE=true",
        "Evon: deterministic demonstration rules\nPrisma: fixed English scam transcript\nTimbre: playable 0.5-second test tone\nTranslation: identity, or fixed mock fixture\nEvery mocked stage has mock=true\nNo provider network calls or API credentials",
        "built",
        size=22,
    )
    p.box(
        844,
        370,
        700,
        385,
        "MOCK_MODE=false",
        "Evon: private /v1/chat/completions HTTP\nPrisma/Timbre: gnani-vachana 0.8.1\nSpeech auth: X-API-Key-ID via official SDK\nTranslation: identity or Google v3 NMT\nSpeech SDK calls: bounded worker threads\nErrors stay explicit; predictions are not fabricated",
        "provider",
        size=22,
    )
    p.line([(400, 310), (400, 370)])
    p.line([(1194, 310), (1194, 370)])
    p.note(
        800,
        "Evon request invariants",
        "enable_thinking=false; temperature=0; max_tokens=8; stream=false. Accept only A/B/C after whitespace with finish_reason=stop. Ignore reasoning_content; confidence=null.",
        h=110,
    )
    pages.append(p)

    p = Page(
        7,
        "07-deployment",
        "Deployment & trust boundaries",
        "Recommended topology: Python and llama.cpp on the same EC2 host; expose only the Python private ingress.",
        "Sources: Dockerfile | docker-compose.yml | app/config.py | app/core/auth.py | app/api/routes_health.py",
    )
    p.box(
        56,
        235,
        350,
        205,
        "Spring Boot server",
        "Separate teammate deployment\nOwns end-user authentication\nChecks user/report ownership\nBackend secret stays server-side",
        "external",
        size=19,
    )
    p.d.add(
        Rect(
            506,
            H - 650,
            1038,
            445,
            rx=18,
            ry=18,
            fillColor=None,
            strokeColor=color("#627C94"),
            strokeWidth=2,
            strokeDashArray=[8, 5],
        )
    )
    p.text(534, 240, "PRIVATE EC2 HOST / NETWORK", 18, MUTED, bold=True)
    p.box(
        546,
        285,
        420,
        225,
        "Python / Uvicorn",
        "One worker / replica per Evon\nPrivate API, typical port 8000\nIn-memory reports + cache\nHTTPS ingress + X-API-Key",
        size=21,
    )
    p.box(
        1086,
        285,
        418,
        225,
        "llama.cpp + Evon",
        "Existing community GGUF\nLoopback 127.0.0.1:8080\nModel alias evon; --parallel 1\nNo public port 8080",
        "provider",
        size=21,
    )
    p.line([(406, 370), (546, 370)])
    p.text(476, 347, "Private/TLS", 16, center=True)
    p.line([(966, 395), (1086, 395)])
    p.text(1026, 370, "Local HTTP", 15, center=True)
    p.text(546, 572, "Private egress to Gnani STT/TTS and optional Google Translation.", 21)
    p.text(546, 610, "Evon readiness: GET /v1/models; no inference during health checks.", 20)
    p.box(
        56,
        725,
        705,
        165,
        "Local Docker option",
        "Compose defaults to mock mode; host 127.0.0.1:8000.\nNon-root image, read-only compose root + tmpfs.\nContainer loopback is not the EC2 host loopback.",
        "store",
        size=19,
    )
    p.box(
        839,
        725,
        705,
        165,
        "Operational constraints",
        "Evon stopped -> readiness/classification 503.\nConfigured speech readiness is not a quota/auth probe.\nNo database or distributed queue is implemented.",
        "error",
        size=19,
    )
    pages.append(p)

    p = Page(
        8,
        "08-state-and-contract",
        "Result lifecycle & teammate contract",
        "IDs refer to real in-memory entries; Spring should retain successful reports durably.",
        "Sources: app/services/report_store.py | app/services/pipeline.py | app/api/routes_analysis.py | schemas/responses.py",
    )
    states = [(56, "QUEUED"), (425, "TRANSCRIBING"), (794, "TRANSLATING"), (1163, "CLASSIFYING")]
    for x, label in states:
        p.box(x, 220, 325, 105, label, "Audio only" if label == "TRANSCRIBING" else "Progress state", size=17)
    for a, b in zip(states, states[1:], strict=False):
        p.line([(a[0] + 325, 270), (b[0], 270)])
    p.line([(218, 220), (218, 185), (956, 185), (956, 220)], dashed=True)
    p.text(565, 178, "Text skips STT", 16, center=True)
    p.box(1163, 415, 325, 140, "COMPLETED", "A / B / C risk\nWarning + provenance", size=18)
    p.line([(1325, 325), (1325, 415)])
    p.box(
        56,
        415,
        650,
        140,
        "FAILED / operational UNDETERMINED",
        "Typed error envelope; no successful risk label.\nFailure after allocation keeps its analysisId.",
        "error",
        size=19,
    )
    p.line([(956, 325), (956, 370), (381, 370), (381, 415)], "#B95959", dashed=True)
    p.text(563, 357, "A ServiceError at any active stage", 17, "#B95959")
    p.box(
        56,
        645,
        450,
        230,
        "Stable report payload",
        "analysisId + status + inputType\nOriginal and normalized text\nRisk: code, level, null confidence\nRules + warning + provenance\nTiming fields + mock flags",
        size=19,
    )
    p.box(
        576,
        645,
        450,
        230,
        "GET /analyses/{id}",
        "200: report, progress or saved error\n404: missing / expired entry\nCheck body status even on HTTP 200\n500 entries / 30-minute report TTL\nProcess restart loses all entries",
        "store",
        size=19,
    )
    p.box(
        1096,
        645,
        448,
        230,
        "Spring integration rules",
        "Never translate failures into LOW_RISK\nKeep backend key away from React\nAuthorize ownership before proxying\nNo automatic paid-request retries\nFetch capabilities before UI setup",
        "external",
        size=19,
    )
    pages.append(p)
    return pages


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pages = build_pages()
    canvas = Canvas(str(OUT / "CallShield_Architecture_and_Technical_Diagrams.pdf"), pagesize=(1024, 640))
    canvas.setTitle("CallShield India - Architecture and Technical Diagrams")
    canvas.setAuthor("CallShield engineering")
    for page in pages:
        renderSVG.drawToFile(page.d, str(OUT / f"{page.slug}.svg"))
        canvas.saveState()
        canvas.scale(0.64, 0.64)
        renderPDF.draw(page.d, canvas, 0, 0)
        canvas.restoreState()
        canvas.showPage()
    canvas.save()
    print(f"Generated {len(pages)} SVG diagrams and one vector PDF in {OUT}")


if __name__ == "__main__":
    main()
