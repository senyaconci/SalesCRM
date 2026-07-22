"""Project, opportunity, and related schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import (
    MatchMethod,
    PreRfqClassification,
    ProcurementStatus,
    ProjectPhase,
    RecordType,
)
from org_intel.schemas.evidence import BudgetConflict, Evidence, SourceConflict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rid(prefix: str = "PRJ") -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


class AnnualFunding(BaseModel):
    fiscal_year: str
    amount: float | None = None
    fund: str | None = None
    source_label: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class FundingSource(BaseModel):
    name: str
    amount: float | None = None
    fund_type: str | None = None
    status: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class CompanyRelationship(BaseModel):
    company_name: str
    canonical_vendor_id: str | None = None
    role: str | None = None
    discipline: str | None = None
    contract_amount: float | None = None
    award_date: str | None = None
    status: str | None = None
    on_call: bool | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class ProjectStakeholder(BaseModel):
    name: str
    title: str | None = None
    department: str | None = None
    functional_role: str | None = None
    email: str | None = None
    phone: str | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class ProjectSourceLink(BaseModel):
    project_id: str
    document_id: str
    match_method: MatchMethod = MatchMethod.FUZZY_NAME
    match_score: float = 0.0
    matching_pages: list[int] = Field(default_factory=list)
    matching_sections: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    likely_fields: list[str] = Field(default_factory=list)
    requires_llm_review: bool = False


class ShallowProjectIndexRecord(BaseModel):
    """Inexpensive project index record from the anchor source."""

    record_id: str = Field(default_factory=lambda: _rid("IDX"))
    organization_id: str
    project_id: str | None = None
    project_name: str
    alternative_names: list[str] = Field(default_factory=list)
    department: str | None = None
    division: str | None = None
    category: str | None = None
    location: str | None = None
    published_stage: str | None = None
    construction_year: str | None = None
    funding_label: str | None = None
    ballot_label: str | None = None
    project_detail_url: str | None = None
    source_url: str | None = None
    source_page: int | None = None
    current_or_archived: str = "current"
    record_type: RecordType = RecordType.UNKNOWN
    total_project_cost: float | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class ProjectRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: _rid("PRJ"))
    organization_id: str

    project_id: str | None = None
    project_name: str
    alternative_names: list[str] = Field(default_factory=list)

    record_type: RecordType = RecordType.UNKNOWN
    lead_eligible: bool = False
    lead_exclusion_reason: str | None = None

    department: str | None = None
    division: str | None = None
    project_manager: str | None = None

    category: str | None = None
    subcategory: str | None = None
    infrastructure_domains: list[str] = Field(default_factory=list)

    location: str | None = None
    address: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None

    project_description: str | None = None
    problem_or_need: str | None = None
    proposed_scope: str | None = None
    major_components: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)

    published_status: str | None = None
    normalized_phase: ProjectPhase = ProjectPhase.UNKNOWN
    phase_evidence: str | None = None
    phase_is_inferred: bool = False

    total_project_cost: float | None = None
    current_year_appropriation: float | None = None
    prior_expenditures: float | None = None
    future_funding: float | None = None
    remaining_balance: float | None = None
    requested_funding: float | None = None
    approved_funding: float | None = None
    unfunded_amount: float | None = None

    funding_schedule: list[AnnualFunding] = Field(default_factory=list)
    funding_sources: list[FundingSource] = Field(default_factory=list)
    budget_conflicts: list[BudgetConflict] = Field(default_factory=list)

    estimated_design_date: str | None = None
    estimated_procurement_date: str | None = None
    estimated_bid_date: str | None = None
    estimated_construction_start: str | None = None
    estimated_completion_date: str | None = None
    construction_year: str | None = None

    consultant_status: str = "unknown"
    consultants: list[CompanyRelationship] = Field(default_factory=list)
    contractors: list[CompanyRelationship] = Field(default_factory=list)
    on_call_contract_possible: bool = False
    on_call_contract_evidence: list[Evidence] = Field(default_factory=list)

    procurement_status: ProcurementStatus = ProcurementStatus.UNKNOWN
    solicitation_ids: list[str] = Field(default_factory=list)
    delivery_method: str | None = None

    pre_rfq_classification: PreRfqClassification = PreRfqClassification.INSUFFICIENT_INFORMATION
    likely_next_procurement: str | None = None
    pursuit_window: str | None = None
    validation_questions: list[str] = Field(default_factory=list)

    stakeholders: list[ProjectStakeholder] = Field(default_factory=list)

    source_links: list[ProjectSourceLink] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    source_conflicts: list[SourceConflict] = Field(default_factory=list)

    first_seen_at: datetime = Field(default_factory=_utcnow)
    last_verified_at: datetime = Field(default_factory=_utcnow)
    confidence_score: float = 0.0
    quality_flags: list[str] = Field(default_factory=list)


class OpportunityAssessment(BaseModel):
    opportunity_id: str = Field(default_factory=lambda: _rid("OPP"))
    organization_id: str
    project_record_id: str
    project_id: str | None = None
    project_name: str
    classification: PreRfqClassification
    likely_next_procurement: str | None = None
    likely_discipline: str | None = None
    pursuit_window: str | None = None
    evidence_for: list[Evidence] = Field(default_factory=list)
    evidence_against: list[Evidence] = Field(default_factory=list)
    known_incumbent: str | None = None
    unknowns: list[str] = Field(default_factory=list)
    validation_questions: list[str] = Field(default_factory=list)
    best_contacts: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    notes: str | None = None


class MergeDecision(BaseModel):
    merge_id: str = Field(default_factory=lambda: _rid("MRG"))
    candidate_record_ids: list[str]
    decision: str  # merge|keep_separate|needs_review
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    selected_fields: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
