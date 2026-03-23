import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { YieldCurveChart } from "./YieldCurveChart";

// Recharts uses ResizeObserver internally; stub it for jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub;

describe("YieldCurveChart", () => {
  it("renders loading state", () => {
    render(<YieldCurveChart data={[]} loading={true} />);
    expect(screen.getByText("Loading yield curve...")).toBeInTheDocument();
  });

  it("renders empty state when no data", () => {
    render(<YieldCurveChart data={[]} loading={false} />);
    expect(screen.getByText("No yield curve data available.")).toBeInTheDocument();
  });

  it("renders chart when data is provided", () => {
    const data = [
      { maturity: "1mo", yield_pct: 4.5 },
      { maturity: "10yr", yield_pct: 4.0 },
    ];
    const { container } = render(<YieldCurveChart data={data} loading={false} />);
    // ResponsiveContainer renders a recharts wrapper
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
