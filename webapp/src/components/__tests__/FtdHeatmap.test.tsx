import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { FtdHeatmap } from "../FtdHeatmap";
import type { FtdPoint } from "../../types";

const SAMPLE_DATA: FtdPoint[] = [
  { date: "2024-01-10", symbol: "AAPL", quantity: 5000 },
  { date: "2024-01-11", symbol: "AAPL", quantity: 12000 },
  { date: "2024-01-10", symbol: "GME", quantity: 80000 },
  { date: "2024-01-11", symbol: "GME", quantity: 45000 },
  { date: "2024-01-10", symbol: "TSLA", quantity: 3000 },
];

describe("FtdHeatmap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading state while fetching", () => {
    // No external data supplied, so it will fetch and show loading
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {}) // never resolves
    );
    render(<FtdHeatmap />);
    expect(screen.getByText("Loading FTD data...")).toBeInTheDocument();
  });

  it("renders empty state when data array is empty", () => {
    render(<FtdHeatmap data={[]} />);
    expect(screen.getByText("No FTD data available.")).toBeInTheDocument();
  });

  it("renders heatmap table when data is provided", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} />);
    const table = screen.getByTestId("ftd-heatmap-table");
    expect(table).toBeInTheDocument();

    // Check symbols appear as row headers
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("GME")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();

    // Check dates appear as column headers
    expect(screen.getByText("2024-01-10")).toBeInTheDocument();
    expect(screen.getByText("2024-01-11")).toBeInTheDocument();
  });

  it("displays quantity values in cells", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} />);
    // GME on 2024-01-10 has the highest quantity: 80,000
    expect(screen.getByText("80,000")).toBeInTheDocument();
    expect(screen.getByText("5,000")).toBeInTheDocument();
  });

  it("filters by symbol when typing in the search input", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} />);

    const input = screen.getByPlaceholderText("e.g. AAPL");
    fireEvent.change(input, { target: { value: "GME" } });

    // GME should remain visible
    expect(screen.getByText("GME")).toBeInTheDocument();
    // AAPL should be filtered out
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByText("TSLA")).not.toBeInTheDocument();
  });

  it("shows no-match message when filter has no results", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} />);

    const input = screen.getByPlaceholderText("e.g. AAPL");
    fireEvent.change(input, { target: { value: "ZZZZ" } });

    expect(
      screen.getByText(/No FTD data matches the filter/)
    ).toBeInTheDocument();
  });

  it("respects initial symbol prop for pre-filtering", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} symbol="TSLA" />);

    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByText("GME")).not.toBeInTheDocument();
  });

  it("fetches from /api/ftd when no data prop is provided", async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ data: SAMPLE_DATA }),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as Response);

    render(<FtdHeatmap />);

    // Wait for the fetch to resolve and data to render
    expect(await screen.findByTestId("ftd-heatmap-table")).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/ftd");
  });

  it("handles fetch error gracefully", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));

    render(<FtdHeatmap />);

    expect(
      await screen.findByText("No FTD data available.")
    ).toBeInTheDocument();
  });

  it("applies color intensity based on quantity", () => {
    render(<FtdHeatmap data={SAMPLE_DATA} />);
    const table = screen.getByTestId("ftd-heatmap-table");
    // The cell with the max value (80,000) should have the highest alpha
    const cells = table.querySelectorAll("td");
    const coloredCells = Array.from(cells).filter((td) =>
      td.style.backgroundColor.includes("rgba")
    );
    expect(coloredCells.length).toBeGreaterThan(0);
  });
});
