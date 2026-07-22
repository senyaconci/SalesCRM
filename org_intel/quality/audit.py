"""Research gap register and quality audit."""

from __future__ import annotations

from org_intel.schemas.contact import StakeholderMap
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.enums import DocumentType, PreRfqClassification
from org_intel.schemas.evidence import ResearchGap
from org_intel.schemas.organization import FinancialCapitalProfile, OrganizationIdentity
from org_intel.schemas.project import OpportunityAssessment, ProjectRecord
from org_intel.schemas.source import SourceRegistry


def build_research_gaps(
    identity: OrganizationIdentity,
    registry: SourceRegistry,
    inventory: DocumentInventory,
    financial: FinancialCapitalProfile,
    projects: list[ProjectRecord],
    opportunities: list[OpportunityAssessment],
    contacts: StakeholderMap,
) -> list[ResearchGap]:
    gaps: list[ResearchGap] = []

    has_cip = any(
        d.document_type in {
            DocumentType.CAPITAL_IMPROVEMENT_PLAN,
            DocumentType.CIP_SPREADSHEET,
            DocumentType.LIVE_REGISTRY,
            DocumentType.CAPITAL_BUDGET,
        }
        for d in inventory.documents
    )
    if not has_cip:
        gaps.append(
            ResearchGap(
                gap_type="missing_current_cip",
                description="No current CIP / capital registry document identified.",
                priority="high",
                suggested_source="capital improvement portal or finance page",
            )
        )

    has_master = any(
        d.document_type
        in {
            DocumentType.MASTER_PLAN,
            DocumentType.FACILITIES_PLAN,
            DocumentType.AIRPORT_MASTER_PLAN,
            DocumentType.WATER_SYSTEM_PLAN,
        }
        for d in inventory.documents
    )
    if not has_master:
        gaps.append(
            ResearchGap(
                gap_type="missing_master_plan",
                description="No master/facilities plan identified in inventory.",
                priority="medium",
            )
        )

    if not financial.total_annual_budget and not financial.cip_value:
        gaps.append(
            ResearchGap(
                gap_type="missing_financial_metrics",
                description="Organization financial/capital metrics not extracted.",
                priority="medium",
            )
        )

    if not contacts.contacts:
        gaps.append(
            ResearchGap(
                gap_type="missing_contact",
                description="No confirmed stakeholders extracted from official pages.",
                priority="medium",
            )
        )

    for src in registry.sources:
        if src.status.value == "broken":
            gaps.append(
                ResearchGap(
                    gap_type="broken_official_link",
                    description=f"Broken source: {src.url}",
                    affected_entity_type="source",
                    affected_entity_id=src.source_id,
                    priority="high",
                )
            )
        if src.access_method.value == "javascript":
            gaps.append(
                ResearchGap(
                    gap_type="js_only_source",
                    description=f"JavaScript-rendered source may need Playwright: {src.url}",
                    affected_entity_type="source",
                    affected_entity_id=src.source_id,
                    priority="low",
                )
            )

    for project in projects:
        if project.consultants == [] and project.pre_rfq_classification in {
            PreRfqClassification.STRONG_PRE_RFQ,
            PreRfqClassification.POSSIBLE_PRE_RFQ,
        }:
            gaps.append(
                ResearchGap(
                    gap_type="unconfirmed_consultant",
                    description=f"Consultant status unconfirmed for {project.project_name}",
                    affected_entity_type="project",
                    affected_entity_id=project.project_id or project.record_id,
                    priority="high",
                )
            )
        if project.budget_conflicts:
            gaps.append(
                ResearchGap(
                    gap_type="conflicting_budget",
                    description=f"Budget conflicts for {project.project_name}",
                    affected_entity_type="project",
                    affected_entity_id=project.project_id or project.record_id,
                    priority="medium",
                )
            )
        if project.on_call_contract_possible and not project.on_call_contract_evidence:
            gaps.append(
                ResearchGap(
                    gap_type="unknown_on_call_agreement",
                    description=f"Possible on-call usage for {project.project_name} without evidence",
                    affected_entity_type="project",
                    affected_entity_id=project.project_id or project.record_id,
                    priority="medium",
                )
            )

    for note in identity.ambiguity_notes:
        gaps.append(
            ResearchGap(
                gap_type="identity_ambiguity",
                description=note,
                affected_entity_type="organization",
                affected_entity_id=identity.organization_id,
                priority="high",
            )
        )

    return gaps
