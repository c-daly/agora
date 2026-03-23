import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  YAxis,
} from "recharts";

interface Indicator {
  seriesId: string;
  label: string;
}

interface ObservationPoint {
  date: string;
  value: number;
}

interface IndicatorState {
  loading: boolean;
  error: string | null;
  value: number | null;
  sparklineData: ObservationPoint[];
}

const DEFAULT_INDICATORS: Indicator[] = [
  { seriesId: "GDP", label: "GDP" },
  { seriesId: "CPIAUCSL", label: "CPI" },
  { seriesId: "UNRATE", label: "Unemployment Rate" },
  { seriesId: "FEDFUNDS", label: "Fed Funds Rate" },
];

interface Props {
  indicators?: Indicator[];
}

export function MacroGrid({ indicators = DEFAULT_INDICATORS }: Props) {
  const [states, setStates] = useState<Record<string, IndicatorState>>(() => {
    const initial: Record<string, IndicatorState> = {};
    for (const ind of indicators) {
      initial[ind.seriesId] = {
        loading: true,
        error: null,
        value: null,
        sparklineData: [],
      };
    }
    return initial;
  });

  useEffect(() => {
    for (const ind of indicators) {
      fetch(`/api/fred?series_id=${ind.seriesId}`)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((json) => {
          const observations: ObservationPoint[] = (
            json.data ?? []
          )
            .slice(-12)
            .map((obs: { date: string; value: number }) => ({
              date: obs.date,
              value: obs.value,
            }));
          const latest =
            observations.length > 0
              ? observations[observations.length - 1].value
              : null;
          setStates((prev) => ({
            ...prev,
            [ind.seriesId]: {
              loading: false,
              error: null,
              value: latest,
              sparklineData: observations,
            },
          }));
        })
        .catch((err: Error) => {
          setStates((prev) => ({
            ...prev,
            [ind.seriesId]: {
              loading: false,
              error: err.message,
              value: null,
              sparklineData: [],
            },
          }));
        });
    }
  }, [indicators]);

  return (
    <div
      data-testid="macro-grid"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 16,
      }}
    >
      {indicators.map((ind) => {
        const state = states[ind.seriesId];
        return (
          <div
            key={ind.seriesId}
            data-testid={`indicator-${ind.seriesId}`}
            style={{
              border: "1px solid #ddd",
              borderRadius: 8,
              padding: 16,
              background: "#fafafa",
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{ind.label}</div>
            {state?.loading && <p>Loading...</p>}
            {state?.error && (
              <p style={{ color: "red" }}>Error: {state.error}</p>
            )}
            {!state?.loading && !state?.error && (
              <>
                <div
                  style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}
                  data-testid={`value-${ind.seriesId}`}
                >
                  {state.value !== null ? state.value : "N/A"}
                </div>
                {state.sparklineData.length > 0 && (
                  <ResponsiveContainer width="100%" height={50}>
                    <LineChart data={state.sparklineData}>
                      <YAxis domain={["dataMin", "dataMax"]} hide />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#1f77b4"
                        strokeWidth={1.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
