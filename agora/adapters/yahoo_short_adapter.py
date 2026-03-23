"""Yahoo Finance short-interest adapter for Agora.

Uses yfinance to fetch short-sale metrics from Yahoo Finance and returns
them as ShortData objects.  Each metric (shortInterest, shortRatio, etc.)
becomes a separate ShortData entry so consumers can work with them
individually.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from agora.schemas import ShortData

logger = logging.getLogger(__name__)

# Maps yfinance info keys to (data_type, companion_key_for_total_for_ratio).
# companion_key_for_total_for_ratio, when present, populates total_for_ratio
# with the value of that companion field, giving context for the metric.
_METRIC_MAP: dict[str, tuple[str, str | None]] = {
    "shortInterest": ("short_interest", None),
    "shortRatio": ("short_ratio", None),
    "shortPercentOfFloat": ("short_percent_of_float", "floatShares"),
    "sharesShort": ("shares_short", "sharesOutstanding"),
    "sharesShortPriorMonth": ("shares_short_prior_month", "sharesOutstanding"),
}


def fetch_short_interest(symbol: str) -> list[ShortData]:
    """Fetch short-interest metrics for *symbol* from Yahoo Finance.

    Parameters
    ----------
    symbol : str
        Ticker symbol, e.g. ``"AAPL"``.

    Returns
    -------
    list[ShortData]
        One entry per available metric.  An empty list is returned when the
        ticker has no short-interest data (e.g. an ETF or invalid symbol).
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "yfinance is required for the Yahoo short adapter. "
            "Install it with: pip install yfinance"
        ) from exc

    try:
        ticker = yf.Ticker(symbol)
        info: dict = ticker.info or {}
    except Exception:
        logger.exception("Failed to fetch Yahoo Finance info for %s", symbol)
        return []

    if not info:
        return []

    # Determine the report date from dateShortInterest (epoch seconds) or
    # fall back to today.
    report_date = _parse_report_date(info)

    results: list[ShortData] = []
    for yf_key, (data_type, companion_key) in _METRIC_MAP.items():
        raw_value = info.get(yf_key)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            logger.warning("Non-numeric value for %s in %s: %r", yf_key, symbol, raw_value)
            continue

        total_for_ratio: float | None = None
        if companion_key is not None:
            raw_companion = info.get(companion_key)
            if raw_companion is not None:
                try:
                    total_for_ratio = float(raw_companion)
                except (TypeError, ValueError):
                    pass

        results.append(
            ShortData(
                symbol=symbol.upper(),
                date=report_date,
                data_type=data_type,
                value=value,
                total_for_ratio=total_for_ratio,
                source="Yahoo Finance",
            )
        )

    return results


def _parse_report_date(info: dict) -> date:
    """Extract the short-interest report date from *info*, or return today."""
    epoch = info.get("dateShortInterest")
    if epoch is not None:
        try:
            return datetime.fromtimestamp(int(epoch), tz=UTC).date()
        except (TypeError, ValueError, OSError):
            pass
    return date.today()
