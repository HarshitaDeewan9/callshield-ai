import { Languages } from "lucide-react";
import type { Capabilities, Result } from "./types";

export function LanguageStudio({ caps }: { caps: Capabilities | null }) {
  if (!caps?.studio) return null;
  const languages = caps.studio.languages;
  return (
    <section
      className="language-studio"
      aria-label="Multilingual Gnani capabilities"
    >
      <div className="language-studio-title">
        <Languages size={23} />
        <div>
          <span className="eyebrow">BUILT FOR THE WAY INDIA SPEAKS</span>
          <h3>Different languages. The original context.</h3>
        </div>
      </div>
      <div className="language-chips">
        {languages
          .filter((l) => l.code !== "hi-Latn")
          .map((l) => (
            <span
              key={l.code}
              title={`${l.name}: ${l.audio ? "text + audio" : "text only"}`}
            >
              {l.nativeName}
            </span>
          ))}
        <span>Hinglish</span>
      </div>
      <p>
        Evon reads original-script text across 11 languages. Prisma accepts 10
        audio languages. Choose a language explicitly; this version does not
        auto-detect or translate speech. Language-specific fraud accuracy still
        needs evaluation.
      </p>
      <small>
        Timbre safety advice currently has curated English and Hindi templates.
      </small>
    </section>
  );
}

export function ResultProvenance({ result }: { result: Result | null }) {
  const a = result?.assessment;
  if (!a) return null;
  return (
    <div
      className={`result-provenance ${a.mock ? "fixture-provenance" : ""}`}
      aria-label="Result provenance"
    >
      <strong>
        {a.mock
          ? "DEMO RESULT — no Evon inference"
          : "RESULT SOURCE — Evon model output"}
      </strong>
      <span>
        {a.model || (a.mock ? "mock-fixture-v2" : "gnani-evon-v3.3-gguf")}
      </span>
      <span>
        Evidence: {a.mock ? "fixture-selected quote" : "model-selected quote"}
        {a.evidenceQuotesValidated ? " · exact transcript match validated" : ""}
      </span>
      {result?.transcription && (
        <span>
          Transcript:{" "}
          {result.transcription.mock
            ? "fixed mock audio fixture"
            : `${result.transcription.provider} / ${result.transcription.modelVersion || "provider"}`}
        </span>
      )}
      {result?.inputLanguage && (
        <span>
          Input: {result.inputLanguage} · user selected · original script
          preserved
        </span>
      )}
      {a.requestedExplanationLanguage && (
        <span>
          Explanation requested: {a.requestedExplanationLanguage}
          {a.mock
            ? " · mock summaries remain English"
            : " · output language is not automatically verified"}
        </span>
      )}
    </div>
  );
}
