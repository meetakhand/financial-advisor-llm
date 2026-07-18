"""Domain math + models + risk sanity tests."""
import pytest

from advisor.domain.calculators import (
    drift, future_value, future_value_annuity, inflate, project_portfolio,
    rebalancing_actions, required_monthly_sip, success_probability,
)
from advisor.domain.models import (
    ASSET_CLASSES, MODEL_HOLDINGS, MODEL_ORDER, asset_class_allocation,
    band_for_score,
)
from advisor.domain.risk import compute_capacity, compute_risk, compute_tolerance


# --- calculators -----------------------------------------------------------

def test_future_value_compounds():
    assert future_value(1000, 0.05, 10) == pytest.approx(1000 * 1.05 ** 10, rel=1e-6)


def test_future_value_zero_years():
    assert future_value(1000, 0.05, 0) == 1000


def test_annuity_zero_rate_is_linear():
    # $100/month for 5 years at 0% = 6000
    assert future_value_annuity(100, 0.0, 5) == pytest.approx(6000)


def test_project_portfolio_positive_growth():
    fv = project_portfolio(50_000, 500, 0.07, 30)
    assert fv > 50_000


def test_required_sip_when_lumpsum_covers():
    # $10,000 at 7% for 30 years FV is already > $50k target
    assert required_monthly_sip(50_000, 10_000, 0.07, 30) == 0.0


def test_required_sip_when_gap():
    sip = required_monthly_sip(1_000_000, 50_000, 0.07, 25)
    assert sip > 0


def test_inflate_positive():
    assert inflate(1000, 10, 0.03) == pytest.approx(1000 * 1.03 ** 10, rel=1e-6)


def test_success_probability_bounds():
    # Way over target -> ~1.0; way under -> ~0.0
    assert success_probability(1_000_000, 500_000, 0.15) > 0.9
    assert success_probability(100_000, 500_000, 0.15) < 0.1


def test_drift_and_rebalance():
    current = {"Equity": 80, "Fixed Income": 15, "Cash": 5}
    target  = {"Equity": 60, "Fixed Income": 30, "Cash": 10}
    d = drift(current, target)
    assert d["Equity"] == pytest.approx(20)
    actions = rebalancing_actions(current, target)
    equity = next(a for a in actions if a["asset_class"] == "Equity")
    assert equity["action"] == "trim"


def test_rebalance_below_threshold_returns_empty():
    current = {"Equity": 61, "Fixed Income": 39}
    target  = {"Equity": 60, "Fixed Income": 40}
    assert rebalancing_actions(current, target, min_drift_pct=5.0) == []


# --- models ----------------------------------------------------------------

def test_model_weights_sum_to_one():
    for name in MODEL_ORDER:
        total = sum(h.weight for h in MODEL_HOLDINGS[name])
        assert total == pytest.approx(1.0, abs=1e-6), name


def test_asset_class_allocation_sums_to_100():
    for name in MODEL_ORDER:
        alloc = asset_class_allocation(name)
        assert sum(alloc.values()) == pytest.approx(100.0, abs=0.5), name
        assert set(alloc.keys()) <= set(ASSET_CLASSES)


def test_band_for_score():
    assert band_for_score(30) == "Moderate"
    assert band_for_score(55) == "Growth"
    assert band_for_score(74) == "Growth"
    assert band_for_score(75) == "Aggressive"
    assert band_for_score(95) == "Aggressive"


# --- risk ------------------------------------------------------------------

def test_tolerance_bounds():
    assert 0.0 <= compute_tolerance([0, 0, 0, 0, 0]) <= 100.0
    assert compute_tolerance([3, 3, 3, 3, 3]) == pytest.approx(90.0)


def test_capacity_bounds():
    c = compute_capacity(30, 100_000, 0)
    assert 20 <= c <= 100


def test_risk_yields_supported_band():
    r = compute_risk([2, 2, 2, 2, 2], age=35, annual_income=120_000, dependents=1)
    assert r.risk_band in MODEL_ORDER
