from advisor.tools import calculators as c


def test_retirement_grows():
    res = c.retirement_projection(30, 60, 50_000, 1500, 0.07)
    assert res["future_value"] > 50_000
    assert res["years"] == 30


def test_retirement_invalid():
    res = c.retirement_projection(60, 30, 0, 0)
    assert "error" in res


def test_savings_goal_basic():
    res = c.savings_goal(500_000, 20, 0.06)
    assert res["monthly_contribution"] > 0


def test_savings_goal_zero_return():
    res = c.savings_goal(120_000, 10, 0.0)
    assert res["monthly_contribution"] == 1000.0


def test_asset_allocation_bounds():
    res = c.asset_allocation(35, "moderate")
    assert 20 <= res["stocks_pct"] <= 95
    assert res["stocks_pct"] + res["bonds_pct"] + res["cash_pct"] == 100


def test_asset_allocation_bad_risk():
    assert "error" in c.asset_allocation(35, "extreme")


def test_debt_payoff_pays_down():
    res = c.debt_payoff(20_000, 0.22, 600)
    assert res["months_to_payoff"] > 0
    assert res["total_interest"] > 0


def test_debt_payoff_undercoverage():
    res = c.debt_payoff(20_000, 0.22, 100)
    assert "error" in res


def test_emergency_fund():
    res = c.emergency_fund(3000, 6)
    assert res["target_amount"] == 18_000
