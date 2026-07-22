"""Identify leadership and project contacts from official pages."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from org_intel.retrieval.html_fetcher import HtmlFetcher, ParsedPage
from org_intel.schemas.contact import ContactRecord, EmailPattern, StakeholderMap
from org_intel.schemas.enums import EmailStatus, FieldProvenance
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import OrganizationIdentity, OrganizationRelationshipGraph
from org_intel.schemas.project import ProjectRecord
from org_intel.utils.text import clean_whitespace
from org_intel.utils.urls import normalize_url

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_NAME_TITLE = re.compile(
    r"(?<![A-Za-z])((?:[A-Z][a-z]+|[A-Z][a-z]*['’][A-Z]?[a-z]+)"
    r"(?:\s(?:[A-Z][a-z]+|[A-Z][a-z]*['’][A-Z]?[a-z]+)){1,2})"
    r"(?:\s*,\s*|\s+)"
    r"(Mayor|City Manager|County Administrator|General Manager|"
    r"Public Works Director|Finance Director|Chief Financial Officer|CFO|"
    r"Procurement Manager|Purchasing Manager|City Engineer|"
    r"Facilities Director|Airport Director|Ward\s+[1-9])\b",
    re.I,
)
_LEADERSHIP_PATHS = (
    "/boards/city-council",
    "/city-council",
    "/city-managers-office",
    "/finance",
    "/public-works",
    "/utilities",
    "/procurement",
)


def map_stakeholders(
    identity: OrganizationIdentity,
    graph: OrganizationRelationshipGraph,
    html_fetcher: HtmlFetcher,
    projects: list[ProjectRecord] | None = None,
) -> StakeholderMap:
    contacts: list[ContactRecord] = []
    pages: list[ParsedPage] = []
    urls: list[str] = []
    if identity.official_url:
        for path in _LEADERSHIP_PATHS:
            urls.append(normalize_url(urljoin(identity.official_url, path.lstrip("/"))))
        urls.append(identity.official_url)
    for node in graph.nodes:
        if node.official_url and any(
            k in (node.name or "").lower()
            for k in (
                "staff",
                "directory",
                "about",
                "council",
                "manager",
                "finance",
                "public works",
                "leadership",
                "contact",
            )
        ):
            urls.append(node.official_url)
    for url in list(dict.fromkeys(urls))[:18]:
        try:
            _, page = html_fetcher.fetch_and_parse(url)
            pages.append(page)
        except Exception:
            continue

    emails_found: list[str] = []
    for page in pages:
        # Normalize curly apostrophes so De’Carlon-style names parse.
        text = (page.text or "").replace("’", "'").replace("`", "'")
        emails_found.extend(_EMAIL_RE.findall(text))
        for match in _NAME_TITLE.finditer(text):
            name = clean_whitespace(match.group(1))
            title = clean_whitespace(match.group(2))
            if not _looks_like_person_name(name):
                parts = name.split()
                if len(parts) >= 2 and _looks_like_person_name(" ".join(parts[-2:])):
                    name = " ".join(parts[-2:])
                else:
                    continue
            if not _looks_like_person_name(name):
                continue
            email = _nearby_email(text, match.start(), match.end())
            phone = _nearby_phone(text, match.start(), match.end())
            contacts.append(
                ContactRecord(
                    name=name,
                    title=title,
                    functional_role=_functional_role(title),
                    email=email,
                    email_status=EmailStatus.CONFIRMED if email else EmailStatus.NONE,
                    phone=phone,
                    official_profile_url=page.url,
                    confidence=0.75 if email else 0.65,
                    evidence=[
                        Evidence(
                            url=page.url,
                            title=page.title,
                            quote=match.group(0),
                            supports_fields=["name", "title"],
                            confidence=0.7,
                            provenance=FieldProvenance.STATED,
                        )
                    ],
                )
            )

    for project in projects or []:
        for stake in project.stakeholders:
            if not _looks_like_person_name(stake.name or ""):
                continue
            contacts.append(
                ContactRecord(
                    name=stake.name,
                    title=stake.title,
                    department=stake.department or project.department,
                    functional_role=stake.functional_role or "project_contact",
                    email=stake.email,
                    email_status=EmailStatus.CONFIRMED if stake.email else EmailStatus.NONE,
                    phone=stake.phone,
                    relevant_projects=[project.project_id or project.record_id],
                    confidence=stake.confidence,
                    evidence=stake.evidence,
                )
            )

    contacts = _dedupe_contacts(contacts)
    pattern = infer_email_pattern(emails_found, identity.official_domain)
    return StakeholderMap(
        organization_id=identity.organization_id,
        contacts=contacts,
        email_pattern=pattern,
    )


def infer_email_pattern(emails: list[str], domain: str | None) -> EmailPattern | None:
    """Record org-wide pattern only — never manufacture individual emails."""
    if not emails or not domain:
        return None
    domain = domain.lower()
    local_parts = []
    for email in emails:
        if email.lower().endswith("@" + domain):
            local_parts.append(email.split("@")[0].lower())
    if not local_parts:
        return None
    if any("." in p for p in local_parts):
        return EmailPattern(
            pattern=f"firstname.lastname@{domain}",
            example=None,
            confidence=0.5,
        )
    if any(re.fullmatch(r"[a-z]\w+", p) for p in local_parts):
        return EmailPattern(
            pattern=f"firstinitiallastname@{domain}",
            confidence=0.4,
        )
    return EmailPattern(pattern=f"*@{domain}", confidence=0.3)


def _looks_like_person_name(name: str) -> bool:
    parts = [p for p in clean_whitespace(name).split(" ") if p]
    if len(parts) < 2 or len(parts) > 3:
        return False
    banned = {
        "city",
        "clerk",
        "department",
        "departments",
        "accreditation",
        "manager",
        "office",
        "finance",
        "public",
        "works",
        "parks",
        "director",
        "menu",
        "press",
        "releases",
        "service",
        "portal",
        "reports",
        "purchasing",
        "recreation",
        "home",
        "trails",
        "sports",
        "leagues",
        "instructions",
        "minority",
        "owned",
        "businesses",
        "terms",
        "about",
        "june",
        "airport",
        "history",
        "all",
        "facility",
        "license",
        "review",
        "board",
        "administration",
        "staff",
        "construction",
        "project",
        "superintendent",
        "vacant",
        "terms",
        "members",
        "about",
        "ward",
        "popular",
        "browse",
    }
    if any(p.lower() in banned for p in parts):
        return False
    # Prefer ordinary First Last / First Middle Last person shapes.
    if len(parts) > 3:
        return False
    return all(re.fullmatch(r"[A-Z][a-z'’\-]+", p) for p in parts)


def _nearby_email(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 120) : end + 180]
    match = _EMAIL_RE.search(window)
    return match.group(0) if match else None


def _nearby_phone(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 80) : end + 120]
    match = _PHONE_RE.search(window)
    return match.group(0) if match else None


def _functional_role(title: str) -> str:
    t = title.lower()
    if "mayor" in t or t.startswith("ward"):
        return "elected_official"
    if "financ" in t or "cfo" in t:
        return "finance_leadership"
    if "procur" in t or "purchas" in t:
        return "procurement_leadership"
    if "public works" in t or "engineer" in t:
        return "public_works_leadership"
    if "manager" in t and "project" in t:
        return "project_manager"
    if "city manager" in t or "general manager" in t or "administrator" in t:
        return "executive_leadership"
    if "facilit" in t:
        return "facilities_leadership"
    return "other"


def _dedupe_contacts(contacts: list[ContactRecord]) -> list[ContactRecord]:
    seen: dict[str, ContactRecord] = {}
    for c in contacts:
        key = (c.name or "").lower()
        if key not in seen or c.confidence > seen[key].confidence:
            seen[key] = c
    return list(seen.values())
