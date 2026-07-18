"""Model portfolios — ticker-level composition per risk band.

Source of truth: corpus/client_portfolio_reference.md (from Client portfolio
data V1.0, 2026-07-12). Three portfolios: Moderate / Growth / Aggressive.

Two layers:
  1. MODEL_HOLDINGS   — ticker-level target composition (weights sum to 1.0)
  2. ASSET_CLASS_PCT  — rolled-up asset-class allocation derived from layer 1

For blended vehicles (Mutual Funds, Pension Baseline Funds), we treat them as
partial equity / partial fixed-income exposure per the mapping in the corpus
doc, so asset-class rollups stay honest.
"""
from __future__ import annotations

from dataclasses import dataclass

# Asset classes used for portfolio-analysis rollups.
ASSET_CLASSES = ["Equity", "International", "Fixed Income", "Pension", "Cash"]

# Investment-category taxonomy (from the PDF). Used in the UI's Current
# Portfolio step so users can describe their holdings in familiar terms.
INVESTMENT_CATEGORIES = [
    "Individual Equity", "Exchange Traded Fund", "Mutual Fund",
    "Fixed Income", "Pension Baseline Fund",
]

# Blended-vehicle equity/fixed-income splits (per corpus reference).
BLENDED_VEHICLE_SPLIT = {
    "VFIAX": {"Equity": 1.0},          # S&P 500 — treat as pure US equity
    "VTSAX": {"Equity": 1.0},          # Total US market — pure US equity
    "FCNTX": {"Equity": 1.0},          # Large-cap growth — pure equity
    "VFORX": {"Equity": 0.6, "Fixed Income": 0.4},   # TDF 2040 balanced
    "VFIFX": {"Equity": 0.7, "Fixed Income": 0.3},   # TDF 2050 growth-tilted
    "VFFVX": {"Equity": 0.85, "Fixed Income": 0.15}, # TDF 2055 aggressive
}


@dataclass(frozen=True)
class ModelHolding:
    ticker: str
    category: str          # from INVESTMENT_CATEGORIES
    weight: float          # 0.0 - 1.0
    asset_class: str       # primary asset class (see ASSET_CLASSES)
    description: str


MODEL_ORDER = ["Moderate", "Growth", "Aggressive"]


MODEL_HOLDINGS: dict[str, list[ModelHolding]] = {
    "Moderate": [
        ModelHolding("AAPL",  "Individual Equity",    0.10, "Equity",        "Mega-cap Growth"),
        ModelHolding("MSFT",  "Individual Equity",    0.10, "Equity",        "Mega-cap Tech/Stability"),
        ModelHolding("VTI",   "Exchange Traded Fund", 0.20, "Equity",        "Broad US Market"),
        ModelHolding("VXUS",  "Exchange Traded Fund", 0.10, "International", "Global Diversification"),
        ModelHolding("VFIAX", "Mutual Fund",          0.10, "Equity",        "Core Large Cap"),
        ModelHolding("AGG",   "Fixed Income",         0.15, "Fixed Income",  "Total US Bond Market"),
        ModelHolding("BND",   "Fixed Income",         0.15, "Fixed Income",  "Govt/Corporate Bond Mix"),
        ModelHolding("VFORX", "Pension Baseline Fund",0.10, "Pension",       "Target Retirement 2040"),
    ],
    "Growth": [
        ModelHolding("MSFT",  "Individual Equity",    0.10, "Equity",        "Enterprise/Cloud Growth"),
        ModelHolding("GOOGL", "Individual Equity",    0.10, "Equity",        "Digital Advertising/AI"),
        ModelHolding("QQQ",   "Exchange Traded Fund", 0.20, "Equity",        "Tech & Innovation Large-Cap"),
        ModelHolding("VXUS",  "Exchange Traded Fund", 0.10, "International", "Global Markets"),
        ModelHolding("VTSAX", "Mutual Fund",          0.15, "Equity",        "Broad US Index"),
        ModelHolding("FCNTX", "Mutual Fund",          0.10, "Equity",        "Large-Cap Growth Focused"),
        ModelHolding("AGG",   "Fixed Income",         0.15, "Fixed Income",  "Core Fixed Income"),
        ModelHolding("VFIFX", "Pension Baseline Fund",0.10, "Pension",       "Target Retirement 2050"),
    ],
    "Aggressive": [
        ModelHolding("NVDA",  "Individual Equity",    0.15, "Equity",        "High-Growth Tech/AI"),
        ModelHolding("AMZN",  "Individual Equity",    0.10, "Equity",        "E-commerce/Cloud Growth"),
        ModelHolding("QQQ",   "Exchange Traded Fund", 0.25, "Equity",        "Tech & Growth Heavy"),
        ModelHolding("IWM",   "Exchange Traded Fund", 0.10, "Equity",        "Small-Cap Growth"),
        ModelHolding("VXUS",  "Exchange Traded Fund", 0.10, "International", "Global Diversification"),
        ModelHolding("VFIAX", "Mutual Fund",          0.15, "Equity",        "Core S&P 500"),
        ModelHolding("VBTLX", "Fixed Income",         0.05, "Fixed Income",  "Total Bond Market"),
        ModelHolding("VFFVX", "Pension Baseline Fund",0.10, "Pension",       "Target Retirement 2055 (Aggressive)"),
    ],
}


# Illustrative long-run return / volatility assumptions per model portfolio.
# Used by Goal Planning success-probability math and Report narration.
MODEL_ASSUMPTIONS = {
    "Moderate":   {"expected_return": 0.075, "volatility": 0.10},
    "Growth":     {"expected_return": 0.095, "volatility": 0.13},
    "Aggressive": {"expected_return": 0.115, "volatility": 0.17},
}


def asset_class_allocation(model_name: str) -> dict[str, float]:
    """Roll ticker-level MODEL_HOLDINGS up into asset-class percentages.

    Blended vehicles are split per BLENDED_VEHICLE_SPLIT so the rollup is
    honest (e.g. VFORX contributes 60% to Equity and 40% to Fixed Income).
    """
    if model_name not in MODEL_HOLDINGS:
        raise ValueError(f"Unknown model: {model_name}")
    alloc: dict[str, float] = {ac: 0.0 for ac in ASSET_CLASSES}
    for h in MODEL_HOLDINGS[model_name]:
        split = BLENDED_VEHICLE_SPLIT.get(h.ticker)
        if split is None:
            alloc[h.asset_class] += h.weight
        else:
            for ac, frac in split.items():
                alloc[ac] += h.weight * frac
    return {ac: round(v * 100, 2) for ac, v in alloc.items()}


def band_for_score(score: float) -> str:
    """Risk score → model band. 3 bands only (no Conservative — see plan)."""
    if score < 55:
        return "Moderate"
    if score < 75:
        return "Growth"
    return "Aggressive"


def total_weight(model_name: str) -> float:
    return round(sum(h.weight for h in MODEL_HOLDINGS[model_name]), 4)


# Sanity: every model must sum to 1.0. Fails loud at import time if a table
# is edited incorrectly.
for _name in MODEL_ORDER:
    _t = total_weight(_name)
    if abs(_t - 1.0) > 1e-6:
        raise ValueError(f"Model {_name} weights sum to {_t}, expected 1.0")
