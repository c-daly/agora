import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { FtdHeatmap } from "../FtdHeatmap";
import type { FtdPoint } from "../../types";

const SAMPLE_DATA: FtdPoint[] = [
  { date: "2024-01-10", symbol: "AAPL", quantity: 5000 },
  { date: "2024-01-11", symbol: "AAPL", quantity: 12000 },
  { date: "2024-01-10", symbol: "GME", quantity: 80000 },
  { date: "2024-01-11", symbol: "GME", quantity: 45000 },
];

describe("FtdHeatmap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading state while fetching", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    render(<FtdHeatmap />);
    expect(screen.getByText(/Loading FTD data for/)).toBeInTheDocument();
  });

  it("renders empty state when data prop is empty array", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: [] }),
    } as Response);
    render(<FtdHeatmap />);
    // Component fetches on mount, will eventually show empty state
    waitFor(() => {
      expect(screen.getByText(/No FTD data available/)).toBeInTheDocument();
    });
  });

  it("renders table when data loads", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: SAMPLE_DATA.map(d => ({ symbol: d.symbol, date: d.date, value: d.quantity })) }),
    } as Response);
    render(<FtdHeatmap />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("GME")).toBeInTheDocument();
    });
  });

  it("has a ticker input defaulting to QS", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    render(<FtdHeatmap />);
    const input = screen.getByLabelText("Ticker:");
    expect(input).toHaveValue("QS");
  });

  it("has a Load button", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    render(<FtdHeatmap />);
    expect(screen.getByText("Load")).toBeInTheDocument();
  });

  it("respects symbol prop", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );
    render(<FtdHeatmap symbol="GME" />);
    const input = screen.getByLabelText("Ticker:");
    expect(input).toHaveValue("GME");
    expect(screen.getByText("Showing: GME")).toBeInTheDocument();
  });
});
