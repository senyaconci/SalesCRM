from org_intel.discovery.canonical_identity import build_canonical_identity
from org_intel.discovery.organization_type import detect_organization_type
from org_intel.retrieval.html_fetcher import HtmlFetcher
from org_intel.schemas.enums import OrganizationType
from org_intel.strategies.base import get_strategy


def test_organization_type_strategy_selection():
    city = get_strategy(OrganizationType.CITY)
    water = get_strategy(OrganizationType.WATER_DISTRICT)
    uni = get_strategy(OrganizationType.UNIVERSITY)
    airport = get_strategy(OrganizationType.AIRPORT)
    assert "Public Works" in city.department_terms
    assert "Treatment" in water.department_terms
    assert "Campus Planning" in uni.department_terms
    assert "Airport Master Plan" in airport.master_plan_terms or "Airport Master Plan" in airport.capital_source_terms


def test_similar_name_disambiguation_notes(municipality_http):
    html = HtmlFetcher(municipality_http)
    identity = build_canonical_identity("https://www.examplecity.gov", html)
    assert "Exampleville" in identity.canonical_name
    assert identity.organization_type == OrganizationType.CITY
    assert identity.official_domain == "examplecity.gov"
    assert identity.state == "Missouri"
    assert identity.field_evidence
    # evidence required for canonical name
    assert any(fe.field == "canonical_name" for fe in identity.field_evidence)


def test_detect_types_from_text():
    ot, conf, _ = detect_organization_type(
        "Welcome to Example Water District wastewater utility",
        title="Example Water District",
    )
    assert ot == OrganizationType.WATER_DISTRICT
    assert conf >= 0.8

    ot, _, _ = detect_organization_type(
        "Example State University Board of Trustees",
        title="Example State University",
    )
    assert ot == OrganizationType.UNIVERSITY

    ot, _, _ = detect_organization_type(
        "Example Airport Authority international airport",
        title="Example Airport Authority",
    )
    assert ot == OrganizationType.AIRPORT
