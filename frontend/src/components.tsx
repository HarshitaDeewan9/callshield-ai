import { motion } from "framer-motion";
import { ShieldCheck, ArrowUpRight, Radio, Waves } from "lucide-react";
import type { Assessment } from "./types";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <ShieldCheck size={23} />
      </span>
      {!compact && (
        <span>
          callshield<span className="brand-dot">.</span>
        </span>
      )}
    </div>
  );
}
export function SignalOrb({
  active = false,
  level = 0,
  small = false,
}: {
  active?: boolean;
  level?: number;
  small?: boolean;
}) {
  return (
    <div
      className={`orb-stage ${active ? "is-listening" : ""} ${small ? "orb-small" : ""}`}
      aria-hidden="true"
    >
      <div className="orb-cross horizontal" />
      <div className="orb-cross vertical" />
      <div className="orb-orbit orbit-one" />
      <div className="orb-orbit orbit-two" />
      <div className="orb-orbit orbit-three" />
      <div
        className="orb-core"
        style={{ transform: `scale(${1 + Math.min(level, 0.4)})` }}
      >
        <div className="orb-mesh" />
        <ShieldCheck strokeWidth={1} size={76} />
        <div className="orb-highlight" />
      </div>
      <span className="orb-satellite satellite-one" />
      <span className="orb-satellite satellite-two" />
      <span className="orb-coordinate coordinate-top">VOICE / CONTEXT</span>
      <span className="orb-coordinate coordinate-bottom">
        SIGNAL INTELLIGENCE
      </span>
    </div>
  );
}
export function RiskGauge({
  assessment,
  stale = false,
}: {
  assessment?: Assessment | null;
  stale?: boolean;
}) {
  const score = assessment?.score;
  const tone =
    score === undefined
      ? "neutral"
      : score >= 80
        ? "critical"
        : score >= 60
          ? "high"
          : score >= 40
            ? "suspicious"
            : "calm";
  return (
    <div className={`risk-gauge ${tone}`}>
      <svg
        viewBox="0 0 240 152"
        role="img"
        aria-label={
          score === undefined
            ? "No risk assessment yet"
            : `Risk index ${score} of 100`
        }
      >
        <defs>
          <linearGradient id="risk-gradient">
            <stop offset="0%" stopColor="#94b873" />
            <stop offset="55%" stopColor="#dfbb61" />
            <stop offset="100%" stopColor="#e0785a" />
          </linearGradient>
        </defs>
        <path className="gauge-track" d="M 25 125 A 95 95 0 0 1 215 125" />
        <path
          className="gauge-fill"
          d="M 25 125 A 95 95 0 0 1 215 125"
          strokeDasharray="298.45"
          strokeDashoffset={298.45 * (1 - (score ?? 0) / 100)}
        />
        <text x="120" y="111" className="gauge-number" textAnchor="middle">
          {score ?? "—"}
        </text>
        <text x="120" y="139" className="gauge-label" textAnchor="middle">
          {score === undefined ? "AWAITING SIGNAL" : "RISK INDEX / 100"}
        </text>
      </svg>
      <span className={`risk-band ${tone}`}>
        {assessment?.band?.replace("_", " ") || "Not assessed"}
        {stale && " · updating"}
      </span>
    </div>
  );
}
export function RiskTimeline({
  history,
  threshold = 70,
}: {
  history: { score: number; revision: number }[];
  threshold?: number;
}) {
  const points = history.map(
    (p, i) =>
      `${24 + (i / Math.max(1, history.length - 1)) * 552},${130 - p.score * 1.05}`,
  );
  return (
    <div className="timeline">
      <div className="section-label">
        <Waves size={15} /> SIGNAL OVER TIME{" "}
        <span>{history.length} checkpoints</span>
      </div>
      <svg viewBox="0 0 600 155" role="img" aria-label="Risk index history">
        <defs>
          <linearGradient id="chart-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#a3bd71" stopOpacity=".32" />
            <stop offset="100%" stopColor="#a3bd71" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[25, 60, 95, 130].map((y) => (
          <line
            key={y}
            x1="24"
            x2="576"
            y1={y}
            y2={y}
            stroke="#e6e7de"
            strokeDasharray="3 6"
          />
        ))}
        <line
          x1="24"
          x2="576"
          y1={130 - threshold * 1.05}
          y2={130 - threshold * 1.05}
          stroke="#dd9d77"
          strokeDasharray="5 5"
        />
        {points.length > 0 && (
          <>
            <polygon
              points={`24,137 ${points.join(" ")} ${points.at(-1)?.split(",")[0]},137`}
              fill="url(#chart-area)"
            />
            <polyline
              points={points.join(" ")}
              stroke="#718b47"
              strokeWidth="2.5"
              fill="none"
              strokeLinejoin="round"
            />
            {history.map((p, i) => (
              <circle
                key={p.revision}
                cx={24 + (i / Math.max(1, history.length - 1)) * 552}
                cy={130 - p.score * 1.05}
                r="4"
                fill="#718b47"
                stroke="#f9faf4"
                strokeWidth="2"
              />
            ))}
          </>
        )}
        <text x="24" y="152" className="chart-caption">
          START
        </text>
        <text x="576" y="152" textAnchor="end" className="chart-caption">
          LATEST
        </text>
      </svg>
      {!history.length && (
        <span className="chart-empty">
          Your conversation will draw the story.
        </span>
      )}
    </div>
  );
}
export function EmptyExplanation() {
  return (
    <div className="explanation-empty">
      <span className="mini-orbit">
        <Radio size={21} />
      </span>
      <h3>Context before conclusions.</h3>
      <p>
        Start a review to see what raised concern, with exact evidence from the
        conversation.
      </p>
      <span className="text-link">
        Every signal has a source <ArrowUpRight size={14} />
      </span>
    </div>
  );
}
export function FadeIn({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
