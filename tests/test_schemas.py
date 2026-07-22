from __future__ import annotations

import pytest
from pydantic import ValidationError

from budget_extractor.schemas import (
    Evidence,
    ProjectPhase,
    ProjectRecord,
    PreRfpStatus,
    generate_record_id,
)
from budget_extractor.validation import coerce_and_validate_project


def _valid_project_dict(**overrides):
    data = {
        "project_name": "Water Treatment Plant Filter Replacement",
        "current_phase": "preliminary_design",
        "pre_rfp_status": "strong_pre_rfp",
        "source_pages": [12, 13],
        "evidence": [{"page": 12, "quote": "Filter replacement funded at $2.1M"}],
        "confidence_score": 0.9,
        "first_seen_chunk": "chunk_0001",
        "total_project_budget": 2100000,
    }
    data.update(overrides)
    return data


def test_schema_accepts_valid_project():
    project = ProjectRecord.model_validate(_valid_project_dict())
    assert project.current_phase == ProjectPhase.PRELIMINARY_DESIGN
    assert project.pre_rfp_status == PreRfpStatus.STRONG_PRE_RFP


def test_invalid_phase_rejected():
    with pytest.raises(ValidationError):
        ProjectRecord.model_validate(_valid_project_dict(current_phase="not_a_phase"))


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        ProjectRecord.model_validate(_valid_project_dict(confidence_score=1.5))


def test_requires_evidence_and_pages():
    with pytest.raises(ValidationError):
        ProjectRecord.model_validate(_valid_project_dict(evidence=[]))
    with pytest.raises(ValidationError):
        ProjectRecord.model_validate(_valid_project_dict(source_pages=[]))


def test_record_id_stable():
    a = generate_record_id(
        document_hash="abc",
        project_id="CIP-1",
        project_name="Main Street Bridge",
        location="Columbia",
    )
    b = generate_record_id(
        document_hash="abc",
        project_id="CIP-1",
        project_name="Main Street Bridge",
        location="Columbia",
    )
    assert a == b
    assert a.startswith("proj_")


def test_coerce_infers_missing_source_pages_from_evidence():
    project = coerce_and_validate_project(
        {
            "project_name": "Fleet Replacement",
            "current_phase": "funding_approved",
            "pre_rfp_status": "possible_pre_rfp",
            "evidence": [{"page": 4, "quote": "Fleet replacement program"}],
            "confidence_score": 0.7,
            "first_seen_chunk": "chunk_0002",
        },
        chunk_id="chunk_0002",
        document_hash="doc",
        total_pages=10,
        chunk_start=3,
        chunk_end=5,
    )
    assert project.source_pages == [4]
    assert isinstance(project.evidence[0], Evidence)


def test_coerce_handles_loose_model_shapes():
    project = coerce_and_validate_project(
        {
            "project_name": "LOW Clubhouse Roof Replacement - 00948",
            "project_number": "00948",
            "department": "Parks & Recreation",
            "location": "6700 E St Charles Rd",
            "current_phase": "funding_requested",
            "pre_rfp_status": "strong_pre_rfp",
            "source_pages": [325],
            "evidence": [
                "Project Description: Replacing the 25+ year old roof",
                "Needs Appropriated: $40,000",
            ],
            "funding_sources": ["Parks Sales Tax"],
            "actual_budget": 40000,
            "needs_appropriated": 40000,
            "confidence_score": 0.95,
            "first_seen_chunk": "chunk_0003",
        },
        chunk_id="chunk_0003",
        document_hash="doc",
        total_pages=462,
        chunk_start=325,
        chunk_end=326,
    )
    assert project.project_id == "00948"
    assert project.department_or_agency == "Parks & Recreation"
    assert project.project_location == "6700 E St Charles Rd"
    assert project.total_project_budget == 40000
    assert project.unfunded_amount == 40000
    assert len(project.evidence) == 2
    assert project.funding_sources[0].source_name == "Parks Sales Tax"
