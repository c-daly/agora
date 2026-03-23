import { useEffect, useMemo, useState } from "react";
import type { FtdPoint } from "../types";

interface Props {
  data?: FtdPoint[];
  symbol?: string;
}

function intensityColor(value: number, max: number): string {
  if (max === 0) return "rgba(30, 100, 200, 0.05)";
  const ratio = Math.min(value / max, 1);
  const alpha = 0.08 + ratio * 0.87; // range 0.08 - 0.95
  return `rgba(30, 100, 200, ${alpha.toFixed(2)})`;
}

export function FtdHeatmap({ data: externalData, symbol: initialSymbol }: Props) {
  const [rawData, setRawData] = useState<FtdPoint[]>(externalData ?? []);
  const [loading, setLoading] = useState(!externalData);
  const [filter, setFilter] = useState(initialSymbol ?? "");

  useEffect(() => {
    if (externalData) {
      setRawData(externalData);
      return;
    }

    setLoading(true);
    fetch("/api/ftd")
      .then((res) => res.json())
      .then((json) => {
        setRawData(json.data ?? []);
      })
      .catch(() => setRawData([]))
      .finally(() => setLoading(false));
  }, [externalData]);

  const filtered = useMemo(() => {
    if (!filter) return rawData;
    const upper = filter.toUpperCase();
    return rawData.filter((d) => d.symbol.toUpperCase().includes(upper));
  }, [rawData, filter]);

  const { symbols, dates, lookup, maxQty } = useMemo(() => {
    const symbolSet = new Set<string>();
    const dateSet = new Set<string>();
    const map = new Map<string, number>();
    let mx = 0;

    for (const d of filtered) {
      symbolSet.add(d.symbol);
      dateSet.add(d.date);
      const key = `${d.symbol}|${d.date}`;
      map.set(key, (map.get(key) ?? 0) + d.quantity);
      const val = map.get(key)!;
      if (val > mx) mx = val;
    }

    const sortedSymbols = Array.from(symbolSet).sort();
    const sortedDates = Array.from(dateSet).sort();
    return { symbols: sortedSymbols, dates: sortedDates, lookup: map, maxQty: mx };
  }, [filtered]);

  if (loading) return <p>Loading FTD data...</p>;

  if (rawData.length === 0) return <p>No FTD data available.</p>;

  if (filtered.length === 0)
    return (
      <div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="ftd-symbol-filter">Symbol filter: </label>
          <input
            id="ftd-symbol-filter"
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="e.g. AAPL"
          />
        </div>
        <p>No FTD data matches the filter &quot;{filter}&quot;.</p>
      </div>
    );

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label htmlFor="ftd-symbol-filter">Symbol filter: </label>
        <input
          id="ftd-symbol-filter"
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="e.g. AAPL"
        />
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          data-testid="ftd-heatmap-table"
          style={{ borderCollapse: "collapse", fontSize: 13 }}
        >
          <thead>
            <tr>
              <th style={{ padding: "4px 8px", textAlign: "left" }}>Symbol</th>
              {dates.map((d) => (
                <th key={d} style={{ padding: "4px 8px", whiteSpace: "nowrap" }}>
                  {d}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((sym) => (
              <tr key={sym}>
                <td style={{ padding: "4px 8px", fontWeight: 600 }}>{sym}</td>
                {dates.map((d) => {
                  const qty = lookup.get(`${sym}|${d}`) ?? 0;
                  return (
                    <td
                      key={d}
                      title={`${sym} ${d}: ${qty.toLocaleString()}`}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: qty > 0 ? intensityColor(qty, maxQty) : "transparent",
                        textAlign: "right",
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
    </div>
  );
}
