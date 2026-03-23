"""Yahoo Finance quotes adapter for Agora."""

from __future__ import annotations

from datetime import date

import yfinance as yf

from agora.schemas import Quote


def fetch_quotes(
    symbol: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Quote]:
    """Fetch historical daily quotes for a ticker symbol via Yahoo Finance.

    Returns a list of Quote objects in chronological order.
    Rows with missing OHLCV data are skipped.
    """
    ticker = yf.Ticker(symbol)
    kwargs: dict = {}
    if start_date is not None:
        kwargs["start"] = start_date.isoformat()
    if end_date is not None:
        kwargs["end"] = end_date.isoformat()
    if not kwargs:
        kwargs["period"] = "1mo"

    df = ticker.history(**kwargs)

    if df is None or df.empty:
        return []

    results: list[Quote] = []
    for ts, row in df.iterrows():
        try:
            row_date = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
            open_ = float(row["Open"])
            high = float(row["High"])
            low = float(row["Low"])
            close = float(row["Close"])
            volume = int(row["Volume"])
        except (ValueError, TypeError, KeyError):
            continue
        results.append(
            Quote(
                symbol=symbol.upper(),
                date=row_date,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )
    return results
