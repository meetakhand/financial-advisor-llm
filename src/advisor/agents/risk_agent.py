"""Risk Profiling Agent — thin wrapper over domain/risk + domain/models."""
from __future__ import annotations

from advisor.domain.models import MODEL_HOLDINGS
from advisor.domain.risk import RiskResult, compute_risk


def run_risk_profiling(answer_points: list[int], age: int, annual_income: float,
                        dependents: int) -> tuple[RiskResult, str]:
    """Compute risk band + return (RiskResult, model_name).

    Model name equals the risk band (Moderate / Growth / Aggressive).
    """
    result = compute_risk(answer_points, age, annual_income, dependents)
    if result.risk_band not in MODEL_HOLDINGS:
        raise RuntimeError(f"Risk band {result.risk_band!r} has no model portfolio")
    return result, result.risk_band
