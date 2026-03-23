export interface YieldCurvePoint {
  maturity: string;
  yield_pct: number;
}

export interface SpreadPoint {
  date: string;
  spread: number;
  inverted: boolean;
}

export interface FtdPoint {
  date: string;
  symbol: string;
  quantity: number;
}
