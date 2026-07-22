"""Detect consultants mentioned near project evidence."""

from __future__ import annotations

import re

from org_intel.schemas.evidence import Evidence
from org_intel.schemas.project import CompanyRelationship, ProjectRecord

_FIRM_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'\-]+(?:\s+[A-Z][A-Za-z0-9&.'\-]+){0,4})\s+"
    r"(?:Engineering|Architects|Consultants|Associates|Inc\.?|LLC|Group)\b"
)


def detect_consultants_in_text(project: ProjectRecord, text: str, url: str | None = None) -> ProjectRecord:
    for match in _FIRM_RE.finditer(text or ""):
        firm = match.group(0).strip()
        if any(c.company_name.lower() == firm.lower() for c in project.consultants):
            continue
        project.consultants.append(
            CompanyRelationship(
                company_name=firm,
                role="consultant",
                evidence=[
                    Evidence(
                        url=url,
                        quote=text[max(0, match.start() - 60) : match.end() + 60],
                        supports_fields=["consultants"],
                        confidence=0.55,
                    )
                ],
            )
        )
        if project.consultant_status == "unknown":
            project.consultant_status = "mentioned"
    return project
