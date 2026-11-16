"""Streamlit dashboard.  Run:  streamlit run frontend/app.py"""

import streamlit as st

from frontend import client
from frontend.views import approvals, audit, incidents, investigate, overview, runbooks

st.set_page_config(page_title="OpsPilot AI", page_icon="⚡", layout="wide")

PAGES = {
    "Overview": overview.render,
    "Incidents": incidents.render,
    "Investigate": investigate.render,
    "Approvals": approvals.render,
    "Runbooks": runbooks.render,
    "Audit trail": audit.render,
}

with st.sidebar:
    st.title("⚡ OpsPilot AI")
    st.caption("AI-assisted incident response")
    page = st.radio("Navigation", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.text_input(
        "Your name",
        key="actor",
        placeholder="e.g. gayatri",
        help="Recorded in the audit trail for every action you take.",
    )
    try:
        health = client.get("/health", timeout=3)
        st.success(f"API online ({health['storage']})")
        st.caption(f"AI mode: **{health['ai_mode']}** · embeddings: {health['embedder']}")
        if health["ai_mode"] == "offline":
            st.warning("No OpenAI key: using rule-based analysis, not an LLM.")
    except client.ApiError as exc:
        st.error(str(exc))

PAGES[page]()
