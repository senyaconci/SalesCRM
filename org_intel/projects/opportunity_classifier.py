"""Pre-RFQ / pre-RFP opportunity assessment."""

from __future__ import annotations

from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import OPPORTUNITY_ASSESS
from org_intel.llm.router import LLMRouter
from org_intel.schemas.enums import (
    PreRfqClassification,
    ProcurementStatus,
    ProjectPhase,
    RecordType,
)
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.project import OpportunityAssessment, ProjectRecord


_BLOCKING_PROC = {
    ProcurementStatus.RFQ_RFP_ACTIVE,
    ProcurementStatus.BID_ACTIVE,
    ProcurementStatus.CONSULTANT_SELECTED,
    ProcurementStatus.CONTRACTOR_SELECTED,
    ProcurementStatus.CONTRACT_AWARDED,
    ProcurementStatus.CONSTRUCTION_UNDERWAY,
    ProcurementStatus.COMPLETED,
}

_BLOCKING_PHASE = {
    ProjectPhase.RFQ_RFP_ISSUED,
    ProjectPhase.BID_EVALUATION,
    ProjectPhase.CONTRACT_AWARDED,
    ProjectPhase.CONSTRUCTION,
    ProjectPhase.COMMISSIONING,
    ProjectPhase.COMPLETED,
    ProjectPhase.CANCELLED,
}


def classify_opportunity(
    project: ProjectRecord,
    *,
    router: LLMRouter | None = None,
) -> OpportunityAssessment:
    classification, reasons_for, reasons_against = _deterministic(project)

    assessment = OpportunityAssessment(
        organization_id=project.organization_id,
        project_record_id=project.record_id,
        project_id=project.project_id,
        project_name=project.project_name,
        classification=classification,
        likely_next_procurement=_next_procurement(project, classification),
        likely_discipline=_discipline(project),
        pursuit_window=_pursuit_window(project, classification),
        evidence_for=[
            Evidence(quote=r, supports_fields=["pre_rfq_classification"], confidence=0.7)
            for r in reasons_for
        ],
        evidence_against=[
            Evidence(quote=r, supports_fields=["pre_rfq_classification"], confidence=0.7)
            for r in reasons_against
        ],
        known_incumbent=project.consultants[0].company_name if project.consultants else None,
        unknowns=_unknowns(project),
        validation_questions=_validation_questions(project, classification),
        best_contacts=[s.name for s in project.stakeholders[:3]],
        confidence=0.55 if classification != PreRfqClassification.INSUFFICIENT_INFORMATION else 0.3,
    )

    project.pre_rfq_classification = classification
    project.likely_next_procurement = assessment.likely_next_procurement
    project.pursuit_window = assessment.pursuit_window
    project.validation_questions = assessment.validation_questions

    if router is not None and classification in {
        PreRfqClassification.STRONG_PRE_RFQ,
        PreRfqClassification.POSSIBLE_PRE_RFQ,
        PreRfqClassification.MONITOR,
        PreRfqClassification.INSUFFICIENT_INFORMATION,
    }:
        try:
            data = router.complete_json(
                ModelRole.REASONING_MODEL,
                OPPORTUNITY_ASSESS,
                _project_brief(project),
                task_type="opportunity_assess",
                organization_id=project.organization_id,
                project_id=project.project_id,
            )
            if isinstance(data, dict) and data.get("classification"):
                try:
                    assessment.classification = PreRfqClassification(data["classification"])
                    project.pre_rfq_classification = assessment.classification
                except ValueError:
                    pass
                for key in (
                    "likely_next_procurement",
                    "likely_discipline",
                    "pursuit_window",
                    "notes",
                ):
                    if data.get(key):
                        setattr(assessment, key, data[key])
                if data.get("unknowns"):
                    assessment.unknowns = list(data["unknowns"])
                if data.get("validation_questions"):
                    assessment.validation_questions = list(data["validation_questions"])
                if data.get("confidence") is not None:
                    assessment.confidence = float(data["confidence"])
        except Exception:
            pass

    return assessment


