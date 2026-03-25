"""Sector analysis module.

Operates on already-fetched Quote data to compute sector performance
and detect sector rotation. Does not fetch any data itself.
"""

from __future__ import annotations

import numpy as np

from collections import defaultdict

from agora.schemas import Quote


def _period_return(quotes: list[Quote]) -> float:
    """Compute percentage return from first to last close in a sorted quote list.

    Returns 0.0 when there are fewer than two quotes or the initial close is zero.
    """
    if len(quotes) < 2:
        return 0.0
    first_close = quotes[0].close
    last_close = quotes[-1].close
    if first_close == 0.0:
        return 0.0
    return (last_close - first_close) / first_close


def _average_volume(quotes: list[Quote]) -> float:
    """Compute mean daily volume across all quotes."""
    if not quotes:
        return 0.0
    return sum(q.volume for q in quotes) / len(quotes)


def compute_sector_performance(
    quotes_by_sector: dict[str, list[Quote]],
) -> list[dict]:
    """Compute performance metrics for each sector.

    Each sector\xe2\x80\x99s quotes are sorted by date, then aggregated into a single
    dict containing: sector name, average return across symbols, total
    volume, symbol count, and the best/worst performing symbols.

    Returns a list of dicts sorted by ``avg_return`` descending (best
    performing sector first).
    """
    if not quotes_by_sector:
        return []

    results: list[dict] = []

    for sector, quotes in quotes_by_sector.items():
        if not quotes:
            continue

        # Group by symbol
        by_symbol: dict[str, list[Quote]] = defaultdict(list)
        for q in quotes:
            by_symbol[q.symbol].append(q)

        # Sort each symbol quotes by date and compute returns
        symbol_returns: dict[str, float] = {}
        total_volume = 0
        for sym, sym_quotes in by_symbol.items():
            sym_quotes.sort(key=lambda q: q.date)
            symbol_returns[sym] = _period_return(sym_quotes)
            total_volume += sum(q.volume for q in sym_quotes)

        avg_return = sum(symbol_returns.values()) / len(symbol_returns)

        # Best and worst symbol
        best_symbol = max(symbol_returns, key=symbol_returns.get)  # type: ignore[arg-type]
        worst_symbol = min(symbol_returns, key=symbol_returns.get)  # type: ignore[arg-type]

        results.append(
            {
                "sector": sector,
                "avg_return": round(avg_return, 6),
                "total_volume": total_volume,
                "symbol_count": len(by_symbol),
                "best_symbol": best_symbol,
                "best_return": round(symbol_returns[best_symbol], 6),
                "worst_symbol": worst_symbol,
                "worst_return": round(symbol_returns[worst_symbol], 6),
            }
        )

    results.sort(key=lambda r: r["avg_return"], reverse=True)
    return results


