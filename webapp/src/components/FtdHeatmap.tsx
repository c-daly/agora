import { useEffect, useMemo, useState } from "react";
import type { FtdPoint } from "../types";

interface Props {
  data?: FtdPoint[];
  symbol?: string;
}

function intensityColor(value: number, max: number): string {
  if (max === 0) return "rgba(30, 100, 200, 0.05)";
  const ratio = Math.min(value / max, 1);
  const alpha = 0.08 + ratio * 0.87;
  return `rgba(30, 100, 200, ${alpha.toFixed(2)})`;
}

export function FtdHeatmap({ data: externalData, symbol: initialSymbol }: Props) {
  const [rawData, setRawData] = useState<FtdPoint[]>(externalData ?? []);
  const [loading, setLoading] = useState(!externalData);
  const [ticker, setTicker] = useState(initialSymbol ?? "QS");
  const [inputValue, setInputValue] = useState(initialSymbol ?? "QS");

  const fetchData = (sym: string) => {
    setLoading(true);
    // Default to last 3 months — FTD data has ~2 week lag
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - 3);
    const startStr = start.toISOString().split("T")[0];
    const endStr = end.toISOString().split("T")[0];
    fetch(`/api/ftd?symbol=${encodeURIComponent(sym)}&start_date=${startStr}&end_date=${endStr}`)
      .then((res) => res.json())
      .then((json) => {
        const points: FtdPoint[] = (json.data ?? []).map((d: { symbol: string; date: string; value: number }) => ({
          symbol: d.symbol,
          date: d.date,
          quantity: d.value,
        }));
        setRawData(points);
      })
      .catch(() => setRawData([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (externalData) {
      setRawData(externalData);
      return;
    }
    fetchData(ticker);
  }, [externalData]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = inputValue.trim().toUpperCase();
    if (sym && sym !== ticker) {
      setTicker(sym);
      fetchData(sym);
    }
  };

  const { symbols, dates, lookup, maxQty } = useMemo(() => {
    const symbolSet = new Set<string>();
    const dateSet = new Set<string>();
    const map = new Map<string, number>();
    let mx = 0;

    for (const d of rawData) {
      symbolSet.add(d.symbol);
      dateSet.add(d.date);
      const key = `${d.symbol}|${d.date}`;
      map.set(key, (map.get(key) ?? 0) + d.quantity);
      const val = map.get(key)!;
      if (val > mx) mx = val;
    }

    return {
      symbols: Array.from(symbolSet).sort(),
      dates: Array.from(dateSet).sort(),
      lookup: map,
      maxQty: mx,
    };
  }, [rawData]);

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
        <label htmlFor="ftd-symbol">Ticker:</label>
        <input
          id="ftd-symbol"
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value.toUpperCase())}
          style={{
            padding: "6px 12px",
            border: "1px solid #ccc",
            borderRadius: 4,
            fontSize: 14,
            width: 100,
            textTransform: "uppercase",
          }}
        />
        <button
          type="submit"
          style={{
            padding: "6px 16px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          Load
        </button>
        {ticker && <span style={{ color: "#666", fontSize: 13 }}>Showing: {ticker}</span>}
      </form>

      {loading && <p>Loading FTD data for {ticker}...</p>}

      {!loading && rawData.length === 0 && (
        <p>No FTD data available for {ticker}.</p>
      )}

      {!loading && rawData.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>
            <thead>
              <tr>
                <th style={{ padding: "6px 8px", textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>Symbol</th>
                {dates.map((d) => (
                  <th key={d} style={{ padding: "6px 8px", whiteSpace: "nowrap", borderBottom: "2px solid #e5e7eb" }}>
                    {d}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {symbols.map((sym) => (
                <tr key={sym}>
                  <td style={{ padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #f0f0f0" }}>{sym}</td>
                  {dates.map((d) => {
                    const qty = lookup.get(`${sym}|${d}`) ?? 0;
                    return (
                      <td
                        key={d}
                        title={`${sym} ${d}: ${qty.toLocaleString()}`}
                        style={{
                          padding: "6px 8px",
                          backgroundColor: qty > 0 ? intensityColor(qty, maxQty) : "transparent",
                          textAlign: "right",
                          borderBottom: "1px solid #f0f0f0",
                        }}
                      >
                        {qty > 0 ? qty.toLocaleString() : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
