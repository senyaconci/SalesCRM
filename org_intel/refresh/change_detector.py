"""Detect document and project field changes."""

from __future__ import annotations

from org_intel.schemas.evidence import ChangeRecord
from org_intel.schemas.project import ProjectRecord


def detect_project_changes(
    previous: list[ProjectRecord],
    current: list[ProjectRecord],
) -> list[ChangeRecord]:
    prev_map = {(p.project_id or p.record_id): p for p in previous}
    changes: list[ChangeRecord] = []
    fields = [
        "normalized_phase",
        "total_project_cost",
        "current_year_appropriation",
        "procurement_status",
        "consultant_status",
        "published_status",
        "pre_rfq_classification",
    ]
    for cur in current:
        key = cur.project_id or cur.record_id
        old = prev_map.get(key)
        if not old:
            changes.append(
                ChangeRecord(
                    project_id=cur.project_id,
                    entity_id=cur.record_id,
                    field="record",
                    old_value=None,
                    new_value="added",
                )
            )
            continue
        for field in fields:
            old_val = getattr(old, field)
            new_val = getattr(cur, field)
            old_cmp = old_val.value if hasattr(old_val, "value") else old_val
            new_cmp = new_val.value if hasattr(new_val, "value") else new_val
            if old_cmp != new_cmp:
                changes.append(
                    ChangeRecord(
                        project_id=cur.project_id,
                        entity_id=cur.record_id,
                        field=field,
                        old_value=old_cmp,
                        new_value=new_cmp,
                        old_evidence=old.evidence[:2],
                        new_evidence=cur.evidence[:2],
                    )
                )
    return changes


def document_changed(old_sha: str | None, new_sha: str | None) -> bool:
    if not old_sha or not new_sha:
        return True
    return old_sha != new_sha
