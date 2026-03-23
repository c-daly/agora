import { useEffect, useState } from "react";
import { YieldCurveChart } from "./components/YieldCurveChart";
import { SpreadChart } from "./components/SpreadChart";
import { FtdHeatmap } from "./components/FtdHeatmap";
import { MacroGrid } from "./components/MacroGrid";
import { GlossaryTooltip } from "./components/GlossaryTooltip";
import type { YieldCurvePoint, SpreadPoint } from "./types";
import "./App.css";

function App() {
  const [curveData, setCurveData] = useState<YieldCurvePoint[]>([]);
  const [curveLoading, setCurveLoading] = useState(true);
  const [spreadData, setSpreadData] = useState<SpreadPoint[]>([]);
  const [spreadLoading, setSpreadLoading] = useState(true);

  useEffect(() => {
    fetch("/api/yields/curve")
      .then((res) => res.json())
      .then((json) => {
        // API returns {data: {maturity: yield, ...}, as_of: "..."}
        // Transform to YieldCurvePoint[]
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
    <div className="app">
      <header className="app-header">
        <h1>Agora</h1>
        <p className="subtitle">Open Financial Intelligence</p>
      </header>

      <main className="dashboard">
        <section className="card">
          <h2>
            <GlossaryTooltip term="yield_curve">Current Yield Curve</GlossaryTooltip>
          </h2>
          <YieldCurveChart data={curveData} loading={curveLoading} />
        </section>

        <section className="card">
          <h2>
            <GlossaryTooltip term="spread">10yr–2yr Spread</GlossaryTooltip>
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
      </main>
    </div>
  );
}

export default App;
