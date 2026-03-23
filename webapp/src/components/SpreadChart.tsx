import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { SpreadPoint } from "../types";

interface Props {
  data: SpreadPoint[];
  loading: boolean;
}

export function SpreadChart({ data, loading }: Props) {
  if (loading) return <p>Loading spread data...</p>;
  if (data.length === 0) return <p>No spread data available.</p>;

  return (
    <ResponsiveContainer width="100%" height={350}>
      <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <defs>
          <linearGradient id="spreadColor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#1f77b4" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#1f77b4" stopOpacity={0.1} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis unit="%" />
        <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Spread"]} />
        <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
        <Area
          type="monotone"
          dataKey="spread"
          stroke="#1f77b4"
          fill="url(#spreadColor)"
          strokeWidth={2}
          dot={false}
          name="Spread"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
