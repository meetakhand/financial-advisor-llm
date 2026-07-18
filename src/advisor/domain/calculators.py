"""Financial math: FV, SIP, drift, success probability.

All functions are pure and deterministic — no LLM, no I/O. The Goal Planning
and Recommendation agents call these; the LLM only narrates the results.
"""
from __future__ import annotations

import math

US_INFLATION = 0.03                    # long-run US CPI assumption
EDUCATION_INFLATION_PREMIUM = 0.02     # education inflation ≈ CPI + 2%


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def future_value(present_value: float, annual_rate: float, years: float) -> float:
    """FV of a lump sum compounded annually."""
    if years <= 0:
        return present_value
    return present_value * ((1 + annual_rate) ** years)


def future_value_annuity(monthly_contribution: float, annual_rate: float, years: float) -> float:
    """FV of a monthly SIP compounded monthly."""
    if years <= 0 or monthly_contribution <= 0:
        return 0.0
    n = years * 12
    r = annual_rate / 12
    if r == 0:
        return monthly_contribution * n
    return monthly_contribution * (((1 + r) ** n - 1) / r)


def project_portfolio(current_savings: float, monthly_contribution: float,
                       annual_rate: float, years: float) -> float:
    """Combined projection: lump-sum FV + monthly-SIP FV."""
    return (future_value(current_savings, annual_rate, years)
            + future_value_annuity(monthly_contribution, annual_rate, years))


def required_monthly_sip(target: float, current_savings: float,
                          annual_rate: float, years: float) -> float:
    """Solve for the monthly contribution that reaches ``target`` in ``years``.

    Returns 0 if the lump-sum future value alone already meets or exceeds
    ``target`` — no additional SIP required.
    """
    if years <= 0:
        return max(target - current_savings, 0.0)
    lump_fv = future_value(current_savings, annual_rate, years)
    remaining = max(target - lump_fv, 0.0)
    if remaining <= 0:
        return 0.0
    n = years * 12
    r = annual_rate / 12
    if r == 0:
        return remaining / n
    return remaining * r / ((1 + r) ** n - 1)


def inflate(present_amount: float, years: float, inflation: float = US_INFLATION) -> float:
    """Inflate a present-day amount to a future year."""
    return present_amount * ((1 + inflation) ** years)


def success_probability(projected: float, target: float, volatility: float) -> float:
    """Rough success probability that the portfolio meets ``target``.

    Models the projected value as normally distributed with mean=projected and
    std = projected * volatility, and computes P(X >= target). Volatility here
    is the annualized portfolio std-dev (from MODEL_ASSUMPTIONS). This is a
    demo-grade approximation, not a Monte Carlo — but it captures the
    "further gap = lower probability" intuition the report needs.
    """
    if projected <= 0:
        return 0.0
    if target <= 0:
        return 1.0
    std = max(projected * volatility, 1e-6)
    z = (target - projected) / std
    # 1 - Phi(z), using erf-based normal CDF
    return clamp(0.5 * (1 - math.erf(z / math.sqrt(2))), 0.0, 1.0)


def drift(current_pct: dict[str, float], target_pct: dict[str, float]) -> dict[str, float]:
    """Per-asset-class drift = current% - target%. Positive = overweight."""
    classes = set(current_pct) | set(target_pct)
    return {ac: round(current_pct.get(ac, 0.0) - target_pct.get(ac, 0.0), 2)
            for ac in classes}


def max_abs_drift(drift_map: dict[str, float]) -> float:
    if not drift_map:
        return 0.0
    return max(abs(v) for v in drift_map.values())


def rebalancing_actions(current_pct: dict[str, float], target_pct: dict[str, float],
                         min_drift_pct: float = 5.0) -> list[dict]:
    """Generate rebalancing actions when |drift| >= min_drift_pct on any class.

    Returns a list of dicts:
        {"asset_class": ..., "action": "trim"|"add", "delta_pct": ...}
    Empty list when no class exceeds the threshold.
    """
    d = drift(current_pct, target_pct)
    if max_abs_drift(d) < min_drift_pct:
        return []
    actions = []
    for ac, delta in sorted(d.items(), key=lambda kv: -abs(kv[1])):
        if abs(delta) < min_drift_pct:
            continue
        actions.append({
            "asset_class": ac,
            "action": "trim" if delta > 0 else "add",
            "delta_pct": round(abs(delta), 2),
        })
    return actions
