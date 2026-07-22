from org_intel.contacts.contact_validator import strip_manufactured_emails
from org_intel.procurement.incumbent_analysis import build_incumbent_analysis
from org_intel.projects.opportunity_classifier import classify_opportunity
from org_intel.schemas.contact import ContactRecord
from org_intel.schemas.enums import (
    EmailStatus,
    PreRfqClassification,
    ProcurementStatus,
    ProjectPhase,
    RecordType,
)
from org_intel.schemas.project import CompanyRelationship, ProjectRecord
from org_intel.utils.money import parse_money


def test_budget_hierarchy_not_conflated():
    assert parse_money("$4,500,000") == 4500000
    assert parse_money("1.2M") == 1_200_000


def test_procurement_blocks_strong_pre_rfq():
    project = ProjectRecord(
        organization_id="ORG-1",
        project_name="Westside Water Main Replacement",
        project_id="W0280",
        record_type=RecordType.SPECIFIC_CAPITAL_PROJECT,
        lead_eligible=True,
        proposed_scope="Replace 12-inch water main",
        normalized_phase=ProjectPhase.PRE_PROCUREMENT,
        procurement_status=ProcurementStatus.RFQ_RFP_ACTIVE,
        total_project_cost=4500000,
    )
    opp = classify_opportunity(project)
    assert opp.classification == PreRfqClassification.PROCUREMENT_ACTIVE


def test_consultant_selected_blocks_strong_pre_rfq():
    project = ProjectRecord(
        organization_id="ORG-1",
        project_name="Broadway Street Reconstruction",
        project_id="S0142",
        record_type=RecordType.SPECIFIC_CAPITAL_PROJECT,
        lead_eligible=True,
        proposed_scope="Reconstruct Broadway",
        normalized_phase=ProjectPhase.PRELIMINARY_DESIGN,
        consultants=[CompanyRelationship(company_name="Burns & McDonnell")],
        total_project_cost=8200000,
    )
    opp = classify_opportunity(project)
    assert opp.classification == PreRfqClassification.CONSULTANT_SELECTED


def test_strong_pre_rfq_possible():
    project = ProjectRecord(
        organization_id="ORG-1",
        project_name="Westside Water Main Replacement",
        project_id="W0280",
        record_type=RecordType.SPECIFIC_CAPITAL_PROJECT,
        lead_eligible=True,
        proposed_scope="Replace aging water main on Westside",
        normalized_phase=ProjectPhase.PRE_PROCUREMENT,
        procurement_status=ProcurementStatus.NO_PROCUREMENT_EVIDENCE,
        total_project_cost=4500000,
        approved_funding=4500000,
        category="Water",
    )
    opp = classify_opportunity(project)
    assert opp.classification in {
        PreRfqClassification.STRONG_PRE_RFQ,
        PreRfqClassification.POSSIBLE_PRE_RFQ,
    }


def test_incumbent_language_and_vendor_normalization():
    projects = [
        ProjectRecord(
            organization_id="ORG-1",
            project_name="A",
            consultants=[
                CompanyRelationship(company_name="Burns & McDonnell", discipline="civil", contract_amount=100),
                CompanyRelationship(
                    company_name="Burns and McDonnell Engineering Co., Inc.",
                    discipline="civil",
                    contract_amount=200,
                ),
            ],
        )
    ]
    analysis = build_incumbent_analysis("ORG-1", projects, [])
    assert len(analysis.vendors) == 1
    assert any(
        d.status == "no_incumbent_identified_in_researched_sources"
        for d in analysis.discipline_coverage
    )


def test_contact_email_status_not_manufactured():
    contacts = [
        ContactRecord(
            name="Pat Lee",
            email="pat.lee@examplecity.gov",
            email_status=EmailStatus.PATTERN_INFERRED,
        ),
        ContactRecord(
            name="Jane Smith",
            email="jane.smith@examplecity.gov",
            email_status=EmailStatus.CONFIRMED,
        ),
    ]
    cleaned = strip_manufactured_emails(contacts)
    assert cleaned[0].email is None
    assert cleaned[0].email_status == EmailStatus.NONE
    assert cleaned[1].email_status == EmailStatus.CONFIRMED
