"""Detect opportunity candidates from the shallow index."""

from __future__ import annotations

from org_intel.projects.record_type_classifier import classify_record_type
from org_intel.schemas.enums import RecordType
from org_intel.schemas.project import ShallowProjectIndexRecord


def select_candidates(
    index: list[ShallowProjectIndexRecord],
    *,
    include_completed: bool = False,
    min_project_value: float | None = None,
    categories: list[str] | None = None,
) -> list[ShallowProjectIndexRecord]:
    out: list[ShallowProjectIndexRecord] = []
    for item in index:
        rtype, eligible, reason = classify_record_type(
            item.project_name, item.category, item.published_stage
        )
        item.record_type = rtype
        if not eligible and rtype not in {
            RecordType.SPECIFIC_CAPITAL_PROJECT,
            RecordType.STUDY_OR_PLAN,
            RecordType.MAJOR_EQUIPMENT_PURCHASE,
            RecordType.CAPITAL_PROGRAM,
        }:
            continue
        stage = (item.published_stage or "").lower()
        if not include_completed and any(k in stage for k in ("complete", "closed", "cancel")):
            continue
        if min_project_value is not None and (item.total_project_cost or 0) < min_project_value:
            continue
        if categories:
            cat = (item.category or "").lower()
            if not any(c.lower() in cat for c in categories):
                continue
        out.append(item)
    return out
