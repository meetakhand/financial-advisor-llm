"""Daily price refresh: append today's row per tracked ticker to history.csv.

Runs paced at 13s per Alpha Vantage call to respect the 5-req/min throttle.
Idempotent: rows for (today, ticker) are skipped unless --force is passed.

Usage:
  python scripts/refresh_prices.py
  python scripts/refresh_prices.py --tickers AAPL MSFT --force
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

# Allow running from repo root without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from advisor.domain.prices import (  # noqa: E402
    HISTORY_CSV, _has_row, _read_all, append_from_quote, tracked_tickers,
)
from advisor.tools.alpha_vantage import AlphaVantageError, get_quote  # noqa: E402

_PACE_SECONDS = 13


def refresh(tickers: list[str], *, force: bool) -> tuple[int, int, int]:
    today = date.today().isoformat()
    rows = _read_all()

    fresh = skipped = failed = 0
    for i, ticker in enumerate(tickers):
        ticker = ticker.upper()
        if not force and _has_row(ticker, today, rows):
            print(f"[{ticker:8s}] skip (row exists for {today})")
            skipped += 1
            continue

        try:
            quote = get_quote(ticker)
            price = quote.get("price")
            if price is None:
                print(f"[{ticker:8s}] FAIL — no price in AV response")
                failed += 1
            else:
                append_from_quote(ticker, price, source="alpha_vantage")
                print(f"[{ticker:8s}] {price:>10.2f}  appended")
                fresh += 1
        except AlphaVantageError as e:
            print(f"[{ticker:8s}] FAIL — {e}")
            failed += 1

        if i < len(tickers) - 1:
            time.sleep(_PACE_SECONDS)

    return fresh, skipped, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", nargs="+", help="Override the tracked set")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite today's row even if it already exists")
    args = ap.parse_args()

    tickers = args.tickers or tracked_tickers()
    if not tickers:
        print(f"No tickers to refresh. Seed {HISTORY_CSV} first.")
        return 1

    print(f"Refreshing {len(tickers)} ticker(s) → {HISTORY_CSV}")
    fresh, skipped, failed = refresh(tickers, force=args.force)
    print(f"\ndone: {fresh} fresh, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
