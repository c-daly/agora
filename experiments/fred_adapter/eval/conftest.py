import os
import pytest


@pytest.fixture
def fred_api_key():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        pytest.skip("FRED_API_KEY not set")
    return key
