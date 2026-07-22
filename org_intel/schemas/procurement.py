"""Procurement, solicitation, award, and vendor schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import FieldProvenance, ProcurementStatus
from org_intel.schemas.evidence import Evidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


class SolicitationRecord(BaseModel):
    solicitation_id: str = Field(default_factory=lambda: _id("SOL"))
    organization_id: str
    solicitation_number: str | None = None
    title: str = ""
    solicitation_type: str | None = None  # RFQ|RFP|IFB|RFI|other
    status: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    department: str | None = None
    related_project_ids: list[str] = Field(default_factory=list)
    url: str | None = None
    portal: str | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class ProcurementEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: _id("PEV"))
    organization_id: str
    project_record_id: str | None = None
    event_type: str
    status: ProcurementStatus = ProcurementStatus.UNKNOWN
    firm_name: str | None = None
    amount: float | None = None
    date: str | None = None
    document_id: str | None = None
    url: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class VendorRecord(BaseModel):
    vendor_id: str = Field(default_factory=lambda: _id("VND"))
    canonical_name: str
    source_names: list[str] = Field(default_factory=list)
    disciplines: list[str] = Field(default_factory=list)
    departments_served: list[str] = Field(default_factory=list)
    award_count: int = 0
    total_known_award_value: float | None = None
    most_recent_award: str | None = None
    active_agreements: list[str] = Field(default_factory=list)
    possible_expiration: str | None = None
    relationship_strength: str | None = None  # confirmed|calculated|inferred
    on_call_status: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    provenance_notes: list[str] = Field(default_factory=list)


class DisciplineCoverage(BaseModel):
    discipline: str
    status: str  # incumbent_identified|no_incumbent_identified_in_researched_sources
    vendors: list[str] = Field(default_factory=list)
    provenance: FieldProvenance = FieldProvenance.INFERRED


class IncumbentVendorAnalysis(BaseModel):
    organization_id: str
    vendors: list[VendorRecord] = Field(default_factory=list)
    discipline_coverage: list[DisciplineCoverage] = Field(default_factory=list)
    concentration_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
