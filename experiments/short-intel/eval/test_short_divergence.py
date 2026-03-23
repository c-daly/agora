"""Tests for short divergence analysis module.

Covers the Analysis checklist:
1.  shorts_rising_insiders_buying detected with rising volume + insider buys
2.  shorts_rising_insiders_buying not triggered with insider sells
3.  shorts_rising_ftd_declining detected with rising volume + declining FTDs
4.  shorts_rising_ftd_declining not triggered with rising FTDs
5.  short_interest_dropping_volume_high detected with declining SI + flat volume
6.  short_interest_dropping_volume_high not triggered with rising SI
7.  Each divergence dict has required keys
8.  Empty input returns empty list
9.  Single data point returns empty list (need 2+ for trend)
10. Mixed data_types handled correctly
11. Deterministic: same input produces same output
12. Severity levels are valid
"""

from datetime import date


from agora.analysis.short_divergence import detect_divergences
from agora.schemas import ShortData


VALID_SEVERITIES = {"low", "medium", "high"}
REQUIRED_KEYS = {"divergence_type", "description", "severity", "date_range", "details"}


# ---------------------------------------------------------------------------
# 1. shorts_rising_insiders_buying
# ---------------------------------------------------------------------------
class TestShortsRisingInsidersBuying:
    def test_detected_with_rising_volume_and_buys(self, rising_short_volume, insider_buys):
        result = detect_divergences(rising_short_volume, insider_buys)
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_insiders_buying"]
        assert len(matches) >= 1

    # 2. Not triggered with insider sells
    def test_not_triggered_with_sells(self, rising_short_volume, insider_sells):
        result = detect_divergences(rising_short_volume, insider_sells)
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_insiders_buying"]
        assert len(matches) == 0

    def test_not_triggered_with_flat_volume(self, flat_short_volume, insider_buys):
        result = detect_divergences(flat_short_volume, insider_buys)
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_insiders_buying"]
        assert len(matches) == 0

    def test_no_insider_trades(self, rising_short_volume):
        result = detect_divergences(rising_short_volume, [])
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_insiders_buying"]
        assert len(matches) == 0

    def test_with_mixed_insiders_net_buy(self, rising_short_volume, insider_mixed_net_buy):
        result = detect_divergences(rising_short_volume, insider_mixed_net_buy)
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_insiders_buying"]
        assert len(matches) >= 1


# ---------------------------------------------------------------------------
# 3. shorts_rising_ftd_declining
# ---------------------------------------------------------------------------
class TestShortsRisingFtdDeclining:
    def test_detected_with_rising_volume_declining_ftd(self, rising_short_volume, declining_ftd):
        data = rising_short_volume + declining_ftd
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_ftd_declining"]
        assert len(matches) >= 1

    # 4. Not triggered with rising FTDs
    def test_not_triggered_with_rising_ftd(self, rising_short_volume, rising_ftd):
        data = rising_short_volume + rising_ftd
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_ftd_declining"]
        assert len(matches) == 0

    def test_not_triggered_with_flat_volume(self, flat_short_volume, declining_ftd):
        data = flat_short_volume + declining_ftd
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "shorts_rising_ftd_declining"]
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# 5. short_interest_dropping_volume_high
# ---------------------------------------------------------------------------
class TestShortInterestDroppingVolumeHigh:
    def test_detected_with_declining_si_flat_volume(self, declining_short_interest, flat_short_volume):
        data = declining_short_interest + flat_short_volume
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "short_interest_dropping_volume_high"]
        assert len(matches) == 1

    def test_detected_with_declining_si_rising_volume(self, declining_short_interest, rising_short_volume):
        data = declining_short_interest + rising_short_volume
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "short_interest_dropping_volume_high"]
        assert len(matches) == 1

    # 6. Not triggered with rising SI
    def test_not_triggered_with_rising_si(self, rising_short_interest, flat_short_volume):
        data = rising_short_interest + flat_short_volume
        result = detect_divergences(data, [])
        matches = [d for d in result if d["divergence_type"] == "short_interest_dropping_volume_high"]
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# 7. Divergence dict structure
# ---------------------------------------------------------------------------
class TestDivergenceDictStructure:
    def test_has_required_keys(self, rising_short_volume, insider_buys):
        result = detect_divergences(rising_short_volume, insider_buys)
        assert len(result) > 0
        for d in result:
            assert isinstance(d, dict)
            assert REQUIRED_KEYS.issubset(d.keys())

    def test_date_range_has_start_and_end(self, rising_short_volume, insider_buys):
        result = detect_divergences(rising_short_volume, insider_buys)
        for d in result:
            assert "start" in d["date_range"]
            assert "end" in d["date_range"]
            assert isinstance(d["date_range"]["start"], date)
            assert isinstance(d["date_range"]["end"], date)

    # 12. Severity levels are valid
    def test_severity_is_valid(self, rising_short_volume, insider_buys):
        result = detect_divergences(rising_short_volume, insider_buys)
        for d in result:
            assert d["severity"] in VALID_SEVERITIES


# ---------------------------------------------------------------------------
# 8. Empty input
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_short_data(self):
        result = detect_divergences([], [])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_empty_short_data_with_trades(self, insider_buys):
        result = detect_divergences([], insider_buys)
        assert len(result) == 0

    # 9. Single data point
    def test_single_data_point(self, insider_buys):
        single = [ShortData(
            symbol="GME", date=date(2024, 1, 1),
            data_type="short_volume", value=1000, source="TEST",
        )]
        result = detect_divergences(single, insider_buys)
        assert len(result) == 0

    # 10. Mixed data_types
    def test_mixed_data_types(
        self, rising_short_volume, declining_short_interest, declining_ftd, insider_buys
    ):
        data = rising_short_volume + declining_short_interest + declining_ftd
        result = detect_divergences(data, insider_buys)
        types_found = {d["divergence_type"] for d in result}
        # Should find at least shorts_rising_insiders_buying (volume rising + buys)
        # and shorts_rising_ftd_declining (volume rising + ftd declining)
        # and short_interest_dropping_volume_high (SI declining + volume rising)
        assert "shorts_rising_insiders_buying" in types_found
        assert "shorts_rising_ftd_declining" in types_found
        assert "short_interest_dropping_volume_high" in types_found


# ---------------------------------------------------------------------------
# 11. Deterministic
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_same_input_same_output(self, rising_short_volume, insider_buys):
        r1 = detect_divergences(rising_short_volume, insider_buys)
        r2 = detect_divergences(rising_short_volume, insider_buys)
        assert r1 == r2

    def test_empty_deterministic(self):
        r1 = detect_divergences([], [])
        r2 = detect_divergences([], [])
        assert r1 == r2
