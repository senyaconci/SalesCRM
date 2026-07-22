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
    r"\d{1,5}\s+[A-Za-z0-9.\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|"
    r"Lane|Ln|Way|Court|Ct|Parkway|Pkwy)\b[^.]{0,80}",
    re.I,
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
    state = _find_state(page.text)
    phone = _find_phone(page.text)
    address = _find_address(page.text)
    additional = discover_additional_domains(page.links, url)

    identity = OrganizationIdentity(
        canonical_name=clean_whitespace(canonical_name),
        common_names=_common_names(canonical_name, page),
        organization_type=detected_type,
        state=state,
        main_address=address,
        main_phone=phone,
        official_domain=domain,
        additional_domains=additional,
        official_url=url,
        field_confidence={
            "canonical_name": 0.9 if org_name else 0.75,
            "organization_type": type_conf,
            "official_domain": 0.99,
            "state": 0.7 if state else 0.0,
            "main_phone": 0.8 if phone else 0.0,
            "main_address": 0.7 if address else 0.0,
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
        identity = _enrich_with_llm(identity, page, router)

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


def _find_address(text: str) -> str | None:
    match = _ADDR_RE.search(text or "")
    return clean_whitespace(match.group(0)) if match else None


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
        if value and not getattr(identity, field_name):
            setattr(identity, field_name, value)
            identity.field_confidence[field_name] = float(
                (data.get("field_confidence") or {}).get(field_name, 0.7)
            )
    if data.get("common_names"):
        identity.common_names = list(
            dict.fromkeys(identity.common_names + list(data["common_names"]))
        )
    if data.get("ambiguity_notes"):
        identity.ambiguity_notes.extend(data["ambiguity_notes"])
    if data.get("organization_type"):
        try:
            identity.organization_type = OrganizationType(data["organization_type"])
        except ValueError:
            pass
    return identity
