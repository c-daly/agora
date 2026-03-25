"""Tests for the yahoo_options_adapter module."""

from __future__ import annotations

from collections import namedtuple
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agora.adapters.yahoo_options_adapter import fetch_options
from agora.schemas import OptionsSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OptionChain = namedtuple("OptionChain", ["calls", "puts"])


def _make_chain_df(strike, volume, oi, iv, bid, ask):
    """Build a single-row DataFrame that mimics a yfinance option chain."""
    return pd.DataFrame(
        [
            {
                "strike": strike,
                "volume": volume,
                "openInterest": oi,
                "impliedVolatility": iv,
                "bid": bid,
                "ask": ask,
            }
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFetchOptionsCallsAndPuts:
    """fetch_options returns both calls and puts as OptionsSnapshot objects."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_returns_calls_and_puts(self, mock_yf):
        calls_df = _make_chain_df(150.0, 1000, 5000, 0.35, 5.10, 5.30)
        puts_df = _make_chain_df(140.0, 800, 3000, 0.40, 2.50, 2.70)
        chain = OptionChain(calls=calls_df, puts=puts_df)

        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17",)
        mock_ticker.option_chain.return_value = chain
        mock_yf.Ticker.return_value = mock_ticker

        with patch(
            "agora.adapters.yahoo_options_adapter.date",
            wraps=date,
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 25)
            mock_date.fromisoformat = date.fromisoformat
            results = fetch_options("AAPL")

        assert len(results) == 2
        assert all(isinstance(r, OptionsSnapshot) for r in results)

        call_snap = [r for r in results if r.type == "call"][0]
        assert call_snap.symbol == "AAPL"
        assert call_snap.date == date(2026, 3, 25)
        assert call_snap.expiry == date(2026, 4, 17)
        assert call_snap.strike == 150.0
        assert call_snap.volume == 1000
        assert call_snap.open_interest == 5000
        assert call_snap.implied_vol == pytest.approx(0.35)
        assert call_snap.bid == pytest.approx(5.10)
        assert call_snap.ask == pytest.approx(5.30)

        put_snap = [r for r in results if r.type == "put"][0]
        assert put_snap.strike == 140.0
        assert put_snap.volume == 800
        assert put_snap.open_interest == 3000


class TestFetchOptionsWithExpiry:
    """When expiry is specified, only that expiry is fetched."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_filters_to_requested_expiry(self, mock_yf):
        calls_df = _make_chain_df(200.0, 500, 2000, 0.25, 3.00, 3.20)
        chain = OptionChain(calls=calls_df, puts=pd.DataFrame())

        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17", "2026-05-15")
        mock_ticker.option_chain.return_value = chain
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("MSFT", expiry=date(2026, 4, 17))

        mock_ticker.option_chain.assert_called_once_with("2026-04-17")
        assert len(results) == 1
        assert results[0].expiry == date(2026, 4, 17)

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_unavailable_expiry_returns_empty(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17",)
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("MSFT", expiry=date(2099, 1, 1))

        assert results == []
        mock_ticker.option_chain.assert_not_called()


class TestFetchOptionsNoOptions:
    """Tickers with no options return an empty list."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_no_options_available(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = ()
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("NOOPT")

        assert results == []

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_none_options(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = None
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("NOOPT")

        assert results == []


class TestFetchOptionsErrorHandling:
    """Graceful handling of errors from yfinance."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_ticker_exception_returns_empty(self, mock_yf):
        mock_yf.Ticker.side_effect = Exception("network error")

        results = fetch_options("FAIL")

        assert results == []

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_chain_exception_skips_expiry(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17", "2026-05-15")

        good_chain = OptionChain(
            calls=_make_chain_df(150.0, 100, 500, 0.30, 1.0, 1.5),
            puts=pd.DataFrame(),
        )
        mock_ticker.option_chain.side_effect = [
            Exception("bad chain"),
            good_chain,
        ]
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("MIXED")

        assert len(results) == 1
        assert results[0].expiry == date(2026, 5, 15)


class TestFetchOptionsMultipleExpiries:
    """Without expiry filter, all available expiries are fetched."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_fetches_all_expiries(self, mock_yf):
        chain1 = OptionChain(
            calls=_make_chain_df(100.0, 10, 50, 0.20, 1.0, 1.1),
            puts=pd.DataFrame(),
        )
        chain2 = OptionChain(
            calls=_make_chain_df(110.0, 20, 60, 0.22, 1.2, 1.3),
            puts=pd.DataFrame(),
        )

        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17", "2026-05-15")
        mock_ticker.option_chain.side_effect = [chain1, chain2]
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("SPY")

        assert len(results) == 2
        assert results[0].expiry == date(2026, 4, 17)
        assert results[1].expiry == date(2026, 5, 15)


class TestFetchOptionsSymbolNormalization:
    """Symbol is normalized to uppercase."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_symbol_uppercased(self, mock_yf):
        chain = OptionChain(
            calls=_make_chain_df(50.0, 10, 50, 0.20, 1.0, 1.1),
            puts=pd.DataFrame(),
        )
        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17",)
        mock_ticker.option_chain.return_value = chain
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("aapl")

        assert results[0].symbol == "AAPL"


class TestFetchOptionsNullFields:
    """Missing optional fields are handled as None / 0."""

    @patch("agora.adapters.yahoo_options_adapter.yf", create=True)
    def test_null_volume_and_oi(self, mock_yf):
        df = pd.DataFrame(
            [
                {
                    "strike": 100.0,
                    "volume": None,
                    "openInterest": None,
                    "impliedVolatility": None,
                    "bid": None,
                    "ask": None,
                }
            ]
        )
        chain = OptionChain(calls=df, puts=pd.DataFrame())
        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-04-17",)
        mock_ticker.option_chain.return_value = chain
        mock_yf.Ticker.return_value = mock_ticker

        results = fetch_options("TEST")

        assert len(results) == 1
        assert results[0].volume == 0
        assert results[0].open_interest == 0
        assert results[0].implied_vol is None
        assert results[0].bid is None
        assert results[0].ask is None