def assess_projects(
    projects: list[ProjectRecord],
    router: LLMRouter | None = None,
) -> list[OpportunityAssessment]:
    out: list[OpportunityAssessment] = []
    for project in projects:
        if not project.lead_eligible and project.record_type not in {
            RecordType.SPECIFIC_CAPITAL_PROJECT,
            RecordType.STUDY_OR_PLAN,
            RecordType.MAJOR_EQUIPMENT_PURCHASE,
            RecordType.CAPITAL_PROGRAM,
        }:
            out.append(
                OpportunityAssessment(
                    organization_id=project.organization_id,
                    project_record_id=project.record_id,
                    project_id=project.project_id,
                    project_name=project.project_name,
                    classification=PreRfqClassification.NOT_AN_EXTERNAL_OPPORTUNITY,
                    unknowns=["Record not lead-eligible"],
                    confidence=0.8,
                    notes=project.lead_exclusion_reason,
                )
            )
            project.pre_rfq_classification = PreRfqClassification.NOT_AN_EXTERNAL_OPPORTUNITY
            continue
        out.append(classify_opportunity(project, router=router))
    return out


def _deterministic(
    project: ProjectRecord,
) -> tuple[PreRfqClassification, list[str], list[str]]:
    reasons_for: list[str] = []
    reasons_against: list[str] = []

    if project.record_type == RecordType.BUDGET_LINE_ITEM:
        return (
            PreRfqClassification.NOT_AN_EXTERNAL_OPPORTUNITY,
            [],
            ["Budget line item without defined external scope"],
        )
    if project.normalized_phase == ProjectPhase.COMPLETED:
        return PreRfqClassification.COMPLETED, [], ["Phase completed"]
    if project.normalized_phase == ProjectPhase.CONSTRUCTION:
        return PreRfqClassification.CONSTRUCTION_UNDERWAY, [], ["Construction underway"]
    if project.normalized_phase == ProjectPhase.CONTRACT_AWARDED:
        return PreRfqClassification.CONTRACT_AWARDED, [], ["Contract awarded"]
    if project.procurement_status in {
        ProcurementStatus.CONSULTANT_SELECTED,
        ProcurementStatus.CONTRACTOR_SELECTED,
    } or project.consultants:
        if project.consultants:
            reasons_against.append("Consultant already identified in evidence")
        return PreRfqClassification.CONSULTANT_SELECTED, [], reasons_against or ["Consultant selected"]
    if project.procurement_status in {
        ProcurementStatus.RFQ_RFP_ACTIVE,
        ProcurementStatus.BID_ACTIVE,
    } or project.normalized_phase == ProjectPhase.RFQ_RFP_ISSUED:
        return PreRfqClassification.PROCUREMENT_ACTIVE, [], ["Active solicitation evidence"]

    if project.normalized_phase in {
        ProjectPhase.CONCEPT_IDENTIFIED_NEED,
        ProjectPhase.EARLY_PLANNING,
        ProjectPhase.MASTER_PLANNING,
    }:
        return PreRfqClassification.TOO_EARLY, [], [f"Phase too early: {project.normalized_phase.value}"]

    scope_defined = bool(project.proposed_scope or project.project_description or project.major_components)
    funded = project.normalized_phase in {
        ProjectPhase.FUNDING_APPROVED,
        ProjectPhase.PRELIMINARY_DESIGN,
        ProjectPhase.FINAL_DESIGN,
        ProjectPhase.PRE_PROCUREMENT,
        ProjectPhase.RFQ_RFP_PREPARATION,
        ProjectPhase.CONSULTANT_SELECTION,
    } or bool(project.approved_funding or project.total_project_cost)

    if scope_defined:
        reasons_for.append("Scope/description present in evidence")
    else:
        reasons_against.append("Scope not sufficiently defined in researched sources")

    if funded:
        reasons_for.append("Funding or advanced planning phase evidenced")
    if project.normalized_phase in {
        ProjectPhase.PRE_PROCUREMENT,
        ProjectPhase.RFQ_RFP_PREPARATION,
        ProjectPhase.CONSULTANT_SELECTION,
        ProjectPhase.FUNDING_APPROVED,
    }:
        reasons_for.append(f"Phase suggests upcoming external procurement: {project.normalized_phase.value}")

    if scope_defined and funded and not project.consultants and project.procurement_status in {
        ProcurementStatus.NO_PROCUREMENT_EVIDENCE,
        ProcurementStatus.INTERNAL_PLANNING,
        ProcurementStatus.CONSULTANT_SELECTION_EXPECTED,
        ProcurementStatus.SOLICITATION_IN_PREPARATION,
        ProcurementStatus.UNKNOWN,
    }:
        if project.normalized_phase in {
            ProjectPhase.PRE_PROCUREMENT,
            ProjectPhase.RFQ_RFP_PREPARATION,
            ProjectPhase.CONSULTANT_SELECTION,
            ProjectPhase.FINAL_DESIGN,
        }:
            return PreRfqClassification.STRONG_PRE_RFQ, reasons_for, reasons_against
        return PreRfqClassification.POSSIBLE_PRE_RFQ, reasons_for, reasons_against

    if scope_defined:
        return PreRfqClassification.MONITOR, reasons_for, reasons_against

    return PreRfqClassification.INSUFFICIENT_INFORMATION, reasons_for, reasons_against + [
        "Insufficient evidence for opportunity classification"
    ]


