import streamlit as st

from frontend import client


def actor() -> str | None:
    """The reviewer/requester name from the sidebar, or None (and a hint)."""
    name = (st.session_state.get("actor") or "").strip()
    if len(name) < 2:
        st.info("Enter your name in the sidebar first. It is recorded in the audit trail.")
        return None
    return name


def safe(fn, *args, **kwargs):
    """Call the API; show the error instead of crashing the page."""
    try:
        return fn(*args, **kwargs)
    except client.ApiError as exc:
        st.error(f"{exc} (HTTP {exc.status})" if exc.status else str(exc))
        return None


def incident_picker(label="Incident", key="incident_pick"):
    data = safe(client.get, "/incidents", params={"limit": 200})
    if not data or not data["incidents"]:
        st.info("No incidents yet. Create one on the Incidents page.")
        return None
    options = {f"#{i['id']} · {i['title']} [{i['status']}]": i["id"] for i in data["incidents"]}
    choice = st.selectbox(label, list(options), key=key)
    return options[choice]


SEVERITY_ICON = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
