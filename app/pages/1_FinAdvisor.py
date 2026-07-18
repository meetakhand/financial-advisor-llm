"""FinAdvisor page — chat-style prompt with quick-start pills.

Classifies intent → planning journey (Risk Profile → Recommendations) or
grounded RAG Q&A. Persists the last answer across reruns.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from advisor.agents.advisor import answer_question  # noqa: E402
from advisor.agents.intent import (  # noqa: E402
    OUT_OF_SCOPE, OUT_OF_SCOPE_MESSAGE, classify_intent,
)

from app.components.session import (  # noqa: E402
    KEY_LAST_ADVISOR_TURN, KEY_LAST_INTENT, KEY_LAST_QUESTION,
    KEY_PENDING_QUESTION, profile_dict_for_prompt, provider_label,
)
from app.components.theme import BRAND_NAME, apply_theme  # noqa: E402

st.set_page_config(page_title=f"FinAdvisor · {BRAND_NAME}",
                    page_icon=":speech_balloon:", layout="wide")

customer = apply_theme(page_key="FinAdvisor")

st.markdown('<div class="nw-hero-title">FinAdvisor by NexWealth AI</div>',
                unsafe_allow_html=True)
st.markdown(
    '<div class="nw-hero-sub">Ask a financial question or pick a planning journey. '
    f'&nbsp;·&nbsp; {provider_label()}.</div>',
    unsafe_allow_html=True,
)

# Persona card
persona_line = (
    f"Chatting as <b>{customer.name}</b> "
    f"({customer.age}, ${customer.annual_income:,.0f}/yr)"
    if customer else "No customer selected — pick one from Home to enable planning."
)
st.markdown(
    f"""
    <div class="nw-persona">
      <div class="avatar">💼</div>
      <div>
        <div class="who">FinAdvisor</div>
        <div class="msg">Hi — I can help with retirement, education, home-buying,
        or general financial questions. {persona_line}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick-start pills
st.markdown('<div class="nw-quickstart-row">', unsafe_allow_html=True)
QUICK_STARTS = [
    ("Retirement Planning",  "Am I on track for retirement at 65?"),
    ("Child Education",      "Save for my daughter's college in 12 years"),
    ("Buy a Home",           "Down payment for a home in 2029"),
    ("Financial Q&A",        "What is a mutual fund vs an ETF?"),
]
cols = st.columns(4)
for col, (label, prompt) in zip(cols, QUICK_STARTS):
    with col:
        if st.button(label, key=f"pill_{label}", use_container_width=True):
            st.session_state[KEY_PENDING_QUESTION] = prompt
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------- Handler -------------------------
def _handle(question: str) -> None:
    st.session_state[KEY_LAST_QUESTION] = question
    intent = classify_intent(question)
    st.session_state[KEY_LAST_INTENT] = intent

    st.markdown(
        f"**Intent:** `{intent.journey}` "
        f"*(source: {intent.source}, confidence {intent.confidence:.2f})*"
    )

    if intent.journey == OUT_OF_SCOPE:
        # Refuse cleanly instead of spending a ReAct loop on a non-finance question.
        st.session_state[KEY_LAST_ADVISOR_TURN] = None
        st.warning(OUT_OF_SCOPE_MESSAGE)
        return

    if intent.journey == "Financial Q&A":
        with st.spinner("Retrieving grounded context and drafting..."):
            answer = answer_question(question,
                                        profile=profile_dict_for_prompt(customer))
        st.session_state[KEY_LAST_ADVISOR_TURN] = answer
        return

    # Planning journey — need an active customer to route.
    if not customer:
        st.warning("Pick a customer from Home to run the planning flow.")
        return

    st.success(f"Routing to **{intent.journey}** — confirm inputs on the Risk Profile page.")
    if customer.primary_goal != intent.journey:
        from advisor.domain.data import upsert_customer
        customer.primary_goal = intent.journey
        upsert_customer(customer)
    st.switch_page("pages/3_Risk_Profile.py")


# ------------------------- Input path -------------------------
pending = st.session_state.pop(KEY_PENDING_QUESTION, None)
if pending:
    _handle(pending)

with st.form("finadvisor_form", clear_on_submit=False):
    default_q = st.session_state.get(KEY_LAST_QUESTION, "")
    question = st.text_area(
        "Ask FinAdvisor a financial question…",
        value=default_q, height=100,
        placeholder="e.g. Am I on track for retirement?",
    )
    submitted = st.form_submit_button("Send", use_container_width=True, type="primary")

if submitted and question.strip():
    _handle(question.strip())

# ------------------------- Rendered answer -------------------------
answer = st.session_state.get(KEY_LAST_ADVISOR_TURN)
if answer:
    st.divider()
    st.markdown("### Answer")
    if answer.was_blocked:
        st.warning("This request was refused by the input guardrail.")
    st.markdown(answer.answer_markdown)

    if answer.citations:
        with st.expander(f"Retrieved context ({len(answer.citations)} snippets)",
                            expanded=False):
            for c in answer.citations:
                st.markdown(f"- **[{c['source']}]** id={c['id']} · score={c['score']}")

    # ReAct audit trail — tool calls the agent made this turn.
    if getattr(answer, "tool_calls", None):
        _stopped = getattr(answer, "stopped_reason", "")
        _steps = getattr(answer, "steps", 0)
        with st.expander(
            f"Agent trace ({len(answer.tool_calls)} tool call"
            f"{'s' if len(answer.tool_calls) != 1 else ''} · "
            f"{_steps} step{'s' if _steps != 1 else ''} · "
            f"{_stopped or 'unknown'})",
            expanded=False,
        ):
            for i, tc in enumerate(answer.tool_calls, 1):
                _ok = "✓" if tc.ok else "✗"
                st.markdown(f"**{i}. `{tc.name}` {_ok}**")
                if tc.args:
                    st.caption(f"args: `{tc.args}`")
                if tc.error:
                    st.caption(f":red[error: {tc.error}]")
                st.code(tc.result_preview, language="json")
    elif getattr(answer, "stopped_reason", "") == "no_llm":
        st.caption("LLM off — answered from retrieved snippets. Set `LLM_PROVIDER` + `HF_TOKEN` to enable the ReAct tool loop.")

    if answer.follow_up and not answer.was_blocked:
        st.info(answer.follow_up)
