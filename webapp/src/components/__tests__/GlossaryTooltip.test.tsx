import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { GlossaryTooltip, _resetGlossaryCache } from "../GlossaryTooltip";

const SAMPLE_GLOSSARY = [
  {
    term: "Yield Curve",
    description: "A line plotting interest rates of bonds with different maturities.",
    interpretation: "An inverted curve often signals a coming recession.",
  },
  {
    term: "Spread",
    description: "The difference between two yields.",
    interpretation: "Narrowing spreads may indicate slowing growth.",
  },
];

function mockFetchSuccess() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ data: SAMPLE_GLOSSARY }),
  } as Response);
}

describe("GlossaryTooltip", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    _resetGlossaryCache();
  });

  it("renders children text", async () => {
    mockFetchSuccess();
    render(
      <GlossaryTooltip term="Yield Curve">
        <span>Yield Curve</span>
      </GlossaryTooltip>
    );
    expect(screen.getByText("Yield Curve")).toBeInTheDocument();
  });

  it("shows tooltip on hover with term info", async () => {
    mockFetchSuccess();
    render(
      <GlossaryTooltip term="Yield Curve">
        <span>Yield Curve</span>
      </GlossaryTooltip>
    );

    // Wait for glossary to load and component to update
    await waitFor(() => {
      expect(screen.getByTestId("glossary-Yield Curve")).toBeInTheDocument();
    });

    // Hover to show tooltip
    fireEvent.mouseEnter(screen.getByTestId("glossary-Yield Curve"));

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveTextContent("Yield Curve");
    expect(tooltip).toHaveTextContent(
      "A line plotting interest rates of bonds with different maturities."
    );
    expect(tooltip).toHaveTextContent(
      "An inverted curve often signals a coming recession."
    );
  });

  it("hides tooltip on mouse leave", async () => {
    mockFetchSuccess();
    render(
      <GlossaryTooltip term="Yield Curve">
        <span>Yield Curve</span>
      </GlossaryTooltip>
    );

    await waitFor(() => {
      expect(screen.getByTestId("glossary-Yield Curve")).toBeInTheDocument();
    });

    fireEvent.mouseEnter(screen.getByTestId("glossary-Yield Curve"));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    fireEvent.mouseLeave(screen.getByTestId("glossary-Yield Curve"));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("renders only children for unknown term", async () => {
    mockFetchSuccess();
    render(
      <GlossaryTooltip term="Unknown Term">
        <span>Some Label</span>
      </GlossaryTooltip>
    );

    // Wait for fetch to complete
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText("Some Label")).toBeInTheDocument();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    // No data-testid wrapper for unknown terms
    expect(screen.queryByTestId("glossary-Unknown Term")).not.toBeInTheDocument();
  });

  it("caches glossary \u2014 one fetch for multiple instances", async () => {
    const fetchSpy = mockFetchSuccess();
    render(
      <>
        <GlossaryTooltip term="Yield Curve">
          <span>YC</span>
        </GlossaryTooltip>
        <GlossaryTooltip term="Spread">
          <span>Spread</span>
        </GlossaryTooltip>
      </>
    );

    await waitFor(() => {
      expect(screen.getByTestId("glossary-Yield Curve")).toBeInTheDocument();
      expect(screen.getByTestId("glossary-Spread")).toBeInTheDocument();
    });

    // Despite two component instances, fetch should only have been called once
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith("/api/glossary");
  });
});
