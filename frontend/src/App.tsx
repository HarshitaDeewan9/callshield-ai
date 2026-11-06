import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileAudio,
  FileText,
  Fingerprint,
  History,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Menu,
  Mic,
  Plus,
  Radio,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Upload,
  Volume2,
  X,
  Zap,
} from "lucide-react";
import { clearCsrf, post, request } from "./api";
import {
  EmptyExplanation,
  FadeIn,
  Logo,
  RiskGauge,
  RiskTimeline,
  SignalOrb,
} from "./components";
import { LanguageStudio, ResultProvenance } from "./LanguageStudio";
import { startMicrophone } from "./microphone";
import type {
  Capabilities,
  LiveEvent,
  RecordSummary,
  RecordView,
  Result,
  User,
} from "./types";

type Mode = "live" | "text" | "audio";
type Policy = {
  threshold: number;
  resetBelow: number;
  cooldownSeconds: number;
};
const SAMPLE =
  "Caller: I am calling from your bank.\nCustomer: What is this about?\nCaller: Tell me your OTP now or your account will be blocked.";
const DEFAULT_POLICY: Policy = {
  threshold: 70,
  resetBelow: 50,
  cooldownSeconds: 30,
};
function initialPolicy() {
  try {
    const value = JSON.parse(
      localStorage.getItem("callshield.policy") || "null",
    );
    if (
      value &&
      Number.isInteger(value.threshold) &&
      value.threshold > 0 &&
      value.threshold <= 100 &&
      value.resetBelow >= 0 &&
      value.resetBelow < value.threshold &&
      value.cooldownSeconds >= 0 &&
      value.cooldownSeconds <= 3600
    )
      return value as Policy;
  } catch {
    /* use safe defaults */
  }
  return DEFAULT_POLICY;
}

