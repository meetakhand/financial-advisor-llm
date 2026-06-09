"""Deterministic financial calculators. Pure functions, easy to test."""
from __future__ import annotations

import math


def retirement_projection(
    current_age: int,
    retire_age: int,
    current_savings: float,
    monthly_contribution: float,
    annual_return: float = 0.07,
) -> dict:
    """Project retirement portfolio value with monthly compounding."""
    if retire_age <= current_age:
        return {"error": "retire_age must exceed current_age"}
    months = (retire_age - current_age) * 12
    r = annual_return / 12
    fv = current_savings * (1 + r) ** months
    if r > 0:
        fv += monthly_contribution * (((1 + r) ** months - 1) / r)
    else:
        fv += monthly_contribution * months
    return {
        "future_value": round(fv, 2),
        "years": retire_age - current_age,
        "monthly_contribution": monthly_contribution,
        "assumed_return": annual_return,
    }


def savings_goal(target: float, years: int, annual_return: float = 0.05) -> dict:
    """Required monthly contribution to hit a target value."""
    if years <= 0:
        return {"error": "years must be positive"}
    months = years * 12
    r = annual_return / 12
    if r == 0:
        monthly = target / months
    else:
        monthly = target * r / ((1 + r) ** months - 1)
    return {
        "monthly_contribution": round(monthly, 2),
        "target": target,
        "years": years,
        "assumed_return": annual_return,
    }


def asset_allocation(age: int, risk_tolerance: str) -> dict:
    """Glide-path style allocation (stocks/bonds/cash). risk_tolerance in {low,moderate,high}."""
    if risk_tolerance not in ("low", "moderate", "high"):
        return {"error": "risk_tolerance must be low|moderate|high"}
    base_equity = max(20, 110 - age)
    adj = {"low": -15, "moderate": 0, "high": 10}[risk_tolerance]
    eq = max(20, min(95, base_equity + adj))
    bonds = 100 - eq - 5
    return {"stocks_pct": eq, "bonds_pct": bonds, "cash_pct": 5,
            "rationale": f"Glide path = 110 - age ({110 - age}%) adjusted for {risk_tolerance} risk."}


def debt_payoff(balance: float, apr: float, monthly_payment: float) -> dict:
    """Months to pay off and total interest paid (fixed monthly payment)."""
    r = apr / 12
    if monthly_payment <= balance * r:
        return {"error": "Payment does not cover interest — debt grows."}
    n = math.log(monthly_payment / (monthly_payment - balance * r)) / math.log(1 + r)
    return {
        "months_to_payoff": round(n, 1),
        "years_to_payoff": round(n / 12, 1),
        "total_paid": round(monthly_payment * n, 2),
        "total_interest": round(monthly_payment * n - balance, 2),
    }


def emergency_fund(monthly_expenses: float, months_target: int = 6) -> dict:
    return {
        "target_amount": round(monthly_expenses * months_target, 2),
        "months_target": months_target,
    }
