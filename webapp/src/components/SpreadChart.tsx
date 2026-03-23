import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { SpreadPoint } from "../types";

interface Props {
  data: SpreadPoint[];
  loading: boolean;
}

export function SpreadChart({ data, loading }: Props) {
  if (loading) return <p>Loading spread data...</p>;
  if (data.length === 0) return <p>No spread data available.</p>;

  const values = data.map((d) => d.spread);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const padding = (max - min) * 0.1 || 0.1;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis
          domain={[min - padding, max + padding]}
          tickFormatter={(v: number) => `${v.toFixed(2)}%`}
        />
        <Tooltip formatter={(value: number) => [`${value.toFixed(3)}%`, "Spread"]} />
        <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" label="Inversion" />
        <Area
          type="monotone"
          dataKey="spread"
          stroke="#2563eb"
          fill="#93c5fd"
          fillOpacity={0.4}
          strokeWidth={2}
          name="10yr-2yr Spread"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
