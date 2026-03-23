"""FastAPI API routes for Agora.

Serves yield curve, FTD, FRED, and glossary data via REST endpoints.
Delegates all data fetching to adapter modules and analysis to the
yield_curve analysis module.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Query

from agora.adapters import fred_adapter, treasury_adapter, sec_ftd_adapter
from agora.api.short_intel import router as short_intel_router
from agora.adapters.treasury_adapter import _MATURITY_TO_CSV_COL
from agora.analysis import yield_curve

# ---------------------------------------------------------------------------
# Glossary file location (patched in tests)
# ---------------------------------------------------------------------------
GLOSSARY_PATH: Path = Path(__file__).resolve().parent.parent / "glossary" / "terms.yaml"

# Valid maturity labels (from the treasury adapter)
_VALID_MATURITIES: set[str] = set(_MATURITY_TO_CSV_COL.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str | None, param_name: str) -> date | None:
    """Parse an ISO date string, raising HTTPException(400) on failure."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for '{param_name}': '{value}'. Expected ISO format (YYYY-MM-DD).",
        )


def _load_glossary() -> dict:
    """Load glossary terms from the YAML file."""
    if not GLOSSARY_PATH.exists():
        return {}
    with open(GLOSSARY_PATH, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {}
    return data


def _get_fred_api_key() -> str:
    """Read FRED API key from environment."""
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="FRED_API_KEY environment variable is not set.",
        )
    return key


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and return a configured FastAPI application."""
    app = FastAPI(title="Agora API", version="0.1.0")

    app.include_router(short_intel_router)

    # ------------------------------------------------------------------
    # GET /api/yields
    # ------------------------------------------------------------------
    @app.get("/api/yields")
    def get_yields(
        maturities: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
    ):
        parsed_start = _parse_date(start_date, "start_date")
        parsed_end = _parse_date(end_date, "end_date")

        mat_list: list[str] | None = None
        if maturities is not None:
            mat_list = [m.strip() for m in maturities.split(",") if m.strip()]
            # Validate maturity labels up-front
            for m in mat_list:
                if m not in _VALID_MATURITIES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown maturity label '{m}'. "
                               f"Valid labels: {', '.join(sorted(_VALID_MATURITIES))}",
                    )

        try:
            series = treasury_adapter.fetch_yields(
                maturities=mat_list,
                start_date=parsed_start,
                end_date=parsed_end,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        # Post-filter results to guarantee correctness even when the
        # underlying adapter is mocked or returns extra data.
        filtered = series
        if mat_list is not None:
            mat_set = set(mat_list)
            filtered = [ts for ts in filtered if ts.metadata.unit in mat_set]
        if parsed_start is not None:
            filtered = [ts for ts in filtered if ts.date >= parsed_start]
        if parsed_end is not None:
            filtered = [ts for ts in filtered if ts.date <= parsed_end]

        data = [
            {
                "date": ts.date.isoformat(),
                "value": ts.value,
                "maturity": ts.metadata.unit,
                "source": ts.metadata.source,
            }
            for ts in filtered
        ]
        return {"data": data, "count": len(data)}

    # ------------------------------------------------------------------
    # GET /api/yields/curve
    # ------------------------------------------------------------------
    @app.get("/api/yields/curve")
    def get_yields_curve():
        try:
            series = treasury_adapter.fetch_yields()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        curve = yield_curve.current_curve(series)

        # Determine as_of date from the series
        if series:
            as_of = max(ts.date for ts in series).isoformat()
        else:
            as_of = date.today().isoformat()

        return {"data": curve, "as_of": as_of}

    # ------------------------------------------------------------------
    # GET /api/yields/spread
    # ------------------------------------------------------------------
    @app.get("/api/yields/spread")
    def get_yields_spread(
        long: str = Query(...),
        short: str = Query(...),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
    ):
        parsed_start = _parse_date(start_date, "start_date")
        parsed_end = _parse_date(end_date, "end_date")

        try:
            series = treasury_adapter.fetch_yields(
                maturities=[long, short],
                start_date=parsed_start,
                end_date=parsed_end,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        spread_series = yield_curve.compute_spread(series, long, short)

        data = [
            {
                "date": ts.date.isoformat(),
                "spread": ts.value,
            }
            for ts in spread_series
        ]
        return {
            "data": data,
            "long": long,
            "short": short,
            "count": len(data),
        }

    # ------------------------------------------------------------------
    # GET /api/yields/inversions
    # ------------------------------------------------------------------
    @app.get("/api/yields/inversions")
    def get_yields_inversions():
        try:
            series = treasury_adapter.fetch_yields()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        inversions = yield_curve.detect_inversions(series)
        return {"data": inversions, "count": len(inversions)}

    # ------------------------------------------------------------------
    # GET /api/ftd
    # ------------------------------------------------------------------
    @app.get("/api/ftd")
    def get_ftd(
        symbol: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
    ):
        parsed_start = _parse_date(start_date, "start_date")
        parsed_end = _parse_date(end_date, "end_date")

        try:
            records = sec_ftd_adapter.fetch_ftd_data(
                symbol=symbol,
                start_date=parsed_start,
                end_date=parsed_end,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        data = [
            {
                "symbol": r.symbol,
                "date": r.date.isoformat(),
                "value": r.value,
                "data_type": r.data_type,
                "source": r.source,
            }
            for r in records
        ]
        return {"data": data, "count": len(data)}

    # ------------------------------------------------------------------
    # GET /api/fred
    # ------------------------------------------------------------------
    @app.get("/api/fred")
    def get_fred(
        series_id: str = Query(...),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
    ):
        parsed_start = _parse_date(start_date, "start_date")
        parsed_end = _parse_date(end_date, "end_date")

        api_key = _get_fred_api_key()

        try:
            series = fred_adapter.fetch_series(
                series_id,
                api_key,
                start_date=parsed_start,
                end_date=parsed_end,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        data = [
            {
                "date": ts.date.isoformat(),
                "value": ts.value,
                "source": ts.metadata.source,
            }
            for ts in series
        ]
        return {"data": data, "series_id": series_id, "count": len(data)}

    # ------------------------------------------------------------------
    # GET /api/glossary
    # ------------------------------------------------------------------
    @app.get("/api/glossary")
    def get_glossary():
        glossary = _load_glossary()
        data = [
            {"term": entry.get("term", key), "description": entry.get("description", "")}
            for key, entry in glossary.items()
        ]
        return {"data": data, "count": len(data)}

    # ------------------------------------------------------------------
    # GET /api/glossary/{term}
    # ------------------------------------------------------------------
    @app.get("/api/glossary/{term}")
    def get_glossary_term(term: str):
        glossary = _load_glossary()
        entry = glossary.get(term)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Glossary term '{term}' not found.",
            )
        return {
            "term": entry.get("term", term),
            "description": entry.get("description", ""),
        }

    return app
