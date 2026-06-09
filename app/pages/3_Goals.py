"""Goals page — retirement, savings, debt-payoff projections + LLM commentary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from advisor.agent.memory import load_profile  # noqa: E402
from advisor.agent.react import run as agent_run  # noqa: E402
from advisor.rag.retrieve import HybridRetriever  # noqa: E402
from advisor.tools.calculators import (  # noqa: E402
    debt_payoff,
    retirement_projection,
    savings_goal,
)

st.title("Goal-Based Planning")


@st.cache_resource
def get_retriever() -> HybridRetriever:
    return HybridRetriever()


goal = st.selectbox("Pick a goal", ["Retirement", "Savings target", "Debt payoff"])

if goal == "Retirement":
    c1, c2, c3 = st.columns(3)
    with c1:
        cur_age = st.number_input("Current age", 18, 90, 30)
        retire_age = st.number_input("Retirement age", 30, 100, 65)
    with c2:
        cur_savings = st.number_input("Current savings ($)", 0, 100_000_000, 50_000, 1_000)
        monthly = st.number_input("Monthly contribution ($)", 0, 1_000_000, 1_500, 100)
    with c3:
        ann_return = st.slider("Assumed annual return", 0.01, 0.12, 0.07, 0.005)

    res = retirement_projection(cur_age, retire_age, cur_savings, monthly, ann_return)
    if "error" in res:
        st.error(res["error"])
    else:
        st.metric("Projected portfolio at retirement", f"${res['future_value']:,.0f}")

        years = list(range(cur_age, retire_age + 1))
        # Year-by-year projection for the chart
        r_m = ann_return / 12
        bal = cur_savings
        path = []
        for y in years:
            for _ in range(12):
                bal = bal * (1 + r_m) + monthly
            path.append({"age": y, "value": bal})
        df = pd.DataFrame(path)
        fig = px.line(df, x="age", y="value", title="Projected Portfolio Path", markers=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Agent Commentary")
        user_id = st.session_state.get("user_id", "demo-user")
        profile = load_profile(user_id)
        msg = (f"My retirement projection: at age {cur_age}, retiring at {retire_age}, "
               f"saving {cur_savings} now and {monthly}/month at {ann_return:.0%} return → "
               f"${res['future_value']:,.0f} at retirement. What should I consider? "
               "If I have a target in my profile, compare and advise.")
        with st.spinner("Analyzing…"):
            comm = agent_run(msg, history=[], profile=profile, retriever=get_retriever())
        st.markdown(comm)

elif goal == "Savings target":
    c1, c2, c3 = st.columns(3)
    with c1:
        target = st.number_input("Target ($)", 1_000, 100_000_000, 500_000, 1_000)
    with c2:
        years = st.number_input("Years", 1, 60, 20)
    with c3:
        ar = st.slider("Assumed annual return", 0.01, 0.12, 0.05, 0.005)
    res = savings_goal(target, years, ar)
    if "error" in res:
        st.error(res["error"])
    else:
        st.metric("Required monthly contribution", f"${res['monthly_contribution']:,.0f}")
        st.caption(f"Assumes {ar:.0%} compounded monthly over {years} years.")

else:  # Debt payoff
    c1, c2, c3 = st.columns(3)
    with c1:
        bal = st.number_input("Balance ($)", 100, 10_000_000, 20_000, 100)
    with c2:
        apr = st.slider("APR", 0.01, 0.40, 0.22, 0.01)
    with c3:
        pay = st.number_input("Monthly payment ($)", 10, 1_000_000, 600, 10)
    res = debt_payoff(bal, apr, pay)
    if "error" in res:
        st.error(res["error"])
    else:
        c1, c2 = st.columns(2)
        c1.metric("Months to payoff", res["months_to_payoff"])
        c2.metric("Total interest paid", f"${res['total_interest']:,.0f}")
