from __future__ import annotations

import argparse
from pathlib import Path
import os
from typing import Iterable, List, Optional

from strike_selector.models import MiniFuture
from strike_selector.providers.avanza import fetch_price_by_id
from strike_selector.providers.vontobel import DEFAULT_URL, VontobelProvider
from strike_selector.providers.vontobel_api import (
    DEFAULT_CULTURE,
    DEFAULT_INVESTOR_TYPE,
    DEFAULT_PAGE_SIZE,
    VontobelApiConfig,
    VontobelApiProvider,
)
from strike_selector.selection import SelectionConfig, select_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Select mini futures based on risk and price levels.")

    price_group = parser.add_argument_group("Underlying price")
    price_group.add_argument("--price", type=float, help="Manual underlying price")
    price_group.add_argument("--avanza-id", help="Avanza instrument id (optional)")

    parser.add_argument("--underlying", required=True, help="Underlying name filter")
    parser.add_argument("--risk", type=float, required=True, help="Risk amount in account currency")
    parser.add_argument("--stop", type=float, required=True, help="Underlying stop price")
    parser.add_argument("--rr", type=float, default=2.0, help="Risk:reward multiple")
    parser.add_argument("--take-profit", type=float, help="Explicit take-profit price")
    parser.add_argument(
        "--direction",
        choices=["long", "short"],
        default="long",
        help="Direction to evaluate",
    )
    parser.add_argument("--issuer", action="append", help="Issuer filter (repeatable)")
    parser.add_argument("--limit", type=int, default=3, help="Maximum rows to show")
    parser.add_argument("--max-spread", type=float, help="Filter out spreads above this")
    parser.add_argument("--min-leverage", type=float, help="Filter out leverage below this")
    parser.add_argument("--max-leverage", type=float, help="Filter out leverage above this")

    source_group = parser.add_argument_group("Mini future sources")
    source_group.add_argument(
        "--vontobel-api",
        action="store_true",
        help="Fetch mini futures from Vontobel's product overview API",
    )
    source_group.add_argument(
        "--vontobel-culture",
        default=DEFAULT_CULTURE,
        help="Culture code for Vontobel API (e.g. en-se, sv-se)",
    )
    source_group.add_argument(
        "--vontobel-investor-type",
        type=int,
        default=DEFAULT_INVESTOR_TYPE,
        help="Investor type for Vontobel API (1=private, 2=professional)",
    )
    source_group.add_argument(
        "--vontobel-page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Page size for Vontobel API pagination",
    )
    source_group.add_argument("--vontobel-csv", type=Path, help="Path to Vontobel CSV export")
    source_group.add_argument(
        "--vontobel-url",
        nargs="?",
        const=DEFAULT_URL,
        default=None,
        help="Download Vontobel CSV (optionally provide custom URL or product-download page)",
    )
    source_group.add_argument(
        "--vontobel-url-file",
        type=Path,
        help="Read the Vontobel CSV URL from a file (to avoid pasting it in the command line)",
    )
    source_group.add_argument(
        "--vontobel-cookie",
        help="Cookie string for Vontobel (use if a disclaimer blocks CSV download)",
    )
    source_group.add_argument(
        "--vontobel-cookie-file",
        type=Path,
        help="Read the Vontobel cookie string from a file (to avoid pasting it in the command line)",
    )
    source_group.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to a .env file that can set VONTOBEL_URL and VONTOBEL_COOKIE",
    )

    args = parser.parse_args()

    underlying_price = resolve_underlying_price(args.price, args.avanza_id)

    take_profit = args.take_profit
    if take_profit is None:
        take_profit = compute_take_profit(underlying_price, args.stop, args.rr, args.direction)

    load_env_file(args.env_file)
    url = resolve_vontobel_url(args.vontobel_url, args.vontobel_url_file)
    cookie = resolve_vontobel_cookie(args.vontobel_cookie, args.vontobel_cookie_file)
    loaded_minis = load_minis(
        args.vontobel_csv,
        url,
        cookie,
        use_api=args.vontobel_api,
        api_culture=args.vontobel_culture,
        api_investor_type=args.vontobel_investor_type,
        api_page_size=args.vontobel_page_size,
    )
    minis = filter_minis(loaded_minis, args.underlying, args.issuer)

    config = SelectionConfig(
        direction=args.direction,
        risk=args.risk,
        stop=args.stop,
        take_profit=take_profit,
        max_spread=args.max_spread,
        min_leverage=args.min_leverage,
        max_leverage=args.max_leverage,
    )
    candidates = select_candidates(minis, underlying_price, config)

    print_summary(
        underlying_price,
        args.stop,
        take_profit,
        args.direction,
        len(loaded_minis),
        len(minis),
    )

    if not candidates:
        print("No candidates matched your filters.")
        return

    best = candidates[0]
    print_best(best)
    print("")
    print(f"Top {min(args.limit, len(candidates))} closest to stop:")
    print_table(candidates[: args.limit])


