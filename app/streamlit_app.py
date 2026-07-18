"""NexWealth AI — Streamlit entry.

Applies the shared theme (dark navy sidebar with brand, customer chip,
in-app nav, agent-pipeline block, LLM-status footer), then bounces to
0_Home. All real work happens in app/pages/.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))          # so `from app.components ...` works

import streamlit as st  # noqa: E402

from app.components.theme import BRAND_NAME, apply_theme  # noqa: E402

st.set_page_config(
    page_title=f"{BRAND_NAME} — FinAdvisor",
    page_icon=":diamonds:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme(page_key="Home")

# Land users straight on the Home page. `st.switch_page` fires on first render.
st.switch_page("pages/0_Home.py")
