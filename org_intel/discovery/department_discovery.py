"""Phase 2 — organization and responsibility mapping."""

from __future__ import annotations

import re

from org_intel.retrieval.html_fetcher import HtmlFetcher, ParsedPage
from org_intel.schemas.enums import EntityNodeType, FieldProvenance, RelationshipType
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import (
    OrganizationIdentity,
    OrganizationNode,
    OrganizationRelationship,
    OrganizationRelationshipGraph,
)
from org_intel.strategies.base import OrganizationStrategy, get_strategy
from org_intel.utils.text import clean_whitespace, excerpt
from org_intel.utils.urls import absolutize, is_same_registrable_domain, normalize_url

_CAPITAL_FUNCS = {
    "capital planning": "capital_planning",
    "budget": "budget_preparation",
    "finance": "finance",
    "engineering": "engineering",
    "public works": "construction_management",
    "facilities": "facilities",
    "utilities": "utilities",
    "procurement": "procurement",
    "purchasing": "procurement",
    "grants": "grants",
    "clerk": "council_or_board_records",
    "planning": "capital_planning",
}


def discover_organization_map(
    identity: OrganizationIdentity,
    html_fetcher: HtmlFetcher,
    seed_page: ParsedPage | None = None,
) -> OrganizationRelationshipGraph:
    strategy = get_strategy(identity.organization_type)
    if seed_page is None:
        _, seed_page = html_fetcher.fetch_and_parse(identity.official_url or "")

    root = OrganizationNode(
        name=identity.canonical_name,
        entity_type=EntityNodeType.ORGANIZATION,
        function="root",
        official_url=identity.official_url,
        confidence=0.95,
        capital_responsibilities=["overall"],
        evidence=[
            Evidence(
                url=identity.official_url,
                title=seed_page.title,
                quote=excerpt(seed_page.text, 200),
                supports_fields=["name"],
                confidence=0.95,
                provenance=FieldProvenance.STATED,
            )
        ],
    )

    nodes = [root]
    relationships: list[OrganizationRelationship] = []
    seen_names = {root.name.lower()}

    # Scan homepage links and department terms
    candidates = _department_candidates(seed_page, strategy, identity.official_url or "")
    # Follow a small set of department/about/government pages
    follow_urls = [
        c["url"]
        for c in candidates
        if c.get("url") and is_same_registrable_domain(c["url"], identity.official_url)
    ][:12]

    pages = [seed_page]
    for url in follow_urls:
        try:
            _, page = html_fetcher.fetch_and_parse(url)
            pages.append(page)
            candidates.extend(_department_candidates(page, strategy, identity.official_url or ""))
        except Exception:
            continue

    for cand in candidates:
        name = cand["name"]
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        entity_type = _entity_type_for(name)
        functions = _functions_for(name, strategy)
        node = OrganizationNode(
            name=name,
            entity_type=entity_type,
            parent_id=root.node_id,
            function="; ".join(functions) if functions else cand.get("function"),
            capital_responsibilities=functions,
            official_url=cand.get("url"),
            confidence=float(cand.get("confidence") or 0.6),
            has_separate_budget=_maybe_separate_budget(name),
            has_separate_procurement=_maybe_separate_procurement(name),
            evidence=[
                Evidence(
                    url=cand.get("url") or identity.official_url,
                    quote=cand.get("quote") or name,
                    supports_fields=["name", "capital_responsibilities"],
                    confidence=float(cand.get("confidence") or 0.6),
                    provenance=FieldProvenance.STATED,
                )
            ],
        )
        nodes.append(node)
        relationships.append(
            OrganizationRelationship(
                from_node_id=node.node_id,
                to_node_id=root.node_id,
                relationship_type=RelationshipType.REPORTS_TO,
                confidence=node.confidence,
            )
        )
        if "procurement" in functions:
            relationships.append(
                OrganizationRelationship(
                    from_node_id=node.node_id,
                    to_node_id=root.node_id,
                    relationship_type=RelationshipType.PROCURES_FOR,
                    confidence=node.confidence,
                )
            )
        if any(f in functions for f in ("engineering", "construction_management", "facilities", "capital_planning")):
            relationships.append(
                OrganizationRelationship(
                    from_node_id=node.node_id,
                    to_node_id=root.node_id,
                    relationship_type=RelationshipType.MANAGES_PROJECTS_FOR,
                    confidence=node.confidence,
                )
            )

    summary: dict[str, list[str]] = {}
    for node in nodes:
        for resp in node.capital_responsibilities:
            summary.setdefault(resp, []).append(node.name)

    return OrganizationRelationshipGraph(
        organization_id=identity.organization_id,
        nodes=nodes,
        relationships=relationships,
        capital_responsibility_summary=summary,
    )


def _department_candidates(
    page: ParsedPage,
    strategy: OrganizationStrategy,
    base_url: str,
) -> list[dict]:
    out: list[dict] = []
    terms = [t.lower() for t in strategy.department_terms]
    for link in page.links:
        text = clean_whitespace(link.get("text") or "")
        url = link.get("url") or ""
        if not text or len(text) > 80:
            continue
        if not _looks_like_org_entity(text):
            continue
        lower = text.lower()
        if any(term in lower or term.replace(" ", "-") in url.lower() for term in terms):
            out.append(
                {
                    "name": text,
                    "url": url,
                    "confidence": 0.7,
                    "quote": text,
                    "function": None,
                }
            )
    # Also scan headings (same entity filter as links).
    for h in page.headings:
        text = clean_whitespace(h.get("text") or "")
        if not _looks_like_org_entity(text):
            continue
        lower = text.lower()
        if any(term in lower for term in terms):
            out.append({"name": text, "url": base_url, "confidence": 0.55, "quote": text})
    # Path hints as synthetic department discovery seeds
    for hint in strategy.path_hints:
        abs_url = absolutize(base_url, hint)
        if abs_url:
            label = hint.strip("/").replace("-", " ").title()
            if not _looks_like_org_entity(label):
                continue
            out.append(
                {
                    "name": label,
                    "url": normalize_url(abs_url),
                    "confidence": 0.4,
                    "quote": hint,
                    "function": None,
                }
            )
    return out


