"""Confidence aggregation helpers."""

from __future__ import annotations

from org_intel.schemas.project import ProjectRecord


def score_project_confidence(project: ProjectRecord) -> float:
    parts = []
    if project.evidence:
        parts.append(min(1.0, sum(e.confidence for e in project.evidence) / max(len(project.evidence), 1)))
    if project.source_links:
        parts.append(min(1.0, max(l.match_score for l in project.source_links) / 100))
    if project.project_id:
        parts.append(0.8)
    if project.proposed_scope or project.project_description:
        parts.append(0.7)
    if project.phase_is_inferred:
        parts.append(0.4)
    if not parts:
        return 0.2
    score = sum(parts) / len(parts)
    project.confidence_score = score
    return score
