"""Phase 4 — ranked document inventory (discover, do not deeply process)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from org_intel.discovery.source_discovery import harvest_document_links_from_sources
from org_intel.documents.document_classifier import classify_document
from org_intel.documents.document_linker import link_supersessions
from org_intel.llm.router import LLMRouter
from org_intel.retrieval.html_fetcher import HtmlFetcher
from org_intel.schemas.document import DocumentInventory, DocumentRecord
from org_intel.schemas.enums import ContentRole, DocumentType
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import OrganizationIdentity
from org_intel.schemas.source import SourceRegistry
from org_intel.utils.text import clean_whitespace
from org_intel.utils.urls import is_same_registrable_domain, normalize_url

_DOC_EXT = re.compile(r"\.(pdf|xlsx?|csv|docx?)(?:$|\?)", re.I)
_DOC_HINT = re.compile(
    r"budget|cip|capital|master plan|agenda|packet|acfr|bond|rfp|rfq|bid|award|"
    r"resolution|ordinance|feasibility|engineering report|official statement",
    re.I,
)


def build_document_inventory(
    identity: OrganizationIdentity,
    registry: SourceRegistry,
    html_fetcher: HtmlFetcher,
    *,
    router: LLMRouter | None = None,
    max_documents: int = 200,
) -> DocumentInventory:
    pages = harvest_document_links_from_sources(registry, html_fetcher)
    docs: list[DocumentRecord] = []
    seen: set[str] = set()

    for source, page in pages:
        for link in page.links:
            url = normalize_url(link.get("url") or "")
            title = clean_whitespace(link.get("text") or "") or url
            if not url or url in seen:
                continue
            if not (
                _DOC_EXT.search(url)
                or _DOC_HINT.search(title)
                or _DOC_HINT.search(url)
            ):
                continue
            if not is_same_registrable_domain(url, identity.official_url) and not _is_hosted_doc(url):
                continue
            seen.add(url)
            file_type = _file_type(url)
            doc = DocumentRecord(
                title=title[:500],
                url=url,
                source_id=source.source_id,
                publishing_entity=source.publishing_entity or identity.canonical_name,
                file_type=file_type,
                evidence=[
                    Evidence(
                        source_id=source.source_id,
                        url=url,
                        title=title,
                        quote=title,
                        supports_fields=["title", "url"],
                        confidence=0.7,
                    )
                ],
                discovered_at=datetime.now(timezone.utc),
            )
            docs.append(classify_document(doc, router=router))
            if len(docs) >= max_documents:
                break
        if len(docs) >= max_documents:
            break

    # Promote live registry / HTML project lists as document records
    for source in registry.sources:
        if source.source_role.value in {
            "live_project_registry",
            "capital_improvement_portal",
            "budget_portal",
        }:
            url = normalize_url(source.url)
            if url in seen:
                continue
            seen.add(url)
            doc = DocumentRecord(
                title=source.source_name or source.url,
                document_type=DocumentType.LIVE_REGISTRY
                if "registry" in source.source_role.value or "cip" in source.source_role.value
                else DocumentType.OTHER,
                url=url,
                source_id=source.source_id,
                publishing_entity=source.publishing_entity,
                file_type="html",
                likely_project_relevance=0.9,
                likely_financial_relevance=0.7,
                content_roles=list(source.content_roles)
                or [ContentRole.PROJECT_INVENTORY],
                confidence=source.confidence,
            )
            docs.append(doc)

    docs = link_supersessions(docs)
    ranked = sorted(
        docs,
        key=lambda d: (
            -(d.likely_project_relevance * 0.5
              + d.likely_financial_relevance * 0.3
              + d.likely_procurement_relevance * 0.2),
            -(d.confidence or 0),
        ),
    )
    return DocumentInventory(
        organization_id=identity.organization_id,
        documents=ranked,
        ranked_document_ids=[d.document_id for d in ranked],
    )


def _file_type(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in ("pdf", "xlsx", "xls", "csv", "docx", "doc"):
        if path.endswith("." + ext):
            return ext
    return "html"


def _is_hosted_doc(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(
        h in host
        for h in (
            "legistar",
            "boarddocs",
            "granicus",
            "opengov",
            "civicplus",
            "municode",
            "amazonaws.com",
            "cloudfront.net",
        )
    )
