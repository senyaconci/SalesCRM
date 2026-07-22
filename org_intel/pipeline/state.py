"""In-memory / on-disk run state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from org_intel.schemas.contact import StakeholderMap
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.evidence import ChangeRecord, ResearchGap, ValidationQuestion
from org_intel.schemas.organization import (
    FinancialCapitalProfile,
    OrganizationIdentity,
    OrganizationRelationshipGraph,
)
from org_intel.schemas.procurement import IncumbentVendorAnalysis, ProcurementEvent, SolicitationRecord
from org_intel.schemas.project import (
    OpportunityAssessment,
    ProjectRecord,
    ProjectSourceLink,
    ShallowProjectIndexRecord,
)
from org_intel.schemas.source import SourceRegistry


@dataclass
class RunState:
    identity: OrganizationIdentity | None = None
    org_graph: OrganizationRelationshipGraph | None = None
    source_registry: SourceRegistry | None = None
    document_inventory: DocumentInventory | None = None
    financial_profile: FinancialCapitalProfile | None = None
    anchor_selection: dict[str, Any] = field(default_factory=dict)
    project_index: list[ShallowProjectIndexRecord] = field(default_factory=list)
    project_source_map: list[ProjectSourceLink] = field(default_factory=list)
    projects_full: list[ProjectRecord] = field(default_factory=list)
    opportunities: list[OpportunityAssessment] = field(default_factory=list)
    solicitations: list[SolicitationRecord] = field(default_factory=list)
    procurement_events: list[ProcurementEvent] = field(default_factory=list)
    incumbent_analysis: IncumbentVendorAnalysis | None = None
    contacts: StakeholderMap | None = None
    validation_plan: list[ValidationQuestion] = field(default_factory=list)
    research_gaps: list[ResearchGap] = field(default_factory=list)
    change_history: list[ChangeRecord] = field(default_factory=list)
    page_indexes: dict[str, Any] = field(default_factory=dict)
