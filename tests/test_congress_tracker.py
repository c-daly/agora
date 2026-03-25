"""Tests for the congress_tracker analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.congress_tracker import (
    _coerce_date,
    _empty_stats,
    analyze_congress_trades,
    detect_timing_anomalies,
)
from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tx(
    day: int,
    entity: str = "Jane Doe",
    action: str = "Buy",
    amount: float = 8_000.0,
    symbol: str = "AAPL",
    party: str = "Democrat",
    month: int = 3,
    year: int = 2026,
) -> Transaction:
    """Shorthand helper to build a single congressional Transaction."""
    return Transaction(
        date=date(year, month, day),
        entity=entity,
        action=action,
        amount=amount,
        context={"symbol": symbol, "party": party},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mixed_trades() -> list[Transaction]:
    """A small set of trades from multiple members, parties, and symbols."""
    return [
        _tx(1, entity="Alice Smith", action="Buy", amount=10_000, symbol="AAPL", party="Democrat"),
        _tx(2, entity="Alice Smith", action="Buy", amount=20_000, symbol="MSFT", party="Democrat"),
        _tx(3, entity="Bob Jones", action="Sell", amount=15_000, symbol="AAPL", party="Republican"),
        _tx(4, entity="Bob Jones", action="Sell", amount=25_000, symbol="TSLA", party="Republican"),
        _tx(5, entity="Carol White", action="Buy", amount=30_000, symbol="AAPL", party="Democrat"),
        _tx(6, entity="Carol White", action="Buy", amount=5_000, symbol="MSFT", party="Democrat"),
    ]


@pytest.fixture()
def buy_only_trades() -> list[Transaction]:
    """Trades with no sells -- buy_sell_ratio should be None."""
    return [
        _tx(1, action="Buy", amount=1_000),
        _tx(2, action="Buy", amount=2_000),
    ]


@pytest.fixture()
def clustered_trades() -> list[Transaction]:
    """Four trades on the same day to trigger cluster detection."""
    return [
        _tx(10, entity="Alice Smith"),
        _tx(10, entity="Bob Jones"),
        _tx(10, entity="Carol White"),
        _tx(10, entity="Dave Brown"),
        _tx(15, entity="Alice Smith"),  # only 1 trade on day 15
    ]


@pytest.fixture()
def pre_event_trades() -> list[Transaction]:
    """Trades clustered in the 7-day window before March 20."""
    return [
        _tx(14, entity="Alice Smith"),
        _tx(15, entity="Bob Jones"),
        _tx(16, entity="Carol White"),
        _tx(25, entity="Dave Brown"),  # outside window
    ]


# ---------------------------------------------------------------------------
# analyze_congress_trades
# ---------------------------------------------------------------------------


class TestAnalyzeCongressTrades:
    def test_empty_list(self) -> None:
        result = analyze_congress_trades([])
        assert result == _empty_stats()

    def test_total_trades_and_volume(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(mixed_trades)
        assert result["total_trades"] == 6
        assert result["total_volume"] == 105_000.0

    def test_buy_sell_ratio(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(mixed_trades)
        # 4 buys / 2 sells = 2.0
        assert result["buy_sell_ratio"] == 2.0

    def test_buy_sell_ratio_no_sells(self, buy_only_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(buy_only_trades)
        assert result["buy_sell_ratio"] is None

    def test_top_traders(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(mixed_trades)
        top = result["top_traders"]
        # Everyone has 2 trades, so we just check the count and presence
        assert len(top) == 3
        entities = {t["entity"] for t in top}
        assert entities == {"Alice Smith", "Bob Jones", "Carol White"}
        for t in top:
            assert t["trade_count"] == 2

    def test_most_traded_symbols(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(mixed_trades)
        symbols = result["most_traded_symbols"]
        # AAPL: 3 trades, MSFT: 2 trades, TSLA: 1 trade
        assert symbols[0]["symbol"] == "AAPL"
        assert symbols[0]["trade_count"] == 3
        assert symbols[1]["symbol"] == "MSFT"
        assert symbols[1]["trade_count"] == 2
        assert symbols[2]["symbol"] == "TSLA"
        assert symbols[2]["trade_count"] == 1

    def test_party_breakdown(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_congress_trades(mixed_trades)
        party = result["party_breakdown"]
        assert set(party.keys()) == {"Democrat", "Republican"}
        assert party["Democrat"]["trade_count"] == 4
        assert party["Democrat"]["buy_count"] == 4
        assert party["Democrat"]["sell_count"] == 0
        assert party["Republican"]["trade_count"] == 2
        assert party["Republican"]["buy_count"] == 0
        assert party["Republican"]["sell_count"] == 2

    def test_no_symbol_in_context(self) -> None:
        """Trades missing the symbol key should not appear in most_traded."""
        trades = [
            Transaction(
                date=date(2026, 1, 1),
                entity="X",
                action="Buy",
                amount=100,
                context={"party": "Independent"},
            )
        ]
        result = analyze_congress_trades(trades)
        assert result["most_traded_symbols"] == []
        assert result["party_breakdown"]["Independent"]["trade_count"] == 1


# ---------------------------------------------------------------------------
# detect_timing_anomalies -- event-based
# ---------------------------------------------------------------------------


class TestEventBasedAnomalies:
    def test_empty_trades(self) -> None:
        assert detect_timing_anomalies([], market_events=[{"date": "2026-03-20", "description": "x"}]) == []

    def test_cluster_before_event(
        self, pre_event_trades: list[Transaction]
    ) -> None:
        events = [{"date": "2026-03-20", "description": "FDA ruling"}]
        anomalies = detect_timing_anomalies(pre_event_trades, market_events=events)
        assert len(anomalies) == 1
        a = anomalies[0]
        assert a["event_date"] == "2026-03-20"
        assert a["description"] == "FDA ruling"
        assert a["trades_in_window"] == 3
        assert "Alice Smith" in a["traders"]

    def test_no_anomaly_when_too_few_trades(self) -> None:
        trades = [_tx(14), _tx(15)]  # only 2 trades in window
        events = [{"date": "2026-03-20", "description": "earnings"}]
        assert detect_timing_anomalies(trades, market_events=events) == []

    def test_date_object_in_event(self, pre_event_trades: list[Transaction]) -> None:
        """Events may supply a date object instead of an ISO string."""
        events = [{"date": date(2026, 3, 20), "description": "rate decision"}]
        anomalies = detect_timing_anomalies(pre_event_trades, market_events=events)
        assert len(anomalies) == 1

    def test_multiple_events(self) -> None:
        trades = [
            _tx(3, entity="A"), _tx(4, entity="B"), _tx(5, entity="C"),
            _tx(23, entity="D"), _tx(24, entity="E"), _tx(25, entity="F"),
        ]
        events = [
            {"date": "2026-03-10", "description": "event1"},
            {"date": "2026-03-28", "description": "event2"},
        ]
        anomalies = detect_timing_anomalies(trades, market_events=events)
        assert len(anomalies) == 2
        assert anomalies[0]["description"] == "event1"
        assert anomalies[1]["description"] == "event2"


# ---------------------------------------------------------------------------
# detect_timing_anomalies -- cluster-based (no events)
# ---------------------------------------------------------------------------


class TestClusterBasedAnomalies:
    def test_detects_high_volume_day(
        self, clustered_trades: list[Transaction]
    ) -> None:
        anomalies = detect_timing_anomalies(clustered_trades)
        assert len(anomalies) == 1
        a = anomalies[0]
        assert a["event_date"] == "2026-03-10"
        assert a["trades_in_window"] == 4
        assert len(a["traders"]) == 4

    def test_no_cluster(self) -> None:
        trades = [_tx(1), _tx(2)]  # only 1 per day
        assert detect_timing_anomalies(trades) == []

    def test_cluster_traders_sorted(self, clustered_trades: list[Transaction]) -> None:
        anomalies = detect_timing_anomalies(clustered_trades)
        traders = anomalies[0]["traders"]
        assert traders == sorted(traders)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestCoerceDate:
    def test_iso_string(self) -> None:
        assert _coerce_date("2026-03-15") == date(2026, 3, 15)

    def test_datetime_string(self) -> None:
        assert _coerce_date("2026-03-15T12:30:00") == date(2026, 3, 15)

    def test_date_object(self) -> None:
        d = date(2026, 3, 15)
        assert _coerce_date(d) is d


class TestEmptyStats:
    def test_shape(self) -> None:
        result = _empty_stats()
        assert result["total_trades"] == 0
        assert result["total_volume"] == 0.0
        assert result["buy_sell_ratio"] is None
        assert result["top_traders"] == []
        assert result["most_traded_symbols"] == []
        assert result["party_breakdown"] == {}
