"""Shared fixtures and metric emission for api_routes eval tests."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agora.schemas import ShortData, TimeSeries, TimeSeriesMetadata


# ---------------------------------------------------------------------------
# Fake data builders
# ---------------------------------------------------------------------------

def _make_yield_series() -> list[TimeSeries]:
    """Return a small fake yield dataset covering two maturities and two dates."""
    entries = []
    for d in [date(2024, 1, 2), date(2024, 1, 3)]:
        for maturity, value in [("2yr", 4.25), ("10yr", 3.95)]:
            entries.append(
                TimeSeries(
                    date=d,
                    value=value,
                    metadata=TimeSeriesMetadata(
                        source="TREASURY",
                        unit=maturity,
                        frequency="Daily",
                    ),
                )
            )
    return entries


def _make_fred_series() -> list[TimeSeries]:
    """Return a small fake FRED GDP dataset."""
    return [
        TimeSeries(
            date=date(2024, 1, 1),
            value=27956.3,
            metadata=TimeSeriesMetadata(
                source="FRED",
                unit="Billions of Dollars",
                frequency="Quarterly",
            ),
        ),
        TimeSeries(
            date=date(2024, 4, 1),
            value=28269.5,
            metadata=TimeSeriesMetadata(
                source="FRED",
                unit="Billions of Dollars",
                frequency="Quarterly",
            ),
        ),
    ]


def _make_ftd_data() -> list[ShortData]:
    """Return a small fake FTD dataset."""
    return [
        ShortData(
            symbol="GME",
            date=date(2024, 1, 2),
            data_type="ftd",
            value=150000.0,
            total_for_ratio=15.25,
            source="SEC",
        ),
        ShortData(
            symbol="GME",
            date=date(2024, 1, 3),
            data_type="ftd",
            value=98000.0,
            total_for_ratio=16.10,
            source="SEC",
        ),
    ]


FAKE_GLOSSARY = {
    "yield_curve": {
        "term": "Yield Curve",
        "description": "A line plotting interest rates of bonds with equal credit quality but differing maturity dates.",
        "interpretation": "A normal curve slopes upward; an inverted curve may signal recession.",
        "caveats": "Shape is influenced by monetary policy expectations.",
    },
    "ftd": {
        "term": "Fails-to-Deliver",
        "description": "Securities that a seller has not delivered to the buyer within the standard settlement period.",
        "interpretation": "High FTDs may indicate settlement stress or naked short selling.",
        "caveats": "FTDs can result from administrative delays, not just short selling.",
    },
    "spread": {
        "term": "Spread",
        "description": "The difference in yield between two bonds, typically of different maturities.",
        "interpretation": "A narrowing spread may signal economic uncertainty.",
        "caveats": "Compare like-for-like: same credit quality, different maturities.",
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_adapters():
    """Patch all external adapter calls so tests never hit real APIs."""
    with (
        patch(
            "agora.adapters.treasury_adapter.fetch_yields",
            return_value=_make_yield_series(),
        ) as mock_yields,
        patch(
            "agora.adapters.fred_adapter.fetch_series",
            return_value=_make_fred_series(),
        ) as mock_fred,
        patch(
            "agora.adapters.sec_ftd_adapter.fetch_ftd_data",
            return_value=_make_ftd_data(),
        ) as mock_ftd,
    ):
        yield {
            "treasury": mock_yields,
            "fred": mock_fred,
            "ftd": mock_ftd,
        }


@pytest.fixture()
def mock_glossary(tmp_path):
    """Write a temporary glossary YAML and patch the app to read it."""
    import yaml

    glossary_file = tmp_path / "terms.yaml"
    glossary_file.write_text(yaml.dump(FAKE_GLOSSARY, default_flow_style=False))
    return glossary_file, FAKE_GLOSSARY


@pytest.fixture()
def client(mock_adapters, mock_glossary):
    """Create a TestClient with all adapters mocked and glossary available."""
    glossary_file, _ = mock_glossary

    # Patch the glossary file path so the app loads our fake data.
    # The routes module should read the glossary path from a well-known
    # location; we patch it to point at our temp file.
    with patch(
        "agora.api.routes.GLOSSARY_PATH",
        glossary_file,
    ):
        from agora.api.routes import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc


@pytest.fixture()
def client_no_glossary(mock_adapters, tmp_path):
    """TestClient where the glossary file does not exist."""
    missing = tmp_path / "nonexistent_terms.yaml"
    with patch(
        "agora.api.routes.GLOSSARY_PATH",
        missing,
    ):
        from agora.api.routes import create_app

        app = create_app()
        with TestClient(app) as tc:
            yield tc


# ---------------------------------------------------------------------------
# Metric emission
# ---------------------------------------------------------------------------

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Emit [METRIC] test_pass_rate for the experiment harness."""
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed
    rate = passed / total if total > 0 else 0.0
    print(f"\n[METRIC] test_pass_rate={rate:.4f}")
