import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { YieldCurveChart } from "./components/YieldCurveChart";
import { SpreadChart } from "./components/SpreadChart";
import { FtdHeatmap } from "./components/FtdHeatmap";
import { MacroGrid } from "./components/MacroGrid";
import { GlossaryTooltip } from "./components/GlossaryTooltip";
import { SymbolDeepDive } from "./pages/SymbolDeepDive";
import type { YieldCurvePoint, SpreadPoint } from "./types";
import "./App.css";

function HeaderSearch() {
  const navigate = useNavigate();
  const [searchValue, setSearchValue] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = searchValue.trim().toUpperCase();
    if (sym) {
      navigate(`/symbol/${sym}`);
      setSearchValue("");
    }
  };

  return (
    <form onSubmit={handleSearch} className="ticker-input" data-testid="header-search">
      <input
        type="text"
        value={searchValue}
        onChange={(e) => setSearchValue(e.target.value.toUpperCase())}
        placeholder="Search ticker..."
        aria-label="Search ticker"
        style={{
          padding: "6px 12px",
          border: "1px solid #ccc",
          borderRadius: 4,
          fontSize: 14,
          width: 110,
          textTransform: "uppercase",
        }}
      />
      <button
        type="submit"
        style={{
          padding: "6px 14px",
          background: "#2563eb",
          color: "#fff",
          border: "none",
          borderRadius: 4,
          fontSize: 14,
          cursor: "pointer",
        }}
      >
        Go
      </button>
    </form>
  );
}

function Dashboard() {
  const [curveData, setCurveData] = useState<YieldCurvePoint[]>([]);
  const [curveLoading, setCurveLoading] = useState(true);
  const [spreadData, setSpreadData] = useState<SpreadPoint[]>([]);
  const [spreadLoading, setSpreadLoading] = useState(true);

  useEffect(() => {
    fetch("/api/yields/curve")
      .then((res) => res.json())
      .then((json) => {
        const dict = json.data ?? {};
        const points: YieldCurvePoint[] = Object.entries(dict).map(
          ([maturity, yield_pct]) => ({
            maturity,
            yield_pct: yield_pct as number,
          })
        );
        setCurveData(points);
      })
      .catch(() => setCurveData([]))
      .finally(() => setCurveLoading(false));

    fetch("/api/yields/spread?long=10yr&short=2yr")
      .then((res) => res.json())
      .then((json) => {
        const points: SpreadPoint[] = (json.data ?? []).map(
          (d: { date: string; spread: number }) => ({
            date: d.date,
            spread: d.spread,
            inverted: d.spread < 0,
          })
        );
        setSpreadData(points);
      })
      .catch(() => setSpreadData([]))
      .finally(() => setSpreadLoading(false));
  }, []);

  return (
    <main className="dashboard">
      <section className="card">
        <h2>
          <GlossaryTooltip term="yield_curve">Current Yield Curve</GlossaryTooltip>
        </h2>
        <YieldCurveChart data={curveData} loading={curveLoading} />
      </section>

      <section className="card">
        <h2>
          <GlossaryTooltip term="spread">10yr\xe2\x80\x932yr Spread</GlossaryTooltip>
        </h2>
        <SpreadChart data={spreadData} loading={spreadLoading} />
      </section>

      <section className="card">
        <h2>
          <GlossaryTooltip term="ftd">Fails-to-Deliver Heatmap</GlossaryTooltip>
        </h2>
        <FtdHeatmap />
      </section>

      <section className="card">
        <h2>Macro Indicators</h2>
        <MacroGrid />
      </section>

      <section className="card" style={{ textAlign: "center" }}>
        <a
          href="/symbol/QS"
          style={{
            display: "inline-block",
            padding: "10px 24px",
            background: "#2563eb",
            color: "#fff",
            borderRadius: 6,
            textDecoration: "none",
            fontSize: 15,
            fontWeight: 600,
          }}
        >
          Deep Dive \xe2\x86\x92
        </a>
      </section>
    </main>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <h1>
                <a href="/" style={{ textDecoration: "none", color: "inherit" }}>Agora</a>
              </h1>
              <p className="subtitle">Open Financial Intelligence</p>
            </div>
            <HeaderSearch />
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/symbol/:ticker" element={<SymbolDeepDive />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