def resolve_underlying_price(price: Optional[float], avanza_id: Optional[str]) -> float:
    if price is not None:
        return price
    if avanza_id:
        result = fetch_price_by_id(avanza_id)
        return result.price.price
    raise SystemExit("Provide either --price or --avanza-id.")


def compute_take_profit(price: float, stop: float, rr: float, direction: str) -> float:
    if direction == "short":
        return price - rr * (stop - price)
    return price + rr * (price - stop)


def load_minis(
    csv_path: Optional[Path],
    url: Optional[str],
    cookie: Optional[str],
    *,
    use_api: bool = False,
    api_culture: str = DEFAULT_CULTURE,
    api_investor_type: int = DEFAULT_INVESTOR_TYPE,
    api_page_size: int = DEFAULT_PAGE_SIZE,
) -> List[MiniFuture]:
    if use_api:
        config = VontobelApiConfig(
            culture=api_culture,
            investor_type=api_investor_type,
            page_size=api_page_size,
        )
        provider = VontobelApiProvider(config)
        return provider.fetch_all()

    provider = VontobelProvider(url=url or DEFAULT_URL, cookie=cookie)
    if csv_path:
        return provider.load_csv_file(csv_path)
    download_url = url or DEFAULT_URL
    if download_url:
        result = provider.download_csv()
        return provider.load_csv_text(result.csv_text)
    raise SystemExit("Provide --vontobel-api, --vontobel-csv, or --vontobel-url.")


def resolve_vontobel_url(url: Optional[str], url_file: Optional[Path]) -> Optional[str]:
    if url:
        return url
    if url_file:
        return url_file.read_text(encoding="utf-8").strip()
    env_url = os.getenv("VONTOBEL_URL")
    if env_url:
        return env_url.strip()
    return None


def resolve_vontobel_cookie(cookie: Optional[str], cookie_file: Optional[Path]) -> Optional[str]:
    if cookie:
        return cookie
    if cookie_file:
        return cookie_file.read_text(encoding="utf-8").strip()
    env_cookie = os.getenv("VONTOBEL_COOKIE")
    if env_cookie:
        return env_cookie.strip()
    return None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw[len("export ") :].strip()
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key or key in os.environ:
            continue
        os.environ[key] = value


def filter_minis(
    minis: Iterable[MiniFuture],
    underlying: str,
    issuers: Optional[List[str]],
) -> List[MiniFuture]:
    underlying_lc = underlying.lower()
    issuer_filters = [issuer.lower() for issuer in issuers] if issuers else []

    results: List[MiniFuture] = []
    for mini in minis:
        if mini.underlying and not _matches_underlying(underlying_lc, mini.underlying.lower()):
            continue
        if issuer_filters:
            issuer = (mini.issuer or "").lower()
            if not any(f in issuer for f in issuer_filters):
                continue
        results.append(mini)
    return results


def _matches_underlying(query: str, target: str) -> bool:
    tokens = [token for token in query.split() if token]
    if not tokens:
        return True
    return all(token in target for token in tokens)


def print_summary(
    underlying_price: float,
    stop: float,
    take_profit: float,
    direction: str,
    total_loaded: int,
    total_filtered: int,
) -> None:
    print(f"Underlying price: {underlying_price:.4f}")
    print(f"Stop: {stop:.4f}")
    print(f"Take profit: {take_profit:.4f}")
    print(f"Direction: {direction}")
    print(f"Mini futures loaded: {total_loaded}")
    print(f"Mini futures after filter: {total_filtered}")
    print("")


def print_best(best) -> None:
    p = best.product
    print("Best pick:")
    print(f"  Issuer: {p.issuer or ''}")
    print(f"  Symbol: {p.symbol or ''}")
    print(f"  ISIN: {p.isin or ''}")
    print(f"  Knockout: {fmt(p.knockout)}")
    print(f"  Distance to stop: {fmt(best.distance_to_stop)}")
    print(f"  Leverage: {fmt(best.leverage)}")
    print(f"  Units to buy: {fmt(best.units)}")
    print(f"  Est. profit at target: {fmt(best.total_profit)}")


def print_table(candidates) -> None:
    headers = [
        "Issuer",
        "Symbol",
        "ISIN",
        "Dir",
        "Ratio",
        "Financing",
        "KO",
        "Ask",
        "Bid",
        "Leverage",
        "KO dist",
        "Units",
        "Profit",
    ]

    rows = []
    for cand in candidates:
        p = cand.product
        rows.append(
            [
                p.issuer or "",
                p.symbol or "",
                p.isin or "",
                (p.direction or "").lower(),
                fmt(p.ratio),
                fmt(p.financing_level),
                fmt(p.knockout),
                fmt(p.ask),
                fmt(p.bid),
                fmt(cand.leverage),
                fmt(cand.distance_to_stop),
                fmt(cand.units),
                fmt(cand.total_profit),
            ]
        )

    print(format_table(headers, rows))


def fmt(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    lines = []
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("  ".join("-" * width for width in widths))

    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))

    return "\n".join(lines)


if __name__ == "__main__":
    main()
