import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MacroGrid } from "../MacroGrid";

function mockFetchSuccess(seriesId: string, values: number[]) {
  return {
    observations: values.map((v, i) => ({
      date: `2024-${String(i + 1).padStart(2, "0")}-01`,
      value: String(v),
    })),
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("MacroGrid", () => {
  it("renders loading state for each indicator", () => {
    // Never resolve the fetches so we stay in loading state
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );

    render(
      <MacroGrid
        indicators={[
          { seriesId: "GDP", label: "GDP" },
          { seriesId: "UNRATE", label: "Unemployment Rate" },
        ]}
      />
    );

    const loadingElements = screen.getAllByText("Loading...");
    expect(loadingElements).toHaveLength(2);
  });

  it("renders indicator labels", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );

    render(
      <MacroGrid
        indicators={[
          { seriesId: "GDP", label: "GDP" },
          { seriesId: "CPI", label: "CPI" },
        ]}
      />
    );

    expect(screen.getByText("GDP")).toBeInTheDocument();
    expect(screen.getByText("CPI")).toBeInTheDocument();
  });

  it("renders current value after successful fetch", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("series_id=TEST1")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(mockFetchSuccess("TEST1", [1.1, 2.2, 3.3])),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify(mockFetchSuccess("TEST2", [10, 20, 30])),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    });

    render(
      <MacroGrid
        indicators={[
          { seriesId: "TEST1", label: "Test One" },
          { seriesId: "TEST2", label: "Test Two" },
        ]}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("value-TEST1")).toHaveTextContent("3.3");
    });
    await waitFor(() => {
      expect(screen.getByTestId("value-TEST2")).toHaveTextContent("30");
    });
  });

  it("renders error state when fetch fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response("Not found", { status: 500 })
      )
    );

    render(
      <MacroGrid
        indicators={[{ seriesId: "BAD", label: "Bad Indicator" }]}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
    });
  });

  it("renders error state when fetch rejects", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.reject(new Error("Network failure"))
    );

    render(
      <MacroGrid
        indicators={[{ seriesId: "FAIL", label: "Failing" }]}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Error: Network failure")).toBeInTheDocument();
    });
  });

  it("isolates errors per indicator — one failure does not break others", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("series_id=GOOD")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(mockFetchSuccess("GOOD", [5, 10, 15])),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.reject(new Error("Network failure"));
    });

    render(
      <MacroGrid
        indicators={[
          { seriesId: "GOOD", label: "Good" },
          { seriesId: "BAD", label: "Bad" },
        ]}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("value-GOOD")).toHaveTextContent("15");
    });
    await waitFor(() => {
      expect(screen.getByText("Error: Network failure")).toBeInTheDocument();
    });
  });

  it("renders the grid container", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );

    render(<MacroGrid indicators={[{ seriesId: "X", label: "X" }]} />);
    expect(screen.getByTestId("macro-grid")).toBeInTheDocument();
  });

  it("uses default indicators when none provided", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );

    render(<MacroGrid />);

    expect(screen.getByText("GDP")).toBeInTheDocument();
    expect(screen.getByText("CPI")).toBeInTheDocument();
    expect(screen.getByText("Unemployment Rate")).toBeInTheDocument();
    expect(screen.getByText("Fed Funds Rate")).toBeInTheDocument();
    // 4 default indicators, 4 fetches
    expect(globalThis.fetch).toHaveBeenCalledTimes(4);
  });

  it("calls the correct API endpoint for each indicator", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {})
    );

    render(
      <MacroGrid
        indicators={[
          { seriesId: "GDP", label: "GDP" },
          { seriesId: "UNRATE", label: "Unemployment Rate" },
        ]}
      />
    );

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/fred?series_id=GDP");
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/fred?series_id=UNRATE");
  });
});
