"""Phase 3 — official source registry discovery."""

from __future__ import annotations

from datetime import datetime, timezone

from org_intel.discovery.source_classifier import (
    apply_source_classification,
    build_field_authority_map,
    classify_source,
)
from org_intel.llm.router import LLMRouter
from org_intel.retrieval.html_fetcher import HtmlFetcher, ParsedPage
from org_intel.schemas.enums import (
    OfficialStatus,
    SourceAccessMethod,
    SourcePriority,
    SourceRole,
    SourceStatus,
)
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import OrganizationIdentity
from org_intel.schemas.source import SourceRecord, SourceRegistry
from org_intel.strategies.base import get_strategy
from org_intel.utils.text import clean_whitespace
from org_intel.utils.urls import domain_of, is_same_registrable_domain, normalize_url

THIRD_PARTY_HOSTS = (
    "legistar.com",
    "boarddocs.com",
    "granicus.com",
    "opengov.com",
    "demandstar.com",
    "bonfirehub.com",
    "planetbids.com",
    "ionwave.net",
    "bidnetdirect.com",
    "municode.com",
)


def discover_sources(
    identity: OrganizationIdentity,
    html_fetcher: HtmlFetcher,
    *,
    official_sources_only: bool = True,
    include_third_party: bool = False,
    router: LLMRouter | None = None,
    max_pages: int = 30,
) -> SourceRegistry:
    strategy = get_strategy(identity.organization_type)
    root_url = normalize_url(identity.official_url or "")
    _, home = html_fetcher.fetch_and_parse(root_url)

    sources: list[SourceRecord] = []
    seen_urls: set[str] = set()

    main = SourceRecord(
        source_name=identity.canonical_name + " Official Website",
        source_role=SourceRole.MAIN_WEBSITE,
        url=root_url,
        domain=domain_of(root_url),
        publishing_entity=identity.canonical_name,
        official_status=OfficialStatus.OFFICIAL,
        access_method=SourceAccessMethod.HTML,
        priority=SourcePriority.HIGH,
        status=SourceStatus.ACTIVE,
        last_checked=datetime.now(timezone.utc),
        confidence=0.99,
        expected_content=["organization identity", "department links", "document links"],
        evidence=[
            Evidence(
                url=root_url,
                title=home.title,
                quote=home.title,
                supports_fields=["url", "source_role"],
                confidence=0.99,
            )
        ],
    )
    sources.append(main)
    seen_urls.add(root_url)

    link_candidates = list(home.links)
    # Seed path hints
    for hint in strategy.path_hints:
        from org_intel.utils.urls import absolutize

        abs_url = absolutize(root_url, hint)
        if abs_url:
            link_candidates.append({"url": abs_url, "text": hint.strip("/"), "domain": domain_of(abs_url)})

    pages_fetched = 0
    for link in link_candidates:
        url = normalize_url(link.get("url") or "")
        if not url or url in seen_urls:
            continue
        text = clean_whitespace(link.get("text") or "")
        host = domain_of(url)
        same_org = is_same_registrable_domain(url, root_url)
        third_party = any(host.endswith(h) for h in THIRD_PARTY_HOSTS)
        if official_sources_only and not same_org and not third_party:
            continue
        if third_party and not include_third_party and not official_sources_only:
            pass
        # Allow official third-party hosts even in official-only mode
        if official_sources_only and not same_org and not third_party:
            continue

        classification = classify_source(text or host, url, router=router)
        # Skip low-value random links unless they matched a role
        if classification["source_role"] == SourceRole.OTHER and classification["confidence"] < 0.5:
            # Still keep path-hint pages
            if not any(h in url for h in strategy.path_hints):
                continue

        sample = ""
        if same_org and pages_fetched < max_pages and classification["priority"] in {
            SourcePriority.ANCHOR,
            SourcePriority.HIGH,
            SourcePriority.MEDIUM,
        }:
            try:
                _, page = html_fetcher.fetch_and_parse(url)
                sample = page.text[:2000]
                pages_fetched += 1
                # harvest nested useful links
                for nested in page.links[:40]:
                    nurl = normalize_url(nested.get("url") or "")
                    if nurl and nurl not in seen_urls and is_same_registrable_domain(nurl, root_url):
                        link_candidates.append(nested)
                classification = classify_source(text or page.title, url, sample, router=router)
            except Exception:
                pass

        source = SourceRecord(
            source_name=text or host,
            url=url,
            domain=host,
            publishing_entity=identity.canonical_name if same_org else host,
            status=SourceStatus.ACTIVE,
            last_checked=datetime.now(timezone.utc),
            evidence=[
                Evidence(
                    url=url,
                    title=text,
                    quote=text or url,
                    supports_fields=["source_role", "url"],
                    confidence=float(classification.get("confidence") or 0.5),
                )
            ],
        )
        if third_party:
            classification["official_status"] = OfficialStatus.OFFICIAL_THIRD_PARTY_HOST
        apply_source_classification(source, classification)
        sources.append(source)
        seen_urls.add(url)

    # Deduplicate by URL
    unique: dict[str, SourceRecord] = {}
    for src in sources:
        key = src.url.rstrip("/")
        if key not in unique or src.confidence > unique[key].confidence:
            unique[key] = src
    sources = list(unique.values())

    registry = SourceRegistry(
        organization_id=identity.organization_id,
        sources=sources,
        field_authority_map=build_field_authority_map(sources),
    )
    return registry


def harvest_document_links_from_sources(
    registry: SourceRegistry,
    html_fetcher: HtmlFetcher,
    *,
    max_sources: int = 25,
) -> list[tuple[SourceRecord, ParsedPage]]:
    """Fetch high-priority source pages for document inventory."""
    priority_order = {
        SourcePriority.ANCHOR: 0,
        SourcePriority.HIGH: 1,
        SourcePriority.MEDIUM: 2,
        SourcePriority.LOW: 3,
    }
    ranked = sorted(registry.sources, key=lambda s: (priority_order.get(s.priority, 9), -s.confidence))
    pages: list[tuple[SourceRecord, ParsedPage]] = []
    for source in ranked[:max_sources]:
        if source.access_method == SourceAccessMethod.PDF or source.url.lower().endswith(".pdf"):
            continue
        try:
            _, page = html_fetcher.fetch_and_parse(source.url)
            pages.append((source, page))
        except Exception:
            continue
    return pages
