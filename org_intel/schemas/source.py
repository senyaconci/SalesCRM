"""Official source registry schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import (
    ContentRole,
    OfficialStatus,
    SourceAccessMethod,
    SourcePriority,
    SourceRole,
    SourceStatus,
)
from org_intel.schemas.evidence import Evidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sid() -> str:
    return f"SRC-{uuid4().hex[:8].upper()}"


class SourceRecord(BaseModel):
    source_id: str = Field(default_factory=_sid)
    source_name: str = ""
    source_role: SourceRole = SourceRole.OTHER
    content_roles: list[ContentRole] = Field(default_factory=list)
    url: str = ""
    domain: str = ""
    publishing_entity: str = ""
    official_status: OfficialStatus = OfficialStatus.OFFICIAL
    access_method: SourceAccessMethod = SourceAccessMethod.HTML
    authentication_required: bool = False
    update_frequency: str = ""
    expected_content: list[str] = Field(default_factory=list)
    priority: SourcePriority = SourcePriority.MEDIUM
    status: SourceStatus = SourceStatus.UNKNOWN
    last_checked: datetime | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)
    authority_fields: list[str] = Field(default_factory=list)
    notes: str | None = None


class SourceRegistry(BaseModel):
    organization_id: str
    sources: list[SourceRecord] = Field(default_factory=list)
    field_authority_map: dict[str, list[str]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
