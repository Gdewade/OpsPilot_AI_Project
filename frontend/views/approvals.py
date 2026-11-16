import streamlit as st

from frontend import client
from frontend.views.common import actor, incident_picker, safe


def render():
    st.header("Human approval")
    st.caption("Proposed actions are never executed automatically. A person other than the requester must decide.")

    tab_pending, tab_all, tab_new = st.tabs(["Pending", "History", "New request"])

    with tab_pending:
        data = safe(client.get, "/approvals", params={"decision": "pending"})
        if data and not data["approvals"]:
            st.success("Nothing waiting for review.")
        for ap in (data or {}).get("approvals", []):
            with st.container(border=True):
                st.markdown(f"**Request #{ap['id']}** · incident #{ap['incident_id']} · by `{ap['requested_by']}`")
                st.text(ap["action"])
                comment = st.text_input("Comment (optional)", key=f"c{ap['id']}")
                a, b, _ = st.columns([1, 1, 4])
                for col, decision, label in ((a, "approved", "✅ Approve"), (b, "rejected", "❌ Reject")):
                    if col.button(label, key=f"{decision}{ap['id']}"):
                        name = actor()
                        if name and safe(
                            client.post,
                            f"/approvals/{ap['id']}/decision",
                            json={"decision": decision, "reviewed_by": name, "comments": comment or None},
                        ):
                            st.rerun()

    with tab_all:
        data = safe(client.get, "/approvals")
        if data:
            rows = [
                {k: ap[k] for k in ("id", "incident_id", "decision", "requested_by", "reviewed_by", "comments", "reviewed_at")}
                for ap in data["approvals"]
            ]
            st.dataframe(rows, hide_index=True, width="stretch")

    with tab_new:
        incident_id = incident_picker(key="approval_incident")
        action = st.text_area("Action that needs approval", height=100)
        if incident_id and st.button("Submit request"):
            name = actor()
            if name:
                created = safe(
                    client.post,
                    "/approvals",
                    json={"incident_id": incident_id, "action": action, "requested_by": name},
                )
                if created:
                    st.success(f"Request #{created['id']} submitted")
