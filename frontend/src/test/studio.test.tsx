import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";
import App from "../App";
const api = vi.hoisted(() => ({
  request: vi.fn(),
  post: vi.fn(),
  clearCsrf: vi.fn(),
}));
vi.mock("../api", () => api);
vi.mock("../microphone", () => ({ startMicrophone: vi.fn() }));
const user = { id: "qa", name: "Studio QA", email: "qa@example.test" };
const caps = {
  mockMode: true,
  ttsAvailable: true,
  studio: {
    speechModel: "prisma-v2.5",
    riskModel: "gnani-evon-v3.3-gguf",
    warningModel: "timbre-v2.5",
    languages: [
      {
        code: "en-IN",
        name: "English",
        nativeName: "English",
        text: true,
        audio: true,
        warningAudio: true,
        fraudAccuracyValidated: false,
      },
      {
        code: "hi-IN",
        name: "Hindi",
        nativeName: "हिन्दी",
        text: true,
        audio: true,
        warningAudio: true,
        fraudAccuracyValidated: false,
      },
      {
        code: "ta-IN",
        name: "Tamil",
        nativeName: "தமிழ்",
        text: true,
        audio: true,
        warningAudio: false,
        fraudAccuracyValidated: false,
      },
      {
        code: "or-IN",
        name: "Odia",
        nativeName: "ଓଡ଼ିଆ",
        text: true,
        audio: false,
        warningAudio: false,
        fraudAccuracyValidated: false,
      },
    ],
  },
  live: { enabled: true, audioAvailable: true, structuredContextReady: true },
};
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.request.mockImplementation(async (path: string) => {
    if (path === "/api/auth/me") return user;
    if (path === "/api/capabilities") return caps;
    if (path === "/api/records") return [];
    throw Error("unexpected route");
  });
});
describe("Studio workflow", () => {
  it("renders honest empty state and configurable policy", async () => {
    render(<App />);
    expect(await screen.findByText("A clearer signal.")).toBeInTheDocument();
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
    expect(await screen.findByText("MOCK PROVIDERS")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Alert preferences"));
    fireEvent.change(screen.getByLabelText("Alert threshold"), {
      target: { value: "85" },
    });
    fireEvent.click(screen.getByText("Save preferences"));
    expect(
      JSON.parse(localStorage.getItem("callshield.policy")!).threshold,
    ).toBe(85);
  });
  it("submits actual text and shows the returned explanation", async () => {
    api.post.mockResolvedValue({
      id: "record",
      kind: "TEXT",
      createdAt: new Date().toISOString(),
      result: {
        mock: true,
        assessment: {
          score: 90,
          band: "CRITICAL",
          explanation: "The caller asks for a secret OTP.",
          scenario: "credential_theft",
          mock: true,
          evidence: [{ turnId: "t1", quote: "Tell me your OTP now." }],
        },
      },
    });
    render(<App />);
    await screen.findByText("A clearer signal.");
    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    fireEvent.change(screen.getByLabelText("Conversation transcript"), {
      target: { value: "Caller: Tell me your OTP now." },
    });
    fireEvent.click(screen.getByText("Read the signals"));
    expect(
      await screen.findByText("The caller asks for a secret OTP."),
    ).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith("/api/analyze/text", {
      transcript: "Caller: Tell me your OTP now.",
      inputLanguage: "en-IN",
      explanationLanguage: "en-IN",
    });
    expect(
      screen.getByRole("img", { name: "Risk index 90 of 100" }),
    ).toBeInTheDocument();
  });
  it("clears conversation state on logout before another user signs in", async () => {
    api.post.mockResolvedValue(undefined);
    render(<App />);
    await screen.findByText("A clearer signal.");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(screen.getByText("Welcome to your studio.")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Studio QA")).not.toBeInTheDocument();
  });
  it("highlights mock limitations and exposes only supported audio locales", async () => {
    render(<App />);
    await screen.findByText("DEMO MODE · No model calls");
    expect(
      screen.getByText(/Audio produces a fixed demo transcript/),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Multilingual Gnani capabilities"),
    ).toBeInTheDocument();
    const language = screen.getByLabelText(
      "Conversation language",
    ) as HTMLSelectElement;
    expect([...language.options].some((o) => o.value === "ta-IN")).toBe(true);
    expect([...language.options].some((o) => o.value === "or-IN")).toBe(false);
    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    expect([...language.options].some((o) => o.value === "or-IN")).toBe(true);
    fireEvent.change(language, { target: { value: "ta-IN" } });
    fireEvent.change(screen.getByLabelText("Explanation language"), {
      target: { value: "hi-IN" },
    });
    api.post.mockResolvedValue({
      id: "native",
      kind: "TEXT",
      result: {
        mock: true,
        assessment: {
          score: 10,
          band: "MINIMAL",
          scenario: "none",
          mock: true,
          explanation: "Demo only.",
          evidence: [],
        },
      },
    });
    fireEvent.change(screen.getByLabelText("Conversation transcript"), {
      target: { value: "உங்கள் OTP எண்ணை சொல்லுங்கள்." },
    });
    fireEvent.click(screen.getByText("Read the signals"));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/api/analyze/text", {
        transcript: "உங்கள் OTP எண்ணை சொல்லுங்கள்.",
        inputLanguage: "ta-IN",
        explanationLanguage: "hi-IN",
      }),
    );
    expect(
      await screen.findByText("DEMO RESULT — no Evon inference"),
    ).toBeInTheDocument();
  });
});
