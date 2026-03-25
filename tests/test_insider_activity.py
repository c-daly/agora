"""Tests for the insider_activity analysis module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.analysis.insider_activity import (
    _build_sector_breakdown,
    _detect_unusual_clusters,
    _empty_result,
    analyze_insider_activity,
)
from agora.schemas import Transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tx(
    day: int,
    entity: str = "Jane Doe",
    action: str = "Buy",
    amount: float = 10_000.0,
    symbol: str = "AAPL",
    month: int = 3,
    year: int = 2026,
) -> Transaction:
    """Shorthand helper to build a single insider Transaction."""
    return Transaction(
        date=date(year, month, day),
        entity=entity,
        action=action,
        amount=amount,
        context={"symbol": symbol},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mixed_trades() -> list[Transaction]:
    """Trades from multiple insiders across companies."""
    return [
        _tx(1, entity="Alice CEO", action="Buy", amount=50_000, symbol="AAPL"),
        _tx(2, entity="Alice CEO", action="Buy", amount=30_000, symbol="AAPL"),
        _tx(3, entity="Bob CFO", action="Sell", amount=20_000, symbol="AAPL"),
        _tx(4, entity="Bob CFO", action="Sell", amount=40_000, symbol="MSFT"),
        _tx(5, entity="Carol VP", action="Buy", amount=15_000, symbol="MSFT"),
        _tx(6, entity="Carol VP", action="Buy", amount=25_000, symbol="TSLA"),
    ]


@pytest.fixture()
def buy_only_trades() -> list[Transaction]:
    """Only buys -- buy_sell_ratio should be None."""
    return [
        _tx(1, action="Buy", amount=1_000),
        _tx(2, action="Buy", amount=2_000),
    ]


@pytest.fixture()
def cluster_trades() -> list[Transaction]:
    """Many trades on one day, spread across others to trigger >3x avg."""
    # 4 days: days 1,2,3 get 1 trade each (3 trades), day 10 gets 10 trades.
    # Total = 13, avg = 13/4 = 3.25, threshold = 9.75. Day 10 has 10 > 9.75.
    trades = [
        _tx(1, entity="A"),
        _tx(2, entity="B"),
        _tx(3, entity="C"),
    ]
    for i in range(10):
        trades.append(_tx(10, entity=f"Insider{i}"))
    return trades


@pytest.fixture()
def sector_map() -> dict[str, str]:
    return {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "TSLA": "Automotive",
    }


# ---------------------------------------------------------------------------
# analyze_insider_activity
# ---------------------------------------------------------------------------


class TestAnalyzeInsiderActivity:
    def test_empty_list(self) -> None:
        result = analyze_insider_activity([])
        assert result["total_trades"] == 0
        assert result["buy_sell_ratio"] is None
        assert result["top_insiders"] == []
        assert result["by_company"] == {}
        assert result["unusual_clusters"] == []
        assert "by_sector" not in result

    def test_empty_list_with_sector_map(self) -> None:
        result = analyze_insider_activity([], sector_map={"AAPL": "Tech"})
        assert result["by_sector"] == {}

    def test_total_trades(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        assert result["total_trades"] == 6

    def test_buy_sell_ratio(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        # 4 buys / 2 sells = 2.0
        assert result["buy_sell_ratio"] == 2.0

    def test_buy_sell_ratio_no_sells(
        self, buy_only_trades: list[Transaction]
    ) -> None:
        result = analyze_insider_activity(buy_only_trades)
        assert result["buy_sell_ratio"] is None

    def test_top_insiders(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        top = result["top_insiders"]
        assert len(top) == 3
        entities = {t["entity"] for t in top}
        assert entities == {"Alice CEO", "Bob CFO", "Carol VP"}
        for t in top:
            assert t["trade_count"] == 2

    def test_top_insiders_amounts(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        top = result["top_insiders"]
        by_entity = {t["entity"]: t["total_amount"] for t in top}
        assert by_entity["Alice CEO"] == 80_000.0
        assert by_entity["Bob CFO"] == 60_000.0
        assert by_entity["Carol VP"] == 40_000.0

    def test_by_company(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        bc = result["by_company"]
        assert set(bc.keys()) == {"AAPL", "MSFT", "TSLA"}
        # AAPL: 2 buys (50k+30k=80k), 1 sell (20k) -> net = 80k-20k = 60k
        assert bc["AAPL"] == {"buys": 2, "sells": 1, "net": 60_000.0}
        # MSFT: 1 buy (15k), 1 sell (40k) -> net = 15k-40k = -25k
        assert bc["MSFT"] == {"buys": 1, "sells": 1, "net": -25_000.0}
        # TSLA: 1 buy (25k), 0 sells -> net = 25k
        assert bc["TSLA"] == {"buys": 1, "sells": 0, "net": 25_000.0}

    def test_by_company_sorted_keys(self, mixed_trades: list[Transaction]) -> None:
        result = analyze_insider_activity(mixed_trades)
        keys = list(result["by_company"].keys())
        assert keys == sorted(keys)

    def test_no_sector_key_without_map(
        self, mixed_trades: list[Transaction]
    ) -> None:
        result = analyze_insider_activity(mixed_trades)
        assert "by_sector" not in result

    def test_by_sector(
        self,
        mixed_trades: list[Transaction],
        sector_map: dict[str, str],
    ) -> None:
        result = analyze_insider_activity(mixed_trades, sector_map=sector_map)
        bs = result["by_sector"]
        assert set(bs.keys()) == {"Technology", "Automotive"}
        # Technology: AAPL buys 2 (80k), AAPL sell 1 (20k), MSFT buy 1 (15k),
        #            MSFT sell 1 (40k)
        # buys=3, sells=2, net = 80k - 20k + 15k - 40k = 35k
        assert bs["Technology"] == {"buys": 3, "sells": 2, "net": 35_000.0}
        # Automotive: TSLA buy 1 (25k)
        assert bs["Automotive"] == {"buys": 1, "sells": 0, "net": 25_000.0}

    def test_unusual_clusters(
        self, cluster_trades: list[Transaction]
    ) -> None:
        result = analyze_insider_activity(cluster_trades)
        clusters = result["unusual_clusters"]
        assert len(clusters) == 1
        assert clusters[0]["date"] == "2026-03-10"
        assert clusters[0]["trade_count"] == 10

    def test_no_unusual_clusters_uniform(self) -> None:
        """Uniform distribution should not flag any day."""
        trades = [_tx(d, entity=f"E{d}") for d in range(1, 11)]
        result = analyze_insider_activity(trades)
        assert result["unusual_clusters"] == []

    def test_no_symbol_in_context(self) -> None:
        """Trades missing the symbol key should not appear in by_company."""
        trades = [
            Transaction(
                date=date(2026, 1, 1),
                entity="X",
                action="Buy",
                amount=100,
                context={},
            )
        ]
        result = analyze_insider_activity(trades)
        assert result["by_company"] == {}
        assert result["total_trades"] == 1

    def test_sector_map_missing_symbol(self) -> None:
        """Symbols not in sector_map are excluded from by_sector."""
        trades = [_tx(1, symbol="UNKNOWN")]
        result = analyze_insider_activity(
            trades, sector_map={"AAPL": "Tech"}
        )
        assert result["by_sector"] == {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestEmptyResult:
    def test_without_sector(self) -> None:
        result = _empty_result(include_sector=False)
        assert "by_sector" not in result
        assert result["total_trades"] == 0

    def test_with_sector(self) -> None:
        result = _empty_result(include_sector=True)
        assert result["by_sector"] == {}


class TestDetectUnusualClusters:
    def test_empty(self) -> None:
        from collections import defaultdict

        assert _detect_unusual_clusters(defaultdict(int)) == []

    def test_no_clusters_when_even(self) -> None:
        from collections import defaultdict

        tbd: defaultdict[date, int] = defaultdict(int)
        tbd[date(2026, 3, 1)] = 5
        tbd[date(2026, 3, 2)] = 5
        tbd[date(2026, 3, 3)] = 5
        assert _detect_unusual_clusters(tbd) == []

    def test_spike_detected(self) -> None:
        from collections import defaultdict

        tbd: defaultdict[date, int] = defaultdict(int)
        tbd[date(2026, 3, 1)] = 1
        tbd[date(2026, 3, 2)] = 1
        tbd[date(2026, 3, 3)] = 1
        tbd[date(2026, 3, 4)] = 20
        # avg = 23/4 = 5.75, 3x = 17.25, day 4 has 20 > 17.25
        clusters = _detect_unusual_clusters(tbd)
        assert len(clusters) == 1
        assert clusters[0]["date"] == "2026-03-04"
        assert clusters[0]["trade_count"] == 20
        assert clusters[0]["avg_daily"] == 5.75


class TestBuildSectorBreakdown:
    def test_basic(self) -> None:
        trades = [
            _tx(1, action="Buy", amount=100, symbol="AAPL"),
            _tx(2, action="Sell", amount=50, symbol="AAPL"),
        ]
        sm = {"AAPL": "Tech"}
        result = _build_sector_breakdown(trades, sm)
        assert result == {"Tech": {"buys": 1, "sells": 1, "net": 50.0}}

    def test_no_matching_symbols(self) -> None:
        trades = [_tx(1, symbol="ZZZ")]
        result = _build_sector_breakdown(trades, {"AAPL": "Tech"})
        assert result == {}
