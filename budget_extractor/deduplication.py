"""Conservative duplicate detection and consolidation."""

from __future__ import annotations

import json
import logging
from typing import Any

from rapidfuzz import fuzz

from budget_extractor.glm_client import GlmClient
from budget_extractor.prompts import build_duplicate_resolution_messages
from budget_extractor.schemas import (
    DuplicateAuditEntry,
    DuplicateDecision,
    ProjectRecord,
    generate_record_id,
    normalize_project_name,
)
from budget_extractor.validation import compute_quality_flags, parse_json_text

LOGGER = logging.getLogger(__name__)

GENERIC_NAME_FRAGMENTS = {
    "water improvements",
    "street improvements",
    "facility upgrades",
    "equipment replacement",
    "improvements",
    "upgrade",
    "upgrades",
    "replacement",
    "renovation",
    "rehabilitation",
}


def find_duplicate_groups(
    projects: list[ProjectRecord],
    *,
    name_threshold: float = 92.0,
) -> list[list[int]]:
    """Return groups of project indexes that are likely duplicates."""
    n = len(projects)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            score, reason = pairwise_similarity(projects[i], projects[j])
            if score >= name_threshold and reason != "generic_only":
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def pairwise_similarity(a: ProjectRecord, b: ProjectRecord) -> tuple[float, str]:
    if a.project_id and b.project_id:
        if _norm_id(a.project_id) == _norm_id(b.project_id):
            return 99.0, "project_id"

    name_a = normalize_project_name(a.project_name)
    name_b = normalize_project_name(b.project_name)
    if not name_a or not name_b:
        return 0.0, "missing_name"

    if _is_generic_name(name_a) and _is_generic_name(name_b):
        # Generic names alone are never enough.
        if not _supporting_signals(a, b):
            return 40.0, "generic_only"

    name_score = float(fuzz.token_set_ratio(name_a, name_b))
    support = 0.0
    reasons: list[str] = ["name"]

    if _same_text(a.project_location, b.project_location) or _same_text(
        a.address_or_site, b.address_or_site
    ):
        support += 8
        reasons.append("location")
    if _same_text(a.department_or_agency, b.department_or_agency):
        support += 5
        reasons.append("department")
    if _budgets_similar(a.total_project_budget, b.total_project_budget):
        support += 8
        reasons.append("budget")
    if set(a.source_pages) & set(b.source_pages):
        support += 6
        reasons.append("pages")
    if a.project_description and b.project_description:
        desc = float(
            fuzz.token_set_ratio(
                normalize_project_name(a.project_description[:500]),
                normalize_project_name(b.project_description[:500]),
            )
        )
        if desc >= 90:
            support += 7
            reasons.append("description")
    if a.major_components and b.major_components:
        comp = float(
            fuzz.token_set_ratio(
                " ".join(a.major_components).lower(),
                " ".join(b.major_components).lower(),
            )
        )
        if comp >= 90:
            support += 5
            reasons.append("components")

    score = min(100.0, name_score + support)
    # Strong name match still required unless project IDs already matched.
    if name_score < 88 and "project_id" not in reasons:
        return min(score, 80.0), "weak_name"
    return score, "+".join(reasons)


