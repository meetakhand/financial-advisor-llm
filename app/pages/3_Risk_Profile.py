"""Risk Profile — arc gauge + questionnaire + journey-specific goal inputs."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from advisor.agents.risk_narrator import narrate_risk  # noqa: E402
from advisor.domain.data import upsert_customer  # noqa: E402
from advisor.domain.risk import QUESTIONNAIRE, compute_risk  # noqa: E402

from app.components.charts import risk_gauge  # noqa: E402
from app.components.floating_chat import render_floating_chat  # noqa: E402
from app.components.session import KEY_RISK_RATIONALE  # noqa: E402
from app.components.theme import BRAND_NAME, apply_theme  # noqa: E402

st.set_page_config(page_title=f"Risk Profile · {BRAND_NAME}",
                    page_icon=":scales:", layout="wide")

customer = apply_theme(page_key="Risk Profile")

st.markdown('<div class="nw-hero-title">Risk Profile</div>', unsafe_allow_html=True)

if not customer:
    st.info("Pick a customer from Home to build a risk profile.")
    st.stop()

journey = customer.primary_goal or "Retirement Planning"

# Live-preview computation from current answers (uses saved answers if any).
answers = list(customer.risk_answers) if customer.risk_answers else [1] * len(QUESTIONNAIRE)
preview = compute_risk(answers, customer.age, customer.annual_income, customer.dependents)

# --- Gauge + summary line -------------------------------------------
gauge_col, summary_col = st.columns([2, 3])
with gauge_col:
    st.plotly_chart(risk_gauge(preview.risk_score, preview.risk_band),
                    use_container_width=True)
with summary_col:
    st.markdown(
        f"""
        <div class="nw-card">
          <div style="font-size:13px; color:#6B7280; letter-spacing:.06em;
                        text-transform:uppercase;">On file for</div>
          <div style="font-size:20px; font-weight:700; padding:2px 0 8px 0;">
            {customer.name}
          </div>
          <div style="font-size:15px;">
            Risk Score <b>{preview.risk_score}/100</b> → <b>{preview.risk_band}</b>
          </div>
          <div style="color:#4A5468; font-size:13px; padding-top:6px;">
            {preview.description}
          </div>
          <div style="color:#6B7280; font-size:12px; padding-top:10px;">
            Active journey: <b>{journey}</b>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='padding-top:12px; color:#4A5468;'>"
        f"Tolerance <b>{preview.tolerance:.0f}/100</b> · "
        f"Capacity <b>{preview.capacity:.0f}/100</b></div>",
        unsafe_allow_html=True,
    )

st.divider()

# --- Questionnaire --------------------------------------------------
st.markdown("### Questionnaire")
for i, q in enumerate(QUESTIONNAIRE):
    labels = [opt[0] for opt in q["options"]]
    picked = st.radio(
        q["question"], labels,
        index=answers[i] if i < len(answers) and 0 <= answers[i] < len(labels) else 1,
        key=f"risk_q_{q['id']}",
    )
    answers[i] = labels.index(picked)

# --- Risk rationale (grounded LLM explanation of the band) ---------
# Cached per (customer_id, answers_tuple) so it doesn't re-fire on every rerun.
_rationale_cache: dict = st.session_state.setdefault(KEY_RISK_RATIONALE, {})
_answers_key = (customer.id, tuple(answers))
_rationale = _rationale_cache.get(_answers_key)

with st.container(border=True):
    st.markdown("### Why this band")
    if _rationale is None:
        st.caption(
            f"Explain why **{customer.name}** landed in the **{preview.risk_band}** band. "
            "The score is deterministic — this only adds context."
        )
        if st.button("Explain this band", use_container_width=True,
                        key="explain_band_btn"):
            with st.spinner("Grounded explanation from the narrator..."):
                _rationale = narrate_risk(customer, preview, answers)
            _rationale_cache[_answers_key] = _rationale
            st.rerun()
    else:
        _src_hint = {
            "llm": "Grounded rationale from the LLM narrator.",
            "template": "Deterministic template rationale (LLM off).",
            "llm_error_fallback": "Deterministic template rationale (LLM unavailable — fell back).",
        }.get(_rationale.source, "Risk-band rationale")
        st.caption(_src_hint)
        st.markdown(_rationale.markdown)
        if st.button("Regenerate", key="regen_band_btn"):
            _rationale_cache.pop(_answers_key, None)
            st.rerun()

