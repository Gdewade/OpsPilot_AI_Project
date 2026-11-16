import streamlit as st

from frontend import client
from frontend.views.common import actor, incident_picker, safe


def _show(result: dict, status: str, approval_id=None):
    rca, ver = result["rca"], result["verification"]

    if status == "completed":
        st.success("Evidence verified. Review the proposed fix below.")
    else:
        st.warning("The evidence stayed weak after several attempts. A human needs to review this incident.")
    if result["mode"] == "offline" or rca["mode"].startswith("heuristic"):
        st.info("Produced by the offline rule-based analyzer, not an LLM. Add OPENAI_API_KEY for LLM analysis.")

    c = st.columns(3)
    c[0].metric("Confidence", f"{rca['confidence']:.0%}")
    c[1].metric("Verification score", f"{ver['score']:.0%}")
    c[2].metric("Search attempts", result["attempts"])

    st.subheader("Root cause")
    st.write(rca["root_cause"])
    if rca.get("reasoning"):
        st.caption(rca["reasoning"])

    left, right = st.columns(2)
    with left:
        st.markdown("**Verified log evidence**")
        for line in ver["verified_log_lines"] or ["(none)"]:
            st.code(line, language="log")
        for line in ver["fabricated_log_lines"]:
            st.error(f"Not found in logs: {line}")
    with right:
        st.markdown("**Runbooks used**")
        for src in ver["valid_runbooks"] or ["(none)"]:
            st.write(f"📘 {src}")

    if ver["issues"]:
        st.markdown("**Verification notes**")
        for issue in ver["issues"]:
            st.write(f"- {issue}")

    if rca["remediation_steps"]:
        st.subheader("Proposed remediation")
        for i, step in enumerate(rca["remediation_steps"], 1):
            st.write(f"{i}. {step}")
    if approval_id:
        st.info(f"Approval request #{approval_id} was created. A reviewer must approve it on the Approvals page. Nothing is executed automatically.")

    with st.expander("How the investigation ran"):
        for step in result["trace"]:
            st.write(f"- {step}")
        st.caption(f"Final search query: {result['query'][:300]}")
        for r in result["runbooks"]:
            st.markdown(f"**{r['source']}** · {r['section']}")
            st.text(r["content"][:600])


def render():
    st.header("AI investigation")
    incident_id = incident_picker()
    if incident_id is None:
        return

    if st.button("🔍 Run investigation", type="primary"):
        name = actor()
        if name:
            with st.spinner("Analysing logs, searching runbooks, verifying evidence..."):
                out = safe(client.post, f"/incidents/{incident_id}/investigate", json={"requested_by": name}, timeout=120)
            if out:
                _show(out["result"], out["status"], out["approval_id"])
                return

    try:
        previous = client.get(f"/incidents/{incident_id}/investigation")
    except client.ApiError as exc:
        if exc.status != 404:  # 404 just means "not investigated yet"
            st.error(str(exc))
        previous = None
    if previous:
        st.caption(f"Latest saved investigation (#{previous['id']}, {previous['created_at']})")
        _show(previous["result"], previous["status"])
