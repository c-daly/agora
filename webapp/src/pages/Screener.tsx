import { useEffect, useState, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";

const DEFAULT_TICKERS = ["QS", "GME", "AMC", "TSLA", "AAPL", "SPY", "NVDA", "PLTR"];

interface ScreenerRow {
  ticker: string;
  composite_score: number;
  signal_label: string;
  short_volume_score: number;
  si_score: number;
  ftd_score: number;
}

type SortKey = keyof ScreenerRow;
type SortDir = "asc" | "desc";

function signalBadgeClass(signal: string): string {
  const s = (signal ?? "low").toLowerCase();
  if (s.includes("extreme")) return "screener-badge screener-badge--extreme";
  if (s.includes("high")) return "screener-badge screener-badge--high";
  if (s.includes("moderate")) return "screener-badge screener-badge--moderate";
  return "screener-badge screener-badge--low";
}

function sortIndicator(column: SortKey, sortKey: SortKey, sortDir: SortDir): string {
  if (column !== sortKey) return "";
  return sortDir === "asc" ? " ▲" : " ▼";
}

export function Screener() {
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [tickers, setTickers] = useState<string[]>(DEFAULT_TICKERS);
  const [inputValue, setInputValue] = useState("");

  const fetchScreener = useCallback((tickerList: string[]) => {
    setLoading(true);
    setError(null);
    fetch(`/api/screener?tickers=${tickerList.join(",")}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        const mapped: ScreenerRow[] = (json.data ?? []).map((r: Record<string, unknown>) => ({
          ticker: r.symbol as string,
          composite_score: r.composite_score as number,
          signal_label: (r.signal as string) ?? "N/A",
          short_volume_score: ((r.components as Record<string, number>)?.short_volume_score) ?? 0,
          si_score: ((r.components as Record<string, number>)?.short_interest_score) ?? 0,
          ftd_score: ((r.components as Record<string, number>)?.ftd_score) ?? 0,
        }));
        setRows(mapped);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchScreener(tickers);
  }, [tickers, fetchScreener]);

  const handleAddTicker = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = inputValue.trim().toUpperCase();
    if (sym && !tickers.includes(sym)) {
      setTickers((prev) => [...prev, sym]);
    }
    setInputValue("");
  };

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortDir === "asc" ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });
  }, [rows, sortKey, sortDir]);

  const columns: { key: SortKey; label: string }[] = [
    { key: "ticker", label: "Ticker" },
    { key: "composite_score", label: "Composite Score" },
    { key: "signal_label", label: "Signal" },
    { key: "short_volume_score", label: "Short Vol Score" },
    { key: "si_score", label: "SI Score" },
    { key: "ftd_score", label: "FTD Score" },
  ];

  return (
    <main className="screener" data-testid="screener-page">
      <section className="card">
        <h2>Screener</h2>

        <form onSubmit={handleAddTicker} className="screener-add-ticker" data-testid="add-ticker-form">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value.toUpperCase())}
            placeholder="Add ticker..."
            aria-label="Add ticker"
          />
          <button type="submit">Add</button>
        </form>

        {loading && (
          <p className="screener-loading" data-testid="screener-loading">
            Loading screener data...
          </p>
        )}

        {error && (
          <p className="screener-error" data-testid="screener-error">
            Error: {error}
          </p>
        )}

        {!loading && !error && (
          <div className="screener-table-wrapper">
            <table className="screener-table" data-testid="screener-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="screener-table__sortable"
                      aria-sort={
                        sortKey === col.key
                          ? sortDir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      {col.label}
                      {sortIndicator(col.key, sortKey, sortDir)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.ticker} data-testid={`screener-row-${row.ticker}`}>
                    <td>
                      <Link to={`/symbol/${row.ticker}`} className="screener-ticker-link">
                        {row.ticker}
                      </Link>
                    </td>
                    <td>{row.composite_score}</td>
                    <td>
                      <span className={signalBadgeClass(row.signal_label)}>
                        {row.signal_label}
                      </span>
                    </td>
                    <td>{row.short_volume_score}</td>
                    <td>{row.si_score}</td>
                    <td>{row.ftd_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
