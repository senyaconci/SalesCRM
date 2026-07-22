"""Search for award notices and professional services agreements."""

from __future__ import annotations

import re

from org_intel.documents.page_index import PageIndex
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.enums import DocumentType, ProcurementStatus
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.procurement import ProcurementEvent
from org_intel.schemas.project import CompanyRelationship, ProjectRecord
from org_intel.utils.money import parse_money

_AWARD_RE = re.compile(
    r"(?:award(?:ed)?|selected|agreement)\s+(?:to|with)?\s*([A-Z][A-Za-z0-9&.,' \-]{2,60})",
    re.I,
)
_FIRM_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'\-]+(?:\s+[A-Z][A-Za-z0-9&.'\-]+){0,5})\s+"
    r"(?:Engineering|Architects|Consultants|Associates|Inc\.?|LLC)\b"
)


def search_awards(
    organization_id: str,
    inventory: DocumentInventory,
    indexes: dict[str, PageIndex],
    projects: list[ProjectRecord],
) -> list[ProcurementEvent]:
    events: list[ProcurementEvent] = []
    for doc in inventory.documents:
        if doc.document_type not in {
            DocumentType.AWARD_NOTICE,
            DocumentType.PROFESSIONAL_SERVICES_AGREEMENT,
            DocumentType.CONSULTANT_AMENDMENT,
            DocumentType.COUNCIL_PACKET,
            DocumentType.RESOLUTION,
        } and doc.likely_procurement_relevance < 0.6:
            continue
        index = indexes.get(doc.document_id)
        if not index:
            continue
        for page in index.pages:
            for firm_match in _FIRM_RE.finditer(page.text):
                firm = firm_match.group(0).strip()
                related = _related_project(page.text, projects)
                amount = parse_money(page.text[firm_match.start() : firm_match.start() + 200])
                event = ProcurementEvent(
                    organization_id=organization_id,
                    project_record_id=related.record_id if related else None,
                    event_type="award_or_agreement",
                    status=ProcurementStatus.CONTRACT_AWARDED
                    if "award" in page.text.lower()
                    else ProcurementStatus.CONSULTANT_SELECTED,
                    firm_name=firm,
                    amount=amount,
                    document_id=doc.document_id,
                    url=doc.url,
                    evidence=[
                        Evidence(
                            document_id=doc.document_id,
                            url=doc.url,
                            page=page.page_number,
                            quote=page.text[max(0, firm_match.start() - 80) : firm_match.end() + 80],
                            supports_fields=["firm_name", "procurement_status"],
                            confidence=0.6,
                        )
                    ],
                )
                events.append(event)
                if related:
                    related.consultants.append(
                        CompanyRelationship(
                            company_name=firm,
                            role="consultant",
                            contract_amount=amount,
                            evidence=event.evidence,
                        )
                    )
                    related.consultant_status = "selected"
                    related.procurement_status = event.status
    return events


def _related_project(text: str, projects: list[ProjectRecord]) -> ProjectRecord | None:
    upper = text.upper()
    lower = text.lower()
    for p in projects:
        if p.project_id and p.project_id.upper() in upper:
            return p
    for p in projects:
        if p.project_name and p.project_name.lower() in lower:
            return p
    return None