def merge_projects_deterministic(
    projects: list[ProjectRecord],
    *,
    document_hash: str,
) -> ProjectRecord:
    if not projects:
        raise ValueError("cannot merge empty project list")
    if len(projects) == 1:
        return projects[0]

    primary = max(
        projects,
        key=lambda p: (
            0 if p.incomplete_at_chunk_boundary else 1,
            len(p.evidence),
            len(p.project_description or ""),
            p.confidence_score,
        ),
    )
    merged = primary.model_copy(deep=True)

    all_names = []
    for project in projects:
        all_names.append(project.project_name)
        all_names.extend(project.alternative_project_names)
    merged.alternative_project_names = _unique_preserve(
        [name for name in all_names if name and name != merged.project_name]
    )

    for field_name in (
        "project_id",
        "owning_organization",
        "department_or_agency",
        "project_location",
        "address_or_site",
        "city",
        "county",
        "state",
        "project_category",
        "project_subcategory",
        "project_description",
        "problem_or_need",
        "proposed_scope",
        "phase_evidence",
        "procurement_status",
        "design_status",
        "construction_status",
        "approval_status",
        "funding_status",
        "priority_level",
        "total_project_budget_raw",
        "current_year_budget_raw",
        "fund_or_account",
        "timeline_notes",
        "approval_body",
        "approval_date",
        "extraction_notes",
    ):
        if not getattr(merged, field_name):
            for project in projects:
                value = getattr(project, field_name)
                if value:
                    setattr(merged, field_name, value)
                    break

    for amount_field in (
        "total_project_budget",
        "current_year_budget",
        "prior_year_spending",
        "future_year_funding",
        "remaining_budget",
        "requested_funding",
        "approved_funding",
        "unfunded_amount",
        "bond_funding",
        "grant_funding",
        "local_funding",
        "state_funding",
        "federal_funding",
        "other_funding",
    ):
        if getattr(merged, amount_field) is None:
            for project in projects:
                value = getattr(project, amount_field)
                if value is not None:
                    setattr(merged, amount_field, value)
                    break

    merged.infrastructure_domains = _unique_preserve(
        [item for p in projects for item in p.infrastructure_domains]
    )
    merged.major_components = _unique_preserve(
        [item for p in projects for item in p.major_components]
    )
    merged.deliverables = _unique_preserve([item for p in projects for item in p.deliverables])
    merged.consultants_or_engineers = _unique_preserve(
        [item for p in projects for item in p.consultants_or_engineers]
    )
    merged.contractors_or_vendors = _unique_preserve(
        [item for p in projects for item in p.contractors_or_vendors]
    )
    merged.dependencies = _unique_preserve([item for p in projects for item in p.dependencies])
    merged.related_projects = _unique_preserve(
        [item for p in projects for item in p.related_projects]
    )
    merged.risks_or_constraints = _unique_preserve(
        [item for p in projects for item in p.risks_or_constraints]
    )
    merged.source_sections = _unique_preserve(
        [item for p in projects for item in p.source_sections]
    )
    merged.source_tables_or_appendices = _unique_preserve(
        [item for p in projects for item in p.source_tables_or_appendices]
    )
    merged.source_pages = sorted({page for p in projects for page in p.source_pages})
    merged.seen_in_chunks = _unique_preserve([item for p in projects for item in p.seen_in_chunks])
    merged.evidence = _unique_evidence([item for p in projects for item in p.evidence])
    merged.annual_funding_schedule = [
        item for p in projects for item in p.annual_funding_schedule
    ]
    merged.funding_sources = [item for p in projects for item in p.funding_sources]
    merged.responsible_contacts = [item for p in projects for item in p.responsible_contacts]
    merged.budget_conflicts = [item for p in projects for item in p.budget_conflicts]
    merged.incomplete_at_chunk_boundary = all(p.incomplete_at_chunk_boundary for p in projects)
    merged.confidence_score = max(p.confidence_score for p in projects)
    merged.merged_from_record_ids = _unique_preserve(
        [p.record_id for p in projects] + [item for p in projects for item in p.merged_from_record_ids]
    )
    merged.record_id = generate_record_id(
        document_hash=document_hash,
        project_id=merged.project_id,
        project_name=merged.project_name,
        location=merged.project_location or merged.address_or_site,
    )
    merged.quality_flags = compute_quality_flags(merged)
    if "possible_duplicate" not in merged.quality_flags:
        merged.quality_flags.append("possible_duplicate")
    return merged


