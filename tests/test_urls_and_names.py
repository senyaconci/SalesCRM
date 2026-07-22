from org_intel.utils.names import (
    company_similarity,
    is_generic_project_name,
    normalize_company_name,
    normalize_project_name,
)
from org_intel.utils.urls import domain_of, is_same_registrable_domain, normalize_url, registrable_domain


def test_canonical_domain_detection():
    assert domain_of("https://www.Como.gov/Budget/") == "como.gov"
    assert registrable_domain("https://finance.como.gov/path") == "como.gov"
    assert is_same_registrable_domain("https://www.como.gov", "https://cip.como.gov")


def test_normalize_url_strips_tracking():
    url = normalize_url("https://www.Example.com/a/?utm_source=x&id=1")
    assert "utm_source" not in url
    assert url.endswith("id=1") or "id=1" in url


def test_vendor_normalization():
    a = normalize_company_name("Burns & McDonnell")
    b = normalize_company_name("Burns and McDonnell Engineering Co., Inc.")
    assert a == b or company_similarity("Burns & McDonnell", "Burns and McDonnell Engineering Co., Inc.") >= 92


def test_generic_name_false_duplicate_prevention():
    assert is_generic_project_name("Water Improvements")
    assert is_generic_project_name("Street Improvements")
    assert not is_generic_project_name("Westside Water Main Replacement")
    assert normalize_project_name("Westside Water Main Replacement")
