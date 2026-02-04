from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class UnderlyingPrice:
    name: str
    price: float
    currency: Optional[str] = None
    source: Optional[str] = None


@dataclass(frozen=True)
class MiniFuture:
    isin: Optional[str]
    symbol: Optional[str]
    name: Optional[str]
    issuer: Optional[str]
    direction: Optional[str]
    underlying: Optional[str]
    ratio: Optional[float]
    financing_level: Optional[float]
    knockout: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    product: MiniFuture
    price_now: float
    price_stop: float
    price_target: float
    units: float
    risk_per_unit: float
    profit_per_unit: float
    total_profit: float
    leverage: Optional[float]
    spread: Optional[float]
    distance_to_stop: float
