"""Validation plan generation."""

from __future__ import annotations

from org_intel.schemas.evidence import ValidationQuestion
from org_intel.schemas.project import OpportunityAssessment, ProjectRecord
from org_intel.schemas.enums import PreRfqClassification


def build_validation_plan(
    projects: list[ProjectRecord],
    opportunities: list[OpportunityAssessment],
) -> list[ValidationQuestion]:
    plan: list[ValidationQuestion] = []
    opp_by_record = {o.project_record_id: o for o in opportunities}

    for project in projects:
        opp = opp_by_record.get(project.record_id)
        if not opp:
            continue
        if opp.classification not in {
            PreRfqClassification.STRONG_PRE_RFQ,
            PreRfqClassification.POSSIBLE_PRE_RFQ,
            PreRfqClassification.MONITOR,
            PreRfqClassification.INSUFFICIENT_INFORMATION,
        }:
            continue
        for q in opp.validation_questions or [
            f"Confirm procurement status for {project.project_name}"
        ]:
            plan.append(
                ValidationQuestion(
                    question=q,
                    why_it_matters="Determines whether the project is a true pre-RFQ opportunity.",
                    best_contact=opp.best_contacts[0] if opp.best_contacts else None,
                    best_official_source="procurement portal or project manager",
                    priority="high"
                    if opp.classification == PreRfqClassification.STRONG_PRE_RFQ
                    else "medium",
                    affected_project=project.project_id or project.record_id,
                    current_evidence=[e.quote for e in (opp.evidence_for + project.evidence)[:5]],
                    required_answer_type="fact",
                )
            )
        if project.budget_conflicts:
            plan.append(
                ValidationQuestion(
                    question=f"Which budget figure is authoritative for {project.project_name}?",
                    why_it_matters="Conflicting budget figures affect pursuit prioritization.",
                    best_official_source="adopted budget / CIP registry",
                    priority="medium",
                    affected_project=project.project_id or project.record_id,
                    current_evidence=[c.notes or "" for c in project.budget_conflicts],
                    required_answer_type="numeric",
                )
            )
    return plan
