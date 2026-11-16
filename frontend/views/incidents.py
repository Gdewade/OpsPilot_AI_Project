import pandas as pd
import streamlit as st

from frontend import client
from frontend.views.common import SEVERITY_ICON, actor, safe

STATUSES = ["open", "investigating", "needs_human", "resolved"]


def render():
    st.header("Incidents")

    with st.expander("➕ Report a new incident", expanded=False):
        with st.form("new_incident", clear_on_submit=True):
            title = st.text_input("Title", max_chars=150)
            description = st.text_area("Description", height=80)
            logs = st.text_area("Logs", height=160, placeholder="Paste the relevant log lines here")
            severity = st.selectbox(
                "Severity", ["auto (from logs)", "low", "medium", "high", "critical"]
            )
            if st.form_submit_button("Create incident"):
                name = actor()
                if name:
                    payload = {"title": title, "description": description, "log_text": logs, "created_by": name}
                    if not severity.startswith("auto"):
                        payload["severity"] = severity
                    created = safe(client.post, "/incidents", json=payload)
                    if created:
                        st.success(f"Incident #{created['id']} created (severity: {created['severity']})")

    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", ["all", *STATUSES])
    severity = c2.selectbox("Severity filter", ["all", "low", "medium", "high", "critical"])
    params = {"limit": 100}
    if status != "all":
        params["status"] = status
    if severity != "all":
        params["severity"] = severity
    data = safe(client.get, "/incidents", params=params)
    if not data:
        return
    st.caption(f"{data['total']} incident(s)")
    if not data["incidents"]:
        return

    df = pd.DataFrame(data["incidents"])
    df["severity"] = df["severity"].map(lambda s: f"{SEVERITY_ICON.get(s, '')} {s}")
    st.dataframe(df[["id", "title", "severity", "status", "created_by", "created_at"]], hide_index=True, width="stretch")

    st.subheader("Incident details")
    ids = [i["id"] for i in data["incidents"]]
    chosen = st.selectbox("Open incident", ids, format_func=lambda i: f"#{i}")
    inc = safe(client.get, f"/incidents/{chosen}")
    if inc:
        st.write(inc["description"])
        st.code(inc["log_text"], language="log")
        new_status = st.selectbox("Change status", STATUSES, index=STATUSES.index(inc["status"]))
        if st.button("Update status") and new_status != inc["status"]:
            name = actor()
            if name and safe(client.patch, f"/incidents/{chosen}/status", json={"status": new_status, "changed_by": name}):
                st.success("Status updated")
                st.rerun()
