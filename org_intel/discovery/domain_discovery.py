"""Official domain discovery and validation."""

from __future__ import annotations

from org_intel.utils.urls import domain_of, registrable_domain


GOV_HINTS = (".gov", ".us", ".edu", ".org")


def canonical_domain_from_url(url: str) -> str:
    return domain_of(url)


def is_likely_official_domain(domain: str) -> bool:
    d = domain.lower()
    return any(d.endswith(suffix) for suffix in GOV_HINTS) or ".gov." in d


def discover_additional_domains(links: list[dict[str, str]], primary_url: str) -> list[str]:
    primary = registrable_domain(primary_url)
    found: list[str] = []
    seen = {primary}
    for link in links:
        host = link.get("domain") or domain_of(link.get("url"))
        reg = registrable_domain(host)
        if not reg or reg in seen:
            continue
        # Keep closely related official hosts (subdomains already stripped to registrable)
        text = (link.get("text") or "").lower()
        url = (link.get("url") or "").lower()
        if any(k in text or k in url for k in ("official", "portal", "opengov", "legistar", "boarddocs")):
            if is_likely_official_domain(host) or "legistar" in host or "boarddocs" in host or "opengov" in host:
                seen.add(reg)
                found.append(host)
    return found
