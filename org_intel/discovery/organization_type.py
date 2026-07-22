"""Organization type detection from official page evidence."""

from __future__ import annotations

import re
from typing import Any

from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import ORG_TYPE_CLASSIFY
from org_intel.llm.router import LLMRouter
from org_intel.schemas.enums import OrganizationType

_PATTERNS: list[tuple[re.Pattern[str], OrganizationType, float]] = [
    (re.compile(r"\b(city of|municipality|town of|village of)\b", re.I), OrganizationType.CITY, 0.85),
    (re.compile(r"\bcounty (of|government|commission)\b|\bboard of (county )?commissioners\b", re.I), OrganizationType.COUNTY, 0.85),
    (re.compile(r"\b(water|wastewater|sanitary|irrigation)\s+(district|agency|authority)\b", re.I), OrganizationType.WATER_DISTRICT, 0.9),
    (re.compile(r"\b(municipal|public)\s+utility\b|\butility authority\b", re.I), OrganizationType.UTILITY_AUTHORITY, 0.8),
    (re.compile(r"\bairport (authority|commission)?\b|\binternational airport\b", re.I), OrganizationType.AIRPORT, 0.85),
    (re.compile(r"\bport (authority|of)\b", re.I), OrganizationType.PORT_AUTHORITY, 0.85),
    (re.compile(r"\b(transit|metropolitan transportation|metro)\b.*(authority|agency|district)", re.I), OrganizationType.TRANSIT_AGENCY, 0.8),
    (re.compile(r"\b(school district|independent school|unified school)\b", re.I), OrganizationType.SCHOOL_DISTRICT, 0.9),
    (re.compile(r"\b(university|college|community college)\b", re.I), OrganizationType.UNIVERSITY, 0.8),
    (re.compile(r"\b(hospital|health system|medical center)\b", re.I), OrganizationType.HOSPITAL, 0.75),
    (re.compile(r"\bhousing authority\b", re.I), OrganizationType.HOUSING_AUTHORITY, 0.9),
    (re.compile(r"\bpark(s)? (district|authority)\b", re.I), OrganizationType.PARK_DISTRICT, 0.85),
    (re.compile(r"\bjoint powers authority\b|\bjpa\b", re.I), OrganizationType.JOINT_POWERS_AUTHORITY, 0.85),
    (re.compile(r"\bdepartment of\b|\bstate of\b.*\bagency\b", re.I), OrganizationType.STATE_AGENCY, 0.55),
]


def detect_organization_type(
    text: str,
    title: str = "",
    url: str = "",
    hinted_type: str | None = None,
    router: LLMRouter | None = None,
) -> tuple[OrganizationType, float, str]:
    if hinted_type:
        try:
            return OrganizationType(hinted_type), 0.95, "cli_hint"
        except ValueError:
            pass

    blob = f"{title}\n{url}\n{text[:8000]}"
    best: tuple[OrganizationType, float, str] = (OrganizationType.UNKNOWN, 0.2, "no_match")
    for pattern, org_type, score in _PATTERNS:
        if pattern.search(blob):
            if score > best[1]:
                best = (org_type, score, f"pattern:{pattern.pattern}")

    if router is not None and best[1] < 0.7:
        try:
            data: dict[str, Any] = router.complete_json(
                ModelRole.CHEAP_CLASSIFIER,
                ORG_TYPE_CLASSIFY,
                f"Title: {title}\nURL: {url}\nText:\n{text[:5000]}",
                task_type="org_type_classify",
            )
            if data.get("organization_type"):
                try:
                    ot = OrganizationType(data["organization_type"])
                    conf = float(data.get("confidence") or 0.6)
                    if conf >= best[1]:
                        return ot, conf, "llm"
                except ValueError:
                    pass
        except Exception:
            pass
    return best