def _entity_type_for(name: str) -> EntityNodeType:
    lower = name.lower()
    if any(k in lower for k in ("council", "commission", "board of", "regents", "trustees")):
        return EntityNodeType.GOVERNING_BODY
    if "committee" in lower:
        return EntityNodeType.COMMITTEE
    if "advisory" in lower:
        return EntityNodeType.ADVISORY_BOARD
    if any(k in lower for k in ("procurement", "purchasing", "bids")):
        return EntityNodeType.PROCUREMENT_OFFICE
    if "utility" in lower or "water" in lower or "wastewater" in lower:
        return EntityNodeType.UTILITY
    if "authority" in lower:
        return EntityNodeType.AUTHORITY
    if "division" in lower:
        return EntityNodeType.DIVISION
    return EntityNodeType.DEPARTMENT


def _functions_for(name: str, strategy: OrganizationStrategy) -> list[str]:
    lower = name.lower()
    funcs = []
    for needle, func in _CAPITAL_FUNCS.items():
        if needle in lower:
            funcs.append(func)
    if not funcs:
        for term in strategy.department_terms:
            if term.lower() in lower:
                funcs.append(re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_"))
    return list(dict.fromkeys(funcs))


def _maybe_separate_budget(name: str) -> bool | None:
    lower = name.lower()
    if any(k in lower for k in ("utility", "enterprise", "authority", "airport")):
        return True
    return None


def _maybe_separate_procurement(name: str) -> bool | None:
    lower = name.lower()
    if any(k in lower for k in ("procurement", "purchasing", "authority")):
        return True
    return None


def _looks_like_org_entity(name: str) -> bool:
    lower = name.lower().strip()
    if not lower or len(lower) < 3 or len(lower) > 60:
        return False
    words = lower.split()
    if len(words) > 6:
        return False
    banned = (
        "pay ",
        "apply",
        "register",
        "report ",
        "opens",
        "faq",
        "news",
        "browse",
        "arrest",
        "shooting",
        "holiday",
        "featured",
        "newsletter",
        "click",
        "rebates",
        "free ",
        "see other",
        "let's talk",
        "responds to",
        "invited to",
        "trash",
        "recycling",
        "pickup",
        "roll-off",
        "hazardous waste",
        "sports leagues",
        "facility rental",
        "activity registration",
        "snow and ice",
        "outage",
        "boil",
        "yard waste",
        "large-item",
        "large item",
        "parking ticket",
        "business license",
        "hotel",
        "citizen self-service",
        "history of",
        "resident",
        "press release",
        "tribute",
        "request for",
        "ride-along",
        "ride along",
        "vehicle stops",
        "extra duty",
        "community event",
        "firefighter",
        "station tours",
        "police academy",
        "university of",
        "senior management",
        "@",
        ".gov",
        "pdf",
        "honor guard",
        "juvenile",
        "escape",
        "safety information",
        "meet the",
        "events",
        "benefits of",
        "dog parks",
        "wards map",
        "how to",
        "upcoming",
        "meetings",
        "follow-up",
        "follow up",
        "audit",
        "ordinances",
        "posts",
        "agenda",
        "friends of",
        "welcome to",
        "water leaks",
        "electric meters",
        "sewer obstructions",
        "about the",
        "about water",
        "about engineering",
        "about finance",
        "about public",
        "about city",
        "about columbia",
        "read more",
        "structure of",
        "approves budget",
        "open finance",
        "inspection",
        "organization",
        "performance",
        "police employment",
        "permit guidelines",
        "permits and planning",
        "dispatch",
        "guidelines",
        "information",
        "browse",
        "popular",
    )
    if any(b in lower for b in banned):
        return False
    if lower.startswith("about ") or lower.startswith("welcome "):
        return False

    unit_suffixes = (
        "department",
        "division",
        "office",
        "council",
        "board",
        "commission",
        "authority",
        "utility",
        "utilities",
    )
    if any(lower.endswith(s) or f" {s}" in lower for s in unit_suffixes):
        return True

    exact_or_core = {
        "finance",
        "public works",
        "procurement",
        "purchasing",
        "engineering",
        "planning",
        "police",
        "fire",
        "parks and recreation",
        "parks & recreation",
        "airport",
        "transit",
        "water",
        "sewer",
        "electric",
        "stormwater",
        "storm water",
        "budget",
        "cip",
        "bids",
        "community development",
        "solid waste",
        "railroad",
        "colt railroad",
        "parking utility",
        "city council",
        "city manager",
        "city manager's office",
        "city managers office",
        "accounting & finance",
        "contracting & purchasing",
        "columbia police",
        "fire department",
    }
    return lower in exact_or_core or any(lower.startswith(x) and len(words) <= 4 for x in exact_or_core)
