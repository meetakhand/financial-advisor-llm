"""Home — customer selector, quick-start prompts, new-customer onboarding."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from advisor.domain.data import Customer, list_customers, upsert_customer  # noqa: E402

from app.components.floating_chat import render_floating_chat  # noqa: E402
from app.components.session import (  # noqa: E402
    KEY_PENDING_QUESTION, set_active_customer,
)
from app.components.theme import BRAND_NAME, apply_theme  # noqa: E402

st.set_page_config(page_title=f"Home · {BRAND_NAME}",
                    page_icon=":diamonds:", layout="wide")

customer = apply_theme(page_key="Home")

st.markdown(f'<div class="nw-hero-title">Welcome to {BRAND_NAME}</div>',
                unsafe_allow_html=True)
st.markdown(
    '<div class="nw-hero-sub">Plan, review, and approve investment decisions '
    'right in the chat panel.</div>',
    unsafe_allow_html=True,
)

# ------------------------- Select a customer -------------------------
st.markdown("### Select a customer")
customers = list_customers()

if not customers:
    st.info("No customers loaded yet. Run `make seed` to load the hero customers.")
else:
    label_by_id = {
        c.id: f"#{c.external_id} — {c.name} "
                f"({c.age}, ${c.annual_income:,.0f}/yr"
                + (f", {c.primary_goal}" if c.primary_goal else "")
                + ")"
        for c in customers
    }

    query = st.text_input(
        "Search customers", placeholder="Search by name or ID…",
        label_visibility="collapsed",
    )
    filtered_ids = [
        cid for cid, lbl in label_by_id.items()
        if query.lower() in lbl.lower()
    ] or list(label_by_id.keys())

    default_index = (
        filtered_ids.index(customer.id)
        if customer and customer.id in filtered_ids else 0
    )
    chosen = st.selectbox(
        "Customer",
        options=filtered_ids,
        format_func=lambda i: label_by_id[i],
        index=default_index,
        label_visibility="collapsed",
    )

    left, _ = st.columns([1, 3])
    with left:
        if st.button("Load Customer", type="primary", use_container_width=True):
            set_active_customer(chosen)
            st.switch_page("pages/1_FinAdvisor.py")

st.divider()

# ------------------------- Start a new customer -------------------------
st.markdown("### Or start a new customer")
with st.form("new_customer_form", clear_on_submit=False):
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        full_name = st.text_input("Full name", placeholder="e.g. Alex Johnson")
    with c2:
        age = st.number_input("Age", min_value=18, max_value=100, value=35, step=1)
    with c3:
        income = st.number_input("Annual income (USD)", min_value=0.0,
                                    value=80_000.0, step=1_000.0)
    submitted = st.form_submit_button(
        "Start New Customer Onboarding", type="primary", use_container_width=True,
    )

if submitted:
    name = full_name.strip()
    if not name:
        st.error("Please enter a name to start onboarding.")
    else:
        existing_ids = {c.external_id for c in list_customers()}
        base = "N" + str(len(existing_ids) + 1).zfill(3)
        external_id = base
        i = 1
        while external_id in existing_ids:
            i += 1
            external_id = f"{base}-{i}"
        new_customer = Customer(
            id=None, external_id=external_id, name=name,
            age=int(age), annual_income=float(income),
        )
        new_id = upsert_customer(new_customer)
        set_active_customer(new_id)
        st.session_state.pop(KEY_PENDING_QUESTION, None)
        st.success(f"Welcome, {name}. Let's set your risk profile.")
        st.switch_page("pages/3_Risk_Profile.py")

st.divider()

# ------------------------- Quick-start prompts -------------------------
st.markdown("### Try a quick-start prompt")
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
        if st.button(label, key=f"qs_{label}", use_container_width=True):
            st.session_state[KEY_PENDING_QUESTION] = prompt
            st.switch_page("pages/1_FinAdvisor.py")
st.markdown("</div>", unsafe_allow_html=True)

render_floating_chat(
    page_key="Home",
    page_context={
        "Active customer": customer.name if customer else "none",
        "Journey on file": (customer.primary_goal if customer else None) or "not set",
    },
    customer=customer,
)
