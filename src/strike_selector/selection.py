from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from strike_selector.models import Candidate, MiniFuture


@dataclass(frozen=True)
class SelectionConfig:
    direction: str
    risk: float
    stop: float
    take_profit: float
    max_spread: Optional[float] = None
    min_leverage: Optional[float] = None
    max_leverage: Optional[float] = None
    require_profit: bool = True


def select_candidates(
    minis: Iterable[MiniFuture],
    underlying_price: float,
    config: SelectionConfig,
) -> List[Candidate]:
    candidates: List[Candidate] = []
    for mini in minis:
        candidate = _evaluate(mini, underlying_price, config)
        if candidate is None:
            continue
        if config.require_profit and candidate.profit_per_unit <= 0:
            continue
        if config.max_spread is not None and candidate.spread is not None:
            if candidate.spread > config.max_spread:
                continue
        if config.min_leverage is not None and candidate.leverage is not None:
            if candidate.leverage < config.min_leverage:
                continue
        if config.max_leverage is not None and candidate.leverage is not None:
            if candidate.leverage > config.max_leverage:
                continue
        candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda c: (
            c.distance_to_stop,
            -(c.leverage or 0.0),
            -c.total_profit,
        ),
    )


def _evaluate(
    mini: MiniFuture,
    underlying_price: float,
    config: SelectionConfig,
) -> Optional[Candidate]:
    if not mini.ratio or not mini.financing_level:
        return None

    direction = _normalize_direction(mini.direction, config.direction)
    if direction is None:
        return None
    if mini.knockout is None:
        return None

    if direction == "bull":
        if mini.knockout is not None and underlying_price <= mini.knockout:
            return None
        if mini.knockout > config.stop:
            return None
        distance_to_stop = config.stop - mini.knockout
    else:
        if mini.knockout is not None and underlying_price >= mini.knockout:
            return None
        if mini.knockout < config.stop:
            return None
        distance_to_stop = mini.knockout - config.stop

    price_now = _choose_price(mini, underlying_price, direction)
    if price_now is None or price_now <= 0:
        return None

    price_stop = _theoretical_price(config.stop, mini.financing_level, mini.ratio, direction)
    if price_stop is None:
        return None
    if price_stop <= 0:
        return None

    risk_per_unit = price_now - price_stop
    if risk_per_unit <= 0:
        return None

    price_target = _theoretical_price(config.take_profit, mini.financing_level, mini.ratio, direction)
    if price_target is None:
        return None
    if price_target <= 0:
        return None

    profit_per_unit = price_target - price_now
    units = config.risk / risk_per_unit
    total_profit = profit_per_unit * units

    leverage = None
    if mini.ratio and price_now > 0:
        leverage = underlying_price / (price_now * mini.ratio)

    spread = None
    if mini.ask is not None and mini.bid is not None:
        spread = mini.ask - mini.bid

    return Candidate(
        product=mini,
        price_now=price_now,
        price_stop=price_stop,
        price_target=price_target,
        units=units,
        risk_per_unit=risk_per_unit,
        profit_per_unit=profit_per_unit,
        total_profit=total_profit,
        leverage=leverage,
        spread=spread,
        distance_to_stop=distance_to_stop,
    )


def _choose_price(mini: MiniFuture, underlying_price: float, direction: str) -> Optional[float]:
    if mini.ask is not None:
        return mini.ask
    if mini.bid is not None:
        return mini.bid
    if mini.last is not None:
        return mini.last
    return _theoretical_price(underlying_price, mini.financing_level, mini.ratio, direction)


def _theoretical_price(
    underlying_price: float,
    financing_level: float,
    ratio: float,
    direction: str,
) -> Optional[float]:
    if ratio == 0:
        return None
    if direction == "bull":
        return (underlying_price - financing_level) / ratio
    if direction == "bear":
        return (financing_level - underlying_price) / ratio
    return None


def _normalize_direction(product_direction: Optional[str], requested: str) -> Optional[str]:
    normalized_requested = requested.strip().lower()
    if normalized_requested in {"long", "bull"}:
        requested_dir = "bull"
    elif normalized_requested in {"short", "bear"}:
        requested_dir = "bear"
    else:
        return None

    if not product_direction:
        return requested_dir

    lowered = product_direction.lower()
    if "bull" in lowered or "long" in lowered:
        return "bull" if requested_dir == "bull" else None
    if "bear" in lowered or "short" in lowered:
        return "bear" if requested_dir == "bear" else None
    return requested_dir
