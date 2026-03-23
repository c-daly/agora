import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import App from "./App";

const mockCurveData = {
  data: [
    { maturity: "1mo", yield_pct: 4.5 },
    { maturity: "3mo", yield_pct: 4.6 },
    { maturity: "2yr", yield_pct: 4.2 },
    { maturity: "10yr", yield_pct: 4.0 },
    { maturity: "30yr", yield_pct: 4.1 },
  ],
  as_of: "2024-01-15",
};

const mockSpreadData = {
  data: [
    { date: "2024-01-10", spread: 0.15 },
    { date: "2024-01-11", spread: -0.05 },
    { date: "2024-01-12", spread: 0.10 },
  ],
  long: "10yr",
  short: "2yr",
  count: 3,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the dashboard heading", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/api/yields/curve")) {
        return Promise.resolve(new Response(JSON.stringify(mockCurveData)));
      }
      if (url.includes("/api/yields/spread")) {
        return Promise.resolve(new Response(JSON.stringify(mockSpreadData)));
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<App />);
    expect(screen.getByText(/Agora/)).toBeInTheDocument();
  });

  it("shows loading states then chart headings", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.includes("/api/yields/curve")) {
        return Promise.resolve(new Response(JSON.stringify(mockCurveData)));
      }
      if (url.includes("/api/yields/spread")) {
        return Promise.resolve(new Response(JSON.stringify(mockSpreadData)));
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<App />);
    expect(screen.getByText("Current Yield Curve")).toBeInTheDocument();
    expect(screen.getByText(/Spread/)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Loading yield curve...")).not.toBeInTheDocument();
    });
  });
});
