#!/usr/bin/env python3
"""Pre-warm the Alpha Vantage cache for demo tickers so live cells hit disk, not the network.

Run this the morning of a mentored session. Uses `requests-cache` with a 30-min TTL,
so re-run within 30 minutes of the demo for a clean cache-hit story on stage.

    python scripts/prewarm_cache.py                 # default: AAPL, MSFT, VOO
    python scripts/prewarm_cache.py AAPL MSFT NVDA  # custom set
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from advisor.tools.alpha_vantage import (  # noqa: E402
    AlphaVantageError,
    get_company_overview,
    get_news_sentiment,
    get_quote,
)

DEFAULT_TICKERS = ["AAPL", "MSFT", "VOO"]


# AV free tier throttles at ~5 req/min. A 13-second gap keeps us safely under.
_PACE_SECONDS = 13


def warm(symbol: str) -> None:
    print(f"[{symbol}]")
    for label, fn, args in (
        ("quote          ", get_quote, (symbol,)),
        ("overview       ", get_company_overview, (symbol,)),
        ("news_sentiment ", get_news_sentiment, (symbol,)),
    ):
        t0 = time.perf_counter()
        try:
            fn(*args)
            dt_ms = (time.perf_counter() - t0) * 1000
            hit = "cache" if dt_ms < 50 else "live "
            print(f"  {label} OK  [{hit}] ({dt_ms:7.1f} ms)")
            if dt_ms >= 50:
                time.sleep(_PACE_SECONDS)
        except AlphaVantageError as e:
            print(f"  {label} FAIL — {e}")
            time.sleep(_PACE_SECONDS)
        except Exception as e:  # noqa: BLE001
            print(f"  {label} ERROR — {type(e).__name__}: {e}")


def main(argv: list[str]) -> int:
    tickers = argv[1:] or DEFAULT_TICKERS
    print(f"Warming AV cache for: {', '.join(tickers)}\n")
    for sym in tickers:
        warm(sym)
    print("\nDone. Cache file: data/raw/av_cache.sqlite (30-min TTL).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
