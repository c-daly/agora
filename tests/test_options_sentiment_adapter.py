"""Tests for the options_sentiment_adapter module."""

from __future__ import annotations

from datetime import date

import pytest

from agora.adapters.options_sentiment_adapter import (
    IV_SKEW,
    PC_OI_RATIO,
    PC_VOLUME_RATIO,
    compute_options_sentiment,
)
from agora.schemas import OptionsSnapshot, ShortData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TODAY = date(2026, 3, 25)
EXPIRY = date(2026, 4, 17)


def _snap(
    *,
    symbol: str = "AAPL",
    snap_date: date = TODAY,
    expiry: date = EXPIRY,
    strike: float = 150.0,
    opt_type: str = "call",
    volume: int = 1000,
    open_interest: int = 5000,
    implied_vol: float | None = 0.30,
) -> OptionsSnapshot:
    return OptionsSnapshot(
        symbol=symbol,
        date=snap_date,
        expiry=expiry,
        strike=strike,
        type=opt_type,
        volume=volume,
        open_interest=open_interest,
        implied_vol=implied_vol,
    )


@pytest.fixture()
def basic_chain() -> list[OptionsSnapshot]:
    """Balanced chain: one call and one put at the same strike."""
    return [
        _snap(opt_type="call", volume=1000, open_interest=5000, implied_vol=0.30),
        _snap(opt_type="put", volume=800, open_interest=3000, implied_vol=0.35),
    ]


@pytest.fixture()
def multi_strike_chain() -> list[OptionsSnapshot]:
    """Multiple strikes with IV data for skew computation."""
    return [
        _snap(opt_type="call", strike=140.0, volume=500, open_interest=2000, implied_vol=0.28),
        _snap(opt_type="put", strike=140.0, volume=300, open_interest=1500, implied_vol=0.38),
        _snap(opt_type="call", strike=150.0, volume=600, open_interest=3000, implied_vol=0.30),
        _snap(opt_type="put", strike=150.0, volume=400, open_interest=2000, implied_vol=0.40),
    ]


# ---------------------------------------------------------------------------
# Tests: empty / trivial inputs
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_list_returns_empty(self):
        assert compute_options_sentiment([]) == []


# ---------------------------------------------------------------------------
# Tests: basic chain
# ---------------------------------------------------------------------------


