"""Risk Profiling: tolerance + capacity -> risk_score -> band.

Rules:
  tolerance = 20 + (sum(answer_points) / (N*3)) * 70   clamped to [0, 100]
  capacity  = f(age, annual_income, dependents)         clamped to [20, 100]
  risk_score = round(0.6 * tolerance + 0.4 * capacity)

Bands (3-band world, no Conservative):
  <55   Moderate
  55-74 Growth
  >=75  Aggressive
"""
from __future__ import annotations

from dataclasses import dataclass

from advisor.domain.models import band_for_score


QUESTIONNAIRE = [
    {
        "id": "market_drop",
        "question": "If your portfolio dropped 20% in a month, what would you do?",
        "options": [
            ("Sell everything to avoid further loss", 0),
            ("Sell some to reduce risk", 1),
            ("Hold and wait it out", 2),
            ("Buy more while prices are low", 3),
        ],
    },
    {
        "id": "experience",
        "question": "How would you describe your investing experience?",
        "options": [
            ("None — I'm just starting out", 0),
            ("Basic — mostly savings accounts / CDs", 1),
            ("Moderate — mutual funds / ETFs for a few years", 2),
            ("Extensive — stocks, options, or active trading", 3),
        ],
    },
    {
        "id": "priority",
        "question": "Which matters more to you?",
        "options": [
            ("Protecting what I have", 0),
            ("A mix of protection and growth, leaning safe", 1),
            ("A mix of protection and growth, leaning growth", 2),
            ("Maximizing long-term growth", 3),
        ],
    },
    {
        "id": "volatility_comfort",
        "question": "How comfortable are you with your investment value swinging up and down?",
        "options": [
            ("Very uncomfortable", 0),
            ("Somewhat uncomfortable", 1),
            ("Fairly comfortable", 2),
            ("Very comfortable", 3),
        ],
    },
    {
        "id": "goal_flexibility",
        "question": "If this goal were delayed by a market downturn, how would that affect you?",
        "options": [
            ("Unacceptable — I need the funds on schedule", 0),
            ("Difficult but manageable", 1),
            ("Minor inconvenience", 2),
            ("No real impact — I'm flexible", 3),
        ],
    },
]


@dataclass(frozen=True)
class RiskResult:
    tolerance: float
    capacity: float
    risk_score: int
    risk_band: str          # Moderate / Growth / Aggressive
    description: str        # plain-language explanation


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_tolerance(answer_points: list[int]) -> float:
    n = len(answer_points)
    if n == 0:
        return 50.0
    avg_fraction = sum(answer_points) / (n * 3)
    return _clamp(20 + avg_fraction * 70, 0, 100)


def compute_capacity(age: int, annual_income: float, dependents: int) -> float:
    """Blend investment horizon, income level, dependents into a 20–100 score."""
    horizon_years = max(60 - age, 0)
    horizon_score = _clamp((horizon_years / 35) * 100, 0, 100)

    low, high = 40_000, 400_000
    if annual_income <= low:
        income_score = 30.0
    elif annual_income >= high:
        income_score = 100.0
    else:
        income_score = 30 + (annual_income - low) / (high - low) * 70

    dependents_penalty = _clamp(dependents * 8, 0, 40)
    base_stability = 60.0

    capacity = (0.4 * horizon_score + 0.35 * income_score +
                0.25 * base_stability) - dependents_penalty
    return _clamp(capacity, 20, 100)


BAND_DESCRIPTIONS = {
    "Moderate": (
        "Balanced 60/40-style allocation. Accepts moderate short-term volatility "
        "in exchange for steady long-term growth. Suited to investors with a "
        "medium horizon and a preference for a mix of protection and growth."
    ),
    "Growth": (
        "Growth-tilted 80/20-style allocation. Higher expected long-term returns "
        "and larger short-term drawdowns. Suited to investors with a long horizon "
        "and comfort watching portfolio values swing."
    ),
    "Aggressive": (
        "Aggressive 85/15-style allocation, heavy in equities and growth-oriented "
        "funds. Highest expected long-term return, largest short-term drawdowns. "
        "Suited to investors with a long horizon and high tolerance for volatility."
    ),
}


def compute_risk(answer_points: list[int], age: int, annual_income: float,
                  dependents: int) -> RiskResult:
    tolerance = compute_tolerance(answer_points)
    capacity = compute_capacity(age, annual_income, dependents)
    score = round(0.6 * tolerance + 0.4 * capacity)
    band = band_for_score(score)
    return RiskResult(
        tolerance=round(tolerance, 1),
        capacity=round(capacity, 1),
        risk_score=int(score),
        risk_band=band,
        description=BAND_DESCRIPTIONS[band],
    )
