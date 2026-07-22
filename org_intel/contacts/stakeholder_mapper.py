"""Identify leadership and project contacts from official pages."""

from __future__ import annotations

import re

from org_intel.retrieval.html_fetcher import HtmlFetcher, ParsedPage
from org_intel.schemas.contact import ContactRecord, EmailPattern, StakeholderMap
from org_intel.schemas.enums import EmailStatus, FieldProvenance
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import OrganizationIdentity, OrganizationRelationshipGraph
from org_intel.schemas.project import ProjectRecord
from org_intel.utils.text import clean_whitespace

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_NAME_TITLE = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z][a-z'’-]+){1,3}),?\s+(City Manager|County Administrator|"
    r"General Manager|Director of [A-Za-z ]+|Public Works Director|Finance Director|"
    r"Procurement Manager|Purchasing Manager|City Engineer|Project Manager|"
    r"Superintendent|President|Facilities Director|Airport Director)",
    re.I,
)


def map_stakeholders(
    identity: OrganizationIdentity,
    graph: OrganizationRelationshipGraph,
    html_fetcher: HtmlFetcher,
    projects: list[ProjectRecord] | None = None,
) -> StakeholderMap:
    contacts: list[ContactRecord] = []
    pages: list[ParsedPage] = []
    urls = [identity.official_url] if identity.official_url else []
    for node in graph.nodes:
        if node.official_url and any(
            k in (node.name or "").lower()
            for k in ("staff", "directory", "about", "department", "contact", "leadership")
        ):
            urls.append(node.official_url)
    for url in list(dict.fromkeys(urls))[:15]:
        try:
            _, page = html_fetcher.fetch_and_parse(url)
            pages.append(page)
        except Exception:
            continue

    emails_found: list[str] = []
    for page in pages:
        emails_found.extend(_EMAIL_RE.findall(page.text))
        for match in _NAME_TITLE.finditer(page.text):
            name = clean_whitespace(match.group(1))
            title = clean_whitespace(match.group(2))
            email = _nearby_email(page.text, match.start(), match.end())
            phone = _nearby_phone(page.text, match.start(), match.end())
            contacts.append(
                ContactRecord(
                    name=name,
                    title=title,
                    functional_role=_functional_role(title),
                    email=email,
                    email_status=EmailStatus.CONFIRMED if email else EmailStatus.NONE,
                    phone=phone,
                    official_profile_url=page.url,
                    confidence=0.7 if email else 0.55,
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

    # Project-specific contacts
    for project in projects or []:
        for stake in project.stakeholders:
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
    if "financ" in t:
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
