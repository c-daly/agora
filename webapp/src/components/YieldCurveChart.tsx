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

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="maturity" />
        <YAxis unit="%" />
        <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Yield"]} />
        <Line
          type="monotone"
          dataKey="yield_pct"
          stroke="#1f77b4"
          strokeWidth={2}
          dot={{ r: 4 }}
          name="Yield"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
