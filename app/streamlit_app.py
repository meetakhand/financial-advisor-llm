"""FinAdvisor — Streamlit entry. Configures sidebar persona; pages live in app/pages/."""
import sys
from pathlib import Path

# Allow running `streamlit run app/streamlit_app.py` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st  # noqa: E402

from advisor.agent.memory import load_profile, save_profile  # noqa: E402

st.set_page_config(page_title="FinAdvisor", page_icon=":bar_chart:", layout="wide")
st.title("FinAdvisor — Personalized Financial Guidance")

if "user_id" not in st.session_state:
    st.session_state.user_id = "demo-user"

with st.sidebar:
    st.header("Your Profile")
    profile = load_profile(st.session_state.user_id)

    age = st.number_input("Age", min_value=18, max_value=100, value=int(profile.get("age", 30)))
    risk_options = ["low", "moderate", "high"]
    risk = st.selectbox(
        "Risk tolerance", risk_options,
        index=risk_options.index(profile.get("risk_tolerance", "moderate")),
    )
    income = st.number_input(
        "Annual income (USD)", min_value=0, max_value=10_000_000,
        value=int(profile.get("income", 80_000)), step=5_000,
    )
    goals = st.multiselect(
        "Goals",
        ["retirement", "home_purchase", "education", "emergency_fund", "debt_payoff"],
        default=profile.get("goals", ["retirement"]),
    )
    holdings = st.text_area(
        "Holdings (free text, e.g. 'AAPL 30%, VOO 50%, cash 20%')",
        value=profile.get("holdings", ""),
        height=80,
    )
    if st.button("Save profile"):
        save_profile(
            st.session_state.user_id,
            {"age": age, "risk_tolerance": risk, "income": income,
             "goals": goals, "holdings": holdings},
        )
        st.success("Profile saved.")

st.markdown(
    """
### Use the sidebar to navigate

- **Chat** — ask anything finance-related; the agent uses RAG and live tools.
- **Portfolio** — analyze your holdings using live Alpha Vantage data.
- **Goals** — retirement, savings, and debt-payoff projections.
- **Markets** — sector heat-map and current news sentiment.

> *Educational use only — not personalized investment advice.*
"""
)
