import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { SpreadChart } from "./SpreadChart";

// Recharts uses ResizeObserver internally; stub it for jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub;

describe("SpreadChart", () => {
  it("renders loading state", () => {
    render(<SpreadChart data={[]} loading={true} />);
    expect(screen.getByText("Loading spread data...")).toBeInTheDocument();
  });

  it("renders empty state when no data", () => {
    render(<SpreadChart data={[]} loading={false} />);
    expect(screen.getByText("No spread data available.")).toBeInTheDocument();
  });

  it("renders chart when data is provided", () => {
    const data = [
      { date: "2024-01-10", spread: 0.15, inverted: false },
      { date: "2024-01-11", spread: -0.05, inverted: true },
    ];
    const { container } = render(<SpreadChart data={data} loading={false} />);
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
