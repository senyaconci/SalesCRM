"""Phase 8 — map projects to supporting documents via local indexes."""

from __future__ import annotations

from pathlib import Path

from org_intel.documents.page_index import PageIndex
from org_intel.documents.pdf_processor import process_pdf
from org_intel.retrieval.http_client import HttpClient
from org_intel.schemas.document import DocumentInventory, DocumentRecord
from org_intel.schemas.enums import MatchMethod
from org_intel.schemas.project import ProjectSourceLink, ShallowProjectIndexRecord
from org_intel.utils.names import normalize_project_name, project_name_similarity
from org_intel.utils.text import clean_whitespace


def map_projects_to_sources(
    projects: list[ShallowProjectIndexRecord],
    inventory: DocumentInventory,
    http: HttpClient,
    *,
    max_documents: int = 40,
    max_pages: int = 5000,
) -> tuple[list[ProjectSourceLink], dict[str, PageIndex]]:
    """Search locally indexed documents before any external web search."""
    indexes: dict[str, PageIndex] = {}
    links: list[ProjectSourceLink] = []
    pages_used = 0

    # Prefer high-relevance docs excluding pure anchor duplicates optionally
    docs = sorted(
        inventory.documents,
        key=lambda d: -(d.likely_project_relevance + d.likely_procurement_relevance * 0.5),
    )[:max_documents]

    for doc in docs:
        if pages_used >= max_pages:
            break
        index = _ensure_index(doc, http, indexes)
        if index is None:
            continue
        pages_used += len(index.pages)

        for project in projects:
            project_key = project.project_id or project.record_id
            hits = []
            if project.project_id:
                hits.extend(index.search_project_id(project.project_id))
            hits.extend(index.search_name(project.project_name, threshold=88.0))
            for alt in project.alternative_names:
                hits.extend(index.search_name(alt, threshold=90.0))
            if project.location:
                # location-only matches are weaker
                loc_hits = index.search_name(project.location, threshold=92.0)
                for h in loc_hits:
                    h.match_method = "location"
                    h.score *= 0.85
                hits.extend(loc_hits)

            if not hits:
                continue
            # collapse by page
            best_by_page = {}
            for h in hits:
                prev = best_by_page.get(h.page_number)
                if not prev or h.score > prev.score:
                    best_by_page[h.page_number] = h
            ordered = sorted(best_by_page.values(), key=lambda h: -h.score)
            method = MatchMethod(ordered[0].match_method) if ordered[0].match_method in MatchMethod._value2member_map_ else MatchMethod.FUZZY_NAME
            links.append(
                ProjectSourceLink(
                    project_id=project_key,
                    document_id=doc.document_id,
                    match_method=method,
                    match_score=float(ordered[0].score),
                    matching_pages=[h.page_number for h in ordered[:12]],
                    matched_terms=list({t for h in ordered for t in h.matched_terms}),
                    likely_fields=_likely_fields(doc),
                    requires_llm_review=ordered[0].score < 92 or method == MatchMethod.LOCATION,
                )
            )

    # Also link by exact detail URL / same source URL
    for project in projects:
        for doc in inventory.documents:
            if project.project_detail_url and normalize_url_simple(project.project_detail_url) == normalize_url_simple(doc.url):
                links.append(
                    ProjectSourceLink(
                        project_id=project.project_id or project.record_id,
                        document_id=doc.document_id,
                        match_method=MatchMethod.URL,
                        match_score=100.0,
                        likely_fields=["project_description", "published_status"],
                    )
                )
    return links, indexes


def _ensure_index(
    doc: DocumentRecord,
    http: HttpClient,
    indexes: dict[str, PageIndex],
) -> PageIndex | None:
    if doc.document_id in indexes:
        return indexes[doc.document_id]
    try:
        result = http.fetch(doc.url, as_binary=True)
        path = Path(result.local_path or "")
        if not path.exists():
            return None
        if path.suffix.lower() == ".pdf" or (doc.file_type or "").lower() == "pdf":
            pdf = process_pdf(path)
            doc.page_count = pdf.page_count
            doc.sha256 = pdf.sha256
            doc.indexed = True
            index = PageIndex.from_pdf(doc.document_id, pdf)
            indexes[doc.document_id] = index
            return index
        # HTML as single "page"
        text = path.read_text(encoding="utf-8", errors="replace")
        from org_intel.documents.pdf_processor import PdfPage

        page = PdfPage(
            page_number=1,
            text=BeautifulSoup_text(text),
            char_count=0,
            is_low_text=False,
            needs_ocr=False,
            sha256=result.sha256 or "",
        )
        page.char_count = len(page.text)
        index = PageIndex(document_id=doc.document_id, pages=[page])
        doc.indexed = True
        indexes[doc.document_id] = index
        return index
    except Exception:
        return None


def BeautifulSoup_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return clean_whitespace(soup.get_text(" ", strip=True))


def normalize_url_simple(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def _likely_fields(doc: DocumentRecord) -> list[str]:
    fields: list[str] = []
    roles = {r.value for r in doc.content_roles}
    if "project_inventory" in roles or doc.likely_project_relevance >= 0.6:
        fields.extend(["published_status", "total_project_cost", "department"])
    if "financial" in roles:
        fields.extend(["current_year_appropriation", "funding_sources"])
    if "technical_planning" in roles:
        fields.extend(["proposed_scope", "problem_or_need"])
    if "procurement" in roles or "award" in roles:
        fields.extend(["procurement_status", "consultants", "contractors"])
    if "approval" in roles:
        fields.extend(["approval_status", "consultants"])
    return list(dict.fromkeys(fields))


def names_conflict_generic(a: str, b: str) -> bool:
    """True if names are similar but too generic to merge alone."""
    from org_intel.utils.names import is_generic_project_name

    if is_generic_project_name(a) or is_generic_project_name(b):
        return project_name_similarity(a, b) >= 90
    return False
