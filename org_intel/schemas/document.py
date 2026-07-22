"""Document inventory schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import ContentRole, DocumentStatus, DocumentType
from org_intel.schemas.evidence import Evidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _did() -> str:
    return f"DOC-{uuid4().hex[:8].upper()}"


class DocumentRecord(BaseModel):
    document_id: str = Field(default_factory=_did)
    title: str = ""
    document_type: DocumentType = DocumentType.OTHER
    content_roles: list[ContentRole] = Field(default_factory=list)
    url: str = ""
    source_id: str | None = None
    publishing_entity: str = ""
    publication_date: str | None = None
    fiscal_year: str | None = None
    planning_period: str | None = None
    status: DocumentStatus = DocumentStatus.UNKNOWN
    file_type: str = ""
    page_count: int | None = None
    sha256: str = ""
    local_path: str | None = None
    likely_project_relevance: float = 0.0
    likely_financial_relevance: float = 0.0
    likely_procurement_relevance: float = 0.0
    expected_project_categories: list[str] = Field(default_factory=list)
    supersedes_document_id: str | None = None
    superseded_by_document_id: str | None = None
    access_notes: str = ""
    confidence: float = 0.0
    indexed: bool = False
    processed: bool = False
    evidence: list[Evidence] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=_utcnow)


class DocumentInventory(BaseModel):
    organization_id: str
    documents: list[DocumentRecord] = Field(default_factory=list)
    ranked_document_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
