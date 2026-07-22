"""Document-level summary statistics and quality checks."""

from __future__ import annotations

from collections import defaultdict

from budget_extractor.schemas import (
    ExtractionSummary,
    PreRfpStatus,
    ProjectPhase,
    ProjectRecord,
    ValidationIssue,
)

AGGREGATION_METHOD = (
    "Totals use each project's total_project_budget when present. "
    "Annual appropriations and funding-source rows are summarized separately and are NOT "
    "added into known_total_project_value, to avoid double-counting multi-year schedules."
)


def build_summary(
    *,
    raw_count: int,
    projects: list[ProjectRecord],
    duplicate_merged_count: int,
) -> ExtractionSummary:
    known = [p for p in projects if p.total_project_budget is not None]
    unknown = [p for p in projects if p.total_project_budget is None]

    by_department: dict[str, float] = defaultdict(float)
    by_category: dict[str, float] = defaultdict(float)
    by_phase: dict[str, float] = defaultdict(float)
    by_year: dict[str, float] = defaultdict(float)

    for project in known:
        amount = float(project.total_project_budget or 0.0)
        dept = project.department_or_agency or "Unknown department"
        category = project.project_category or "Unknown category"
        phase = (
            project.current_phase.value
            if isinstance(project.current_phase, ProjectPhase)
            else str(project.current_phase)
        )
        by_department[dept] += amount
        by_category[category] += amount
        by_phase[phase] += amount

    # Fiscal-year sums are based on annual schedules only (not mixed into master total).
    for project in projects:
        for row in project.annual_funding_schedule:
            year = row.fiscal_year or "Unknown FY"
            if row.amount is not None:
                by_year[year] += float(row.amount)

    return ExtractionSummary(
        raw_project_records=raw_count,
        final_project_count=len(projects),
        duplicate_records_merged=duplicate_merged_count,
        projects_with_known_total_budget=len(known),
        projects_with_unknown_budget=len(unknown),
        known_total_project_value=round(sum(float(p.total_project_budget or 0.0) for p in known), 2),
        strong_pre_rfp_count=sum(
            1 for p in projects if p.pre_rfp_status == PreRfpStatus.STRONG_PRE_RFP
        ),
        possible_pre_rfp_count=sum(
            1 for p in projects if p.pre_rfp_status == PreRfpStatus.POSSIBLE_PRE_RFP
        ),
        active_procurement_count=sum(
            1 for p in projects if p.pre_rfp_status == PreRfpStatus.PROCUREMENT_ACTIVE
        ),
        unknown_phase_count=sum(1 for p in projects if p.current_phase == ProjectPhase.UNKNOWN),
        budget_conflict_count=sum(len(p.budget_conflicts) for p in projects),
        low_confidence_count=sum(1 for p in projects if p.confidence_score < 0.55),
        sums_by_department=dict(sorted(by_department.items())),
        sums_by_category=dict(sorted(by_category.items())),
        sums_by_phase=dict(sorted(by_phase.items())),
        sums_by_fiscal_year=dict(sorted(by_year.items())),
    )


def build_document_quality_issues(projects: list[ProjectRecord]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Detect project IDs reused by apparently different projects.
    by_id: dict[str, list[ProjectRecord]] = defaultdict(list)
    for project in projects:
        if project.project_id:
            by_id[project.project_id.strip().lower()].append(project)

    for project_id, group in by_id.items():
        if len(group) < 2:
            continue
        names = {p.project_name.strip().lower() for p in group}
        if len(names) > 1:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    issue_type="reused_project_id",
                    record_id=group[0].record_id,
                    project_name=group[0].project_name,
                    pages=sorted({page for p in group for page in p.source_pages}),
                    description=(
                        f"Project ID {project_id!r} is shared by {len(group)} records "
                        f"with different names."
                    ),
                    recommended_review="Confirm whether these are aliases or distinct projects.",
                )
            )
            for project in group:
                if "reused_project_id" not in project.quality_flags:
                    project.quality_flags.append("reused_project_id")

    for project in projects:
        for flag in project.quality_flags:
            if flag in {"missing_budget", "low_confidence", "conflicting_budgets", "incomplete_chunk_boundary"}:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        issue_type=flag,
                        record_id=project.record_id,
                        project_name=project.project_name,
                        pages=project.source_pages,
                        description=f"Quality flag raised: {flag}",
                        recommended_review="Review source pages and evidence excerpts.",
                    )
                )
    return issues
