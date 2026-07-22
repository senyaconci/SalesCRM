"""Phase 1 — canonical organization identity with field-level evidence."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from org_intel.discovery.domain_discovery import (
    canonical_domain_from_url,
    discover_additional_domains,
    is_likely_official_domain,
)
from org_intel.discovery.organization_type import detect_organization_type
from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import IDENTITY_EXTRACT
from org_intel.llm.router import LLMRouter
from org_intel.retrieval.html_fetcher import HtmlFetcher, ParsedPage
from org_intel.schemas.enums import FieldProvenance, OrganizationType
from org_intel.schemas.evidence import Evidence, FieldEvidence
from org_intel.schemas.organization import OrganizationIdentity
from org_intel.utils.text import clean_whitespace, excerpt
from org_intel.utils.urls import normalize_url

_STATE_RE = re.compile(
    r"\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|"
    r"Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|"
    r"Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|"
    r"New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|"
    r"Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|"
    r"Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|"
    r"District of Columbia)\b"
)
_PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_ADDR_RE = re.compile(
    r"\b(\d{1,5}\s+[A-Za-z0-9.'\-\s]{2,50}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|"
    r"Broadway|Drive|Dr|Lane|Ln|Way|Court|Ct|Parkway|Pkwy|Circle|Cir|Place|Pl)\.?"
    r"(?:\s*,?\s*[A-Za-z .]+){0,4}(?:\s+\d{5}(?:-\d{4})?)?)\b",
    re.I,
)
_PO_BOX_RE = re.compile(
    r"\bP\.?\s*O\.?\s*Box\s+\d+[^.]{0,60}\d{5}(?:-\d{4})?\b",
    re.I,
)
_COUNTY_RE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s+County)\b")
_BAD_COUNTY_PREFIXES = {
    "pay",
    "online",
    "fees",
    "county",
    "the",
    "this",
    "our",
    "city",
    "work",
    "session",
    "meeting",
    "special",
}
_GOVERNANCE_RE = re.compile(
    r"\b(Council[- ]Manager|Mayor[- ]Council|Commission|Board of Supervisors|"
    r"Board of Trustees|Board of Regents|Authority Board)\b",
    re.I,
)
_SECONDARY_PATHS = (
    "/finance",
    "/city-council",
    "/boards/city-council",
    "/city-managers-office",
    "/city-managers-office/contact-center",
    "/budget",
    "/contact",
    "/contact-us",
    "/about",
)


def build_canonical_identity(
    org_url: str,
    html_fetcher: HtmlFetcher,
    *,
    org_name: str | None = None,
    org_type: str | None = None,
    router: LLMRouter | None = None,
) -> OrganizationIdentity:
    url = normalize_url(org_url)
    _result, page = html_fetcher.fetch_and_parse(url)
    domain = canonical_domain_from_url(url)

    if not is_likely_official_domain(domain) and not domain.endswith((".gov", ".edu", ".us")):
        # Still proceed, but note ambiguity
        pass

    detected_type, type_conf, type_method = detect_organization_type(
        page.text, page.title, url, hinted_type=org_type, router=router
    )

    canonical_name = org_name or _extract_name(page) or page.title or domain
    pages = [page]
    pages.extend(_fetch_secondary_pages(html_fetcher, url))
    combined_text = "\n".join(p.text for p in pages)

    state = _find_state(combined_text)
    phone = _find_phone(combined_text)
    address = _find_address(combined_text)
    county = _find_county(combined_text)
    governance = _find_governance(combined_text)
    additional = discover_additional_domains(page.links, url)

    identity = OrganizationIdentity(
        canonical_name=clean_whitespace(canonical_name),
        common_names=_common_names(canonical_name, page),
        organization_type=detected_type,
        state=state,
        county=county,
        main_address=address,
        main_phone=phone,
        official_domain=domain,
        additional_domains=additional,
        official_url=url,
        governance_model=governance,
        service_area=f"{canonical_name}" if detected_type == OrganizationType.CITY and state else None,
        field_confidence={
            "canonical_name": 0.9 if org_name else 0.75,
            "organization_type": type_conf,
            "official_domain": 0.99,
            "state": 0.7 if state else 0.0,
            "county": 0.75 if county else 0.0,
            "main_phone": 0.8 if phone else 0.0,
            "main_address": 0.75 if address else 0.0,
            "governance_model": 0.8 if governance else 0.0,
        },
    )

    now = datetime.now(timezone.utc)
    identity.field_evidence = [
        FieldEvidence(
            field="canonical_name",
            value=identity.canonical_name,
            source_url=url,
            source_title=page.title,
            quote=excerpt(page.title or identity.canonical_name),
            retrieved_at=now,
            confidence=identity.field_confidence["canonical_name"],
            provenance=FieldProvenance.STATED if org_name or page.title else FieldProvenance.INFERRED,
        ),
        FieldEvidence(
            field="organization_type",
            value=detected_type.value,
            source_url=url,
            source_title=page.title,
            quote=excerpt(page.text, 200),
            retrieved_at=now,
            confidence=type_conf,
            provenance=FieldProvenance.STATED if type_method.startswith("pattern") else FieldProvenance.INFERRED,
        ),
        FieldEvidence(
            field="official_domain",
            value=domain,
            source_url=url,
            source_title=page.title,
            quote=url,
            retrieved_at=now,
            confidence=0.99,
            provenance=FieldProvenance.STATED,
        ),
    ]
    identity.evidence.append(
        Evidence(
            url=url,
            title=page.title,
            quote=excerpt(page.text, 400),
            supports_fields=["canonical_name", "organization_type", "official_domain"],
            confidence=0.85,
            provenance=FieldProvenance.STATED,
        )
    )

    if router is not None and router.provider.name != "mock":
        try:
            # Prefer finance/council pages for LLM identity fields when available.
            enrich_page = next(
                (p for p in pages if any(k in (p.url or "") for k in ("finance", "city-council", "budget"))),
                page,
            )
            identity = _enrich_with_llm(identity, enrich_page, router)
        except Exception:
            # Deterministic identity already captured; LLM enrichment is optional.
            identity.ambiguity_notes.append(
                "LLM identity enrichment failed; continuing with official-page evidence only."
            )

    if identity.organization_type == OrganizationType.UNKNOWN and org_type:
        try:
            identity.organization_type = OrganizationType(org_type)
        except ValueError:
            pass

    # Disambiguation note for similarly named entities
    if "city of" in identity.canonical_name.lower() and not identity.state:
        identity.ambiguity_notes.append(
            "State not confirmed from official homepage; verify before merging with similarly named cities."
        )

    return identity


def _extract_name(page: ParsedPage) -> str | None:
    # Prefer og:site_name / first h1
    if page.meta.get("og:site_name"):
        return clean_whitespace(page.meta["og:site_name"])
    for h in page.headings:
        if h.get("level") == "1" and h.get("text"):
            return h["text"]
    return None


def _common_names(canonical: str, page: ParsedPage) -> list[str]:
    names = {canonical}
    if page.title:
        names.add(clean_whitespace(page.title.split("|")[0].split("-")[0]))
    return [n for n in names if n]


def _find_state(text: str) -> str | None:
    match = _STATE_RE.search(text or "")
    return match.group(1) if match else None


def _find_phone(text: str) -> str | None:
    match = _PHONE_RE.search(text or "")
    return match.group(0) if match else None


def _find_county(text: str) -> str | None:
    for match in _COUNTY_RE.finditer(text or ""):
        candidate = clean_whitespace(match.group(1))
        first = candidate.split()[0].lower()
        if first in _BAD_COUNTY_PREFIXES:
            continue
        if "pay" in candidate.lower() or "online" in candidate.lower():
            continue
        return candidate
    return None


def _find_governance(text: str) -> str | None:
    match = _GOVERNANCE_RE.search(text or "")
    return clean_whitespace(match.group(1)) if match else None


def _find_address(text: str) -> str | None:
    text = text or ""
    # Prefer compact civic street addresses; attach nearby PO Box when present.
    for match in _ADDR_RE.finditer(text):
        candidate = clean_whitespace(match.group(1 if match.lastindex else 0))
        if not _is_plausible_address(candidate):
            continue
        # Trim trailing non-address prose accidentally captured after street token.
        candidate = re.split(
            r"\b(?:Budget|Town|Hall|Contact|Phone|Fax|Email|Hours|Monday)\b",
            candidate,
            maxsplit=1,
        )[0].strip(" ,;")
        if candidate.lower().endswith("p.o. box") or candidate.lower().endswith("po box"):
            window = text[match.end() : match.end() + 80]
            po = re.search(r"P\.?\s*O\.?\s*Box\s+\d+[^.]{0,40}\d{5}(?:-\d{4})?", window, re.I)
            if po:
                candidate = clean_whitespace(candidate + " " + po.group(0))
            else:
                candidate = re.sub(r"\s*P\.?\s*O\.?\s*Box\s*$", "", candidate, flags=re.I).strip(" ,;")
        if _is_plausible_address(candidate):
            return candidate[:160]
    po = _PO_BOX_RE.search(text)
    if po:
        return clean_whitespace(po.group(0))[:160]
    return None


def _fetch_secondary_pages(html_fetcher: HtmlFetcher, base_url: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    for path in _SECONDARY_PATHS:
        try:
            from urllib.parse import urljoin

            secondary = normalize_url(urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/")))
            _result, page = html_fetcher.fetch_and_parse(secondary)
            if page and page.text:
                pages.append(page)
        except Exception:
            continue
        if len(pages) >= 5:
            break
    return pages


def _is_plausible_address(candidate: str | None) -> bool:
    if not candidate:
        return False
    candidate = clean_whitespace(candidate)
    if len(candidate) < 12 or len(candidate) > 160:
        return False
    lower = candidate.lower()
    if any(
        bad in lower
        for bad in (
            "newsletter",
            "featured",
            "project city",
            "click",
            "menu",
            "july",
            "june",
            "recycling",
            "solid waste",
            "utility hosts",
            "drop-off",
            "drop off",
        )
    ):
        return False
    if not re.search(r"\d", candidate):
        return False
    # Require a street-like token, not free-form prose.
    if not re.search(
        r"\b(?:street|st|avenue|ave|road|rd|boulevard|blvd|broadway|drive|dr|"
        r"lane|ln|way|court|ct|parkway|pkwy|circle|cir|place|pl|p\.?\s*o\.?\s*box)\b",
        lower,
    ):
        return False
    return True


def _enrich_with_llm(
    identity: OrganizationIdentity,
    page: ParsedPage,
    router: LLMRouter,
) -> OrganizationIdentity:
    data = router.complete_json(
        ModelRole.STRUCTURED_EXTRACTOR,
        IDENTITY_EXTRACT,
        f"URL: {identity.official_url}\nTitle: {page.title}\nText:\n{page.text[:7000]}",
        task_type="identity_extract",
        organization_id=identity.organization_id,
    )
    if not isinstance(data, dict):
        return identity
    for field_name in (
        "canonical_name",
        "state",
        "county",
        "main_address",
        "main_phone",
        "service_area",
        "governance_model",
        "population_or_customer_base",
        "fiscal_year",
    ):
        value = data.get(field_name)
        if not value or getattr(identity, field_name):
            continue
        if field_name == "main_address" and not _is_plausible_address(str(value)):
            continue
        if field_name == "county":
            county = clean_whitespace(str(value))
            if county.split()[0].lower() in _BAD_COUNTY_PREFIXES or not county.lower().endswith("county"):
                continue
            value = county
        if field_name == "main_phone" and not _PHONE_RE.search(str(value)):
            continue
        setattr(identity, field_name, value)
        identity.field_confidence[field_name] = float(
            (data.get("field_confidence") or {}).get(field_name, 0.7)
        )
    common = data.get("common_names")
    if isinstance(common, list):
        identity.common_names = list(dict.fromkeys(identity.common_names + [str(x) for x in common]))
    notes = data.get("ambiguity_notes")
    if isinstance(notes, str) and notes.strip():
        identity.ambiguity_notes.append(notes.strip())
    elif isinstance(notes, list):
        identity.ambiguity_notes.extend(str(n).strip() for n in notes if str(n).strip())
    if data.get("organization_type"):
        try:
            identity.organization_type = OrganizationType(data["organization_type"])
        except ValueError:
            pass
    return identity
