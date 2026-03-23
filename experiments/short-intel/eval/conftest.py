import pytest
from datetime import date, timedelta

from agora.schemas import ShortData, Transaction


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Emit [METRIC] test_pass_rate for the experiment harness."""
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed
    rate = passed / total if total > 0 else 0.0
    print(f"\n[METRIC] test_pass_rate={rate:.4f}")


def _make_short(day_offset, value, data_type="short_volume", symbol="GME"):
    return ShortData(
        symbol=symbol,
        date=date(2024, 1, 1) + timedelta(days=day_offset),
        data_type=data_type,
        value=value,
        source="TEST",
    )


def _make_tx(day_offset, action, amount, entity="CEO"):
    return Transaction(
        date=date(2024, 1, 1) + timedelta(days=day_offset),
        entity=entity,
        action=action,
        amount=amount,
    )


@pytest.fixture
def rising_short_volume():
    """Short volume increasing over 5 days."""
    return [_make_short(i, 1000 + i * 200, "short_volume") for i in range(5)]


@pytest.fixture
def flat_short_volume():
    """Short volume flat over 5 days."""
    return [_make_short(i, 1000, "short_volume") for i in range(5)]


@pytest.fixture
def declining_short_interest():
    """Short interest declining over 5 days."""
    return [_make_short(i, 5000 - i * 500, "short_interest") for i in range(5)]


@pytest.fixture
def rising_short_interest():
    """Short interest rising over 5 days."""
    return [_make_short(i, 5000 + i * 500, "short_interest") for i in range(5)]


@pytest.fixture
def declining_ftd():
    """FTD counts declining over 5 days."""
    return [_make_short(i, 800 - i * 150, "ftd") for i in range(5)]


@pytest.fixture
def rising_ftd():
    """FTD counts rising over 5 days."""
    return [_make_short(i, 100 + i * 150, "ftd") for i in range(5)]


@pytest.fixture
def insider_buys():
    """Net insider buying activity."""
    return [
        _make_tx(1, "Purchase", 10000),
        _make_tx(3, "Buy", 5000),
    ]


@pytest.fixture
def insider_sells():
    """Net insider selling activity."""
    return [
        _make_tx(1, "Sale", 20000),
        _make_tx(3, "Sell", 15000),
    ]


@pytest.fixture
def insider_mixed_net_buy():
    """Mixed insider activity, net buying."""
    return [
        _make_tx(1, "Purchase", 10000),
        _make_tx(2, "Sale", 3000),
        _make_tx(3, "Buy", 8000),
    ]
