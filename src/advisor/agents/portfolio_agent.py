"""Portfolio Analysis Agent — value + allocation from user holdings.

Uses live prices via advisor.domain.prices (three-tier: AV → CSV → seed).
Rolls up asset-class allocation using the same blended-vehicle splits as
domain/models.py, so current% and target% are directly comparable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from advisor.domain.data import Holding
from advisor.domain.models import ASSET_CLASSES, BLENDED_VEHICLE_SPLIT
from advisor.domain.prices import PriceLookup, get_price


# Category → primary asset class fallback when a ticker isn't in a model.
CATEGORY_TO_ASSET_CLASS = {
    "Individual Equity":    "Equity",
    "Exchange Traded Fund": "Equity",   # per-ticker override happens in the split map
    "Mutual Fund":          "Equity",
    "Fixed Income":         "Fixed Income",
    "Pension Baseline Fund":"Pension",
    "Cash":                 "Cash",
}

# Ticker → primary asset class when the category alone isn't enough (e.g.
# international ETF VXUS is a category=ETF but asset class=International).
TICKER_ASSET_CLASS = {
    "VXUS": "International", "IWM": "Equity",
    "AGG": "Fixed Income", "BND": "Fixed Income", "VBTLX": "Fixed Income",
    "AOM": "Equity", "AOR": "Equity", "AOA": "Equity",
    "CASH": "Cash",
}


@dataclass(frozen=True)
class HoldingView:
    ticker: str
    category: str
    units: float
    buy_price: float
    current_price: float
    price_freshness: str
    market_value: float
    cost_basis: float
    gain_loss: float
    gain_loss_pct: float
    asset_class: str


@dataclass
class PortfolioAnalysis:
    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    total_gain_loss: float = 0.0
    total_gain_loss_pct: float = 0.0
    allocation_pct: dict[str, float] = field(default_factory=dict)
    allocation_value: dict[str, float] = field(default_factory=dict)
    by_holding: list[HoldingView] = field(default_factory=list)
    has_holdings: bool = False
    price_sources: dict[str, str] = field(default_factory=dict)  # ticker -> freshness


def _asset_class_for(holding: Holding) -> str:
    if holding.ticker in TICKER_ASSET_CLASS:
        return TICKER_ASSET_CLASS[holding.ticker]
    return CATEGORY_TO_ASSET_CLASS.get(holding.category, "Equity")


def _split_market_value(holding: Holding, primary_class: str,
                         market_value: float) -> dict[str, float]:
    """If the ticker is a blended vehicle, split its market value across
    asset classes per BLENDED_VEHICLE_SPLIT. Else it all lands on primary_class.
    """
    split = BLENDED_VEHICLE_SPLIT.get(holding.ticker)
    if split is None:
        return {primary_class: market_value}
    return {ac: market_value * frac for ac, frac in split.items()}


def analyze_portfolio(holdings: list[Holding], *, allow_live: bool = True) -> PortfolioAnalysis:
    if not holdings:
        return PortfolioAnalysis(
            allocation_pct={ac: 0.0 for ac in ASSET_CLASSES},
            allocation_value={ac: 0.0 for ac in ASSET_CLASSES},
        )

    allocation_value = {ac: 0.0 for ac in ASSET_CLASSES}
    price_sources: dict[str, str] = {}
    views: list[HoldingView] = []
    total_mv = 0.0
    total_cb = 0.0

    for h in holdings:
        lookup: PriceLookup = get_price(h.ticker, allow_live=allow_live)
        price = lookup.price if lookup.price > 0 else h.buy_price
        mv = h.units * price
        cb = h.units * h.buy_price
        pl = mv - cb
        pl_pct = (pl / cb * 100) if cb else 0.0
        primary_class = _asset_class_for(h)
        for ac, val in _split_market_value(h, primary_class, mv).items():
            allocation_value[ac] = allocation_value.get(ac, 0.0) + val

        views.append(HoldingView(
            ticker=h.ticker, category=h.category, units=h.units,
            buy_price=h.buy_price, current_price=price,
            price_freshness=lookup.freshness, market_value=round(mv, 2),
            cost_basis=round(cb, 2), gain_loss=round(pl, 2),
            gain_loss_pct=round(pl_pct, 2), asset_class=primary_class,
        ))
        price_sources[h.ticker] = lookup.freshness
        total_mv += mv
        total_cb += cb

    allocation_pct = {
        ac: (round(v / total_mv * 100, 2) if total_mv else 0.0)
        for ac, v in allocation_value.items()
    }
    total_pl = total_mv - total_cb
    total_pl_pct = (total_pl / total_cb * 100) if total_cb else 0.0

    return PortfolioAnalysis(
        total_market_value=round(total_mv, 2),
        total_cost_basis=round(total_cb, 2),
        total_gain_loss=round(total_pl, 2),
        total_gain_loss_pct=round(total_pl_pct, 2),
        allocation_pct=allocation_pct,
        allocation_value={ac: round(v, 2) for ac, v in allocation_value.items()},
        by_holding=views,
        has_holdings=True,
        price_sources=price_sources,
    )
