import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Screener } from "../Screener";

const MOCK_SCREENER = {
  data: [
    {
      symbol: "QS",
      composite_score: 82,
      signal: "extreme",
      components: { short_volume_score: 90, short_interest_score: 75, ftd_score: 80 },
    },
    {
      symbol: "AAPL",
      composite_score: 25,
      signal: "low",
      components: { short_volume_score: 20, short_interest_score: 15, ftd_score: 30 },
    },
    {
      symbol: "GME",
      composite_score: 65,
      signal: "high",
      components: { short_volume_score: 70, short_interest_score: 60, ftd_score: 65 },
    },
  ],
};

function renderScreener() {
  return render(
    <MemoryRouter initialEntries={["/screener"]}>
      <Routes>
        <Route path="/screener" element={<Screener />} />
      </Routes>
    </MemoryRouter>
  );
}

function mockFetchSuccess() {
  vi.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(MOCK_SCREENER),
    } as Response)
  );
}

function mockFetchPending() {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    () => new Promise(() => {})
  );
}

function mockFetchError() {
  vi.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.reject(new Error("Network error"))
  );
}

describe("Screener", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders without error", () => {
    mockFetchPending();
    renderScreener();
    expect(screen.getByTestId("screener-page")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockFetchPending();
    renderScreener();
    expect(screen.getByTestId("screener-loading")).toBeInTheDocument();
    expect(screen.getByText(/Loading screener data/)).toBeInTheDocument();
  });

  it("displays table with data after loading", async () => {
    mockFetchSuccess();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-table")).toBeInTheDocument();
    });
    expect(screen.getByText("QS")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("GME")).toBeInTheDocument();
  });

  it("displays signal badges with correct classes", async () => {
    mockFetchSuccess();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-table")).toBeInTheDocument();
    });
    const extremeBadge = screen.getByText("extreme");
    expect(extremeBadge).toHaveClass("screener-badge--extreme");
    const lowBadge = screen.getByText("low");
    expect(lowBadge).toHaveClass("screener-badge--low");
    const highBadge = screen.getByText("high");
    expect(highBadge).toHaveClass("screener-badge--high");
  });

  it("sorts by composite score desc by default", async () => {
    mockFetchSuccess();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-table")).toBeInTheDocument();
    });
    const rows = screen.getAllByTestId(/^screener-row-/);
    expect(rows[0]).toHaveAttribute("data-testid", "screener-row-QS");
    expect(rows[1]).toHaveAttribute("data-testid", "screener-row-GME");
    expect(rows[2]).toHaveAttribute("data-testid", "screener-row-AAPL");
  });

  it("toggles sort direction on header click", async () => {
    mockFetchSuccess();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-table")).toBeInTheDocument();
    });
    // Click Composite Score header to toggle to asc
    const compositeHeader = screen.getByText(/Composite Score/);
    fireEvent.click(compositeHeader);
    const rowsAsc = screen.getAllByTestId(/^screener-row-/);
    expect(rowsAsc[0]).toHaveAttribute("data-testid", "screener-row-AAPL");
    expect(rowsAsc[2]).toHaveAttribute("data-testid", "screener-row-QS");
  });

  it("shows error state on fetch failure", async () => {
    mockFetchError();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-error")).toBeInTheDocument();
    });
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });

  it("has an add ticker form", () => {
    mockFetchPending();
    renderScreener();
    expect(screen.getByTestId("add-ticker-form")).toBeInTheDocument();
    expect(screen.getByLabelText("Add ticker")).toBeInTheDocument();
  });

  it("ticker links navigate to symbol page", async () => {
    mockFetchSuccess();
    renderScreener();
    await waitFor(() => {
      expect(screen.getByTestId("screener-table")).toBeInTheDocument();
    });
    const qsLink = screen.getByText("QS").closest("a");
    expect(qsLink).toHaveAttribute("href", "/symbol/QS");
  });

  it("fetches with correct ticker query param", () => {
    mockFetchPending();
    renderScreener();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/screener?tickers=QS,GME,AMC,TSLA,AAPL,SPY,NVDA,PLTR"
    );
  });
});