def consolidate_projects(
    projects: list[ProjectRecord],
    *,
    document_hash: str,
    glm_client: GlmClient | None = None,
    prompts_dir: str | None = None,
    use_llm_for_ambiguous: bool = True,
) -> tuple[list[ProjectRecord], list[DuplicateAuditEntry]]:
    if not projects:
        return [], []

    groups = find_duplicate_groups(projects)
    consumed: set[int] = set()
    final: list[ProjectRecord] = []
    audit: list[DuplicateAuditEntry] = []

    for group in groups:
        members = [projects[i] for i in group]
        scores = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                score, _ = pairwise_similarity(members[i], members[j])
                scores.append(score)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        clear_merge = avg_score >= 96 and _group_has_hard_key(members)

        if clear_merge:
            merged = merge_projects_deterministic(members, document_hash=document_hash)
            final.append(merged)
            audit.append(
                DuplicateAuditEntry(
                    decision="merge",
                    final_record_id=merged.record_id,
                    candidate_record_ids=[m.record_id for m in members],
                    candidate_names=[m.project_name for m in members],
                    similarity_scores=scores,
                    merge_reason="Deterministic merge based on strong identifiers/similarity",
                    source_pages=merged.source_pages,
                    resolution_method="deterministic",
                    resolution_confidence=min(1.0, avg_score / 100.0),
                )
            )
            consumed.update(group)
            continue

        if use_llm_for_ambiguous and glm_client and prompts_dir:
            decision = resolve_with_glm(
                members,
                glm_client=glm_client,
                prompts_dir=prompts_dir,
                document_hash=document_hash,
            )
            if decision.decision == "merge" and decision.merged_record is not None:
                merged = decision.merged_record
                # Ensure provenance preserved even if model omitted fields.
                fallback = merge_projects_deterministic(members, document_hash=document_hash)
                merged.source_pages = sorted(set(merged.source_pages) | set(fallback.source_pages))
                merged.evidence = _unique_evidence(merged.evidence + fallback.evidence)
                merged.merged_from_record_ids = _unique_preserve(
                    merged.merged_from_record_ids + [m.record_id for m in members]
                )
                merged.quality_flags = compute_quality_flags(merged)
                final.append(merged)
                audit.append(
                    DuplicateAuditEntry(
                        decision="merge",
                        final_record_id=merged.record_id,
                        candidate_record_ids=[m.record_id for m in members],
                        candidate_names=[m.project_name for m in members],
                        similarity_scores=scores,
                        merge_reason=decision.reason,
                        source_pages=merged.source_pages,
                        resolution_method="glm",
                        resolution_confidence=decision.confidence,
                    )
                )
                consumed.update(group)
                continue

            audit.append(
                DuplicateAuditEntry(
                    decision=decision.decision,
                    final_record_id=None,
                    candidate_record_ids=[m.record_id for m in members],
                    candidate_names=[m.project_name for m in members],
                    similarity_scores=scores,
                    merge_reason=decision.reason,
                    source_pages=sorted({p for m in members for p in m.source_pages}),
                    resolution_method="glm",
                    resolution_confidence=decision.confidence,
                )
            )
            # Keep separate / uncertain => retain individuals.
            continue

        audit.append(
            DuplicateAuditEntry(
                decision="uncertain",
                final_record_id=None,
                candidate_record_ids=[m.record_id for m in members],
                candidate_names=[m.project_name for m in members],
                similarity_scores=scores,
                merge_reason="Ambiguous duplicate group left unmerged pending review",
                source_pages=sorted({p for m in members for p in m.source_pages}),
                resolution_method="local",
                resolution_confidence=min(1.0, avg_score / 100.0),
            )
        )

    for idx, project in enumerate(projects):
        if idx not in consumed:
            # If project appeared in an uncertain group, flag it.
            if any(idx in group for group in groups):
                if "possible_duplicate" not in project.quality_flags:
                    project.quality_flags.append("possible_duplicate")
            final.append(project)

    return final, audit


def resolve_with_glm(
    members: list[ProjectRecord],
    *,
    glm_client: GlmClient,
    prompts_dir: str,
    document_hash: str,
) -> DuplicateDecision:
    payload = [m.model_dump(mode="json") for m in members]
    messages = build_duplicate_resolution_messages(
        prompts_dir=prompts_dir,
        candidates_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        result = glm_client.complete_json(messages)
        data = parse_json_text(result.content)
        decision = DuplicateDecision.model_validate(data)
        if decision.decision == "merge" and decision.merged_record is not None:
            if not decision.merged_record.record_id:
                decision.merged_record.record_id = generate_record_id(
                    document_hash=document_hash,
                    project_id=decision.merged_record.project_id,
                    project_name=decision.merged_record.project_name,
                    location=decision.merged_record.project_location,
                )
        return decision
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("GLM duplicate resolution failed: %s", exc)
        return DuplicateDecision(
            decision="uncertain",
            reason=f"GLM duplicate resolution failed: {exc}",
            confidence=0.0,
            merged_record=None,
        )


def _norm_id(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _same_text(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return normalize_project_name(a) == normalize_project_name(b)


def _budgets_similar(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    if a == 0 and b == 0:
        return True
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom <= 0.05


def _is_generic_name(normalized_name: str) -> bool:
    if normalized_name in GENERIC_NAME_FRAGMENTS:
        return True
    tokens = set(normalized_name.split())
    generic_tokens = {
        "water",
        "street",
        "facility",
        "equipment",
        "improvements",
        "upgrade",
        "upgrades",
        "replacement",
        "project",
        "capital",
    }
    return tokens.issubset(generic_tokens) or normalized_name in GENERIC_NAME_FRAGMENTS


def _supporting_signals(a: ProjectRecord, b: ProjectRecord) -> bool:
    return any(
        [
            a.project_id and b.project_id and _norm_id(a.project_id) == _norm_id(b.project_id),
            _same_text(a.project_location, b.project_location),
            _budgets_similar(a.total_project_budget, b.total_project_budget),
            bool(set(a.source_pages) & set(b.source_pages)),
        ]
    )


def _group_has_hard_key(members: list[ProjectRecord]) -> bool:
    ids = [_norm_id(m.project_id) for m in members if m.project_id]
    if ids and len(set(ids)) == 1:
        return True
    names = [normalize_project_name(m.project_name) for m in members]
    return len(set(names)) == 1 and not _is_generic_name(names[0])


def _unique_preserve(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = str(value).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _unique_evidence(items: list[Any]) -> list[Any]:
    seen: set[tuple[int, str]] = set()
    result = []
    for item in items:
        key = (int(item.page), item.quote.strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
