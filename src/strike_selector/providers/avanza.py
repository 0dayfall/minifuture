from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strike_selector.models import UnderlyingPrice


@dataclass(frozen=True)
class AvanzaLookupResult:
    price: UnderlyingPrice
    raw: object


def fetch_price_by_id(avanza_id: str) -> AvanzaLookupResult:
    """Fetch a price using Avanza instrument ID.

    This uses unofficial libraries if installed. The user must install one of them.
    """
    errors: list[str] = []

    try:
        import avanza  # type: ignore

        stock = avanza.Stock(avanza_id)
        price = float(stock.price)
        name = getattr(stock, "name", None) or f"Avanza:{avanza_id}"
        currency = getattr(stock, "currency", None)
        return AvanzaLookupResult(
            price=UnderlyingPrice(name=name, price=price, currency=currency, source="avanza"),
            raw=stock,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"python-avanza failed: {exc}")

    try:
        from avanzapy import Avanza, InstrumentType  # type: ignore

        client = Avanza()
        instrument = client.getInstrument(InstrumentType.STOCK, avanza_id)
        price = float(instrument.price)
        name = getattr(instrument, "name", None) or f"Avanza:{avanza_id}"
        currency = getattr(instrument, "currency", None)
        return AvanzaLookupResult(
            price=UnderlyingPrice(name=name, price=price, currency=currency, source="avanza"),
            raw=instrument,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"avanzapy failed: {exc}")

    message = "Could not fetch Avanza price. Install one of: python-avanza or avanzapy."\
        + (" Details: " + " | ".join(errors) if errors else "")
    raise RuntimeError(message)