# --- Goal inputs ----------------------------------------------------
st.markdown("### Goal inputs")
goal_inputs = dict(customer.goal_inputs or {})
if journey == "Retirement Planning":
    goal_inputs["target_retirement_age"] = st.number_input(
        "Target retirement age", min_value=customer.age + 1, max_value=90,
        value=int(goal_inputs.get("target_retirement_age", 65)))
    goal_inputs["desired_monthly_income"] = st.number_input(
        "Desired monthly income in retirement (today's $)", min_value=0.0,
        value=float(goal_inputs.get("desired_monthly_income", customer.annual_income / 12 * 0.8)),
        step=500.0)
    goal_inputs["current_savings"] = st.number_input(
        "Current retirement savings ($)", min_value=0.0,
        value=float(goal_inputs.get("current_savings", 50_000.0)), step=1000.0)
    goal_inputs["monthly_contribution"] = st.number_input(
        "Monthly contribution ($)", min_value=0.0,
        value=float(goal_inputs.get("monthly_contribution", 1000.0)), step=100.0)
elif journey == "Child Education":
    goal_inputs["child_current_age"] = st.number_input(
        "Child's current age", min_value=0, max_value=17,
        value=int(goal_inputs.get("child_current_age", 5)))
    goal_inputs["target_cost_today"] = st.number_input(
        "Target 4-yr college cost (today's $)", min_value=0.0,
        value=float(goal_inputs.get("target_cost_today", 120_000.0)), step=5000.0)
    goal_inputs["current_savings"] = st.number_input(
        "Current 529 balance ($)", min_value=0.0,
        value=float(goal_inputs.get("current_savings", 5_000.0)), step=500.0)
    goal_inputs["monthly_contribution"] = st.number_input(
        "Monthly contribution ($)", min_value=0.0,
        value=float(goal_inputs.get("monthly_contribution", 400.0)), step=50.0)
elif journey == "Buy Home":
    goal_inputs["home_price"] = st.number_input(
        "Home price ($)", min_value=0.0,
        value=float(goal_inputs.get("home_price", 500_000.0)), step=10000.0)
    goal_inputs["down_payment_pct"] = st.number_input(
        "Down payment (%)", min_value=0.0, max_value=100.0,
        value=float(goal_inputs.get("down_payment_pct", 20.0)), step=1.0)
    goal_inputs["target_purchase_year"] = st.number_input(
        "Target purchase year", min_value=2026, max_value=2050,
        value=int(goal_inputs.get("target_purchase_year", 2029)))
    goal_inputs["current_year"] = 2026
    goal_inputs["current_savings"] = st.number_input(
        "Down-payment savings so far ($)", min_value=0.0,
        value=float(goal_inputs.get("current_savings", 20_000.0)), step=1000.0)
    goal_inputs["monthly_saving_capacity"] = st.number_input(
        "Monthly saving capacity ($)", min_value=0.0,
        value=float(goal_inputs.get("monthly_saving_capacity", 1_500.0)), step=100.0)
else:
    st.info("This journey doesn't require goal inputs — use the FinAdvisor chat instead.")

col_l, col_r = st.columns(2)
if col_l.button("Save profile", use_container_width=True):
    customer.risk_answers = answers
    customer.goal_inputs = goal_inputs
    upsert_customer(customer)
    st.success("Saved.")
if col_r.button("Save + generate recommendations →",
                  use_container_width=True, type="primary"):
    customer.risk_answers = answers
    customer.goal_inputs = goal_inputs
    upsert_customer(customer)
    st.switch_page("pages/4_Recommendations.py")

render_floating_chat(
    page_key="Risk Profile",
    page_context={
        "Journey": journey,
        "Risk band (preview)": f"{preview.risk_band} (score {preview.risk_score})",
        "Tolerance": f"{preview.tolerance:.0f}/100",
        "Capacity": f"{preview.capacity:.0f}/100",
    },
    customer=customer,
)
