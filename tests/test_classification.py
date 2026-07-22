from org_intel.discovery.source_classifier import classify_source
from org_intel.documents.document_classifier import classify_document_heuristic
from org_intel.projects.phase import normalize_phase
from org_intel.projects.record_type_classifier import classify_record_type
from org_intel.schemas.enums import DocumentType, ProjectPhase, RecordType, SourceRole


def test_source_role_classification():
    result = classify_source("Capital Improvement Plan", "https://city.gov/cip")
    assert result["source_role"] == SourceRole.CIP_PORTAL
    result = classify_source("PlanetBids Portal", "https://city.planetbids.com")
    assert result["source_role"] == SourceRole.PLANETBIDS
    result = classify_source("Legistar Meetings", "https://city.legistar.com")
    assert result["source_role"] == SourceRole.LEGISTAR


def test_document_classification():
    result = classify_document_heuristic("Adopted Budget FY2026", "https://city.gov/budget.pdf")
    assert result["document_type"] == DocumentType.ADOPTED_BUDGET
    result = classify_document_heuristic("Capital Improvement Plan", "https://city.gov/cip.pdf")
    assert result["document_type"] == DocumentType.CAPITAL_IMPROVEMENT_PLAN
    result = classify_document_heuristic("RFQ for Design Services", "https://city.gov/rfq.pdf")
    assert result["document_type"] == DocumentType.BID_SOLICITATION


def test_record_type_classification():
    rtype, eligible, _ = classify_record_type("Westside Water Main Replacement", "Water", "Funding Approved")
    assert rtype == RecordType.SPECIFIC_CAPITAL_PROJECT
    assert eligible
    rtype, eligible, reason = classify_record_type("Annual Capital Maintenance", "Maintenance", "Active")
    assert rtype == RecordType.MAINTENANCE_PROGRAM
    assert not eligible
    rtype, eligible, _ = classify_record_type("Bond Refunding Series 2024")
    assert rtype == RecordType.DEBT_FINANCING_RECORD


def test_phase_classification():
    phase, inferred, _ = normalize_phase("Preliminary Design")
    assert phase == ProjectPhase.PRELIMINARY_DESIGN
    assert inferred is False
    phase, inferred, _ = normalize_phase("Funding Approved")
    assert phase == ProjectPhase.FUNDING_APPROVED
    # funded does not imply design started — classification stays funding_approved
    assert phase != ProjectPhase.PRELIMINARY_DESIGN
