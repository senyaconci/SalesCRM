"""Phase 6 — select the cheapest/most comprehensive anchor project source."""

from __future__ import annotations

from dataclasses import dataclass

from org_intel.schemas.document import DocumentInventory, DocumentRecord
from org_intel.schemas.enums import DocumentType, SourcePriority, SourceRole
from org_intel.schemas.source import SourceRecord, SourceRegistry


@dataclass
class AnchorSelection:
    document: DocumentRecord | None
    source: SourceRecord | None
    score: float
    reason: str
    candidates: list[dict]


_TYPE_BASE = {
    DocumentType.LIVE_REGISTRY: 100,
    DocumentType.CIP_SPREADSHEET: 95,
    DocumentType.CAPITAL_IMPROVEMENT_PLAN: 85,
    DocumentType.CAPITAL_BUDGET: 75,
    DocumentType.ADOPTED_BUDGET: 55,
    DocumentType.CAPITAL_FACILITIES_PLAN: 70,
    DocumentType.PROJECT_PAGE: 50,
    DocumentType.OTHER: 20,
}


def select_anchor(
    inventory: DocumentInventory,
    registry: SourceRegistry,
) -> AnchorSelection:
    sources_by_id = {s.source_id: s for s in registry.sources}
    candidates: list[tuple[float, DocumentRecord, str]] = []

    for doc in inventory.documents:
        score = float(_TYPE_BASE.get(doc.document_type, 20))
        score += doc.likely_project_relevance * 20
        score += doc.confidence * 10
        if doc.file_type in {"csv", "xlsx", "xls"}:
            score += 25  # structured / cheap
        elif doc.file_type == "html":
            score += 15
        elif doc.file_type == "pdf":
            # Prefer smaller / dedicated CIP over giant budget PDFs
            if doc.document_type == DocumentType.ADOPTED_BUDGET:
                score -= 20
            if doc.page_count and doc.page_count > 400:
                score -= 15
        if doc.fiscal_year:
            score += 5
        if doc.status and doc.status.value in {"adopted", "approved", "active"}:
            score += 8

        source = sources_by_id.get(doc.source_id or "")
        if source:
            if source.priority == SourcePriority.ANCHOR:
                score += 12
            if source.source_role in {
                SourceRole.LIVE_PROJECT_REGISTRY,
                SourceRole.CIP_PORTAL,
                SourceRole.OPENGOV,
            }:
                score += 18

        reason_parts = [
            f"type={doc.document_type.value}",
            f"file={doc.file_type or 'unknown'}",
            f"project_relevance={doc.likely_project_relevance:.2f}",
        ]
        candidates.append((score, doc, "; ".join(reason_parts)))

    # Also consider sources without explicit docs
    for source in registry.sources:
        if source.source_role in {
            SourceRole.LIVE_PROJECT_REGISTRY,
            SourceRole.CIP_PORTAL,
            SourceRole.OPENGOV,
        }:
            # synthetic if no matching doc
            if not any(d.url.rstrip("/") == source.url.rstrip("/") for d in inventory.documents):
                synthetic = DocumentRecord(
                    title=source.source_name,
                    document_type=DocumentType.LIVE_REGISTRY,
                    url=source.url,
                    source_id=source.source_id,
                    file_type="html",
                    likely_project_relevance=0.95,
                    confidence=source.confidence,
                )
                candidates.append(
                    (
                        110 + source.confidence * 10,
                        synthetic,
                        f"source_role={source.source_role.value}; structured_portal_preference",
                    )
                )

    if not candidates:
        return AnchorSelection(
            document=None,
            source=None,
            score=0.0,
            reason="No candidate project inventory sources found.",
            candidates=[],
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_doc, best_reason = candidates[0]
    source = sources_by_id.get(best_doc.source_id or "")
    return AnchorSelection(
        document=best_doc,
        source=source,
        score=best_score,
        reason=f"Selected for score={best_score:.1f}: {best_reason}. "
        "Preference order favors live registries and structured CIP data over large budget PDFs.",
        candidates=[
            {
                "document_id": d.document_id,
                "title": d.title,
                "url": d.url,
                "score": s,
                "reason": r,
            }
            for s, d, r in candidates[:15]
        ],
    )
