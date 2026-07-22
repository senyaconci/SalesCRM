"""Evidence, conflict, gap, and validation schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import FieldProvenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _eid(prefix: str = "EV") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: _eid("EV"))
    source_id: str | None = None
    document_id: str | None = None
    url: str | None = None
    title: str | None = None
    page: int | None = None
    section: str | None = None
    quote: str = ""
    retrieved_at: datetime = Field(default_factory=_utcnow)
    evidence_type: str = "excerpt"
    supports_fields: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: FieldProvenance = FieldProvenance.STATED


class FieldEvidence(BaseModel):
    field: str
    value: Any = None
    source_url: str | None = None
    source_title: str | None = None
    quote: str | None = None
    retrieved_at: datetime = Field(default_factory=_utcnow)
    confidence: float = 0.0
    provenance: FieldProvenance = FieldProvenance.STATED
    page: int | None = None
    section: str | None = None


class SourceConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: _eid("CF"))
    field: str
    values: list[Any] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    resolution: str | None = None
    notes: str | None = None


class BudgetConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: _eid("BC"))
    field: str
    values: list[float] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str | None = None


class ResearchGap(BaseModel):
    gap_id: str = Field(default_factory=lambda: _eid("GAP"))
    gap_type: str
    description: str
    affected_entity_type: str | None = None
    affected_entity_id: str | None = None
    priority: str = "medium"
    suggested_source: str | None = None
    status: str = "open"


class ValidationQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: _eid("VQ"))
    question: str
    why_it_matters: str
    best_contact: str | None = None
    best_official_source: str | None = None
    priority: str = "medium"
    affected_project: str | None = None
    current_evidence: list[str] = Field(default_factory=list)
    required_answer_type: str = "fact"


class CostLedgerEntry(BaseModel):
    task_id: str = Field(default_factory=lambda: _eid("TASK"))
    task_type: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    cache_hit: bool = False
    organization_id: str | None = None
    document_id: str | None = None
    project_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ChangeRecord(BaseModel):
    change_id: str = Field(default_factory=lambda: _eid("CH"))
    project_id: str | None = None
    entity_type: str = "project"
    entity_id: str | None = None
    field: str
    old_value: Any = None
    new_value: Any = None
    detected_at: datetime = Field(default_factory=_utcnow)
    old_evidence: list[Evidence] = Field(default_factory=list)
    new_evidence: list[Evidence] = Field(default_factory=list)