def _split_into_periods(
    quotes: list[Quote],
    periods: int,
) -> list[list[Quote]]:
    """Split a date-sorted quote list into *periods* roughly equal chunks.

    If there are fewer quotes than *periods*, each quote becomes its own
    chunk (and some periods may be empty).
    """
    if not quotes or periods <= 0:
        return []
    chunk_size = max(1, len(quotes) // periods)
    chunks: list[list[Quote]] = []
    for i in range(0, len(quotes), chunk_size):
        chunks.append(quotes[i : i + chunk_size])
    # Merge any tiny trailing remainder into the last real chunk
    if len(chunks) > periods:
        chunks[-2].extend(chunks[-1])
        chunks.pop()
    return chunks


def compute_sector_rotation(
    quotes_by_sector: dict[str, list[Quote]],
    periods: int = 2,
) -> list[dict]:
    """Identify sector rotation by comparing relative strength across periods.

    For each sector the full date range is divided into *periods* sub-ranges.
    The return for the latest period is compared to the return for the
    previous period, producing a ``momentum_change`` value.  Positive values
    indicate the sector is gaining relative strength; negative values
    indicate it is losing strength.

    Returns a list of dicts sorted by ``momentum_change`` descending
    (sectors gaining the most strength first).  Each dict contains:
    ``sector``, ``prior_return``, ``recent_return``, ``momentum_change``,
    and ``rotation_signal`` ("gaining", "losing", or "stable").
    """
    if not quotes_by_sector or periods < 2:
        return []

    results: list[dict] = []

    for sector, quotes in quotes_by_sector.items():
        if not quotes:
            continue

        # Aggregate all quotes for the sector, sorted by date
        all_quotes = sorted(quotes, key=lambda q: q.date)

        # Group by symbol to compute per-period returns, then average
        by_symbol: dict[str, list[Quote]] = defaultdict(list)
        for q in all_quotes:
            by_symbol[q.symbol].append(q)

        prior_returns: list[float] = []
        recent_returns: list[float] = []

        for sym, sym_quotes in by_symbol.items():
            sym_quotes.sort(key=lambda q: q.date)
            chunks = _split_into_periods(sym_quotes, periods)
            if len(chunks) < 2:
                continue
            prior_returns.append(_period_return(chunks[-2]))
            recent_returns.append(_period_return(chunks[-1]))

        if not prior_returns:
            continue

        avg_prior = sum(prior_returns) / len(prior_returns)
        avg_recent = sum(recent_returns) / len(recent_returns)
        momentum_change = avg_recent - avg_prior

        # Classify rotation signal
        threshold = 0.01  # 1 percentage point
        if momentum_change > threshold:
            signal = "gaining"
        elif momentum_change < -threshold:
            signal = "losing"
        else:
            signal = "stable"

        results.append(
            {
                "sector": sector,
                "prior_return": round(avg_prior, 6),
                "recent_return": round(avg_recent, 6),
                "momentum_change": round(momentum_change, 6),
                "rotation_signal": signal,
            }
        )

    results.sort(key=lambda r: r["momentum_change"], reverse=True)
    return results


def compute_sector_correlation(
    quotes_by_sector: dict[str, list],
) -> dict:
    """Compute pairwise correlation of sector average daily returns.

    Returns dict with sectors, matrix, most_correlated_pair, least_correlated_pair.
    """
    if len(quotes_by_sector) < 2:
        sectors = list(quotes_by_sector.keys())
        return {
            "sectors": sectors,
            "matrix": [[1.0]] if sectors else [],
            "most_correlated_pair": None,
            "least_correlated_pair": None,
        }

    # Compute daily returns per sector (average across symbols)
    sector_returns: dict[str, list[float]] = {}
    for sector, quotes in quotes_by_sector.items():
        sorted_q = sorted(quotes, key=lambda q: q.date)
        if len(sorted_q) < 2:
            continue
        returns = []
        for i in range(1, len(sorted_q)):
            prev_close = sorted_q[i - 1].close
            if prev_close != 0:
                returns.append((sorted_q[i].close - prev_close) / prev_close)
        if returns:
            sector_returns[sector] = returns

    sectors = sorted(sector_returns.keys())
    if len(sectors) < 2:
        return {
            "sectors": sectors,
            "matrix": [[1.0]] if sectors else [],
            "most_correlated_pair": None,
            "least_correlated_pair": None,
        }

    # Align lengths (use minimum)
    min_len = min(len(sector_returns[s]) for s in sectors)
    matrix_data = [sector_returns[s][:min_len] for s in sectors]

    corr = np.corrcoef(matrix_data)
    corr = np.nan_to_num(corr, nan=0.0)
    corr_list = corr.tolist()

    # Find most/least correlated pairs
    best_pair = None
    worst_pair = None
    best_corr = -2.0
    worst_corr = 2.0

    for i in range(len(sectors)):
        for j in range(i + 1, len(sectors)):
            c = corr_list[i][j]
            if c > best_corr:
                best_corr = c
                best_pair = (sectors[i], sectors[j], round(c, 6))
            if c < worst_corr:
                worst_corr = c
                worst_pair = (sectors[i], sectors[j], round(c, 6))

    return {
        "sectors": sectors,
        "matrix": corr_list,
        "most_correlated_pair": best_pair,
        "least_correlated_pair": worst_pair,
    }
