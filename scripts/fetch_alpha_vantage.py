#!/usr/bin/env python3
"""Smoke-test Alpha Vantage credentials and warm the cache for a few common tickers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from advisor.tools.alpha_vantage import (  # noqa: E402
    AlphaVantageError,
    get_company_overview,
    get_quote,
    get_sector_performance,
)

TICKERS = ["AAPL", "MSFT", "GOOGL", "VOO", "BND"]


def main():
    print("Sectors…")
    try:
        get_sector_performance()
    except AlphaVantageError as e:
        print(f"  ! {e}")
    for sym in TICKERS:
        print(f"{sym}…")
        try:
            q = get_quote(sym)
            o = get_company_overview(sym)
            print(f"  price={q.get('price')}  sector={o.get('Sector')}")
        except AlphaVantageError as e:
            print(f"  ! {e}")


if __name__ == "__main__":
    main()
