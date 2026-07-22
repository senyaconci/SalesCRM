"""Search procurement-related documents for solicitations."""

from __future__ import annotations

import re

from org_intel.documents.page_index import PageIndex
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.enums import DocumentType
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.procurement import SolicitationRecord
from org_intel.schemas.project import ProjectRecord

_SOLICIT_RE = re.compile(
    r"\b(RFQ|RFP|IFB|RFI)[- ]?#?\s*([A-Z0-9-]{2,})?\b.*",
    re.I,
)


def search_solicitations(
    organization_id: str,
    inventory: DocumentInventory,
    indexes: dict[str, PageIndex],
    projects: list[ProjectRecord],
) -> list[SolicitationRecord]:
    out: list[SolicitationRecord] = []
    project_names = {p.project_name.lower(): p for p in projects if p.project_name}
    project_ids = { (p.project_id or "").upper(): p for p in projects if p.project_id}

    for doc in inventory.documents:
        if doc.document_type not in {
            DocumentType.BID_SOLICITATION,
            DocumentType.COUNCIL_PACKET,
            DocumentType.AWARD_NOTICE,
            DocumentType.PROFESSIONAL_SERVICES_AGREEMENT,
        } and doc.likely_procurement_relevance < 0.5:
            continue
        index = indexes.get(doc.document_id)
        text_pages = index.pages if index else []
        if not text_pages:
            continue
        for page in text_pages:
            for match in _SOLICIT_RE.finditer(page.text):
                title_line = match.group(0)[:240]
                related = []
                for pid, proj in project_ids.items():
                    if pid and pid in page.text.upper():
                        related.append(pid)
                for name, proj in project_names.items():
                    if name and name in page.text.lower():
                        if proj.project_id:
                            related.append(proj.project_id)
                out.append(
                    SolicitationRecord(
                        organization_id=organization_id,
                        solicitation_number=match.group(2),
                        title=title_line,
                        solicitation_type=(match.group(1) or "").upper(),
                        related_project_ids=list(dict.fromkeys(related)),
                        url=doc.url,
                        confidence=0.55,
                        evidence=[
                            Evidence(
                                document_id=doc.document_id,
                                url=doc.url,
                                page=page.page_number,
                                quote=title_line,
                                supports_fields=["title", "solicitation_type"],
                                confidence=0.55,
                            )
                        ],
                    )
                )
    return out
