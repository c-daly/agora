import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { YieldCurvePoint } from "../types";

interface Props {
  data: YieldCurvePoint[];
  loading: boolean;
}

export function YieldCurveChart({ data, loading }: Props) {
  if (loading) return <p>Loading yield curve...</p>;
  if (data.length === 0) return <p>No yield curve data available.</p>;

  const values = data.map((d) => d.yield_pct);
  const min = Math.floor(Math.min(...values) * 2) / 2;
  const max = Math.ceil(Math.max(...values) * 2) / 2;

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="maturity" />
        <YAxis
          domain={[min, max]}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
        />
        <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Yield"]} />
        <Line
          type="monotone"
          dataKey="yield_pct"
          stroke="#2563eb"
          strokeWidth={2.5}
          dot={{ r: 5, fill: "#2563eb" }}
          name="Yield"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
