"""Markets page — sector performance heatmap + news sentiment feed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from advisor.tools.alpha_vantage import (  # noqa: E402
    AlphaVantageError,
    get_news_sentiment,
    get_sector_performance,
)

st.title("Markets")

tab_sectors, tab_news = st.tabs(["Sector Performance", "News & Sentiment"])

with tab_sectors:
    st.caption("Live sector performance from Alpha Vantage.")
    if st.button("Refresh sector data", key="refresh_sectors"):
        st.cache_data.clear()

    try:
        data = get_sector_performance()
    except AlphaVantageError as e:
        st.error(str(e))
        st.stop()

    rows = []
    for window, perf in data.items():
        if not isinstance(perf, dict) or window == "Meta Data":
            continue
        for sector, val in perf.items():
            try:
                pct = float(str(val).rstrip("%"))
            except ValueError:
                continue
            rows.append({"window": window, "sector": sector, "pct": pct})
    if not rows:
        st.warning("No sector rows parsed.")
    else:
        df = pd.DataFrame(rows)
        st.subheader("Real-time")
        rt = df[df["window"].str.contains("Real")]
        if not rt.empty:
            fig = px.bar(rt.sort_values("pct"),
                         x="pct", y="sector", orientation="h",
                         color="pct", color_continuous_scale="RdYlGn",
                         title="Real-time Sector Performance (%)")
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("All windows"):
            st.dataframe(df, use_container_width=True, hide_index=True)

with tab_news:
    tickers = st.text_input("Tickers (comma-separated, optional)", "AAPL,MSFT,GOOGL")
    topics = st.text_input("Topics (optional, e.g. economy_macro,earnings)", "")
    limit = st.slider("Number of articles", 5, 50, 15)
    if st.button("Fetch news", key="fetch_news"):
        try:
            res = get_news_sentiment(tickers=tickers or None, topics=topics or None, limit=limit)
        except AlphaVantageError as e:
            st.error(str(e))
            st.stop()
        st.caption(f"Retrieved {res['count']} articles.")
        for item in res["items"]:
            with st.container(border=True):
                st.markdown(f"**[{item['title']}]({item['url']})**")
                st.caption(f"{item['time']} · sentiment: "
                           f"{item['overall_sentiment_label']} ({item['overall_sentiment_score']})")
                st.write(item["summary"])
