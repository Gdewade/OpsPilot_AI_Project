import pandas as pd
import streamlit as st

from frontend import client
from frontend.views.common import SEVERITY_ICON, safe


def render():
    st.header("Overview")
    data = safe(client.get, "/incidents", params={"limit": 200})
    approvals = safe(client.get, "/approvals", params={"decision": "pending"})
    if data is None:
        return
    df = pd.DataFrame(data["incidents"])

    cols = st.columns(4)
    cols[0].metric("Incidents", data["total"])
    cols[1].metric("Investigating", int((df["status"] == "investigating").sum()) if not df.empty else 0)
    cols[2].metric("Need a human", int((df["status"] == "needs_human").sum()) if not df.empty else 0)
    cols[3].metric("Pending approvals", approvals["total"] if approvals else 0)

    if df.empty:
        st.info("No incidents yet.")
        return
    left, right = st.columns(2)
    left.subheader("By severity")
    left.bar_chart(df["severity"].value_counts())
    right.subheader("By status")
    right.bar_chart(df["status"].value_counts())

    st.subheader("Latest incidents")
    latest = df.head(8).copy()
    latest["severity"] = latest["severity"].map(lambda s: f"{SEVERITY_ICON.get(s, '')} {s}")
    st.dataframe(latest[["id", "title", "severity", "status", "created_at"]], hide_index=True, width="stretch")
