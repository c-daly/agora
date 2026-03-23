import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Bar,
  ComposedChart,
  Line,
} from "recharts";
import { FtdHeatmap } from "../components/FtdHeatmap";
import { GlossaryTooltip } from "../components/GlossaryTooltip";

interface QuotePoint {
  date: string;
  close: number;
  volume: number;
}

interface ShortVolumePoint {
  date: string;
  short_volume_ratio: number;
}

interface InsiderTrade {
  date: string;
  name: string;
  action: string;
  shares: number;
  price: number;
}

interface DivergenceAlert {
  signal: string;
  severity: "high" | "medium" | "low";
  description: string;
}

interface SymbolSummary {
  ticker: string;
  composite_score: number;
  signal_label: string;
  quote: QuotePoint[];
  short_volume: ShortVolumePoint[];
  insider_trades: InsiderTrade[];
  divergences: DivergenceAlert[];
}

function scoreColor(score: number): string {
  if (score >= 70) return "#16a34a";
  if (score >= 40) return "#eab308";
  return "#dc2626";
}

function severityColor(severity: string): string {
  if (severity === "high") return "#dc2626";
  if (severity === "medium") return "#eab308";
  return "#2563eb";
}

export function SymbolDeepDive() {
  const { ticker: routeTicker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();

  const [ticker, setTicker] = useState(routeTicker?.toUpperCase() || "QS");
  const [inputValue, setInputValue] = useState(ticker);
  const [summary, setSummary] = useState<SymbolSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback((sym: string) => {
    setLoading(true);
    setError(null);
    fetch(`/api/symbol/${encodeURIComponent(sym)}/summary`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        const data = json.data ?? json;
        // Map composite (nested object)
        const comp = data.composite ?? {};
        // Map quotes: API returns {date, open, high, low, close, volume}
        const quotes = (data.quote ?? []).map((q: Record<string, unknown>) => ({
          date: q.date,
          close: q.close,
          volume: q.volume,
        }));
        // Map short volume: API returns {value, total_for_ratio} -> compute ratio
        const svol = (data.short_volume ?? []).map((sv: Record<string, unknown>) => ({
          date: sv.date,
          short_volume_ratio: (sv.total_for_ratio as number) > 0
            ? (sv.value as number) / (sv.total_for_ratio as number)
            : 0,
        }));
        // Map insider trades: API returns {entity, action, amount, context}
        const insiders = (data.insider_trades ?? []).map((t: Record<string, unknown>) => ({
          date: t.date,
          name: t.entity,
          action: t.action,
          shares: t.amount,
          price: (t.context as Record<string, unknown>)?.price ?? 0,
        }));
        // Map divergences: API returns {divergence_type, description, severity}
        const divs = (data.divergences ?? []).map((d: Record<string, unknown>) => ({
          signal: d.divergence_type,
          severity: d.severity,
          description: d.description,
        }));
        setSummary({
          ticker: data.symbol ?? sym,
          composite_score: comp.composite_score ?? 0,
          signal_label: comp.signal ?? "N/A",
          quote: quotes,
          short_volume: svol,
          insider_trades: insiders,
          divergences: divs,
        });
      })
      .catch((err) => {
        setError(err.message ?? "Failed to load data");
        setSummary(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchSummary(ticker);
  }, [ticker, fetchSummary]);

  useEffect(() => {
    if (routeTicker && routeTicker.toUpperCase() !== ticker) {
      const sym = routeTicker.toUpperCase();
      setTicker(sym);
      setInputValue(sym);
    }
  }, [routeTicker]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = inputValue.trim().toUpperCase();
    if (sym && sym !== ticker) {
      setTicker(sym);
      setInputValue(sym);
      navigate(`/symbol/${sym}`, { replace: true });
    }
  };

  return (
    <>
      <form onSubmit={handleSubmit} className="ticker-input" data-testid="ticker-form">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value.toUpperCase())}
          placeholder="Enter ticker..."
          aria-label="Ticker symbol"
          style={{
            padding: "8px 14px",
            border: "1px solid #ccc",
            borderRadius: 4,
            fontSize: 15,
            width: 120,
            textTransform: "uppercase",
          }}
        />
        <button
          type="submit"
          style={{
            padding: "8px 20px",
            background: "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            fontSize: 15,
            cursor: "pointer",
          }}
        >
          Go
        </button>
        <span style={{ color: "#666", fontSize: 14, marginLeft: 8 }}>
          Viewing: <strong>{ticker}</strong>
        </span>
      </form>

      {loading && (
        <div className="card" data-testid="loading-state">
          <p>Loading summary for {ticker}...</p>
        </div>
      )}

      {error && !loading && (
        <div className="card" style={{ borderLeft: "4px solid #dc2626" }}>
          <p style={{ color: "#dc2626" }}>Error: {error}</p>
        </div>
      )}

      {summary && !loading && (
        <main className="dashboard">
          <section className="card">
            <h2>
              <GlossaryTooltip term="composite_score">Composite Score</GlossaryTooltip>
            </h2>
            <div className="composite-score" data-testid="composite-score">
              <span
                className="composite-score__value"
                style={{ color: scoreColor(summary.composite_score) }}
              >
                {summary.composite_score}
              </span>
              <span className="composite-score__label">{summary.signal_label}</span>
            </div>
          </section>

          <section className="card">
            <h2>
              <GlossaryTooltip term="price_chart">Price Chart</GlossaryTooltip>
            </h2>
            {summary.quote.length === 0 ? (
              <p>No price data available.</p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={summary.quote}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="price" orientation="left" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="volume" orientation="right" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar yAxisId="volume" dataKey="volume" fill="rgba(37, 99, 235, 0.15)" name="Volume" />
                  <Line yAxisId="price" type="monotone" dataKey="close" stroke="#2563eb" strokeWidth={2} dot={false} name="Close" />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="card">
            <h2>
              <GlossaryTooltip term="short_volume">Short Volume Ratio</GlossaryTooltip>
            </h2>
            {summary.short_volume.length === 0 ? (
              <p>No short volume data available.</p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={summary.short_volume}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="short_volume_ratio" stroke="#dc2626" fill="rgba(220, 38, 38, 0.15)" name="Short Vol Ratio" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="card">
            <h2>
              <GlossaryTooltip term="ftd">Fails-to-Deliver</GlossaryTooltip>
            </h2>
            <FtdHeatmap symbol={ticker} />
          </section>

          <section className="card">
            <h2>
              <GlossaryTooltip term="insider_trades">Insider Trades</GlossaryTooltip>
            </h2>
            {summary.insider_trades.length === 0 ? (
              <p>No insider trade data available.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="insider-table" data-testid="insider-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Name</th>
                      <th>Action</th>
                      <th>Shares</th>
                      <th>Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.insider_trades.map((trade, i) => (
                      <tr key={`${trade.date}-${trade.name}-${i}`}>
                        <td>{trade.date}</td>
                        <td>{trade.name}</td>
                        <td style={{ color: trade.action.toLowerCase().includes("buy") ? "#16a34a" : "#dc2626", fontWeight: 600 }}>
                          {trade.action}
                        </td>
                        <td style={{ textAlign: "right" }}>{trade.shares.toLocaleString()}</td>
                        <td style={{ textAlign: "right" }}>${trade.price.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card">
            <h2>
              <GlossaryTooltip term="divergence">Divergence Alerts</GlossaryTooltip>
            </h2>
            {summary.divergences.length === 0 ? (
              <p>No divergence signals detected.</p>
            ) : (
              <div className="divergence-list" data-testid="divergence-alerts">
                {summary.divergences.map((d, i) => (
                  <div
                    key={`${d.signal}-${i}`}
                    className="divergence-card"
                    style={{ borderLeftColor: severityColor(d.severity) }}
                  >
                    <div className="divergence-card__header">
                      <span className="divergence-card__badge" style={{ background: severityColor(d.severity) }}>
                        {d.severity.toUpperCase()}
                      </span>
                      <strong>{d.signal}</strong>
                    </div>
                    <p>{d.description}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      )}
    </>
  );
}
