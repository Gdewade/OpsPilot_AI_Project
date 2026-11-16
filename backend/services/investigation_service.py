"""Runs an investigation for a stored incident and records everything."""

import logging

logger = logging.getLogger("opspilot.service")

AI_ACTOR = "opspilot-ai"


def _approval_text(rca: dict) -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(rca["remediation_steps"], start=1))
    return f"Apply recommended remediation for: {rca['root_cause']}\n\n{steps}"


def run_investigation(repo, cache, pipeline, incident_id: int, requested_by: str) -> dict:
    """Investigate, persist the result, write the audit trail and, when the
    evidence is verified, open an approval request for the proposed fix.

    Nothing is executed automatically: a human must approve the request.
    """
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise LookupError(f"incident {incident_id} not found")

    repo.update_status(incident_id, "investigating")
    cache.delete(f"incident:{incident_id}")
    repo.add_audit(incident_id, "INVESTIGATION_STARTED", requested_by, f"mode={pipeline.mode}")

    try:
        state = pipeline.run(incident["title"], incident["log_text"])
    except Exception as exc:
        # do not leave the incident stuck in "investigating"
        logger.exception("investigation failed for incident %s", incident_id)
        repo.update_status(incident_id, incident["status"])
        cache.delete(f"incident:{incident_id}")
        repo.add_audit(incident_id, "INVESTIGATION_FAILED", AI_ACTOR, type(exc).__name__)
        raise

    status = state["status"]  # "completed" or "needs_human"
    result = {
        "mode": pipeline.mode,
        "analysis": state["analysis"],
        "query": state["query"],
        "attempts": state["attempt"] + 1,
        "runbooks": [
            {k: r[k] for k in ("source", "section", "score", "content")} for r in state["runbooks"]
        ],
        "rca": state["rca"],
        "verification": state["verification"],
        "trace": state["trace"],
    }
    investigation = repo.save_investigation(incident_id, status, result, requested_by)

    approval = None
    if status == "completed" and state["rca"]["remediation_steps"]:
        approval = repo.create_approval(
            incident_id, _approval_text(state["rca"]), AI_ACTOR, investigation_id=investigation["id"]
        )
        repo.add_audit(
            incident_id, "APPROVAL_REQUESTED", AI_ACTOR, f"approval #{approval['id']} awaiting review"
        )

    new_status = "needs_human" if status == "needs_human" else "investigating"
    repo.update_status(incident_id, new_status)
    cache.delete(f"incident:{incident_id}")
    repo.add_audit(
        incident_id,
        "INVESTIGATION_COMPLETED" if status == "completed" else "INVESTIGATION_ESCALATED",
        AI_ACTOR,
        f"score={state['verification']['score']} attempts={result['attempts']}",
    )
    return {
        "investigation_id": investigation["id"],
        "status": status,
        "approval_id": approval["id"] if approval else None,
        "result": result,
    }
