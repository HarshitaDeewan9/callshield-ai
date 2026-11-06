import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RiskGauge, EmptyExplanation, RiskTimeline } from "../components";
import type { Assessment } from "../types";
describe("Risk display integrity", () => {
  it("does not invent a score before assessment", () => {
    render(<RiskGauge />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "No risk assessment yet",
    );
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });
  it("shows model score and staleness without probability claims", () => {
    const assessment = { score: 90, band: "CRITICAL" } as Assessment;
    render(<RiskGauge assessment={assessment} stale />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Risk index 90 of 100",
    );
    expect(screen.getByText(/updating/)).toBeInTheDocument();
    expect(screen.queryByText(/90%/)).not.toBeInTheDocument();
  });
  it("shows actual checkpoints only", () => {
    render(
      <RiskTimeline
        history={[
          { score: 10, revision: 1 },
          { score: 90, revision: 2 },
        ]}
      />,
    );
    expect(screen.getByText("2 checkpoints")).toBeInTheDocument();
  });
  it("explains the empty state", () => {
    render(<EmptyExplanation />);
    expect(screen.getByText("Context before conclusions.")).toBeInTheDocument();
  });
});
