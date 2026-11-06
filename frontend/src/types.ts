export interface User {
  id: string;
  name: string;
  email: string;
}
export interface Assessment {
  model?: string;
  explanationSource?: string;
  evidenceSource?: string;
  evidenceQuotesValidated?: boolean;
  requestedExplanationLanguage?: string;
  explanationLanguage?: string;
  score: number;
  band: string;
  explanation: string;
  scenario: string;
  evidence: { turnId: string; quote: string }[];
  source: string;
  mock: boolean;
  calibrated: false;
  confidence: null;
  window?: { contextLimited: boolean; omittedTurnIds: string[] };
}
export interface Result {
  inputLanguage?: string;
  languageSource?: string;
  translationApplied?: boolean;
  alerts?: { threshold: number; resetBelow: number; cooldownSeconds: number };
  history?: { score: number; revision: number }[];
  assessment?: Assessment | null;
  originalTranscript?: string;
  status?: string;
  riskStatus?: string;
  mock?: boolean;
  stale?: boolean;
  assessedRevision?: number;
  inputRevision?: number;
  peakScore?: number;
  assessmentAgeMs?: number;
  transcription?: { provider: string; mock?: boolean; modelVersion?: string };
  error?: { code: string; message: string };
}
export interface RecordView {
  id: string;
  kind: string;
  createdAt: string;
  result: Result;
}
export interface RecordSummary {
  id: string;
  kind: string;
  createdAt: string;
  title: string;
  score: number | null;
  band: string;
  mock: boolean;
}
export interface Capabilities {
  studio?: {
    languages: StudioLanguage[];
    speechModel: string;
    riskModel: string;
    warningModel: string;
  };
  mockMode: boolean;
  evonContextTokens: number;
  ttsAvailable: boolean;
  sttAvailable: boolean;
  live: {
    enabled: boolean;
    audioAvailable: boolean;
    structuredContextReady: boolean;
  };
}
export interface StudioLanguage {
  code: string;
  name: string;
  nativeName: string;
  text: boolean;
  audio: boolean;
  warningAudio: boolean;
  fraudAccuracyValidated: boolean;
}
export interface LiveEvent extends Result {
  type: string;
  sessionId?: string;
  revision?: number;
  turn?: { id: string; speaker: string; text: string };
  code?: string;
  message?: string;
  threshold?: number;
  score?: number;
  warning?: { text: string };
}
