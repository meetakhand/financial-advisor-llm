"""Alpha Vantage API wrappers with on-disk caching.

Free tier is 25 requests/day and 5/min, so caching is essential during dev.
"""
from __future__ import annotations

from pathlib import Path

import requests_cache

from advisor.config import settings

_CACHE_DIR = Path("data/raw")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_session = requests_cache.CachedSession(
    str(_CACHE_DIR / "av_cache"),
    expire_after=60 * 30,  # 30 min for quotes; news has its own short TTL via params
    allowable_methods=("GET",),
)
_BASE = "https://www.alphavantage.co/query"


class AlphaVantageError(RuntimeError):
    pass


def _call(params: dict) -> dict:
    params = {**params, "apikey": settings.alpha_vantage_key}
    r = _session.get(_BASE, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "Note" in data:
        raise AlphaVantageError(f"AV rate-limited: {data['Note']}")
    if "Information" in data and "rate limit" in str(data["Information"]).lower():
        raise AlphaVantageError(f"AV rate-limited: {data['Information']}")
    if "Error Message" in data:
        raise AlphaVantageError(f"AV error: {data['Error Message']}")
    return data


def get_quote(symbol: str) -> dict:
    """Latest price + change for a symbol."""
    data = _call({"function": "GLOBAL_QUOTE", "symbol": symbol.upper()})
    q = data.get("Global Quote", {})
    return {
        "symbol": q.get("01. symbol"),
        "price": float(q["05. price"]) if q.get("05. price") else None,
        "change": float(q["09. change"]) if q.get("09. change") else None,
        "change_percent": q.get("10. change percent"),
        "volume": int(q["06. volume"]) if q.get("06. volume") else None,
        "latest_trading_day": q.get("07. latest trading day"),
    }


def get_company_overview(symbol: str) -> dict:
    """Fundamentals for a stock."""
    data = _call({"function": "OVERVIEW", "symbol": symbol.upper()})
    keep = [
        "Symbol", "Name", "Sector", "Industry", "MarketCapitalization",
        "PERatio", "PEGRatio", "DividendYield", "EPS", "Beta",
        "52WeekHigh", "52WeekLow", "Description",
    ]
    return {k: data.get(k) for k in keep}


def get_news_sentiment(tickers: str | None = None, topics: str | None = None,
                       limit: int = 20) -> dict:
    """Recent news with sentiment scores. tickers='AAPL,MSFT' or topics='technology,ipo'."""
    p: dict = {"function": "NEWS_SENTIMENT", "limit": limit}
    if tickers:
        p["tickers"] = tickers.upper()
    if topics:
        p["topics"] = topics
    raw = _call(p)
    feed = raw.get("feed", [])[:limit]
    return {
        "items": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "time": item.get("time_published"),
                "summary": item.get("summary"),
                "overall_sentiment_label": item.get("overall_sentiment_label"),
                "overall_sentiment_score": item.get("overall_sentiment_score"),
                "tickers": [t.get("ticker") for t in item.get("ticker_sentiment", [])],
            }
            for item in feed
        ],
        "count": len(feed),
    }


def get_technical(symbol: str, indicator: str = "RSI", interval: str = "daily",
                  time_period: int = 14, series_type: str = "close") -> dict:
    """Technical indicator (RSI, SMA, EMA, MACD, ...) for a symbol."""
    return _call({
        "function": indicator.upper(),
        "symbol": symbol.upper(),
        "interval": interval,
        "time_period": time_period,
        "series_type": series_type,
    })


def get_sector_performance() -> dict:
    """Realtime + lagged sector performance."""
    return _call({"function": "SECTOR"})


def get_fx_rate(from_currency: str, to_currency: str) -> dict:
    data = _call({
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
    })
    rate = data.get("Realtime Currency Exchange Rate", {})
    return {
        "from": rate.get("1. From_Currency Code"),
        "to": rate.get("3. To_Currency Code"),
        "rate": float(rate["5. Exchange Rate"]) if rate.get("5. Exchange Rate") else None,
        "as_of": rate.get("6. Last Refreshed"),
    }
