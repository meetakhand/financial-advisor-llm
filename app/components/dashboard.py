"""Reusable dashboard block — used by 2_Dashboard.py and embedded in Report.

Renders: customer chips, risk band, goal projection, allocation donut,
current-vs-target bars, benchmark stats, HITL log.
"""
from __future__ import annotations

import streamlit as st

from advisor.agents.orchestrator import PipelineResult
from advisor.domain.data import Customer, get_hitl_log

from app.components.charts import (
    allocation_donut, current_vs_target_bars, project_series, projection_line,
)


def _fmt_usd(x: float) -> str: return f"${x:,.0f}"
def _fmt_pct(x: float) -> str: return f"{x:.1f}%"


def render(customer: Customer, result: PipelineResult) -> None:
    """Render the full dashboard block. Idempotent — safe to call from any page."""
    st.subheader(f"{customer.name} · {result.journey}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Age", customer.age)
    c2.metric("Income", _fmt_usd(customer.annual_income),
                help="Annual pre-tax income on file for this customer.")
    c3.metric(
        "Risk band", result.risk.risk_band, f"score {result.risk.risk_score}",
        help=(
            "AI-assigned risk band derived from a blend of **tolerance** (five-question "
            "questionnaire) and **capacity** (age, income, dependents). Bands: "
            "0–34 Moderate · 35–74 Growth · 75–100 Aggressive."
        ),
    )
    c4.metric(
        "Model", result.recommendation.active_model,
        "overridden" if result.recommendation.is_overridden else None,
        help=(
            "The active model portfolio driving the target allocation and rebalancing "
            "actions. Defaults to the AI-suggested band; changes to *overridden* once "
            "the reviewer picks a different model on the Recommendations page."
        ),
    )

    # Warnings from the pipeline
    if result.warnings:
        with st.expander("Pipeline warnings", expanded=False):
            for w in result.warnings:
                st.warning(w)

    st.markdown("### Goal projection")
    goal = result.goal
    g1, g2, g3, g4 = st.columns(4)
    g1.metric(
        "Target (today $)", _fmt_usd(goal.target_amount_today),
        help="Goal amount stated in *today's* dollars — before applying inflation.",
    )
    g2.metric(
        f"Target (yr {int(goal.years)})",
        _fmt_usd(goal.target_amount_future),
        help=(
            "Same goal after inflation compounding to the target year. Retirement "
            "and Buy-Home use CPI ≈ 3%; Child Education uses CPI + 2% education premium."
        ),
    )
    g3.metric(
        "Projected", _fmt_usd(goal.projected_amount),
        _fmt_usd(goal.projected_amount - goal.target_amount_future),
        help=(
            "Deterministic year-end projection of the customer's savings — current "
            "balance compounded at the assumed annual return plus monthly contributions. "
            "Delta shown is *Projected − Target (yr N)*: positive means on track, negative "
            "means a funding gap."
        ),
    )
    g4.metric(
        "Success prob", _fmt_pct(goal.success_prob * 100),
        help=(
            "Rule-based estimate of the probability of hitting the future target, using "
            "a normal-return approximation on the model portfolio's expected return and "
            "volatility. Directional, not a Monte-Carlo output."
        ),
    )

    xs, ys = project_series(
        current_savings=goal.current_savings,
        monthly_contribution=goal.planned_monthly_contribution,
        annual_return=goal.assumed_annual_return,
        years=int(goal.years),
    )
    st.plotly_chart(projection_line(xs, ys, goal.target_amount_future),
                    use_container_width=True)

    st.markdown("### Portfolio")
    port = result.portfolio
    if port.has_holdings:
        p1, p2, p3 = st.columns(3)
        p1.metric(
            "Market value", _fmt_usd(port.total_market_value),
            help=(
                "Σ *units × current price* across all holdings. CASH is priced at "
                "$1.00 per unit. Prices come from live Alpha Vantage → cached CSV "
                "history → seed row, in that order."
            ),
        )
        p2.metric(
            "Gain/Loss", _fmt_usd(port.total_gain_loss),
            _fmt_pct(port.total_gain_loss_pct),
            help=(
                "Unrealised P/L = market value − cost basis. Cost basis is "
                "*units × buy price* per holding as recorded in the seed / onboarding data."
            ),
        )
        p3.metric(
            "# Holdings", len(port.by_holding),
            help="Number of distinct tickers on the customer's book.",
        )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.plotly_chart(allocation_donut(port.allocation_pct), use_container_width=True)
        with col_b:
            active_target = _active_target(result)
            st.plotly_chart(
                current_vs_target_bars(port.allocation_pct, active_target),
                use_container_width=True,
            )

        with st.expander("Holdings (with price freshness)", expanded=False):
            st.dataframe(
                [{
                    "Ticker": h.ticker, "Category": h.category,
                    "Units": h.units, "Buy $": h.buy_price, "Now $": h.current_price,
                    "Freshness": h.price_freshness,
                    "Market Value": h.market_value, "P/L": h.gain_loss,
                    "Asset Class": h.asset_class,
                } for h in port.by_holding],
                use_container_width=True,
            )
    else:
        st.info("No holdings on record. Recommendation uses model target allocation.")

    st.markdown("### Benchmarking")
    st.caption(
        "How the customer's target allocation stacks up against a public reference "
        "portfolio at the same risk band. Higher **excess return** means the target "
        "allocation is expected to outrun the reference on a like-for-like basis; "
        "negative means it lags."
    )
    bm = result.benchmark
    b1, b2 = st.columns([2, 3])
    b1.markdown(
        f"""
        <div class="nw-card">
          <div style="font-size:12px; color:#6B7280; letter-spacing:.06em;
                        text-transform:uppercase;">Proxy benchmark</div>
          <div style="font-size:18px; font-weight:700; padding:4px 0 2px 0;">
            {bm.proxy_ticker}
          </div>
          <div style="font-size:14px; color:#3F4A63;">{bm.proxy_name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with b2:
        r1, r2 = st.columns(2)
        r1.metric(
            "Portfolio return",
            _fmt_pct(bm.portfolio_expected_return * 100),
            help=(
                "Expected annual return of the customer's *target* allocation, "
                "computed as the weighted average of asset-class expected returns "
                "(Moderate/Growth/Aggressive model assumptions). Forward-looking, "
                "not realised."
            ),
        )
        r2.metric(
            "Benchmark return",
            _fmt_pct(bm.benchmark_expected_return * 100),
            _fmt_pct(bm.excess_return * 100),
            help=(
                "Expected annual return of the proxy benchmark for this risk band "
                "(iShares AOM / AOR / AOA). Delta shown below is **excess return** "
                "= portfolio − benchmark. Positive = portfolio expected to beat "
                "the market blend; negative = lagging."
            ),
        )
    st.caption(f"**Underlying blend:** {bm.blend_description}")

    st.markdown("### HITL decision log")
    log = get_hitl_log(customer.id, only_committed=True)
    if not log:
        st.caption("No committed HITL decisions yet.")
    else:
        st.dataframe(
            [{
                "When": r["committed_at"], "Journey": r["journey"],
                "AI suggested": r["ai_suggested"], "Final": r["final_choice"],
                "Action": r["final_action"], "Rationale": r["rationale"] or "",
            } for r in log],
            use_container_width=True,
        )


def _active_target(result: PipelineResult) -> dict[str, float]:
    if result.recommendation.custom_allocation:
        return result.recommendation.custom_allocation
    for o in result.recommendation.options:
        if o.model == result.recommendation.active_model:
            return o.target_allocation_pct
    return {}
