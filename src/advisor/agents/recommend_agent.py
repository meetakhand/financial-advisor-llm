"""Recommendation Agent — thin wrapper over domain/recommend."""
from __future__ import annotations

from advisor.domain.recommend import (
    RecommendationBundle, apply_custom_allocation_override, apply_model_override,
    run_recommendation as _run,
)


def run_recommendation(ai_suggested: str,
                        current_allocation_pct: dict[str, float]) -> RecommendationBundle:
    return _run(ai_suggested, current_allocation_pct)


__all__ = [
    "RecommendationBundle", "run_recommendation",
    "apply_model_override", "apply_custom_allocation_override",
]
