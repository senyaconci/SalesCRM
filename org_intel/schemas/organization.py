"""Organization identity, relationships, and financial profile schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from org_intel.schemas.enums import (
    EntityNodeType,
    FieldProvenance,
    OrganizationType,
    RelationshipType,
)
from org_intel.schemas.evidence import Evidence, FieldEvidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


class MetricValue(BaseModel):
    value: float | str | None = None
    fiscal_year: str | None = None
    period: str | None = None
    source_url: str | None = None
    page: int | None = None
    section: str | None = None
    confidence: float = 0.0
    exactness: str = "unknown"  # exact|rounded|calculated|inferred|unknown
    provenance: FieldProvenance = FieldProvenance.UNKNOWN
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str | None = None


class OrganizationIdentity(BaseModel):
    organization_id: str = Field(default_factory=lambda: _id("ORG"))
    canonical_name: str
    common_names: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    organization_type: OrganizationType = OrganizationType.UNKNOWN
    parent_organization: str | None = None
    subsidiaries: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    state: str | None = None
    county: str | None = None
    main_address: str | None = None
    main_phone: str | None = None
    official_domain: str | None = None
    additional_domains: list[str] = Field(default_factory=list)
    official_url: str | None = None
    service_area: str | None = None
    population_or_customer_base: str | None = None
    fiscal_year: str | None = None
    governance_model: str | None = None
    active_status: str = "active"
    government_identifiers: dict[str, str] = Field(default_factory=dict)
    ambiguity_notes: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_evidence: list[FieldEvidence] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class OrganizationNode(BaseModel):
    node_id: str = Field(default_factory=lambda: _id("NODE"))
    name: str
    entity_type: EntityNodeType = EntityNodeType.DEPARTMENT
    parent_id: str | None = None
    function: str | None = None
    has_separate_budget: bool | None = None
    has_separate_procurement: bool | None = None
    capital_responsibilities: list[str] = Field(default_factory=list)
    official_url: str | None = None
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class OrganizationRelationship(BaseModel):
    relationship_id: str = Field(default_factory=lambda: _id("REL"))
    from_node_id: str
    to_node_id: str
    relationship_type: RelationshipType
    confidence: float = 0.0
    evidence: list[Evidence] = Field(default_factory=list)


class OrganizationRelationshipGraph(BaseModel):
    organization_id: str
    nodes: list[OrganizationNode] = Field(default_factory=list)
    relationships: list[OrganizationRelationship] = Field(default_factory=list)
    capital_responsibility_summary: dict[str, list[str]] = Field(default_factory=dict)


class FinancialCapitalProfile(BaseModel):
    organization_id: str
    total_annual_budget: MetricValue | None = None
    total_operating_expenditure: MetricValue | None = None
    total_capital_expenditure: MetricValue | None = None
    cip_value: MetricValue | None = None
    enterprise_fund_capital: MetricValue | None = None
    general_fund_position: MetricValue | None = None
    major_revenue_sources: list[MetricValue] = Field(default_factory=list)
    capital_sales_taxes: list[MetricValue] = Field(default_factory=list)
    bonds: list[MetricValue] = Field(default_factory=list)
    grants: list[MetricValue] = Field(default_factory=list)
    state_revolving_funds: list[MetricValue] = Field(default_factory=list)
    developer_contributions: list[MetricValue] = Field(default_factory=list)
    utility_rates_and_fees: list[MetricValue] = Field(default_factory=list)
    debt_capacity: MetricValue | None = None
    major_ballot_measures: list[dict[str, Any]] = Field(default_factory=list)
    capital_planning_period: str | None = None
    budget_development_calendar: str | None = None
    adoption_dates: list[str] = Field(default_factory=list)
    cip_update_cycle: str | None = None
    notes: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = 0.0
