"""Project deduplication and entity resolution."""

from __future__ import annotations

from org_intel.schemas.project import MergeDecision, ProjectRecord, ShallowProjectIndexRecord
from org_intel.utils.names import is_generic_project_name, project_name_similarity


def find_merge_candidates(projects: list[ProjectRecord]) -> list[MergeDecision]:
    decisions: list[MergeDecision] = []
    for i, a in enumerate(projects):
        for b in projects[i + 1 :]:
            decision = _compare(a, b)
            if decision:
                decisions.append(decision)
    return decisions


def _compare(a: ProjectRecord, b: ProjectRecord) -> MergeDecision | None:
    signals: list[str] = []
    score = 0.0

    if a.project_id and b.project_id and a.project_id.upper() == b.project_id.upper():
        signals.append("exact_project_id")
        score += 50
    name_sim = project_name_similarity(a.project_name, b.project_name)
    if name_sim >= 95:
        signals.append("similar_official_name")
        score += 30
    elif name_sim >= 88:
        signals.append("fuzzy_name")
        score += 15

    if is_generic_project_name(a.project_name) or is_generic_project_name(b.project_name):
        # Never merge on generic names alone
        if "exact_project_id" not in signals:
            return MergeDecision(
                candidate_record_ids=[a.record_id, b.record_id],
                decision="keep_separate",
                confidence=0.9,
                evidence=["generic_name_false_duplicate_prevention"] + signals,
                notes="Generic project names must not merge without project ID or strong multi-signal evidence.",
            )

    if a.location and b.location and a.location.lower() == b.location.lower():
        signals.append("same_location")
        score += 10
    if a.department and b.department and a.department.lower() == b.department.lower():
        signals.append("same_department")
        score += 8
    if (
        a.total_project_cost
        and b.total_project_cost
        and abs(a.total_project_cost - b.total_project_cost) / max(a.total_project_cost, 1) < 0.05
    ):
        signals.append("similar_budget")
        score += 10
    if a.construction_year and b.construction_year and a.construction_year == b.construction_year:
        signals.append("same_construction_year")
        score += 8

    if score < 40:
        return None

    decision = "merge" if score >= 60 and "exact_project_id" in signals else "needs_review"
    if score >= 70 and name_sim >= 95 and len(signals) >= 3:
        decision = "merge"

    return MergeDecision(
        candidate_record_ids=[a.record_id, b.record_id],
        decision=decision,
        confidence=min(0.99, score / 100),
        evidence=signals,
        selected_fields={
            "project_name": a.project_name if (a.confidence_score or 0) >= (b.confidence_score or 0) else b.project_name,
            "total_project_cost": a.total_project_cost or b.total_project_cost,
        },
    )


def dedupe_shallow(records: list[ShallowProjectIndexRecord]) -> list[ShallowProjectIndexRecord]:
    by_id: dict[str, ShallowProjectIndexRecord] = {}
    no_id: list[ShallowProjectIndexRecord] = []
    for rec in records:
        if rec.project_id:
            key = rec.project_id.upper()
            if key not in by_id:
                by_id[key] = rec
            else:
                # keep higher confidence
                if rec.confidence > by_id[key].confidence:
                    by_id[key] = rec
        else:
            no_id.append(rec)
    # filter generic duplicates among no_id
    kept: list[ShallowProjectIndexRecord] = []
    for rec in no_id:
        if any(
            project_name_similarity(rec.project_name, k.project_name) >= 95
            and not is_generic_project_name(rec.project_name)
            for k in kept
        ):
            continue
        kept.append(rec)
    return list(by_id.values()) + kept
