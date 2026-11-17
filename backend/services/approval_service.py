"""What happens to an incident after a human decides on an approval request."""

AUTO_ACTOR = "opspilot-system"


def status_after_decision(incident_status: str, decision: str, other_pending: int) -> str | None:
    """Return the new incident status, or None to leave it unchanged.

    Only an incident that is being investigated moves:
    - approved + no other request still waiting  -> "resolved"
      (a human accepted the fix; OpsPilot does not run it, the team applies it)
    - rejected                                   -> "needs_human"
      (the proposed fix was refused, so a person has to decide what to do)
    """
    if incident_status != "investigating":
        return None
    if decision == "approved":
        return "resolved" if other_pending == 0 else None
    if decision == "rejected":
        return "needs_human"
    return None


def apply_decision_outcome(repo, cache, approval: dict, decision: str, reviewer: str) -> str | None:
    """Update the incident status after a decision and record it in the audit trail."""
    incident_id = approval["incident_id"]
    incident = repo.get_incident(incident_id)
    if incident is None:
        return None
    other_pending = sum(
        1 for a in repo.list_approvals("pending", incident_id) if a["id"] != approval["id"]
    )
    new_status = status_after_decision(incident["status"], decision, other_pending)
    if new_status is None:
        return None
    repo.update_status(incident_id, new_status)
    cache.delete(f"incident:{incident_id}")
    repo.add_audit(
        incident_id,
        "STATUS_CHANGED",
        AUTO_ACTOR,
        f"{incident['status']} -> {new_status} (approval #{approval['id']} {decision} by {reviewer})",
    )
    return new_status
