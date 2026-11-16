import streamlit as st

from frontend import client
from frontend.views.common import incident_picker, safe


def render():
    st.header("Audit trail")
    incident_id = incident_picker()
    if incident_id is None:
        return
    data = safe(client.get, f"/incidents/{incident_id}/audit")
    if not data:
        return
    st.caption(f"{data['total']} event(s), newest first")
    rows = [
        {k: log[k] for k in ("created_at", "action", "actor", "details")}
        for log in data["audit_logs"]
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
