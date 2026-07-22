"""Name normalization for projects, vendors, and organizations."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from org_intel.utils.text import clean_whitespace

GENERIC_PROJECT_NAMES = {
    "water improvements",
    "street improvements",
    "facility upgrades",
    "annual capital maintenance",
    "equipment replacement",
    "miscellaneous improvements",
    "general capital improvements",
    "various projects",
    "contingency",
    "capital outlay",
}

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|l\.?l\.?c\.?|corp\.?|corporation|co\.?|company|"
    r"ltd\.?|limited|plc|pc|p\.c\.|llp|l\.l\.p\.|pllc|engineering|"
    r"engineers|architects|associates|group|consultants|consulting)\b",
    re.I,
)

_AND_RE = re.compile(r"\s*&\s*|\s+and\s+", re.I)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")


def normalize_project_name(name: str | None) -> str:
    text = clean_whitespace(name).lower()
    text = _NON_ALNUM.sub(" ", text)
    return clean_whitespace(text)


def is_generic_project_name(name: str | None) -> bool:
    return normalize_project_name(name) in GENERIC_PROJECT_NAMES


def normalize_company_name(name: str | None) -> str:
    text = clean_whitespace(name).lower()
    text = _AND_RE.sub(" and ", text)
    text = _COMPANY_SUFFIXES.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    return clean_whitespace(text)


def company_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize_company_name(a), normalize_company_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    return float(fuzz.token_sort_ratio(na, nb))


def project_name_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize_project_name(a), normalize_project_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    return float(fuzz.token_set_ratio(na, nb))
