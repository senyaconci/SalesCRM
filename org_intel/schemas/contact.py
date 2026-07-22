"""Contact and stakeholder schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import EmailStatus
from org_intel.schemas.evidence import Evidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cid() -> str:
    return f"CTC-{uuid4().hex[:8].upper()}"


class ContactRecord(BaseModel):
    contact_id: str = Field(default_factory=_cid)
    name: str
    title: str | None = None
    department: str | None = None
    functional_role: str | None = None
    email: str | None = None
    email_status: EmailStatus = EmailStatus.NONE
    phone: str | None = None
    official_profile_url: str | None = None
    relevant_projects: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class EmailPattern(BaseModel):
    """Organization-wide email pattern — never treated as confirmed individual email."""

    pattern: str
    example: str | None = None
    confidence: float = 0.0
    notes: str = "Pattern only; individual emails remain unverified unless confirmed."


class StakeholderMap(BaseModel):
    organization_id: str
    contacts: list[ContactRecord] = Field(default_factory=list)
    email_pattern: EmailPattern | None = None
    created_at: datetime = Field(default_factory=_utcnow)
