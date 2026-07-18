"""Three-tier price lookup: Alpha Vantage → CSV history → PDF seed.

The CSV at ``data/prices/history.csv`` is the source-of-truth floor. Live AV
quotes enrich it (and get appended back), so a fresh row is available for
tomorrow even after today's AV quota is spent.

Row shape: date,ticker,price,source  (long format, one row per ticker per day).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from advisor.tools.alpha_vantage import AlphaVantageError, get_quote

HISTORY_CSV = Path("data/prices/history.csv")
_FIELDS = ("date", "ticker", "price", "source")


@dataclass(frozen=True)
class PriceRow:
    date: str
    ticker: str
    price: float
    source: str


@dataclass(frozen=True)
class PriceLookup:
    """Result of get_price(). ``freshness`` is what the UI renders."""
    ticker: str
    price: float
    as_of: str
    source: str        # 'alpha_vantage' | 'csv' | 'seed'
    freshness: str     # 'live' | 'cached (<date>)' | 'seed (<date>)'


def _read_all() -> list[PriceRow]:
    if not HISTORY_CSV.exists():
        return []
    with HISTORY_CSV.open() as f:
        return [
            PriceRow(date=r["date"], ticker=r["ticker"], price=float(r["price"]), source=r["source"])
            for r in csv.DictReader(f)
        ]


def _append(row: PriceRow) -> None:
    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not HISTORY_CSV.exists()
    with HISTORY_CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        if write_header:
            w.writeheader()
        w.writerow({"date": row.date, "ticker": row.ticker, "price": row.price, "source": row.source})


def _latest_for(ticker: str, rows: list[PriceRow] | None = None) -> PriceRow | None:
    rows = rows if rows is not None else _read_all()
    matches = [r for r in rows if r.ticker == ticker]
    if not matches:
        return None
    return max(matches, key=lambda r: r.date)


def _has_row(ticker: str, day: str, rows: list[PriceRow]) -> bool:
    return any(r.ticker == ticker and r.date == day for r in rows)


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def get_price(ticker: str, *, allow_live: bool = True) -> PriceLookup:
    """Return the freshest price we have for ``ticker``.

    Tries Alpha Vantage first (and appends the fresh row to the CSV), then
    falls back to the most recent CSV row. Never raises — a missing ticker
    with no history returns price=0.0 with source='missing', which the UI
    can surface as a warning instead of a crash.
    """
    ticker = ticker.upper()

    if allow_live:
        try:
            quote = get_quote(ticker)
            price = quote.get("price")
            if price is not None:
                today = _today()
                rows = _read_all()
                if not _has_row(ticker, today, rows):
                    _append(PriceRow(date=today, ticker=ticker, price=float(price), source="alpha_vantage"))
                return PriceLookup(
                    ticker=ticker, price=float(price),
                    as_of=quote.get("latest_trading_day") or today,
                    source="alpha_vantage", freshness="live",
                )
        except AlphaVantageError:
            pass  # fall through to CSV

    row = _latest_for(ticker)
    if row is not None:
        label = "seed" if row.source == "seed" else "cached"
        return PriceLookup(
            ticker=ticker, price=row.price, as_of=row.date,
            source=row.source, freshness=f"{label} ({row.date})",
        )

    return PriceLookup(ticker=ticker, price=0.0, as_of="", source="missing", freshness="missing")


def get_prices(tickers: Iterable[str], *, allow_live: bool = True) -> dict[str, PriceLookup]:
    return {t.upper(): get_price(t, allow_live=allow_live) for t in tickers}


def append_from_quote(ticker: str, price: float, source: str = "alpha_vantage",
                       when: date | None = None) -> None:
    """Explicit appender for use by scripts/refresh_prices.py."""
    day = (when or date.today()).isoformat()
    rows = _read_all()
    if _has_row(ticker.upper(), day, rows):
        return
    _append(PriceRow(date=day, ticker=ticker.upper(), price=float(price), source=source))


def tracked_tickers() -> list[str]:
    """Distinct tickers currently present in the history file."""
    return sorted({r.ticker for r in _read_all()})