function Access({ onUser }: { onUser: (user: User) => void }) {
  const [register, setRegister] = useState(false),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onUser(
        await post<User>(register ? "/api/auth/register" : "/api/auth/login", {
          email,
          password,
          ...(register ? { name } : {}),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="access">
      <div className="access-visual">
        <Logo />
        <span className="access-eyebrow">
          <span className="status-dot" /> A LITTLE MORE CLARITY. A LOT MORE
          CONFIDENCE.
        </span>
        <h1>
          Listen beyond
          <br />
          the <em>words.</em>
        </h1>
        <p>
          Because a conversation tells you more
          <br />
          when you know what to listen for.
        </p>
        <SignalOrb active />
        <div className="access-bottom">
          <span>
            <Fingerprint size={17} /> Your conversations. Your control.
          </span>
          <span>BUILT FOR INDIA ↗</span>
        </div>
      </div>
      <div className="access-form-panel">
        <span className="edition">CALLSHIELD / INTELLIGENCE STUDIO</span>
        <FadeIn className="access-form-inner">
          <span className="access-icon">
            <ShieldCheck size={27} />
          </span>
          <h2>
            {register ? "Your clearer next move." : "Welcome to your studio."}
          </h2>
          <p className="muted">
            {register
              ? "Create your private space to investigate suspicious conversations."
              : "Sign in to pick up the signals that matter."}
          </p>
          <form onSubmit={submit}>
            {register && (
              <label>
                Your name
                <input
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="How should we call you?"
                  required
                  minLength={2}
                  maxLength={80}
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                maxLength={255}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={
                  register ? "At least 12 characters" : "Your password"
                }
                required
                minLength={register ? 12 : 1}
                maxLength={72}
              />
            </label>
            {error && (
              <div className="inline-error" role="alert">
                {error}
              </div>
            )}
            <button className="primary full" disabled={busy}>
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <>
                  {register ? "Create my studio" : "Step inside"}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>
          <p className="auth-switch">
            {register ? "Already have a studio?" : "New around here?"}{" "}
            <button
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register ? "Sign in" : "Create an account"}{" "}
              <ArrowUpRight size={13} />
            </button>
          </p>
          <div className="auth-note">
            <LockKeyhole size={17} />
            <span>
              Account sessions use secure cookies.
              <br />
              Recording only starts with your permission.
            </span>
          </div>
        </FadeIn>
        <footer>LESS NOISE. MORE KNOWING.</footer>
      </div>
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [boot, setBoot] = useState(true),
    [caps, setCaps] = useState<Capabilities | null>(null),
    [records, setRecords] = useState<RecordSummary[]>([]);
  const [page, setPage] = useState<"studio" | "history">("studio"),
    [mode, setMode] = useState<Mode>("live"),
    [language, setLanguage] = useState("en-IN"),
    [warningLanguage, setWarningLanguage] = useState("en-IN");
  const [text, setText] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [consent, setConsent] = useState(false),
    [liveInput, setLiveInput] = useState<"microphone" | "typed">("microphone"),
    [turnText, setTurnText] = useState(""),
    [speaker, setSpeaker] = useState("caller");
  const [record, setRecord] = useState<RecordView | null>(null),
    [result, setResult] = useState<Result | null>(null),
    [chart, setChart] = useState<{ score: number; revision: number }[]>([]),
    [turns, setTurns] = useState<{ speaker: string; text: string }[]>([]);
  const [busy, setBusy] = useState(false),
    [phase, setPhase] = useState<
      "idle" | "connecting" | "listening" | "ending"
    >("idle"),
    [level, setLevel] = useState(0),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [policy, setPolicy] = useState<Policy>(initialPolicy),
    [settings, setSettings] = useState(false),
    [help, setHelp] = useState(false),
    [navOpen, setNavOpen] = useState(false),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("ALL");
  const socket = useRef<WebSocket | null>(null),
    stopMic = useRef<null | (() => Promise<void>)>(null),
    turnId = useRef(0),
    audioRef = useRef<HTMLAudioElement | null>(null),
    audioUrl = useRef("");
  const [playing, setPlaying] = useState(false);
  const [explanationLanguage, setExplanationLanguage] = useState("en-IN");
  const languageCatalog = caps?.studio?.languages || [
    {
      code: "en-IN",
      name: "English",
      nativeName: "English",
      text: true,
      audio: true,
    },
    {
      code: "hi-IN",
      name: "Hindi",
      nativeName: "हिन्दी",
      text: true,
      audio: true,
    },
    {
      code: "hi-Latn",
      name: "Hinglish",
      nativeName: "Roman",
      text: true,
      audio: false,
    },
  ];
  const audioInput =
    mode === "audio" || (mode === "live" && liveInput === "microphone");
  const effectiveLanguage =
    audioInput && !languageCatalog.find((l) => l.code === language)?.audio
      ? language === "hi-Latn"
        ? "hi-IN"
        : "en-IN"
      : language;
  const assessment = result?.assessment,
    active = phase !== "idle";
  const displayThreshold = result?.alerts?.threshold ?? policy.threshold;
  useEffect(() => {
    request<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setBoot(false));
    return () => {
      socket.current?.close();
      void stopMic.current?.();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    };
  }, []);
  async function refreshRecords() {
    try {
      setRecords(await request<RecordSummary[]>("/api/records"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    if (!user) return;
    void refreshRecords();
    request<Capabilities>("/api/capabilities")
      .then(setCaps)
      .catch((e) => setError(e.message));
  }, [user]);
  function reset() {
    if (active) return;
    setRecord(null);
    setResult(null);
    setChart([]);
    setTurns([]);
    setText("");
    setFile(null);
    setError("");
    setNotice("");
    setPage("studio");
    setNavOpen(false);
  }
  function applyRecord(value: RecordView) {
    setRecord(value);
    setResult(value.result);
    setChart(
      value.result.history ||
        (value.result.assessment
          ? [{ score: value.result.assessment.score, revision: 1 }]
          : []),
    );
    setTurns([]);
    setPage("studio");
    setError("");
  }
  async function analyze() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      let value: RecordView;
      if (mode === "text") {
        value = await post("/api/analyze/text", {
          transcript: text,
          inputLanguage: effectiveLanguage,
          explanationLanguage,
        });
      } else {
        if (!file) throw new Error("Choose an audio clip first.");
        if (!consent)
          throw new Error("Confirm recording consent before uploading.");
        if (file.size > 15 * 1024 * 1024)
          throw new Error("Choose a clip smaller than 15 MiB.");
        const body = new FormData();
        body.append("file", file);
        body.append("consent", "true");
        body.append("inputLanguage", effectiveLanguage);
        body.append("explanationLanguage", explanationLanguage);
        value = await request("/api/analyze/audio", { method: "POST", body });
      }
      applyRecord(value);
      await refreshRecords();
      setNotice("Review complete. Your report is saved to history.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function startLive() {
    if (!consent) {
      setError("Confirm everyone involved has consented before starting.");
      return;
    }
    setError("");
    setNotice("");
    setResult(null);
    setChart([]);
    setTurns([]);
    setRecord(null);
    setPhase("connecting");
    turnId.current = 0;
    try {
      const session = await post<
        Result & {
          sessionId: string;
          recordId: string;
          websocketPath: string;
        }
      >("/api/live/sessions", {
        consent: true,
        inputMode: liveInput === "microphone" ? "audio" : "text",
        inputLanguage: effectiveLanguage,
        explanationLanguage,
        warningLanguage,
        alerts: policy,
      });
      setResult(session);
      setRecord({
        id: session.recordId,
        kind: "LIVE",
        createdAt: new Date().toISOString(),
        result: {},
      });
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${session.websocketPath}`,
      );
      socket.current = ws;
      let closedNormally = false;
      ws.onmessage = async (message) => {
        let event: LiveEvent;
        try {
          event = JSON.parse(message.data);
        } catch {
          return;
        }
        if (event.type === "ready" && liveInput === "typed")
          setPhase("listening");
        if (event.type === "audio_ready") {
          try {
            const stop = await startMicrophone(ws, setLevel);
            if (ws.readyState !== WebSocket.OPEN) {
              await stop();
              return;
            }
            stopMic.current = stop;
            setPhase("listening");
          } catch (e) {
            setError((e as Error).message);
            ws.close();
          }
        }
        if (event.type === "transcript" && event.turn)
          setTurns((current) =>
            [
              ...current,
              { speaker: event.turn!.speaker, text: event.turn!.text },
            ].slice(-200),
          );
        if (event.type === "classifying") setBusy(true);
        if (event.type === "risk") {
          setResult(event);
          setBusy(false);
          if (event.assessment)
            setChart((current) =>
              [
                ...current.filter((p) => p.revision !== event.assessedRevision),
                {
                  score: event.assessment!.score,
                  revision: event.assessedRevision || 1,
                },
              ].slice(-100),
            );
        }
        if (event.type === "status" && event.assessment) setResult(event);
        if (event.type === "alert")
          setNotice(
            `Alert threshold crossed at ${event.score}/100. ${event.warning?.text || "Pause and verify independently."}`,
          );
        if (event.type === "error") {
          setError(event.message || "Live analysis failed.");
          setBusy(false);
          setResult((previous) =>
            previous
              ? { ...previous, stale: true, riskStatus: "UNDETERMINED" }
              : previous,
          );
        }
        if (event.type === "closed") {
          closedNormally = true;
          setResult(event);
          setPhase("idle");
          setBusy(false);
          await stopMic.current?.();
          stopMic.current = null;
          await refreshRecords();
        }
      };
      ws.onerror = () =>
        setError(
          "The live connection could not be established. Check the gateway and private AI connection.",
        );
      ws.onclose = () => {
        if (!closedNormally)
          setResult((previous) =>
            previous
              ? { ...previous, stale: true, status: "INTERRUPTED" }
              : previous,
          );
        setPhase("idle");
        setBusy(false);
        void stopMic.current?.();
        stopMic.current = null;
        setLevel(0);
        void refreshRecords();
      };
    } catch (e) {
      setError((e as Error).message);
      setPhase("idle");
    }
  }
  async function endLive() {
    setPhase("ending");
    await stopMic.current?.();
    stopMic.current = null;
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify({ type: "end" }));
    else setPhase("idle");
  }
  function sendTurn() {
    if (!turnText.trim() || socket.current?.readyState !== WebSocket.OPEN)
      return;
    socket.current.send(
      JSON.stringify({
        type: "turn",
        id: `t${++turnId.current}`,
        speaker,
        text: turnText,
      }),
    );
    setTurnText("");
  }
  async function playWarning() {
    if (!record) return;
    setError("");
    setPlaying(true);
    try {
      const blob = await post<Blob>(`/api/records/${record.id}/warning-audio`, {
        language: warningLanguage,
      });
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl.current);
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      await audio.play();
    } catch (e) {
      setError((e as Error).message);
      setPlaying(false);
    }
  }
  async function openRecord(id: string) {
    if (active) {
      setError("Finish the live session before opening another report.");
      return;
    }
    try {
      applyRecord(await request(`/api/records/${id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function deleteRecord(id: string) {
    try {
      await request(`/api/records/${id}`, { method: "DELETE" });
      await refreshRecords();
      if (record?.id === id) reset();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function download() {
    if (!record || !result) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ ...record, result }, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `callshield-${record.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  async function logout() {
    await stopMic.current?.();
    if (socket.current) {
      socket.current.onmessage = null;
      socket.current.onclose = null;
      socket.current.onerror = null;
      socket.current.close();
      socket.current = null;
    }
    audioRef.current?.pause();
    try {
      await post("/api/auth/logout", {});
      clearCsrf();
      setUser(null);
      setCaps(null);
      setRecords([]);
      setPhase("idle");
      setRecord(null);
      setResult(null);
      setChart([]);
      setTurns([]);
      setText("");
      setTurnText("");
      setFile(null);
      setConsent(false);
      setBusy(false);
      setPlaying(false);
      setError("");
      setNotice("");
      setPage("studio");
      setSettings(false);
      setHelp(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (boot)
    return (
      <div className="boot-screen">
        <Logo />
        <LoaderCircle className="spin" />
        <span>Opening your studio…</span>
      </div>
    );
  if (!user) return <Access onUser={setUser} />;
  const count = records.length,
    filtered = records.filter(
      (r) =>
        (filter === "ALL" || r.kind === filter) &&
        r.title.toLowerCase().includes(query.toLowerCase()),
    );
  return (
    <div className="app-shell">
      <aside className={`sidebar ${navOpen ? "nav-open" : ""}`}>
        <Logo />
        <div className="sidebar-caption">YOUR INTELLIGENCE STUDIO</div>
        <nav>
          <button
            className={page === "studio" ? "selected" : ""}
            onClick={() => {
              setPage("studio");
              setNavOpen(false);
            }}
          >
            <LayoutDashboard size={19} /> Overview{" "}
            <span className="nav-selected-dot" />
          </button>
          <button
            className={page === "history" ? "selected" : ""}
            onClick={() => {
              setPage("history");
              setNavOpen(false);
            }}
          >
            <History size={19} /> Conversation history{" "}
            <span className="nav-count">{count}</span>
          </button>
          <button onClick={() => setSettings(true)}>
            <Settings2 size={19} /> Alert preferences
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="sidebar-note-icon">
            <Sparkles size={22} />
          </span>
          <h3>
            A second perspective.
            <br />
            Not a final verdict.
          </h3>
          <p>
            Understand the signals.
            <br />
            Then verify independently.
          </p>
          <button onClick={() => setHelp(true)}>
            How it works <ArrowUpRight size={15} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={18} /> The field guide <ArrowUpRight size={14} />
          </button>
          <div className="account">
            <div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div>
            <div>
              <strong>{user.name}</strong>
              <span>Personal workspace</span>
            </div>
            <button title="Sign out" aria-label="Sign out" onClick={logout}>
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu"
              aria-label="Open navigation"
              onClick={() => setNavOpen(!navOpen)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>
              {page === "studio" ? "Overview" : "Conversation history"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="provider-badge">
              <span className={`status-dot ${caps ? "" : "offline"}`} />
              {caps
                ? caps.mockMode
                  ? "MOCK PROVIDERS"
                  : "REAL PROVIDERS"
                : "CONNECTING"}
            </span>
            <button
              className="icon-button"
              title="Alert preferences"
              onClick={() => setSettings(true)}
            >
              <Settings2 size={18} />
            </button>
            <div className="avatar small">{user.name[0].toUpperCase()}</div>
          </div>
        </header>
        <main className="workspace">
          {caps?.mockMode && (
            <div className="demo-mode-banner" role="status">
              <strong>DEMO MODE · No model calls</strong>
              <span>
                Scores and explanations use offline fixtures. Audio produces a
                fixed demo transcript, unrelated to your recording. Restart with
                --real to use Evon, Prisma and Timbre.
              </span>
            </div>
          )}
          <AnimatePresence>
            {error && (
              <motion.div
                className="banner error-banner"
                role="alert"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <span>{error}</span>
                <button aria-label="Dismiss error" onClick={() => setError("")}>
                  <X size={17} />
                </button>
              </motion.div>
            )}
            {notice && (
              <motion.div
                className="banner notice-banner"
                role="status"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <CheckCheck size={18} />
                <span>{notice}</span>
                <button
                  aria-label="Dismiss notification"
                  onClick={() => setNotice("")}
                >
                  <X size={17} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          {page === "studio" ? (
            <FadeIn>
              <section className="page-intro">
                <div>
                  <div className="eyebrow">
                    <span className="tiny-line" /> THE CONVERSATION INTELLIGENCE
                    STUDIO
                  </div>
                  <h1>
                    A clearer signal.
                    <br />
                    <span>A safer conversation.</span>
                  </h1>
                  <p>Go beyond what was said. Understand what it could mean.</p>
                </div>
                <button
                  className="outline-button new-review"
                  onClick={reset}
                  disabled={active}
                >
                  <Plus size={17} /> New review
                </button>
              </section>
              <LanguageStudio caps={caps} />
              <section className="overview-strip">
                <div>
                  <span className="strip-icon">
                    <Radio size={20} />
                  </span>
                  <div>
                    <span>SESSION STATUS</span>
                    <strong>
                      {phase === "connecting"
                        ? "Connecting"
                        : phase === "ending"
                          ? "Finishing"
                          : phase === "listening"
                            ? "Listening live"
                            : busy
                              ? "Analyzing"
                              : "Ready when you are"}
                    </strong>
                  </div>
                  {active && <span className="live-pulse" />}
                </div>
                <div>
                  <span className="strip-icon">
                    <ShieldCheck size={20} />
                  </span>
                  <div>
                    <span>YOUR ALERT THRESHOLD</span>
                    <strong>
                      {displayThreshold}
                      <small> / 100</small>
                      <button
                        className="inline-edit"
                        onClick={() => setSettings(true)}
                      >
                        Adjust <ArrowUpRight size={12} />
                      </button>
                    </strong>
                  </div>
                </div>
                <div>
                  <span className="strip-icon">
                    <Fingerprint size={20} />
                  </span>
                  <div>
                    <span>BUILT AROUND YOUR CONSENT</span>
                    <strong>You decide when to listen.</strong>
                  </div>
                </div>
              </section>
              <div className="studio-grid">
                <section className="panel conversation-panel">
                  <div className="panel-heading">
                    <div>
                      <span className="eyebrow">01 / CAPTURE THE CONTEXT</span>
                      <h2>Your conversation, in focus.</h2>
                    </div>
                    <span className="corner-icon">
                      <AudioLines size={21} />
                    </span>
                  </div>
                  <div
                    className="mode-tabs"
                    role="tablist"
                    aria-label="Analysis input"
                  >
                    {(
                      [
                        { id: "live", icon: Radio, label: "Live monitor" },
                        { id: "text", icon: FileText, label: "Transcript" },
                        { id: "audio", icon: FileAudio, label: "Audio clip" },
                      ] as const
                    ).map((tab) => (
                      <button
                        key={tab.id}
                        role="tab"
                        aria-selected={mode === tab.id}
                        className={mode === tab.id ? "active" : ""}
                        disabled={active || busy}
                        onClick={() => setMode(tab.id)}
                      >
                        <tab.icon size={16} />
                        {tab.label}
                        {tab.id === "live" && (
                          <span className="new-label">LIVE</span>
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="input-toolbar">
                    <label className="language-select">
                      <span>Conversation language</span>
                      <div>
                        <select
                          aria-label="Conversation language"
                          value={effectiveLanguage}
                          disabled={active || busy}
                          onChange={(e) => setLanguage(e.target.value)}
                        >
                          {languageCatalog
                            .filter((l) => !audioInput || l.audio)
                            .map((l) => (
                              <option key={l.code} value={l.code}>
                                {l.name} · {l.nativeName}
                              </option>
                            ))}
                        </select>
                        <ChevronDown size={13} />
                      </div>
                    </label>
                    <label className="language-select">
                      <span>Explanation language</span>
                      <div>
                        <select
                          aria-label="Explanation language"
                          value={explanationLanguage}
                          disabled={active || busy}
                          onChange={(e) =>
                            setExplanationLanguage(e.target.value)
                          }
                        >
                          {languageCatalog.map((l) => (
                            <option key={l.code} value={l.code}>
                              {l.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </label>
                    {mode === "live" && (
                      <div className="input-toggle">
                        <button
                          className={liveInput === "microphone" ? "active" : ""}
                          disabled={active}
                          onClick={() => setLiveInput("microphone")}
                        >
                          <Mic size={14} /> Mic
                        </button>
                        <button
                          className={liveInput === "typed" ? "active" : ""}
                          disabled={active}
                          onClick={() => setLiveInput("typed")}
                        >
                          <FileText size={14} /> Turns
                        </button>
                      </div>
                    )}
                  </div>
                  {mode === "live" ? (
                    <>
                      <div className="listening-space">
                        <div className="signal-label">
                          <span
                            className={`status-dot ${active ? "" : "quiet"}`}
                          />
                          {phase === "listening"
                            ? "LIVE INPUT CONNECTED"
                            : phase === "connecting"
                              ? "ESTABLISHING A PRIVATE CONNECTION"
                              : phase === "ending"
                                ? "FINISHING YOUR LAST CHECKPOINT"
                                : "A SPACE TO LISTEN CLOSELY"}
                        </div>
                        <SignalOrb
                          active={phase === "listening"}
                          level={level}
                        />
                        <h3>
                          {phase === "listening"
                            ? liveInput === "microphone"
                              ? "Listening. Looking for context."
                              : "One turn at a time."
                            : "Every conversation has a signal."}
                        </h3>
                        <p>
                          {phase === "listening"
                            ? "New evidence updates the assessment. Silence does not create a score."
                            : "Start with consent. We’ll help you make sense of the rest."}
                        </p>
                        <div
                          className="sound-bars"
                          aria-label={
                            level
                              ? "Microphone input level"
                              : "No active microphone signal"
                          }
                        >
                          {Array.from({ length: 36 }, (_, i) => (
                            <span
                              key={i}
                              style={{
                                height: `${3 + Math.min(level * 300, 30) * (0.4 + 0.6 * Math.abs(Math.sin(i * 0.8)))}px`,
                              }}
                            />
                          ))}
                        </div>
                      </div>
                      {liveInput === "typed" && phase === "listening" && (
                        <div className="turn-composer">
                          <select
                            aria-label="Speaker"
                            value={speaker}
                            onChange={(e) => setSpeaker(e.target.value)}
                          >
                            <option value="caller">Caller</option>
                            <option value="customer">Customer</option>
                            <option value="unknown">Unknown</option>
                          </select>
                          <input
                            aria-label="Next conversation turn"
                            value={turnText}
                            maxLength={1000}
                            onChange={(e) => setTurnText(e.target.value)}
                            placeholder="What was just said?"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") sendTurn();
                            }}
                          />
                          <button
                            className="icon-button"
                            aria-label="Send turn"
                            disabled={!turnText.trim()}
                            onClick={sendTurn}
                          >
                            <Send size={17} />
                          </button>
                        </div>
                      )}
                      <div className="capture-footer">
                        <label className="consent">
                          <input
                            type="checkbox"
                            checked={consent}
                            disabled={active}
                            onChange={(e) => setConsent(e.target.checked)}
                          />
                          <span>
                            Everyone involved has consented to this recording or
                            analysis.
                          </span>
                        </label>
                        {active ? (
                          <button
                            className="stop-button"
                            onClick={endLive}
                            disabled={
                              phase === "ending" || phase === "connecting"
                            }
                          >
                            {phase === "ending" ? (
                              <LoaderCircle className="spin" size={16} />
                            ) : (
                              <Square size={14} />
                            )}
                            Finish session
                          </button>
                        ) : (
                          <button
                            className="primary"
                            onClick={startLive}
                            disabled={!consent || !caps?.live.enabled}
                          >
                            <Mic size={17} />
                            {liveInput === "microphone"
                              ? "Start listening"
                              : "Start live review"}
                            <ArrowUpRight size={17} />
                          </button>
                        )}
                        <span className="capture-disclaimer">
                          <LockKeyhole size={12} /> Only starts when you say so.{" "}
                          {caps?.mockMode &&
                            "Mock audio uses a fixed demo transcript."}
                        </span>
                      </div>
                    </>
                  ) : mode === "text" ? (
                    <div className="text-input-area">
                      <div className="textarea-label">
                        <span>PASTE A CONVERSATION</span>
                        <button
                          className="text-link"
                          onClick={() => setText(SAMPLE)}
                        >
                          Try a sample <Sparkles size={13} />
                        </button>
                      </div>
                      <textarea
                        aria-label="Conversation transcript"
                        value={text}
                        maxLength={3000}
                        onChange={(e) => setText(e.target.value)}
                        placeholder={
                          "Caller: …\nCustomer: …\n\nInclude the context, not just a suspicious phrase."
                        }
                      />
                      <div className="textarea-meta">
                        <span>
                          Caller / Customer labels are optional. Max 1000
                          characters per line.
                        </span>
                        <span>{text.length}/3000</span>
                      </div>
                      <button
                        className="primary"
                        disabled={busy || !text.trim()}
                        onClick={analyze}
                      >
                        {busy ? (
                          <LoaderCircle className="spin" size={17} />
                        ) : (
                          <Sparkles size={17} />
                        )}
                        Read the signals <ArrowUpRight size={17} />
                      </button>
                    </div>
                  ) : (
                    <div className="upload-area">
                      <label
                        className={`dropzone ${file ? "has-file" : ""}`}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          setFile(e.dataTransfer.files[0] || null);
                        }}
                      >
                        <input
                          type="file"
                          accept=".wav,.mp3,audio/wav,audio/mpeg"
                          aria-label="Choose an audio clip"
                          onChange={(e) => setFile(e.target.files?.[0] || null)}
                        />
                        <span className="upload-icon">
                          {file ? (
                            <FileAudio size={28} />
                          ) : (
                            <Upload size={28} />
                          )}
                        </span>
                        <h3>
                          {file ? file.name : "Drop a conversation here."}
                        </h3>
                        <p>
                          {file
                            ? `${(file.size / 1024 / 1024).toFixed(2)} MiB · Click to change`
                            : "Or browse your files. WAV / MP3, up to 15 MiB and 60 seconds."}
                        </p>
                        <span className="outline-button">
                          {file
                            ? "Choose another clip"
                            : "Choose an audio clip"}{" "}
                          <Plus size={15} />
                        </span>
                      </label>
                      <label className="consent">
                        <input
                          type="checkbox"
                          checked={consent}
                          onChange={(e) => setConsent(e.target.checked)}
                        />
                        <span>I have consent to process this recording.</span>
                      </label>
                      <button
                        className="primary"
                        disabled={busy || !file || !consent}
                        onClick={analyze}
                      >
                        {busy ? (
                          <LoaderCircle className="spin" size={17} />
                        ) : (
                          <AudioLines size={17} />
                        )}
                        Analyze this conversation <ArrowUpRight size={17} />
                      </button>
                    </div>
                  )}
                </section>
                <aside className="panel insight-panel">
                  <div className="panel-heading">
                    <div>
                      <span className="eyebrow">02 / MAKE SENSE OF IT</span>
                      <h2>The signal, decoded.</h2>
                    </div>
                    <span className="live-tag">
                      <span className="status-dot" />
                      {busy ? "READING" : "CONTEXT"}
                    </span>
                  </div>
                  <RiskGauge assessment={assessment} stale={result?.stale} />
                  <div className="risk-footnote">
                    An uncalibrated risk index.
                    <br />
                    Not a probability or a verdict.
                  </div>
                  {assessment ? (
                    <div className="assessment-content">
                      <div className="checkpoint-meta">
                        {result?.peakScore !== undefined && (
                          <span>Peak {result.peakScore}/100</span>
                        )}
                        {result?.assessmentAgeMs != null && (
                          <span>
                            Assessed {Math.floor(result.assessmentAgeMs / 1000)}
                            s ago
                          </span>
                        )}
                        {result?.assessedRevision !== undefined && (
                          <span>
                            Context {result.assessedRevision}/
                            {result.inputRevision}
                          </span>
                        )}
                      </div>
                      <ResultProvenance result={result} />
                      <div className="assessment-title">
                        <span>WHY THIS ASSESSMENT</span>
                        <span className="source-pill">
                          {assessment.mock ? "MOCK FIXTURE" : "EVON"}
                        </span>
                      </div>
                      <p className="model-explanation">
                        {assessment.explanation}
                      </p>
                      <div className="scenario">
                        <span className="status-dot" />
                        {assessment.scenario.replaceAll("_", " ")}
                      </div>
                      {assessment.evidence.map((item, i) => (
                        <blockquote key={i}>
                          <span>
                            {assessment.mock
                              ? "DEMO QUOTE"
                              : "ORIGINAL TRANSCRIPT QUOTE"}{" "}
                            / {item.turnId}
                          </span>
                          “{item.quote}”
                        </blockquote>
                      ))}
                      {result?.stale && (
                        <p className="stale-note">
                          This assessment is awaiting newer context. Do not
                          treat it as a fresh result.
                        </p>
                      )}
                      {assessment.window?.contextLimited && (
                        <p className="stale-note">
                          Earlier turns fell outside the model context.
                          Peak/history remain available.
                        </p>
                      )}
                      <div className="result-actions">
                        <button
                          className="outline-button"
                          onClick={playWarning}
                          disabled={
                            playing ||
                            active ||
                            assessment.score < 20 ||
                            !caps?.ttsAvailable
                          }
                        >
                          {playing ? (
                            <LoaderCircle className="spin" size={15} />
                          ) : (
                            <Volume2 size={15} />
                          )}
                          Play safety advice
                        </button>
                        <button
                          className="icon-button"
                          aria-label="Download report"
                          title="Download report"
                          onClick={download}
                        >
                          <ArrowDownToLine size={17} />
                        </button>
                      </div>
                      <span className="audio-note">
                        {caps?.mockMode
                          ? "Mock playback is a short test tone."
                          : "Approved English / Hindi warning templates."}
                      </span>
                    </div>
                  ) : (
                    <EmptyExplanation />
                  )}
                  <div className="insight-bottom">
                    <ShieldCheck size={15} />
                    <span>Evidence first. Always verify independently.</span>
                  </div>
                </aside>
              </div>
              <div className="lower-grid">
                <section className="panel timeline-panel">
                  <RiskTimeline history={chart} threshold={displayThreshold} />
                  <div className="timeline-footer">
                    <span>
                      <span className="legend-dot" /> Current risk index
                    </span>
                    <span>
                      Alerts at {displayThreshold}+ · No invented updates
                    </span>
                  </div>
                </section>
                <section className="panel context-note">
                  <span className="note-icon">
                    <Zap size={20} />
                  </span>
                  <div>
                    <span className="eyebrow">LESS ALARM. MORE CONTEXT.</span>
                    <h3>
                      The words are only
                      <br />
                      part of the story.
                    </h3>
                    <p>
                      Intent, urgency, and what came before matter. Loudness
                      alone doesn’t prove fraud.
                    </p>
                    <button className="text-link" onClick={() => setHelp(true)}>
                      Understand the signals <ArrowUpRight size={14} />
                    </button>
                  </div>
                </section>
              </div>
              {(turns.length > 0 || result?.originalTranscript) && (
                <section className="panel transcript-panel">
                  <div className="section-label">
                    <FileText size={15} /> CONVERSATION CONTEXT{" "}
                    <span>Private to your account</span>
                  </div>
                  {turns.length ? (
                    turns.map((t, i) => (
                      <p key={i}>
                        <strong>{t.speaker}</strong>
                        {t.text}
                      </p>
                    ))
                  ) : (
                    <p>{result?.originalTranscript}</p>
                  )}
                </section>
              )}
              <footer className="workspace-footer">
                <span>
                  CALLSHIELD INDIA <span className="footer-plus">+</span> BUILT
                  FOR A CLEARER NEXT MOVE.
                </span>
                <span>Consent-led. Context-aware. Human-decided.</span>
              </footer>
            </FadeIn>
          ) : (
            <FadeIn>
              <section className="page-intro">
                <div>
                  <div className="eyebrow">
                    <span className="tiny-line" /> YOUR CONVERSATION ARCHIVE
                  </div>
                  <h1>
                    Every signal.
                    <br />
                    <span>A little more perspective.</span>
                  </h1>
                  <p>Your saved reviews, private to your account.</p>
                </div>
                <button
                  className="primary"
                  onClick={() => {
                    reset();
                    setMode("text");
                  }}
                >
                  <Plus size={17} /> New review
                </button>
              </section>
              <section className="panel history-panel">
                <div className="history-toolbar">
                  <div className="history-filters">
                    {["ALL", "TEXT", "AUDIO", "LIVE"].map((value) => (
                      <button
                        key={value}
                        className={filter === value ? "active" : ""}
                        onClick={() => setFilter(value)}
                      >
                        {value === "ALL" ? "All reviews" : value.toLowerCase()}
                      </button>
                    ))}
                  </div>
                  <label className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search history"
                      placeholder="Find a conversation"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                </div>
                {filtered.length ? (
                  <div className="history-list">
                    {filtered.map((item) => (
                      <article key={item.id} className="history-row">
                        <span className="history-type">
                          {item.kind === "AUDIO" ? (
                            <FileAudio size={21} />
                          ) : item.kind === "LIVE" ? (
                            <Radio size={21} />
                          ) : (
                            <FileText size={21} />
                          )}
                        </span>
                        <button
                          className="history-open"
                          onClick={() => openRecord(item.id)}
                        >
                          <strong>{item.title || "Conversation review"}</strong>
                          <span>
                            {new Date(item.createdAt).toLocaleString()} ·{" "}
                            {item.kind.toLowerCase()}
                            {item.mock ? " · mock" : ""}
                          </span>
                        </button>
                        <span
                          className={`history-score ${(item.score ?? 0) >= 60 ? "elevated" : ""}`}
                        >
                          {item.score ?? "—"}
                          <small>{item.band}</small>
                        </span>
                        <button
                          className="icon-button"
                          aria-label="Delete saved report"
                          title="Delete permanently"
                          onClick={() => deleteRecord(item.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                        <button
                          className="icon-button"
                          aria-label="Open report"
                          onClick={() => openRecord(item.id)}
                        >
                          <ArrowUpRight size={18} />
                        </button>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="history-empty">
                    <History size={35} />
                    <h3>
                      {query
                        ? "No matching conversations."
                        : "A fresh perspective starts here."}
                    </h3>
                    <p>
                      {query
                        ? "Try another search."
                        : "Your completed reviews will appear here."}
                    </p>
                    <button
                      className="primary"
                      onClick={() => {
                        setPage("studio");
                        setMode("text");
                      }}
                    >
                      Start a review <ArrowRight size={16} />
                    </button>
                  </div>
                )}
              </section>
            </FadeIn>
          )}
        </main>
      </div>
      <AnimatePresence>
        {settings && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSettings(false)}
          >
            <motion.section
              className="modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-title"
              initial={{ y: 25, scale: 0.97 }}
              animate={{ y: 0, scale: 1 }}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                className="modal-close icon-button"
                aria-label="Close preferences"
                onClick={() => setSettings(false)}
              >
                <X size={20} />
              </button>
              <span className="access-icon">
                <Settings2 size={24} />
              </span>
              <h2 id="settings-title">A signal on your terms.</h2>
              <p>
                Applied to your next live session. These are thresholds on a
                model-assessed index, not probability cutoffs.
              </p>
              <label>
                Alert at <strong>{policy.threshold} / 100</strong>
                <input
                  aria-label="Alert threshold"
                  type="range"
                  min={1}
                  max={100}
                  value={policy.threshold}
                  onChange={(e) => {
                    const threshold = +e.target.value;
                    setPolicy({
                      ...policy,
                      threshold,
                      resetBelow: Math.min(policy.resetBelow, threshold - 1),
                    });
                  }}
                />
              </label>
              <label>
                Re-arm below <strong>{policy.resetBelow} / 100</strong>
                <input
                  aria-label="Alert reset threshold"
                  type="range"
                  min={0}
                  max={Math.max(0, policy.threshold - 1)}
                  value={policy.resetBelow}
                  onChange={(e) =>
                    setPolicy({ ...policy, resetBelow: +e.target.value })
                  }
                />
              </label>
              <label>
                Minimum time between alerts
                <select
                  value={policy.cooldownSeconds}
                  onChange={(e) =>
                    setPolicy({ ...policy, cooldownSeconds: +e.target.value })
                  }
                >
                  <option value={15}>15 seconds</option>
                  <option value={30}>30 seconds</option>
                  <option value={60}>1 minute</option>
                  <option value={120}>2 minutes</option>
                </select>
              </label>
              <label>
                Safety advice language
                <select
                  value={warningLanguage}
                  onChange={(e) => setWarningLanguage(e.target.value)}
                >
                  <option value="en-IN">English</option>
                  <option value="hi-IN">Hindi</option>
                </select>
              </label>
              <div className="preference-note">
                <Clock3 size={17} /> Persistent high risk doesn’t trigger an
                alert every second. A lower score must re-arm the policy.
              </div>
              <button
                className="primary full"
                onClick={() => {
                  localStorage.setItem(
                    "callshield.policy",
                    JSON.stringify(policy),
                  );
                  setSettings(false);
                }}
              >
                <Check size={17} /> Save preferences
              </button>
            </motion.section>
          </motion.div>
        )}
        {help && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setHelp(false)}
          >
            <section
              className="modal field-guide"
              role="dialog"
              aria-modal="true"
              aria-labelledby="guide-title"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                className="modal-close icon-button"
                aria-label="Close field guide"
                onClick={() => setHelp(false)}
              >
                <X size={20} />
              </button>
              <span className="eyebrow">THE FIELD GUIDE</span>
              <h2 id="guide-title">
                A clearer picture.
                <br />A considered response.
              </h2>
              <ol>
                <li>
                  <strong>Bring the context.</strong>
                  <p>
                    Paste a transcript, upload a consented clip, or stream
                    microphone audio. We do not intercept phone calls.
                  </p>
                </li>
                <li>
                  <strong>Read the signals.</strong>
                  <p>
                    Evon considers conversational intent and generates a short
                    summary with quoted evidence. Its index is uncalibrated and
                    may be wrong.
                  </p>
                </li>
                <li>
                  <strong>Stay in control.</strong>
                  <p>
                    Scores update after new speech and inference, not on a
                    guaranteed one-second schedule. Verify identity through a
                    known official channel.
                  </p>
                </li>
              </ol>
              <div className="preference-note">
                <LockKeyhole size={18} />
                <span>
                  Reports are saved to your account. You can delete them in
                  history. Raw live audio is not retained by the service.
                </span>
              </div>
              <button className="primary full" onClick={() => setHelp(false)}>
                Got it <ArrowRight size={17} />
              </button>
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
