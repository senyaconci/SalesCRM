"""Phase 5 — organization-level financial and capital profile."""

from __future__ import annotations

import re

from org_intel.documents.page_index import PageIndex
from org_intel.retrieval.html_fetcher import HtmlFetcher
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.enums import DocumentType, FieldProvenance
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.organization import FinancialCapitalProfile, MetricValue, OrganizationIdentity
from org_intel.utils.money import parse_money
from org_intel.utils.text import excerpt

_BUDGET_TOTAL_RE = re.compile(
    r"(?:total\s+(?:annual\s+)?budget|all funds(?:\s+budget)?|total appropriations)"
    r"[^\d$]{0,40}(\$?[\d,]+(?:\.\d+)?(?:\s*[kmb])?)",
    re.I,
)
_CAPITAL_RE = re.compile(
    r"(?:total\s+capital|capital\s+(?:improvement\s+)?(?:plan|program|budget)\s+(?:total|of)?)"
    r"[^\d$]{0,40}(\$?[\d,]+(?:\.\d+)?(?:\s*[kmb])?)",
    re.I,
)


def build_financial_profile(
    identity: OrganizationIdentity,
    inventory: DocumentInventory,
    indexes: dict[str, PageIndex],
    html_fetcher: HtmlFetcher | None = None,
) -> FinancialCapitalProfile:
    profile = FinancialCapitalProfile(organization_id=identity.organization_id)
    texts: list[tuple[str, str | None, int | None]] = []  # text, url, page

    for doc in inventory.documents:
        if doc.document_type not in {
            DocumentType.ADOPTED_BUDGET,
            DocumentType.PROPOSED_BUDGET,
            DocumentType.CAPITAL_IMPROVEMENT_PLAN,
            DocumentType.CAPITAL_BUDGET,
            DocumentType.ACFR,
            DocumentType.MULTI_YEAR_FINANCIAL_PLAN,
        } and doc.likely_financial_relevance < 0.5:
            continue
        index = indexes.get(doc.document_id)
        if index:
            for page in index.pages[:30]:
                texts.append((page.text, doc.url, page.page_number))
        elif html_fetcher and doc.file_type == "html":
            try:
                _, page = html_fetcher.fetch_and_parse(doc.url)
                texts.append((page.text, doc.url, None))
            except Exception:
                continue

    for text, url, page in texts:
        if not profile.total_annual_budget:
            m = _BUDGET_TOTAL_RE.search(text)
            if m:
                profile.total_annual_budget = MetricValue(
                    value=parse_money(m.group(1)),
                    fiscal_year=identity.fiscal_year,
                    source_url=url,
                    page=page,
                    confidence=0.65,
                    exactness="stated",
                    provenance=FieldProvenance.STATED,
                    evidence=[
                        Evidence(
                            url=url,
                            page=page,
                            quote=excerpt(m.group(0), 240),
                            supports_fields=["total_annual_budget"],
                            confidence=0.65,
                        )
                    ],
                )
        if not profile.cip_value:
            m = _CAPITAL_RE.search(text)
            if m:
                profile.cip_value = MetricValue(
                    value=parse_money(m.group(1)),
                    fiscal_year=identity.fiscal_year,
                    source_url=url,
                    page=page,
                    confidence=0.6,
                    exactness="stated",
                    provenance=FieldProvenance.STATED,
                    evidence=[
                        Evidence(
                            url=url,
                            page=page,
                            quote=excerpt(m.group(0), 240),
                            supports_fields=["cip_value"],
                            confidence=0.6,
                        )
                    ],
                )
        if "capital improvement" in text.lower() and not profile.capital_planning_period:
            period = re.search(r"(20\d{2}\s*[-–/]\s*20\d{2})", text)
            if period:
                profile.capital_planning_period = period.group(1)

    if profile.total_annual_budget and profile.cip_value:
        profile.notes.append(
            "Do not combine annual appropriation totals with multi-year CIP project cost totals."
        )
    confidences = []
    for metric in (profile.total_annual_budget, profile.cip_value, profile.total_capital_expenditure):
        if metric:
            confidences.append(metric.confidence)
    profile.confidence = sum(confidences) / len(confidences) if confidences else 0.2
    return profile
