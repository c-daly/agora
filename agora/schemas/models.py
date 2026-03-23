"""Common data schemas. All adapters normalize to these shapes."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


class TimeSeriesMetadata(BaseModel):
    source: str
    unit: Optional[str] = None
    frequency: Optional[str] = None


class TimeSeries(BaseModel):
    date: date
    value: float
    metadata: TimeSeriesMetadata


class Filing(BaseModel):
    date: date
    entity: str
    type: str
    url: str
    extracted_fields: dict[str, Any] = {}


class Transaction(BaseModel):
    date: date
    entity: str
    action: str
    amount: float
    context: dict[str, Any] = {}


class Quote(BaseModel):
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ShortData(BaseModel):
    symbol: str
    date: date
    data_type: str  # volume | interest | ftd | threshold
    value: float
    total_for_ratio: Optional[float] = None
    source: str


class OptionsSnapshot(BaseModel):
    symbol: str
    date: date
    expiry: date
    strike: float
    type: str  # put | call
    volume: int
    open_interest: int
    implied_vol: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
