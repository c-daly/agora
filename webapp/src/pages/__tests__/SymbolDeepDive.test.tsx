import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SymbolDeepDive } from "../SymbolDeepDive";

const MOCK_SUMMARY = {
  data: {
    ticker: "QS",
    composite_score: 72,
    signal_label: "Bullish",
    quote: [
      { date: "2024-01-10", close: 5.5, volume: 1000000 },
      { date: "2024-01-11", close: 5.8, volume: 1200000 },
    ],
    short_volume: [
      { date: "2024-01-10", short_volume_ratio: 0.42 },
    ],
    insider_trades: [
      { date: "2024-01-05", name: "John Doe", action: "Buy", shares: 10000, price: 5.2 },
    ],
    divergences: [
      { signal: "Price-Volume Divergence", severity: "high", description: "Price rising on declining volume" },
    ],
  },
};

function renderWithRouter(ticker?: string) {
  const path = ticker ? `/symbol/${ticker}` : "/symbol/QS";
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/symbol/:ticker" element={<SymbolDeepDive />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SymbolDeepDive", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders without error", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    renderWithRouter();
    expect(screen.getByTestId("ticker-form")).toBeInTheDocument();
  });

  it("shows default ticker QS", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    renderWithRouter();
    expect(screen.getByText("QS")).toBeInTheDocument();
  });

  it("displays loading state", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    renderWithRouter();
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.getByText(/Loading summary for QS/)).toBeInTheDocument();
  });

  it("shows composite score after data loads", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_SUMMARY),
      } as Response)
    );
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId("composite-score")).toBeInTheDocument();
    });
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Bullish")).toBeInTheDocument();
  });
});
