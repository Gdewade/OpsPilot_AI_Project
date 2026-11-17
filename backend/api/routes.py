"""HTTP API. All routes except /health need X-API-Key when API_KEY is set."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.analysis.log_analyzer import analyze_logs
from backend.deps import AppContext, get_ctx, require_api_key
from backend.schemas import (
    ApprovalCreate,
    ApprovalDecision,
    IncidentCreate,
    IncidentStatus,
    InvestigationRequest,
    RunbookSearch,
    Severity,
    StatusUpdate,
)
from backend.services.approval_service import apply_decision_outcome
from backend.services.investigation_service import run_investigation

logger = logging.getLogger("opspilot.api")

public = APIRouter()
router = APIRouter(dependencies=[Depends(require_api_key)])


def _incident_or_404(ctx: AppContext, incident_id: int) -> dict:
    incident = ctx.repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return incident


# ---------------------------------------------------------------- health
@public.get("/health")
def health(ctx: AppContext = Depends(get_ctx)):
    return {
        "status": "ok" if ctx.repo.ping() else "degraded",
        "storage": ctx.repo.name,
        "database": ctx.repo.ping(),
        "redis": ctx.cache.ping() if ctx.cache.enabled else "disabled",
        "runbook_chunks": ctx.retriever.size,
        "ai_mode": ctx.pipeline.mode,
        "embedder": ctx.retriever.embedder.name,
        "auth_required": bool(ctx.settings.api_key),
    }


# ------------------------------------------------------------- incidents
@router.post("/incidents", status_code=201)
def create_incident(body: IncidentCreate, ctx: AppContext = Depends(get_ctx)):
    analysis = analyze_logs(body.log_text)
    severity = (body.severity or Severity(analysis["severity"])).value
    incident = ctx.repo.create_incident(
        body.title, body.description, body.log_text, severity, body.created_by
    )
    ctx.repo.add_audit(
        incident["id"], "INCIDENT_CREATED", body.created_by, f"severity={severity}"
    )
    return incident


@router.get("/incidents")
def list_incidents(
    status: IncidentStatus | None = None,
    severity: Severity | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AppContext = Depends(get_ctx),
):
    items, total = ctx.repo.list_incidents(
        status.value if status else None,
        severity.value if severity else None,
        q,
        limit,
        offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "incidents": items}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int, ctx: AppContext = Depends(get_ctx)):
    key = f"incident:{incident_id}"
    cached = ctx.cache.get_json(key)
    if cached:
        return cached
    incident = _incident_or_404(ctx, incident_id)
    ctx.cache.set_json(key, incident)
    return incident


@router.patch("/incidents/{incident_id}/status")
def update_status(incident_id: int, body: StatusUpdate, ctx: AppContext = Depends(get_ctx)):
    incident = _incident_or_404(ctx, incident_id)
    updated = ctx.repo.update_status(incident_id, body.status.value)
    ctx.cache.delete(f"incident:{incident_id}")
    ctx.repo.add_audit(
        incident_id,
        "STATUS_CHANGED",
        body.changed_by,
        f"{incident['status']} -> {body.status.value}",
    )
    return updated


@router.get("/incidents/{incident_id}/audit")
def incident_audit(incident_id: int, ctx: AppContext = Depends(get_ctx)):
    _incident_or_404(ctx, incident_id)
    logs = ctx.repo.list_audit(incident_id)
    return {"incident_id": incident_id, "total": len(logs), "audit_logs": logs}


# -------------------------------------------------------- investigations
@router.post("/incidents/{incident_id}/investigate")
def investigate(
    incident_id: int,
    body: InvestigationRequest,
    request: Request,
    ctx: AppContext = Depends(get_ctx),
):
    _incident_or_404(ctx, incident_id)
    client = request.client.host if request.client else "unknown"
    if not ctx.cache.allow(f"investigate:{client}", ctx.settings.rate_limit_per_minute):
        raise HTTPException(429, "Too many investigations, try again in a minute")
    try:
        return run_investigation(ctx.repo, ctx.cache, ctx.pipeline, incident_id, body.requested_by)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except Exception:
        logger.exception("investigation error")
        raise HTTPException(500, "Investigation failed, see server logs")


@router.get("/incidents/{incident_id}/investigation")
def latest_investigation(incident_id: int, ctx: AppContext = Depends(get_ctx)):
    _incident_or_404(ctx, incident_id)
    inv = ctx.repo.latest_investigation(incident_id)
    if inv is None:
        raise HTTPException(404, "No investigation yet for this incident")
    return inv


# ------------------------------------------------------------- approvals
@router.post("/approvals", status_code=201)
def create_approval(body: ApprovalCreate, ctx: AppContext = Depends(get_ctx)):
    _incident_or_404(ctx, body.incident_id)
    approval = ctx.repo.create_approval(body.incident_id, body.action, body.requested_by)
    ctx.repo.add_audit(
        body.incident_id, "APPROVAL_REQUESTED", body.requested_by, f"approval #{approval['id']}"
    )
    return approval


@router.get("/approvals")
def list_approvals(
    decision: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    incident_id: int | None = None,
    ctx: AppContext = Depends(get_ctx),
):
    rows = ctx.repo.list_approvals(decision, incident_id)
    return {"total": len(rows), "approvals": rows}


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: int, body: ApprovalDecision, ctx: AppContext = Depends(get_ctx)):
    approval = ctx.repo.get_approval(approval_id)
    if approval is None:
        raise HTTPException(404, f"Approval {approval_id} not found")
    if body.reviewed_by == approval["requested_by"]:
        raise HTTPException(403, "The requester cannot review their own request")
    updated = ctx.repo.decide_approval(
        approval_id, body.decision.value, body.reviewed_by, body.comments
    )
    if updated is None:
        raise HTTPException(409, "This request was already decided")
    ctx.repo.add_audit(
        approval["incident_id"],
        f"APPROVAL_{body.decision.value.upper()}",
        body.reviewed_by,
        f"approval #{approval_id}: {body.comments or 'no comment'}",
    )
    apply_decision_outcome(ctx.repo, ctx.cache, approval, body.decision.value, body.reviewed_by)
    return updated


# -------------------------------------------------------------- runbooks
@router.post("/runbooks/search")
def search_runbooks(body: RunbookSearch, ctx: AppContext = Depends(get_ctx)):
    results = ctx.retriever.search(body.query, k=body.k)
    return {"query": body.query, "embedder": ctx.retriever.embedder.name, "results": results}


@router.get("/runbooks")
def list_runbooks(ctx: AppContext = Depends(get_ctx)):
    return {"runbooks": ctx.retriever.sources(), "chunks": ctx.retriever.size}
