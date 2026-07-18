"""Streamlit session helpers — active-customer, nav, provider label.

Only touches ``st.session_state``. Sidebar rendering lives in
``app.components.theme``.
"""
from __future__ import annotations

import streamlit as st

from advisor.config import settings
from advisor.domain.data import Customer, get_customer, list_customers

# Keys we own in st.session_state
KEY_ACTIVE_CUSTOMER = "active_customer_id"
KEY_LAST_PIPELINE = "last_pipeline_result"    # advisor.agents.orchestrator.PipelineResult
KEY_LAST_ADVISOR_TURN = "last_advisor_turn"   # advisor.agents.advisor.AdvisorAnswer
KEY_LAST_INTENT = "last_intent"
KEY_LAST_QUESTION = "last_question"
KEY_PENDING_QUESTION = "pending_question"     # question queued from Home → FinAdvisor
KEY_HITL_PENDING = "hitl_pending"             # {hitl_id, ai_suggested, journey}
KEY_ANSWERED = "risk_answers_temp"            # in-flight questionnaire answers
KEY_RISK_RATIONALE = "risk_rationale_cache"   # {(customer_id, answers_tuple): RiskRationale}


def customer_options() -> list[Customer]:
    return list_customers()


def active_customer() -> Customer | None:
    cid = st.session_state.get(KEY_ACTIVE_CUSTOMER)
    if cid is None:
        return None
    c = get_customer(cid)
    if c is None:
        st.session_state.pop(KEY_ACTIVE_CUSTOMER, None)
        return None
    return c


def set_active_customer(customer_id: int | None) -> None:
    if customer_id is None:
        st.session_state.pop(KEY_ACTIVE_CUSTOMER, None)
    else:
        st.session_state[KEY_ACTIVE_CUSTOMER] = customer_id
    for k in (KEY_LAST_PIPELINE, KEY_LAST_ADVISOR_TURN, KEY_HITL_PENDING,
                KEY_ANSWERED, KEY_RISK_RATIONALE):
        st.session_state.pop(k, None)


def provider_label() -> str:
    if settings.llm_provider == "none" or not settings.hf_token:
        return "LLM: rule-based fallback"
    return f"LLM: {settings.llm_provider} · {settings.llm_model_id.split('/')[-1]}"


def profile_dict_for_prompt(customer: Customer | None) -> dict | None:
    if not customer:
        return None
    holdings_summary = (
        ", ".join(f"{h.ticker}({h.units:.0f})" for h in customer.holdings)
        if customer.holdings else "none"
    )
    return {
        "age": customer.age,
        "risk_tolerance": customer.primary_goal or "unspecified",
        "income": customer.annual_income,
        "goals": [customer.primary_goal] if customer.primary_goal else [],
        "holdings": holdings_summary,
    }
