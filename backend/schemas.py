"""Request/response models and shared enums."""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, Enum):
    open = "open"
    investigating = "investigating"
    needs_human = "needs_human"
    resolved = "resolved"


class Decision(str, Enum):
    approved = "approved"
    rejected = "rejected"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5, max_length=4000)
    log_text: str = Field(min_length=1, max_length=200_000)
    # Optional manual override. If omitted, severity is derived from the logs.
    severity: Severity | None = None
    created_by: str = Field(default="unknown", min_length=2, max_length=100)


class StatusUpdate(BaseModel):
    status: IncidentStatus
    changed_by: str = Field(min_length=2, max_length=100)


class InvestigationRequest(BaseModel):
    requested_by: str = Field(min_length=2, max_length=100)


class ApprovalCreate(BaseModel):
    incident_id: int = Field(gt=0)
    action: str = Field(min_length=3, max_length=4000)
    requested_by: str = Field(min_length=2, max_length=100)


class ApprovalDecision(BaseModel):
    decision: Decision
    reviewed_by: str = Field(min_length=2, max_length=100)
    comments: str | None = Field(default=None, max_length=2000)


class RunbookSearch(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    k: int = Field(default=3, ge=1, le=10)