class TestBasicChain:
    """Single symbol, single date, one call + one put at the same strike."""

    def test_returns_three_metrics(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        assert len(results) == 3

    def test_all_have_correct_source(self, basic_chain):
        for sd in compute_options_sentiment(basic_chain):
            assert sd.source == "Derived"

    def test_all_have_correct_symbol_and_date(self, basic_chain):
        for sd in compute_options_sentiment(basic_chain):
            assert sd.symbol == "AAPL"
            assert sd.date == TODAY

    def test_put_call_volume_ratio(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        vol_ratio = [r for r in results if r.data_type == PC_VOLUME_RATIO][0]
        # 800 / 1000 = 0.8
        assert vol_ratio.value == pytest.approx(0.8)
        assert vol_ratio.total_for_ratio == pytest.approx(1800.0)

    def test_put_call_oi_ratio(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        oi_ratio = [r for r in results if r.data_type == PC_OI_RATIO][0]
        # 3000 / 5000 = 0.6
        assert oi_ratio.value == pytest.approx(0.6)
        assert oi_ratio.total_for_ratio == pytest.approx(8000.0)

    def test_iv_skew(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        skew = [r for r in results if r.data_type == IV_SKEW][0]
        # 0.35 - 0.30 = 0.05
        assert skew.value == pytest.approx(0.05)
        assert skew.total_for_ratio == pytest.approx(1.0)  # 1 matched strike


# ---------------------------------------------------------------------------
# Tests: multi-strike chain
# ---------------------------------------------------------------------------


class TestMultiStrikeChain:
    """Two strikes at the same expiry."""

    def test_put_call_volume_ratio(self, multi_strike_chain):
        results = compute_options_sentiment(multi_strike_chain)
        vol_ratio = [r for r in results if r.data_type == PC_VOLUME_RATIO][0]
        # puts: 300+400=700, calls: 500+600=1100 => 700/1100
        assert vol_ratio.value == pytest.approx(700.0 / 1100.0, abs=1e-5)

    def test_put_call_oi_ratio(self, multi_strike_chain):
        results = compute_options_sentiment(multi_strike_chain)
        oi_ratio = [r for r in results if r.data_type == PC_OI_RATIO][0]
        # puts: 1500+2000=3500, calls: 2000+3000=5000 => 3500/5000=0.7
        assert oi_ratio.value == pytest.approx(0.7)

    def test_iv_skew_averaged_across_strikes(self, multi_strike_chain):
        results = compute_options_sentiment(multi_strike_chain)
        skew = [r for r in results if r.data_type == IV_SKEW][0]
        # strike 140: 0.38 - 0.28 = 0.10
        # strike 150: 0.40 - 0.30 = 0.10
        # mean skew = 0.10
        assert skew.value == pytest.approx(0.1)
        assert skew.total_for_ratio == pytest.approx(2.0)  # 2 matched strikes


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_only_calls_no_puts(self):
        """When there are no puts, ratios should be 0 and skew 0."""
        options = [
            _snap(opt_type="call", volume=500, open_interest=2000, implied_vol=0.30),
        ]
        results = compute_options_sentiment(options)
        assert len(results) == 3
        vol_ratio = [r for r in results if r.data_type == PC_VOLUME_RATIO][0]
        assert vol_ratio.value == pytest.approx(0.0)

        oi_ratio = [r for r in results if r.data_type == PC_OI_RATIO][0]
        assert oi_ratio.value == pytest.approx(0.0)

        skew = [r for r in results if r.data_type == IV_SKEW][0]
        assert skew.value == pytest.approx(0.0)
        assert skew.total_for_ratio is None  # no matched strikes

    def test_only_puts_no_calls(self):
        """When there are no calls, volume/OI ratios should be 0 (division guarded)."""
        options = [
            _snap(opt_type="put", volume=800, open_interest=3000, implied_vol=0.35),
        ]
        results = compute_options_sentiment(options)
        vol_ratio = [r for r in results if r.data_type == PC_VOLUME_RATIO][0]
        assert vol_ratio.value == pytest.approx(0.0)

        oi_ratio = [r for r in results if r.data_type == PC_OI_RATIO][0]
        assert oi_ratio.value == pytest.approx(0.0)

    def test_no_implied_vol_gives_zero_skew(self):
        """Contracts missing implied_vol should still produce a valid iv_skew of 0."""
        options = [
            _snap(opt_type="call", implied_vol=None),
            _snap(opt_type="put", implied_vol=None),
        ]
        results = compute_options_sentiment(options)
        skew = [r for r in results if r.data_type == IV_SKEW][0]
        assert skew.value == pytest.approx(0.0)
        assert skew.total_for_ratio is None

    def test_different_strike_no_iv_match(self):
        """Put and call at different strikes should not match for IV skew."""
        options = [
            _snap(opt_type="call", strike=150.0, implied_vol=0.30),
            _snap(opt_type="put", strike=140.0, implied_vol=0.35),
        ]
        results = compute_options_sentiment(options)
        skew = [r for r in results if r.data_type == IV_SKEW][0]
        assert skew.value == pytest.approx(0.0)
        assert skew.total_for_ratio is None

    def test_zero_volume_total_for_ratio_is_none(self):
        """If both put and call volume are 0, total_for_ratio should be None."""
        options = [
            _snap(opt_type="call", volume=0, open_interest=100),
            _snap(opt_type="put", volume=0, open_interest=50),
        ]
        results = compute_options_sentiment(options)
        vol_ratio = [r for r in results if r.data_type == PC_VOLUME_RATIO][0]
        assert vol_ratio.total_for_ratio is None


# ---------------------------------------------------------------------------
# Tests: multiple symbols / dates
# ---------------------------------------------------------------------------


class TestMultipleGroups:
    def test_two_symbols_produce_six_metrics(self):
        """Each (symbol, date) group produces 3 metrics."""
        options = [
            _snap(symbol="AAPL", opt_type="call"),
            _snap(symbol="AAPL", opt_type="put"),
            _snap(symbol="MSFT", opt_type="call"),
            _snap(symbol="MSFT", opt_type="put"),
        ]
        results = compute_options_sentiment(options)
        assert len(results) == 6
        aapl = [r for r in results if r.symbol == "AAPL"]
        msft = [r for r in results if r.symbol == "MSFT"]
        assert len(aapl) == 3
        assert len(msft) == 3

    def test_two_dates_produce_six_metrics(self):
        """Same symbol on two dates produces 6 metrics."""
        d1 = date(2026, 3, 24)
        d2 = date(2026, 3, 25)
        options = [
            _snap(snap_date=d1, opt_type="call"),
            _snap(snap_date=d1, opt_type="put"),
            _snap(snap_date=d2, opt_type="call"),
            _snap(snap_date=d2, opt_type="put"),
        ]
        results = compute_options_sentiment(options)
        assert len(results) == 6


# ---------------------------------------------------------------------------
# Tests: output types
# ---------------------------------------------------------------------------


class TestOutputTypes:
    def test_returns_short_data_instances(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        for r in results:
            assert isinstance(r, ShortData)

    def test_data_types_are_expected(self, basic_chain):
        results = compute_options_sentiment(basic_chain)
        types = {r.data_type for r in results}
        assert types == {PC_VOLUME_RATIO, PC_OI_RATIO, IV_SKEW}
