"""Cross-source evidence consolidation with conflict preservation."""

from __future__ import annotations

from org_intel.schemas.enums import FieldProvenance
from org_intel.schemas.evidence import BudgetConflict, Evidence, SourceConflict
from org_intel.schemas.project import ProjectRecord


def consolidate_project(record: ProjectRecord) -> ProjectRecord:
    """Preserve conflicts rather than silently overwriting."""
    # Budget hierarchy: do not mix appropriation with total cost
    if (
        record.current_year_appropriation
        and record.total_project_cost
        and abs(record.current_year_appropriation - record.total_project_cost)
        / max(record.total_project_cost, 1)
        < 0.01
    ):
        record.quality_flags.append(
            "annual_appropriation_equals_total_cost_check — verify these are not conflated"
        )
        record.budget_conflicts.append(
            BudgetConflict(
                field="total_project_cost_vs_appropriation",
                values=[record.total_project_cost, record.current_year_appropriation],
                notes="Possible conflation of annual appropriation with total project cost.",
            )
        )

    # Phase vs procurement consistency
    if record.consultants and record.consultant_status == "unknown":
        record.consultant_status = "identified"
    if record.consultants and record.normalized_phase.value in {
        "funding_approved",
        "early_planning",
        "concept_identified_need",
    }:
        record.source_conflicts.append(
            SourceConflict(
                field="phase_vs_consultant",
                values=[record.normalized_phase.value, "consultant_present"],
                evidence=record.evidence[:1],
                notes="Consultant evidence present; phase may need update. Conflict preserved.",
            )
        )

    # Mark inferred phases
    if record.phase_is_inferred:
        record.quality_flags.append("phase_is_inferred")
        record.evidence.append(
            Evidence(
                quote=record.phase_evidence or "phase inferred",
                supports_fields=["normalized_phase"],
                confidence=0.4,
                provenance=FieldProvenance.INFERRED,
                evidence_type="inference",
            )
        )
    return record


def consolidate_many(records: list[ProjectRecord]) -> list[ProjectRecord]:
    return [consolidate_project(r) for r in records]
