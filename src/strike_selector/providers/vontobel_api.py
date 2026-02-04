from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from strike_selector.models import MiniFuture

DEFAULT_API_BASE_URL = "https://markets.vontobel.com/api"
DEFAULT_CULTURE = "en-se"
DEFAULT_INVESTOR_TYPE = 1
DEFAULT_PAGE_SIZE = 1000
PRODUCT_TYPE_MINI_FUTURES = 2


@dataclass(frozen=True)
class VontobelApiConfig:
    base_url: str = DEFAULT_API_BASE_URL
    culture: str = DEFAULT_CULTURE
    investor_type: int = DEFAULT_INVESTOR_TYPE
    page_size: int = DEFAULT_PAGE_SIZE


class VontobelApiProvider:
    def __init__(self, config: VontobelApiConfig) -> None:
        self.config = config

    def fetch_all(self, product_type: int = PRODUCT_TYPE_MINI_FUTURES) -> List[MiniFuture]:
        page = 0
        total = None
        minis: List[MiniFuture] = []

        while True:
            payload = self._fetch_page(product_type, page, self.config.page_size)
            items = payload.get("items", [])
            total = payload.get("totalCount", total)

            for item in items:
                mini = _item_to_mini(item)
                if mini is not None:
                    minis.append(mini)

            if not items:
                break
            if total is not None and len(minis) >= total:
                break
            if len(items) < self.config.page_size:
                break
            page += 1

        return minis

    def _fetch_page(self, product_type: int, page: int, page_size: int) -> Dict[str, Any]:
        url = f"{self.config.base_url}/v1/products/search"
        params = {"c": self.config.culture, "it": str(self.config.investor_type)}
        payload = {"productType": product_type, "page": page, "pageSize": page_size}
        headers = {
            "User-Agent": "Mozilla/5.0 (strike-selector)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        response = requests.post(url, params=params, json=payload, headers=headers, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(
                "Vontobel API request failed with status "
                f"{response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        if not data.get("isSuccess", True):
            raise RuntimeError(
                "Vontobel API returned an error payload: "
                f"{data.get('errorCode') or data}"
            )
        return data.get("payload", {})


def _item_to_mini(item: Dict[str, Any]) -> Optional[MiniFuture]:
    if not isinstance(item, dict):
        return None

    direction_val = item.get("direction")
    direction = _map_direction(direction_val)

    underlyings = item.get("underlyings") or []
    underlying = None
    if isinstance(underlyings, list) and underlyings:
        first = underlyings[0]
        if isinstance(first, dict):
            underlying = first.get("name")

    price = item.get("price") or {}
    bid = _as_float(price.get("bid"))
    ask = _as_float(price.get("ask"))
    last = _as_float(price.get("latest"))

    currency = price.get("currency") or item.get("currency")
    symbol = None
    primary_identifier = item.get("primaryIdentifier") or {}
    if isinstance(primary_identifier, dict):
        symbol = primary_identifier.get("value")

    return MiniFuture(
        isin=item.get("isin"),
        symbol=symbol,
        name=None,
        issuer="Vontobel",
        direction=direction,
        underlying=underlying,
        ratio=_as_float(item.get("ratio")),
        financing_level=_as_float(item.get("strikeLevel")),
        knockout=_as_float(item.get("stopLoss")),
        bid=bid,
        ask=ask,
        last=last,
        currency=currency,
        source="vontobel_api",
        raw=item,
    )


def _map_direction(value: Any) -> Optional[str]:
    if value == 1:
        return "bull"
    if value == 2:
        return "bear"
    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
