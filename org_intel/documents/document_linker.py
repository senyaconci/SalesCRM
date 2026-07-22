"""Link related documents (supersedes, packets to projects, etc.)."""

from __future__ import annotations

import re

from org_intel.schemas.document import DocumentRecord
from org_intel.schemas.enums import DocumentType


def link_supersessions(documents: list[DocumentRecord]) -> list[DocumentRecord]:
    """Mark older CIP/budget docs as superseded when a newer same-type exists."""
    by_type: dict[DocumentType, list[DocumentRecord]] = {}
    for doc in documents:
        by_type.setdefault(doc.document_type, []).append(doc)

    for dtype, group in by_type.items():
        if dtype not in {
            DocumentType.CAPITAL_IMPROVEMENT_PLAN,
            DocumentType.ADOPTED_BUDGET,
            DocumentType.PROPOSED_BUDGET,
            DocumentType.CAPITAL_BUDGET,
        }:
            continue
        ranked = sorted(group, key=_recency_key, reverse=True)
        for older in ranked[1:]:
            newer = ranked[0]
            if older.document_id == newer.document_id:
                continue
            older.superseded_by_document_id = newer.document_id
            newer.supersedes_document_id = newer.supersedes_document_id or older.document_id
    return documents


def _recency_key(doc: DocumentRecord) -> tuple:
    fy = 0
    if doc.fiscal_year:
        match = re.search(r"20\d{2}", doc.fiscal_year)
        if match:
            fy = int(match.group(0))
    date = doc.publication_date or ""
    return (fy, date, doc.likely_project_relevance)
