"""Batch screener API for Agora.

Accepts a comma-separated list of ticker symbols and returns composite
short-selling pressure scores for each, sorted highest-first.  Per-ticker
failures are handled gracefully: the ticker is included in the response
with an error message instead of aborting the entire request.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from agora.adapters import (
    finra_short_volume_adapter,
    sec_ftd_adapter,
    yahoo_short_adapter,
)
from agora.analysis import short_composite

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_TICKERS = 20


def _score_ticker(ticker: str) -> dict:
    """Fetch data and compute composite score for a single ticker.

    Individual adapter failures are logged and degraded (empty data).
    Only raises if compute_short_composite itself fails.
    """
    try:
        short_vol = finra_short_volume_adapter.fetch_short_volume(ticker)
    except Exception:
        logger.warning("Short volume fetch failed for %s", ticker, exc_info=True)
        short_vol = []

    try:
        short_int = yahoo_short_adapter.fetch_short_interest(ticker)
    except Exception:
        logger.warning("Short interest fetch failed for %s", ticker, exc_info=True)
        short_int = []

    try:
        end = date.today()
        start = end - timedelta(days=30)
        ftd = sec_ftd_adapter.fetch_ftd_data(symbol=ticker, start_date=start, end_date=end)
    except Exception:
        logger.warning("FTD fetch failed for %s", ticker, exc_info=True)
        ftd = []

    return short_composite.compute_short_composite(short_vol, short_int, ftd)


@router.get("/api/screener")
def get_screener(
    tickers: str = Query(
        ...,
        description="Comma-separated ticker symbols (e.g. QS,GME,AMC,TSLA,AAPL)",
    ),
):
    """Batch short-selling pressure screener.

    For each ticker, fetches short volume, short interest, and FTD data,
    computes a composite score, and returns results sorted by score
    (highest first).  Individual ticker failures are captured as error
    entries rather than aborting the whole request.
    """
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if not symbols:
        raise HTTPException(
            status_code=400,
            detail="No valid ticker symbols provided.",
        )

    if len(symbols) > _MAX_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many tickers ({len(symbols)}). Maximum is {_MAX_TICKERS}.",
        )

    results: list[dict] = []
    errors: list[dict] = []

    for symbol in symbols:
        try:
            composite = _score_ticker(symbol)
            results.append(composite)
        except Exception as exc:
            logger.warning("Screener failed for %s: %s", symbol, exc)
            errors.append({"symbol": symbol, "error": "Failed to compute score"})

    # Sort by composite_score descending
    results.sort(key=lambda r: r.get("composite_score", 0), reverse=True)

    return {
        "data": results,
        "errors": errors,
        "count": len(results),
    }
