"""Short intel API routes for Agora.

Serves per-symbol short-selling intelligence: quotes, short volume,
short interest, FTDs, insider trades, composite scores, and divergences.
Delegates all data fetching to adapter modules and analysis to the
short_composite and short_divergence analysis modules.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agora.adapters import (
    edgar_insider_adapter,
    finra_short_volume_adapter,
    sec_ftd_adapter,
    yahoo_quotes_adapter,
    yahoo_short_adapter,
)
from agora.analysis import short_composite, short_divergence


router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FTD_LOOKBACK_DAYS = 30


def _ftd_dates(start: date | None, end: date | None) -> tuple[date, date]:
    """Default FTD date range to 90-day lookback if not specified."""
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=_FTD_LOOKBACK_DAYS)
    return start, end

def _parse_date(value: str | None, param_name: str) -> date | None:
    """Parse an ISO date string, raising HTTPException(400) on failure."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid date format for {param_name}: {value}. "
                "Expected ISO format (YYYY-MM-DD)."
            ),
        )


def _serialize_quote(q):
    """Serialize a Quote to a dict."""
    return {
        "symbol": q.symbol,
        "date": q.date.isoformat(),
        "open": q.open,
        "high": q.high,
        "low": q.low,
        "close": q.close,
        "volume": q.volume,
    }


def _serialize_short_data(sd):
    """Serialize a ShortData to a dict."""
    result = {
        "symbol": sd.symbol,
        "date": sd.date.isoformat(),
        "data_type": sd.data_type,
        "value": sd.value,
        "source": sd.source,
    }
    if sd.total_for_ratio is not None:
        result["total_for_ratio"] = sd.total_for_ratio
    return result


def _serialize_transaction(t):
    """Serialize a Transaction to a dict."""
    return {
        "date": t.date.isoformat(),
        "entity": t.entity,
        "action": t.action,
        "amount": t.amount,
        "context": t.context,
    }


def _serialize_divergence(d):
    """Serialize a divergence dict, converting dates to ISO strings."""
    result = dict(d)
    if "date_range" in result:
        dr = result["date_range"]
        result["date_range"] = {
            k: v.isoformat() if isinstance(v, date) else v
            for k, v in dr.items()
        }
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/symbol/{ticker}/quote")
def get_quote(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Price data from Yahoo Finance."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        quotes = yahoo_quotes_adapter.fetch_quotes(
            ticker,
            start_date=parsed_start,
            end_date=parsed_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    data = [_serialize_quote(q) for q in quotes]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/short-volume")
def get_short_volume(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """FINRA daily short volume data."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        records = finra_short_volume_adapter.fetch_short_volume(
            ticker,
            start_date=parsed_start,
            end_date=parsed_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    data = [_serialize_short_data(r) for r in records]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/short-interest")
def get_short_interest(ticker: str):
    """Yahoo Finance short-interest metrics."""
    try:
        records = yahoo_short_adapter.fetch_short_interest(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    data = [_serialize_short_data(r) for r in records]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/ftd")
def get_ftd(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """SEC Fails-to-Deliver data for a symbol."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        records = sec_ftd_adapter.fetch_ftd_data(
            symbol=ticker, start_date=_ftd_dates(parsed_start, parsed_end)[0], end_date=_ftd_dates(parsed_start, parsed_end)[1],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    data = [_serialize_short_data(r) for r in records]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/insider-trades")
def get_insider_trades(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """SEC EDGAR Form 4 insider trades."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        trades = edgar_insider_adapter.fetch_insider_trades(
            ticker,
            start_date=parsed_start,
            end_date=parsed_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    data = [_serialize_transaction(t) for t in trades]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/short-composite")
def get_short_composite(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Composite short-selling pressure score."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        short_vol = finra_short_volume_adapter.fetch_short_volume(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        short_vol = []

    try:
        short_int = yahoo_short_adapter.fetch_short_interest(ticker)
    except Exception:
        short_int = []

    try:
        ftd = sec_ftd_adapter.fetch_ftd_data(
            symbol=ticker, start_date=_ftd_dates(parsed_start, parsed_end)[0], end_date=_ftd_dates(parsed_start, parsed_end)[1],
        )
    except Exception:
        ftd = []

    result = short_composite.compute_short_composite(short_vol, short_int, ftd)
    return result


@router.get("/api/symbol/{ticker}/divergences")
def get_divergences(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Divergences between short signals and insider trading."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    try:
        short_vol = finra_short_volume_adapter.fetch_short_volume(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        short_vol = []

    try:
        short_int = yahoo_short_adapter.fetch_short_interest(ticker)
    except Exception:
        short_int = []

    try:
        ftd = sec_ftd_adapter.fetch_ftd_data(
            symbol=ticker, start_date=_ftd_dates(parsed_start, parsed_end)[0], end_date=_ftd_dates(parsed_start, parsed_end)[1],
        )
    except Exception:
        ftd = []

    try:
        trades = edgar_insider_adapter.fetch_insider_trades(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        trades = []

    all_short_data = short_vol + short_int + ftd
    divergences = short_divergence.detect_divergences(all_short_data, trades)
    data = [_serialize_divergence(d) for d in divergences]
    return {"data": data, "count": len(data)}


@router.get("/api/symbol/{ticker}/summary")
def get_summary(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Full short intel summary: everything in one call."""
    parsed_start = _parse_date(start_date, "start_date")
    parsed_end = _parse_date(end_date, "end_date")

    # Fetch all data sources, tolerating individual failures
    try:
        quotes = yahoo_quotes_adapter.fetch_quotes(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        quotes = []

    try:
        short_vol = finra_short_volume_adapter.fetch_short_volume(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        short_vol = []

    try:
        short_int = yahoo_short_adapter.fetch_short_interest(ticker)
    except Exception:
        short_int = []

    try:
        ftd = sec_ftd_adapter.fetch_ftd_data(
            symbol=ticker, start_date=_ftd_dates(parsed_start, parsed_end)[0], end_date=_ftd_dates(parsed_start, parsed_end)[1],
        )
    except Exception:
        ftd = []

    try:
        trades = edgar_insider_adapter.fetch_insider_trades(
            ticker, start_date=parsed_start, end_date=parsed_end,
        )
    except Exception:
        trades = []

    # Compute analysis
    composite = short_composite.compute_short_composite(short_vol, short_int, ftd)

    all_short_data = short_vol + short_int + ftd
    divergences = short_divergence.detect_divergences(all_short_data, trades)

    return {
        "symbol": ticker.upper(),
        "quote": [_serialize_quote(q) for q in quotes],
        "short_volume": [_serialize_short_data(r) for r in short_vol],
        "short_interest": [_serialize_short_data(r) for r in short_int],
        "ftd": [_serialize_short_data(r) for r in ftd],
        "insider_trades": [_serialize_transaction(t) for t in trades],
        "composite": composite,
        "divergences": [_serialize_divergence(d) for d in divergences],
    }
