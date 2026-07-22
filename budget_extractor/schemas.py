"""Pydantic v2 schemas for capital-project extraction."""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectPhase(str, Enum):
    CONCEPT_IDENTIFIED_NEED = "concept_identified_need"
    EARLY_PLANNING = "early_planning"
    FEASIBILITY_STUDY = "feasibility_study"
    MASTER_PLANNING = "master_planning"
    FUNDING_REQUESTED = "funding_requested"
    FUNDING_APPROVED = "funding_approved"
    CONSULTANT_SELECTION = "consultant_selection"
    PRELIMINARY_DESIGN = "preliminary_design"
    FINAL_DESIGN = "final_design"
    PERMITTING_ENVIRONMENTAL_REVIEW = "permitting_environmental_review"
    PRE_PROCUREMENT = "pre_procurement"
    RFQ_RFP_PREPARATION = "rfq_rfp_preparation"
    RFQ_RFP_ISSUED = "rfq_rfp_issued"
    BID_EVALUATION = "bid_evaluation"
    CONTRACT_AWARDED = "contract_awarded"
    CONSTRUCTION = "construction"
    COMMISSIONING = "commissioning"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class PreRfpStatus(str, Enum):
    STRONG_PRE_RFP = "strong_pre_rfp"
    POSSIBLE_PRE_RFP = "possible_pre_rfp"
    PROCUREMENT_ACTIVE = "procurement_active"
    CONTRACT_AWARDED = "contract_awarded"
    CONSTRUCTION_UNDERWAY = "construction_underway"
    COMPLETED = "completed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class AnnualFunding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fiscal_year: str | None = None
    amount: float | None = None
    amount_raw: str | None = None
    funding_status: str | None = None
    source_pages: list[int] = Field(default_factory=list)

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return _normalize_pages(value)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float | None) -> float | None:
        return _validate_amount(value)


class FundingSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_name: str
    source_type: str | None = None
    amount: float | None = None
    amount_raw: str | None = None
    fiscal_year: str | None = None
    source_pages: list[int] = Field(default_factory=list)

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return _normalize_pages(value)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float | None) -> float | None:
        return _validate_amount(value)


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    title: str | None = None
    department: str | None = None
    email: str | None = None
    phone: str | None = None
    source_pages: list[int] = Field(default_factory=list)

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return _normalize_pages(value)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    quote: str
    evidence_type: str | None = None

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        if value < 1:
            raise ValueError("evidence page must be a positive integer")
        return value

    @field_validator("quote")
    @classmethod
    def validate_quote(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("evidence quote must be non-empty")
        return cleaned


class BudgetConflict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field_name: str
    values: list[str | float] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    explanation: str | None = None

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return _normalize_pages(value)


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    record_id: str = ""
    project_id: str | None = None
    project_name: str
    alternative_project_names: list[str] = Field(default_factory=list)

    owning_organization: str | None = None
    department_or_agency: str | None = None

    project_location: str | None = None
    address_or_site: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None

    project_category: str | None = None
    project_subcategory: str | None = None
    infrastructure_domains: list[str] = Field(default_factory=list)

    project_description: str | None = None
    problem_or_need: str | None = None
    proposed_scope: str | None = None
    major_components: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)

    current_phase: ProjectPhase
    phase_evidence: str | None = None
    phase_is_inferred: bool = False

    pre_rfp_status: PreRfpStatus
    procurement_status: str | None = None
    design_status: str | None = None
    construction_status: str | None = None
    approval_status: str | None = None
    funding_status: str | None = None
    priority_level: str | None = None

    total_project_budget: float | None = None
    total_project_budget_raw: str | None = None
    current_year_budget: float | None = None
    current_year_budget_raw: str | None = None
    prior_year_spending: float | None = None
    future_year_funding: float | None = None
    remaining_budget: float | None = None
    requested_funding: float | None = None
    approved_funding: float | None = None
    unfunded_amount: float | None = None

    bond_funding: float | None = None
    grant_funding: float | None = None
    local_funding: float | None = None
    state_funding: float | None = None
    federal_funding: float | None = None
    other_funding: float | None = None

    annual_funding_schedule: list[AnnualFunding] = Field(default_factory=list)
    funding_sources: list[FundingSource] = Field(default_factory=list)
    fund_or_account: str | None = None
    budget_conflicts: list[BudgetConflict] = Field(default_factory=list)

    estimated_start_date: str | None = None
    estimated_design_date: str | None = None
    estimated_procurement_date: str | None = None
    estimated_bid_date: str | None = None
    estimated_construction_start: str | None = None
    estimated_completion_date: str | None = None
    timeline_notes: str | None = None

    approval_body: str | None = None
    approval_date: str | None = None

    responsible_contacts: list[Contact] = Field(default_factory=list)
    consultants_or_engineers: list[str] = Field(default_factory=list)
    contractors_or_vendors: list[str] = Field(default_factory=list)

    dependencies: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)
    risks_or_constraints: list[str] = Field(default_factory=list)

    source_pages: list[int] = Field(default_factory=list)
    source_sections: list[str] = Field(default_factory=list)
    source_tables_or_appendices: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    first_seen_chunk: str = ""
    seen_in_chunks: list[str] = Field(default_factory=list)
    incomplete_at_chunk_boundary: bool = False

    confidence_score: float
    extraction_notes: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    merged_from_record_ids: list[str] = Field(default_factory=list)

    @field_validator("project_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("project_name must be non-empty")
        return cleaned

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence_score must be between 0 and 1")
        return value

    @field_validator("source_pages")
    @classmethod
    def validate_source_pages(cls, value: list[int]) -> list[int]:
        pages = _normalize_pages(value)
        if not pages:
            raise ValueError("every project must have at least one source page")
        return pages

    @field_validator(
        "total_project_budget",
        "current_year_budget",
        "prior_year_spending",
        "future_year_funding",
        "remaining_budget",
        "requested_funding",
        "approved_funding",
        "unfunded_amount",
        "bond_funding",
        "grant_funding",
        "local_funding",
        "state_funding",
        "federal_funding",
        "other_funding",
    )
    @classmethod
    def validate_budget_fields(cls, value: float | None) -> float | None:
        return _validate_amount(value)

    @model_validator(mode="after")
    def validate_evidence_and_ids(self) -> ProjectRecord:
        if not self.evidence:
            raise ValueError("every project must have at least one evidence excerpt")
        if not self.seen_in_chunks and self.first_seen_chunk:
            self.seen_in_chunks = [self.first_seen_chunk]
        return self


class ChunkValidationIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    severity: Literal["info", "warning", "error"] = "warning"
    issue_type: str
    description: str
    pages: list[int] = Field(default_factory=list)
    record_id: str | None = None
    project_name: str | None = None
    recommended_review: str | None = None


class ChunkExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_metadata: dict[str, Any] = Field(default_factory=dict)
    projects: list[ProjectRecord] = Field(default_factory=list)
    chunk_validation_issues: list[ChunkValidationIssue] = Field(default_factory=list)


class DuplicateDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: Literal["merge", "keep_separate", "uncertain"]
    reason: str = ""
    confidence: float = 0.0
    merged_record: ProjectRecord | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class DuplicateAuditEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: str
    final_record_id: str | None = None
    candidate_record_ids: list[str] = Field(default_factory=list)
    candidate_names: list[str] = Field(default_factory=list)
    similarity_scores: list[float] = Field(default_factory=list)
    merge_reason: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    resolution_method: str
    resolution_confidence: float | None = None


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    severity: Literal["info", "warning", "error"] = "warning"
    issue_type: str
    record_id: str | None = None
    project_name: str | None = None
    chunk_id: str | None = None
    pages: list[int] = Field(default_factory=list)
    description: str
    recommended_review: str | None = None


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_title: str = ""
    organization_name: str = ""
    fiscal_year_or_period: str = ""
    source_file: str = ""
    source_url: str | None = None
    file_sha256: str = ""
    total_pages: int = 0
    processed_pages: int = 0
    ocr_pages: list[int] = Field(default_factory=list)
    failed_pages: list[int] = Field(default_factory=list)
    processing_started_at: str = ""
    processing_completed_at: str = ""
    model: str = ""
    application_version: str = ""
    aggregation_method: str = ""


class ExtractionSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_project_records: int = 0
    final_project_count: int = 0
    duplicate_records_merged: int = 0
    projects_with_known_total_budget: int = 0
    projects_with_unknown_budget: int = 0
    known_total_project_value: float = 0.0
    strong_pre_rfp_count: int = 0
    possible_pre_rfp_count: int = 0
    active_procurement_count: int = 0
    unknown_phase_count: int = 0
    budget_conflict_count: int = 0
    low_confidence_count: int = 0
    sums_by_department: dict[str, float] = Field(default_factory=dict)
    sums_by_category: dict[str, float] = Field(default_factory=dict)
    sums_by_phase: dict[str, float] = Field(default_factory=dict)
    sums_by_fiscal_year: dict[str, float] = Field(default_factory=dict)


class RunStatistics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunks_total: int = 0
    chunks_completed: int = 0
    chunks_failed: int = 0
    api_requests: int = 0
    api_retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    pages_native_text: int = 0
    pages_ocr: int = 0
    pages_failed: int = 0
    scout_enabled: bool = False
    scout_model: str | None = None
    scout_primary_windows: int = 0
    scout_audit_windows: int = 0
    scout_failed_windows: int = 0
    scout_candidate_pages: int = 0
    heavy_pages_selected: int = 0
    pages_filtered_before_extraction: int = 0
    scout_api_requests: int = 0
    scout_prompt_tokens: int = 0
    scout_completion_tokens: int = 0


class FinalExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_metadata: DocumentMetadata
    summary: ExtractionSummary
    projects: list[ProjectRecord] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    duplicate_audit: list[DuplicateAuditEntry] = Field(default_factory=list)
    run_statistics: RunStatistics = Field(default_factory=RunStatistics)


def _normalize_pages(value: list[int] | None) -> list[int]:
    pages: list[int] = []
    for item in value or []:
        page = int(item)
        if page < 1:
            raise ValueError("page numbers must be positive integers")
        if page not in pages:
            pages.append(page)
    return sorted(pages)


def _validate_amount(value: float | None) -> float | None:
    if value is None:
        return None
    # Allow small negative adjustments (credits / reductions) but reject absurd values.
    if value < -1_000_000_000:
        raise ValueError("budget amount is unreasonably negative")
    return float(value)


def normalize_project_name(name: str) -> str:
    text = (name or "").lower()
    text = re.sub(r"\bfy\s*\d{2,4}\b", " ", text)
    text = re.sub(r"\bfiscal year\s*\d{2,4}\b", " ", text)
    replacements = {
        "st.": "street",
        "rd.": "road",
        "ave.": "avenue",
        "blvd.": "boulevard",
        "hwy.": "highway",
        "wwtp": "wastewater treatment plant",
        "wtp": "water treatment plant",
        "&": " and ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_record_id(
    *,
    document_hash: str,
    project_id: str | None,
    project_name: str,
    location: str | None,
) -> str:
    basis = "|".join(
        [
            document_hash or "",
            (project_id or "").strip().lower(),
            normalize_project_name(project_name),
            normalize_project_name(location or ""),
        ]
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"proj_{digest}"
