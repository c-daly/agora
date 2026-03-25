"""Yahoo Finance options adapter for Agora.

Uses yfinance to fetch options chains and returns them as OptionsSnapshot objects.
"""

from __future__ import annotations

import logging
from datetime import date

import yfinance as yf

from agora.schemas import OptionsSnapshot

logger = logging.getLogger(__name__)


def fetch_options(
    symbol: str,
    *,
    expiry: date | None = None,
) -> list[OptionsSnapshot]:
    """Fetch options chain data for a ticker symbol via Yahoo Finance.

    Parameters
    ----------
    symbol : str
        Ticker symbol, e.g. AAPL.
    expiry : date | None
        If given, fetch the chain for this specific expiration date.
        Otherwise, fetch chains for all available expiration dates.

    Returns
    -------
    list[OptionsSnapshot]
        One entry per contract (both puts and calls).  An empty list is
        returned when the ticker has no listed options.
    """
    try:
        ticker = yf.Ticker(symbol)
        available: tuple[str, ...] = ticker.options or ()
    except Exception:
        logger.exception("Failed to fetch options expiries for %s", symbol)
        return []

    if not available:
        return []

    today = date.today()

    if expiry is not None:
        expiry_str = expiry.isoformat()
        if expiry_str not in available:
            logger.warning(
                "Expiry %s not available for %s; available: %s",
                expiry_str,
                symbol,
                available,
            )
            return []
        expiry_dates = [expiry_str]
    else:
        expiry_dates = list(available)

    results: list[OptionsSnapshot] = []

    for exp_str in expiry_dates:
        try:
            chain = ticker.option_chain(exp_str)
        except Exception:
            logger.exception(
                "Failed to fetch option chain for %s exp %s", symbol, exp_str
            )
            continue

        exp_date = date.fromisoformat(exp_str)

        for opt_type, df in [("call", chain.calls), ("put", chain.puts)]:
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                try:
                    strike = float(row["strike"])
                    volume = int(row.get("volume", 0) or 0)
                    open_interest = int(row.get("openInterest", 0) or 0)
                    implied_vol = (
                        float(row["impliedVolatility"])
                        if row.get("impliedVolatility") is not None
                        else None
                    )
                    bid = float(row["bid"]) if row.get("bid") is not None else None
                    ask = float(row["ask"]) if row.get("ask") is not None else None
                except (ValueError, TypeError, KeyError):
                    continue

                results.append(
                    OptionsSnapshot(
                        symbol=symbol.upper(),
                        date=today,
                        expiry=exp_date,
                        strike=strike,
                        type=opt_type,
                        volume=volume,
                        open_interest=open_interest,
                        implied_vol=implied_vol,
                        bid=bid,
                        ask=ask,
                    )
                )

    return results