def _next_procurement(project: ProjectRecord, classification: PreRfqClassification) -> str | None:
    if classification in {
        PreRfqClassification.STRONG_PRE_RFQ,
        PreRfqClassification.POSSIBLE_PRE_RFQ,
    }:
        if project.record_type == RecordType.STUDY_OR_PLAN:
            return "planning_or_engineering_study_rfq"
        if project.normalized_phase in {ProjectPhase.FINAL_DESIGN, ProjectPhase.PRE_PROCUREMENT}:
            return "construction_bid_or_cm"
        return "design_or_professional_services_rfq"
    return None


def _discipline(project: ProjectRecord) -> str | None:
    cat = (project.category or "").lower()
    name = project.project_name.lower()
    blob = f"{cat} {name} {' '.join(project.infrastructure_domains)}"
    for key, label in (
        ("water", "water_engineering"),
        ("wastewater", "wastewater_engineering"),
        ("sewer", "wastewater_engineering"),
        ("storm", "stormwater_engineering"),
        ("street", "civil_transportation"),
        ("road", "civil_transportation"),
        ("bridge", "structural_bridge"),
        ("airport", "aviation_engineering"),
        ("park", "landscape_architecture"),
        ("facility", "architecture_facilities"),
        ("school", "architecture_education"),
    ):
        if key in blob:
            return label
    return None


def _pursuit_window(project: ProjectRecord, classification: PreRfqClassification) -> str | None:
    if classification == PreRfqClassification.STRONG_PRE_RFQ:
        return "near_term_0_12_months"
    if classification == PreRfqClassification.POSSIBLE_PRE_RFQ:
        return "medium_term_6_24_months"
    if classification == PreRfqClassification.MONITOR:
        return "monitor_for_funding_or_scope"
    return None


def _unknowns(project: ProjectRecord) -> list[str]:
    unknowns = []
    if not project.consultants:
        unknowns.append("Unconfirmed consultant status")
    if project.procurement_status == ProcurementStatus.UNKNOWN:
        unknowns.append("Unknown procurement schedule")
    if not project.proposed_scope and not project.project_description:
        unknowns.append("Missing technical scope")
    if project.budget_conflicts:
        unknowns.append("Conflicting budget figures")
    return unknowns


def _validation_questions(project: ProjectRecord, classification: PreRfqClassification) -> list[str]:
    qs = [
        f"Has a design consultant already been selected for {project.project_name}?",
        "Is there an active on-call agreement that will absorb this work?",
        "What is the expected RFQ/RFP advertisement date?",
    ]
    if classification in {
        PreRfqClassification.STRONG_PRE_RFQ,
        PreRfqClassification.POSSIBLE_PRE_RFQ,
    }:
        qs.append("Which department will manage procurement for this project?")
    return qs


def _project_brief(project: ProjectRecord) -> str:
    return (
        f"Name: {project.project_name}\n"
        f"ID: {project.project_id}\n"
        f"Type: {project.record_type.value}\n"
        f"Phase: {project.normalized_phase.value} (inferred={project.phase_is_inferred})\n"
        f"Procurement: {project.procurement_status.value}\n"
        f"Consultants: {[c.company_name for c in project.consultants]}\n"
        f"Scope: {project.proposed_scope or project.project_description}\n"
        f"Cost: {project.total_project_cost}\n"
        f"Evidence quotes: {[e.quote for e in project.evidence[:5]]}\n"
    )
