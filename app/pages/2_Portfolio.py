"""Portfolio page — enter holdings, fetch quotes, render allocation + LLM commentary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from advisor.agent.memory import load_profile  # noqa: E402
from advisor.agent.react import run as agent_run  # noqa: E402
from advisor.rag.retrieve import HybridRetriever  # noqa: E402
from advisor.tools.alpha_vantage import AlphaVantageError, get_quote  # noqa: E402

st.title("Portfolio Analysis")


@st.cache_resource
def get_retriever() -> HybridRetriever:
    return HybridRetriever()


st.markdown("Enter holdings (one per line) as `TICKER,SHARES`. Example: `AAPL,10`")
default = st.session_state.get("portfolio_text",
                               "AAPL,10\nMSFT,5\nVOO,15")
text = st.text_area("Holdings", value=default, height=180)
st.session_state["portfolio_text"] = text

if st.button("Analyze portfolio"):
    rows = []
    for line in text.strip().splitlines():
        if "," not in line:
            continue
        sym, sh = (p.strip() for p in line.split(",", 1))
        try:
            shares = float(sh)
        except ValueError:
            st.warning(f"Skipping bad line: {line}")
            continue
        try:
            q = get_quote(sym)
        except AlphaVantageError as e:
            st.error(f"AV error for {sym}: {e}")
            continue
        if q.get("price") is None:
            st.warning(f"No price for {sym}")
            continue
        rows.append({"symbol": sym.upper(), "shares": shares, "price": q["price"],
                     "value": shares * q["price"], "change_pct": q.get("change_percent")})

    if not rows:
        st.stop()

    df = pd.DataFrame(rows)
    total = df["value"].sum()
    df["weight_pct"] = (df["value"] / total * 100).round(2)
    st.subheader("Holdings")
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(df, values="value", names="symbol",
                     title=f"Allocation (Total ${total:,.0f})", hole=0.35)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig2 = px.bar(df.sort_values("value", ascending=True),
                      x="value", y="symbol", orientation="h",
                      title="Position Value ($)")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Agent Commentary")
    user_id = st.session_state.get("user_id", "demo-user")
    profile = load_profile(user_id)
    holdings_str = ", ".join(f"{r['symbol']} {r['weight_pct']:.1f}%" for r in df.to_dict("records"))
    msg = (f"Here is my portfolio: {holdings_str}. Total value ${total:,.0f}. "
           "Identify concentration risks, sector tilts, and suggest considerations "
           "(not directives) for a rebalance given my profile. Use tools to look up "
           "sectors / fundamentals as needed.")
    with st.spinner("Analyzing…"):
        try:
            commentary = agent_run(msg, history=[], profile=profile, retriever=get_retriever())
        except Exception as e:
            commentary = f":warning: Error: `{type(e).__name__}: {e}`"
    st.markdown(commentary)
