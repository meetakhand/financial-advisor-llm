"""Chat page — conversational interface to the agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import streamlit as st  # noqa: E402

from advisor.agent.memory import load_profile, log_message  # noqa: E402
from advisor.agent.react import run as agent_run  # noqa: E402
from advisor.agent.safety import check_user_input  # noqa: E402
from advisor.rag.retrieve import HybridRetriever  # noqa: E402

st.title("Chat")


@st.cache_resource
def get_retriever() -> HybridRetriever:
    return HybridRetriever()


user_id = st.session_state.get("user_id", "demo-user")
if "history" not in st.session_state:
    st.session_state.history = []

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Ask anything finance-related…")
if prompt:
    flags = check_user_input(prompt)["flags"]
    if flags:
        st.warning(f"Heads up — input flags: {', '.join(flags)}. Response will be extra cautious.")

    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    log_message(user_id, "user", prompt)

    profile = load_profile(user_id)
    retriever = get_retriever()
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = agent_run(
                    prompt,
                    history=st.session_state.history[:-1],
                    profile=profile,
                    retriever=retriever,
                )
            except Exception as e:
                answer = f":warning: Error: `{type(e).__name__}: {e}`"
        st.markdown(answer)
    st.session_state.history.append({"role": "assistant", "content": answer})
    log_message(user_id, "assistant", answer)
