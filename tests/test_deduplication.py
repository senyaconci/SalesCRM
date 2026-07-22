from __future__ import annotations

from budget_extractor.deduplication import (
    consolidate_projects,
    find_duplicate_groups,
    merge_projects_deterministic,
    pairwise_similarity,
)
from budget_extractor.schemas import ProjectRecord


def _project(**overrides) -> ProjectRecord:
    data = {
        "record_id": overrides.pop("record_id", "proj_a"),
        "project_name": "North Pump Station Rehabilitation",
        "project_id": "CIP-100",
        "department_or_agency": "Utilities",
        "project_location": "North Plant",
        "current_phase": "construction",
        "pre_rfp_status": "construction_underway",
        "source_pages": [20, 21],
        "evidence": [{"page": 20, "quote": "North Pump Station Rehabilitation underway"}],
        "confidence_score": 0.88,
        "first_seen_chunk": "chunk_0001",
        "total_project_budget": 4_500_000,
    }
    data.update(overrides)
    return ProjectRecord.model_validate(data)


def test_exact_project_id_is_duplicate_candidate():
    a = _project(record_id="r1")
    b = _project(
        record_id="r2",
        project_name="North Pump Station Rehab",
        source_pages=[21, 22],
        first_seen_chunk="chunk_0002",
        evidence=[{"page": 22, "quote": "CIP-100 North Pump Station Rehab"}],
    )
    score, reason = pairwise_similarity(a, b)
    assert score >= 92
    assert "project_id" in reason
    groups = find_duplicate_groups([a, b])
    assert groups == [[0, 1]]


def test_generic_names_not_merged():
    a = _project(
        record_id="g1",
        project_id=None,
        project_name="Water Improvements",
        project_location="Zone A",
        total_project_budget=100000,
        source_pages=[1],
        evidence=[{"page": 1, "quote": "Water Improvements Zone A"}],
    )
    b = _project(
        record_id="g2",
        project_id=None,
        project_name="Water Improvements",
        project_location="Zone B",
        total_project_budget=900000,
        source_pages=[8],
        evidence=[{"page": 8, "quote": "Water Improvements Zone B"}],
        first_seen_chunk="chunk_0003",
    )
    score, reason = pairwise_similarity(a, b)
    assert reason in {"generic_only", "weak_name"} or score < 92
    groups = find_duplicate_groups([a, b])
    assert groups == []


def test_merge_preserves_provenance():
    a = _project(record_id="m1", source_pages=[10], alternative_project_names=["NPS Rehab"])
    b = _project(
        record_id="m2",
        source_pages=[11, 12],
        evidence=[{"page": 12, "quote": "Additional schedule detail"}],
        first_seen_chunk="chunk_0002",
        seen_in_chunks=["chunk_0002"],
    )
    merged = merge_projects_deterministic([a, b], document_hash="doc123")
    assert set(merged.source_pages) == {10, 11, 12}
    assert len(merged.evidence) >= 2
    assert "NPS Rehab" in merged.alternative_project_names
    assert set(merged.merged_from_record_ids) >= {"m1", "m2"}


def test_consolidate_merges_clear_duplicates_without_llm():
    a = _project(record_id="c1")
    b = _project(
        record_id="c2",
        project_name="North Pump Station Rehabilitation",
        source_pages=[21],
        first_seen_chunk="chunk_0002",
        evidence=[{"page": 21, "quote": "Same project continued"}],
    )
    final, audit = consolidate_projects(
        [a, b],
        document_hash="doc",
        glm_client=None,
        use_llm_for_ambiguous=False,
    )
    assert len(final) == 1
    assert audit[0].decision == "merge"
    assert audit[0].resolution_method == "deterministic"
