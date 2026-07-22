"""Deterministic parsers for live CIP project detail pages."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from org_intel.schemas.evidence import Evidence
from org_intel.schemas.project import ProjectRecord
from org_intel.utils.money import parse_money
from org_intel.utils.text import clean_whitespace

_LABEL_RE = re.compile(
    r"(Classification|Department|HTE/Munis Project Number|Project Manager|"
    r"Design Fiscal Year|Construction/Purchase Fiscal Year|Target Budget|"
    r"Total Appropriated|Needs Appropriated|Actual Budget|Total Encumbered|"
    r"Total Spent to Date|Actual Project Balance|Ballot Issue|"
    r"Eligible Funding Sources|Project Status)\s*:\s*(.+?)(?="
    r"Classification|Department|HTE/Munis Project Number|Project Manager|"
    r"Design Fiscal Year|Construction/Purchase Fiscal Year|Target Budget|"
    r"Total Appropriated|Needs Appropriated|Actual Budget|Total Encumbered|"
    r"Total Spent to Date|Actual Project Balance|Ballot Issue|"
    r"Eligible Funding Sources|Project Status|Images|Project Map|$)",
    re.I | re.S,
)


def enrich_from_cip_detail_html(project: ProjectRecord, html: str, url: str) -> ProjectRecord:
    soup = BeautifulSoup(html, "lxml")
    text = clean_whitespace(soup.get_text(" ", strip=True))
    if not text:
        return project

    # Description often appears before "Project Status"
    desc_match = re.search(
        r"Search Projects\s+(.+?)\s+Project Status\s+(.+?)\s+Project Details",
        text,
        re.I,
    )
    if desc_match:
        project.project_description = clean_whitespace(desc_match.group(1))[:2000]
        status = clean_whitespace(desc_match.group(2))
        project.published_status = status[:240]
        project.phase_evidence = status[:240]

    fields = {m.group(1).lower(): clean_whitespace(m.group(2)) for m in _LABEL_RE.finditer(text)}
    if fields.get("department") and not project.department:
        project.department = fields["department"]
    if fields.get("classification") and not project.category:
        project.category = fields["classification"]
    if fields.get("hte/munis project number") and not project.project_id:
        project.project_id = fields["hte/munis project number"]
    if fields.get("project manager"):
        project.project_manager = fields["project manager"]
    if fields.get("design fiscal year"):
        project.estimated_design_date = fields["design fiscal year"]
    if fields.get("construction/purchase fiscal year"):
        project.construction_year = fields["construction/purchase fiscal year"]
        project.estimated_construction_start = fields["construction/purchase fiscal year"]
    if fields.get("ballot issue"):
        # keep as quality note / funding label via funding sources below
        pass

    for key, attr in (
        ("target budget", "total_project_cost"),
        ("total appropriated", "approved_funding"),
        ("needs appropriated", "unfunded_amount"),
        ("actual budget", "total_project_cost"),
        ("total spent to date", "prior_expenditures"),
        ("actual project balance", "remaining_balance"),
    ):
        if fields.get(key) is not None:
            amount = parse_money(fields[key])
            if amount is not None and getattr(project, attr) is None:
                setattr(project, attr, amount)

    if fields.get("eligible funding sources"):
        from org_intel.schemas.project import FundingSource

        for part in re.split(r"[,;]", fields["eligible funding sources"]):
            name = clean_whitespace(part)
            if name:
                project.funding_sources.append(FundingSource(name=name))

    project.evidence.append(
        Evidence(
            url=url,
            title=project.project_name,
            quote=text[:500],
            supports_fields=["project_description", "published_status", "total_project_cost"],
            confidence=0.8,
        )
    )
    project.confidence_score = max(project.confidence_score, 0.75)
    return project
