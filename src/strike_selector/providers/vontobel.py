from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urljoin

import requests

from strike_selector.models import MiniFuture
from strike_selector.utils import normalize_header, parse_number, pick_column

DEFAULT_URL = "https://markets.vontobel.com/en-ch/product-download"
DEFAULT_CSV_URL = "https://markets.vontobel.com/cms/productdownload/export_en-ch-csv"
DEFAULT_REFERER = "https://markets.vontobel.com/en-ch/product-download"
CSV_LINK_RE = re.compile(r'href=["\']([^"\']*csv[^"\']*)["\']', re.IGNORECASE)


@dataclass(frozen=True)
class VontobelDownloadResult:
    csv_text: str
    source_url: str


class VontobelProvider:
    def __init__(
        self,
        url: str = DEFAULT_URL,
        referer: str = DEFAULT_REFERER,
        cookie: Optional[str] = None,
    ) -> None:
        self.url = url
        self.referer = referer
        self.cookie = cookie

    def download_csv(self, timeout: int = 20) -> VontobelDownloadResult:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (strike-selector)",
            "Accept": "text/csv,application/csv,text/plain,*/*",
            "Accept-Language": "en-CH,en;q=0.8",
            "Referer": self.referer,
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        response = session.get(self.url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                "Vontobel download failed with status "
                f"{response.status_code}. Try a different --vontobel-url or pass --vontobel-cookie."
            )

        csv_text, source_url = _resolve_csv_response(response.text, self.url)
        if csv_text is None:
            response = session.get(DEFAULT_CSV_URL, headers=headers, timeout=timeout)
            if response.status_code == 200 and not _looks_like_html(response.text):
                return VontobelDownloadResult(csv_text=response.text, source_url=DEFAULT_CSV_URL)
            raise RuntimeError(
                "Vontobel download returned HTML instead of CSV. "
                "You may need to accept the disclaimer in a browser and pass --vontobel-cookie, "
                "or provide --vontobel-csv."
            )
        if csv_text:
            return VontobelDownloadResult(csv_text=csv_text, source_url=source_url or self.url)

        if source_url and source_url != self.url:
            headers["Referer"] = self.url
        response = session.get(source_url or DEFAULT_CSV_URL, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                "Vontobel CSV download failed with status "
                f"{response.status_code}. Try a different --vontobel-url or pass --vontobel-cookie."
            )
        if _looks_like_html(response.text):
            raise RuntimeError(
                "Vontobel download returned HTML instead of CSV. "
                "You may need to accept the disclaimer in a browser and pass --vontobel-cookie, "
                "or provide --vontobel-csv."
            )
        return VontobelDownloadResult(csv_text=response.text, source_url=source_url)

    def load_csv_file(self, path: Path) -> List[MiniFuture]:
        text = path.read_text(encoding="utf-8-sig")
        return self._parse_csv(text)

    def load_csv_text(self, text: str) -> List[MiniFuture]:
        return self._parse_csv(text)

    def _parse_csv(self, text: str) -> List[MiniFuture]:
        delimiter = _detect_delimiter(text)
        text = _strip_sep_prefix(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter, skipinitialspace=True)
        headers = reader.fieldnames or []
        if not headers or len(headers) < 3:
            raise RuntimeError(
                "Could not parse Vontobel CSV headers. "
                "If you downloaded via --vontobel-url, please try a manual CSV download "
                "and pass --vontobel-csv."
            )

        columns = _ColumnMap.from_headers(headers)
        minis: List[MiniFuture] = []
        row_count = 0
        for row in reader:
            row_count += 1
            mini = _row_to_mini(row, columns)
            if mini is None:
                continue
            minis.append(mini)
        if row_count == 0:
            raise RuntimeError(
                "Vontobel CSV contained no data rows. "
                "The download may be blocked by a disclaimer or require a cookie. "
                "Try passing --vontobel-cookie or use --vontobel-url with the direct CSV link."
            )
        return minis


