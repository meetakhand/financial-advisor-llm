"""Recommendation logic: 3-option builder + fit + rebalancing.

Given the AI-suggested band, produce 3 candidate options centered on it:
one band below (if any), the AI-suggested, and one band above (if any).
Each option carries the model's asset-class target, drift vs current
holdings, and rebalancing actions when drift >= 5% on any class.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from advisor.domain.calculators import drift, rebalancing_actions
from advisor.domain.models import (
    MODEL_ASSUMPTIONS, MODEL_HOLDINGS, MODEL_ORDER, asset_class_allocation,
)


@dataclass(frozen=True)
class InvestmentOption:
    model: str                    # Moderate / Growth / Aggressive
    is_ai_suggested: bool
    target_allocation_pct: dict[str, float]     # asset class -> %
    ticker_holdings: list[dict]                 # for the UI table
    expected_return: float
    volatility: float
    drift_from_current: dict[str, float]        # asset class -> %pts (pos = overweight)
    rebalancing_actions: list[dict]             # trim/add per class
    fit_score: float                            # 0-100, higher = closer to current


@dataclass
class RecommendationBundle:
    ai_suggested: str                           # Moderate / Growth / Aggressive
    active_model: str                           # what the user picked (== ai_suggested unless overridden)
    options: list[InvestmentOption]
    is_overridden: bool = False
    override_note: str = ""
    custom_allocation: dict[str, float] | None = None
    text_recommendations: list[str] = field(default_factory=list)


def _fit_score(current_pct: dict[str, float], target_pct: dict[str, float]) -> float:
    """Higher score = closer to current. 100 - sum of absolute drift, clipped."""
    d = drift(current_pct, target_pct)
    total_abs = sum(abs(v) for v in d.values())
    return round(max(0.0, 100.0 - total_abs / 2), 1)  # divide by 2 since drift double-counts


def _ticker_view(model_name: str) -> list[dict]:
    return [
        {
            "ticker": h.ticker,
            "category": h.category,
            "weight_pct": round(h.weight * 100, 2),
            "asset_class": h.asset_class,
            "description": h.description,
        }
        for h in MODEL_HOLDINGS[model_name]
    ]


def _build_option(model_name: str, current_pct: dict[str, float],
                    is_ai: bool) -> InvestmentOption:
    target_pct = asset_class_allocation(model_name)
    d = drift(current_pct, target_pct)
    actions = rebalancing_actions(current_pct, target_pct)
    return InvestmentOption(
        model=model_name,
        is_ai_suggested=is_ai,
        target_allocation_pct=target_pct,
        ticker_holdings=_ticker_view(model_name),
        expected_return=MODEL_ASSUMPTIONS[model_name]["expected_return"],
        volatility=MODEL_ASSUMPTIONS[model_name]["volatility"],
        drift_from_current=d,
        rebalancing_actions=actions,
        fit_score=_fit_score(current_pct, target_pct),
    )


def build_options(ai_suggested: str, current_pct: dict[str, float]) -> list[InvestmentOption]:
    """Three options centered on ai_suggested (one below, itself, one above).

    At the tails of MODEL_ORDER we only have two neighbours — return however
    many exist without padding.
    """
    if ai_suggested not in MODEL_ORDER:
        raise ValueError(f"Unknown model: {ai_suggested}")
    idx = MODEL_ORDER.index(ai_suggested)
    picked = []
    for offset in (-1, 0, 1):
        j = idx + offset
        if 0 <= j < len(MODEL_ORDER):
            picked.append(MODEL_ORDER[j])
    return [_build_option(m, current_pct, is_ai=(m == ai_suggested)) for m in picked]


def _text_bullets(bundle_model: str, options: list[InvestmentOption]) -> list[str]:
    """Deterministic bullet lines the Report uses when the LLM is off."""
    bullets = []
    for o in options:
        label = " (AI-suggested)" if o.is_ai_suggested else ""
        bullets.append(
            f"{o.model}{label}: expected {o.expected_return:.1%} return / "
            f"{o.volatility:.1%} vol · fit {o.fit_score:.0f}/100"
        )
        if o.rebalancing_actions:
            actions = "; ".join(
                f"{a['action']} {a['asset_class']} by {a['delta_pct']:.0f}pp"
                for a in o.rebalancing_actions
            )
            bullets.append(f"  rebalancing: {actions}")
    return bullets


def run_recommendation(ai_suggested: str,
                        current_pct: dict[str, float]) -> RecommendationBundle:
    options = build_options(ai_suggested, current_pct)
    return RecommendationBundle(
        ai_suggested=ai_suggested,
        active_model=ai_suggested,
        options=options,
        text_recommendations=_text_bullets(ai_suggested, options),
    )


def apply_model_override(bundle: RecommendationBundle, chosen_model: str,
                          rationale: str) -> RecommendationBundle:
    if chosen_model not in MODEL_ORDER:
        raise ValueError(f"Unknown override model: {chosen_model}")
    bundle.active_model = chosen_model
    bundle.is_overridden = chosen_model != bundle.ai_suggested
    bundle.override_note = rationale
    return bundle


def apply_custom_allocation_override(bundle: RecommendationBundle,
                                       custom_pct: dict[str, float],
                                       rationale: str) -> RecommendationBundle:
    total = sum(custom_pct.values())
    if abs(total - 100.0) > 0.5:
        raise ValueError(f"Custom allocation must sum to 100, got {total:.1f}")
    bundle.active_model = "custom"
    bundle.custom_allocation = {k: round(v, 2) for k, v in custom_pct.items()}
    bundle.is_overridden = True
    bundle.override_note = rationale
    return bundle
