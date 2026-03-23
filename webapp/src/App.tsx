import { useEffect, useState } from "react";
import { YieldCurveChart } from "./components/YieldCurveChart";
import { SpreadChart } from "./components/SpreadChart";
import type { YieldCurvePoint, SpreadPoint } from "./types";

function App() {
  const [curveData, setCurveData] = useState<YieldCurvePoint[]>([]);
  const [curveLoading, setCurveLoading] = useState(true);
  const [spreadData, setSpreadData] = useState<SpreadPoint[]>([]);
  const [spreadLoading, setSpreadLoading] = useState(true);

  useEffect(() => {
    fetch("/api/yields/curve")
      .then((res) => res.json())
      .then((json) => {
        setCurveData(json.data ?? []);
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
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Agora — Yield Curve Dashboard</h1>
      <section>
        <h2>Current Yield Curve</h2>
        <YieldCurveChart data={curveData} loading={curveLoading} />
      </section>
      <section style={{ marginTop: 32 }}>
        <h2>10yr–2yr Spread</h2>
        <SpreadChart data={spreadData} loading={spreadLoading} />
      </section>
    </div>
  );
}

export default App;