@dataclass(frozen=True)
class _ColumnMap:
    isin: Optional[str]
    symbol: Optional[str]
    name: Optional[str]
    issuer: Optional[str]
    product_type: Optional[str]
    direction: Optional[str]
    underlying: Optional[str]
    ratio: Optional[str]
    financing_level: Optional[str]
    knockout: Optional[str]
    bid: Optional[str]
    ask: Optional[str]
    currency: Optional[str]

    @classmethod
    def from_headers(cls, headers: Iterable[str]) -> "_ColumnMap":
        return cls(
            isin=pick_column(headers, "ISIN"),
            symbol=pick_column(headers, "Symbol", "Ticker", "Trading Symbol"),
            name=pick_column(headers, "Product Name", "Name"),
            issuer=pick_column(headers, "Issuer", "Issuer Name", "Emitter"),
            product_type=pick_column(headers, "Product Type", "Type", "Product Category"),
            direction=pick_column(headers, "Direction", "Long/Short"),
            underlying=pick_column(headers, "Underlying", "Underlying Name", "Underlying Description"),
            ratio=pick_column(headers, "Ratio", "Conversion Ratio", "Multiplier"),
            financing_level=pick_column(
                headers, "Financing Level", "Financing", "Strike", "Strike Level"
            ),
            knockout=pick_column(headers, "Knock-Out", "Knock Out", "Stop Loss", "Barrier"),
            bid=pick_column(headers, "Bid", "Bid Price"),
            ask=pick_column(headers, "Ask", "Ask Price", "Offer"),
            currency=pick_column(headers, "Currency", "Product Currency"),
        )


def _row_to_mini(row: dict, columns: _ColumnMap) -> Optional[MiniFuture]:
    product_type = _get(row, columns.product_type)
    if product_type and "mini" not in product_type.lower():
        return None

    direction = _get(row, columns.direction)
    if not direction:
        direction = _infer_direction(product_type)

    ratio = parse_number(_get(row, columns.ratio))
    financing_level = parse_number(_get(row, columns.financing_level))
    knockout = parse_number(_get(row, columns.knockout))
    bid = parse_number(_get(row, columns.bid))
    ask = parse_number(_get(row, columns.ask))

    return MiniFuture(
        isin=_get(row, columns.isin),
        symbol=_get(row, columns.symbol),
        name=_get(row, columns.name),
        issuer=_get(row, columns.issuer),
        direction=direction,
        underlying=_get(row, columns.underlying),
        ratio=ratio,
        financing_level=financing_level,
        knockout=knockout,
        bid=bid,
        ask=ask,
        currency=_get(row, columns.currency),
        source="vontobel",
        raw={normalize_header(k): v for k, v in row.items() if k is not None},
    )


def _infer_direction(product_type: Optional[str]) -> Optional[str]:
    if not product_type:
        return None
    lowered = product_type.lower()
    if "bull" in lowered or "long" in lowered:
        return "bull"
    if "bear" in lowered or "short" in lowered:
        return "bear"
    return None


def _get(row: dict, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return row.get(key)


def _detect_delimiter(text: str) -> str:
    sample = text[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample else ""
        for delim in (";", "\t", ",", "|"):
            if delim in first_line:
                return delim
    return ","


def _strip_sep_prefix(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    first = lines[0].strip().lower()
    if first.startswith("sep="):
        return "\n".join(lines[1:])
    return text


def _looks_like_html(text: str) -> bool:
    snippet = text.lstrip()[:200].lower()
    return snippet.startswith("<!doctype") or snippet.startswith("<html") or "<html" in snippet


def _resolve_csv_response(text: str, base_url: str) -> tuple[Optional[str], Optional[str]]:
    if not _looks_like_html(text):
        return text, base_url
    link = _extract_csv_link(text, base_url)
    if not link:
        return None, None
    return "", link


def _extract_csv_link(text: str, base_url: str) -> Optional[str]:
    match = CSV_LINK_RE.search(text)
    if not match:
        return None
    href = match.group(1)
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("/"):
        return urljoin(base_url, href)
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)
