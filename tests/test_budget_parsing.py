from __future__ import annotations

from budget_extractor.utils import normalize_budget_string, parse_currency
from budget_extractor.validation import conservative_json_cleanup, parse_json_text


def test_parse_currency_basic():
    assert parse_currency("$1,234,567") == 1234567.0
    assert parse_currency("($500)") == -500.0
    assert parse_currency("2.5M") == 2_500_000.0
    assert parse_currency("750k") == 750_000.0
    assert parse_currency("n/a") is None
    assert parse_currency(None) is None


def test_normalize_budget_string():
    assert normalize_budget_string("  $1,000 \n") == "$1,000"
    assert normalize_budget_string(None) == ""


def test_json_repair_cleanup_and_parse():
    messy = """
    ```json
    {
      "projects": [
        {"project_name": "A",}
      ],
      "chunk_validation_issues": [],
    }
    ```
    trailing junk
    """
    cleaned = conservative_json_cleanup(messy)
    parsed = parse_json_text(cleaned)
    assert isinstance(parsed, dict)
    assert parsed["projects"][0]["project_name"] == "A"
