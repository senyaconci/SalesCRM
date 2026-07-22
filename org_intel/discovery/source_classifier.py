"""Source-role classification and authority mapping."""

from __future__ import annotations

import re
from typing import Any

from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import SOURCE_CLASSIFY
from org_intel.llm.router import LLMRouter
from org_intel.schemas.enums import (
    ContentRole,
    OfficialStatus,
    SourceAccessMethod,
    SourcePriority,
    SourceRole,
)
from org_intel.schemas.source import SourceRecord

_PORTAL_HINTS: list[tuple[re.Pattern[str], SourceRole, list[ContentRole], SourcePriority]] = [
    (re.compile(r"legistar", re.I), SourceRole.LEGISTAR, [ContentRole.APPROVAL, ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"boarddocs", re.I), SourceRole.BOARDDOCS, [ContentRole.APPROVAL], SourcePriority.HIGH),
    (re.compile(r"granicus", re.I), SourceRole.GRANICUS, [ContentRole.APPROVAL], SourcePriority.HIGH),
    (re.compile(r"opengov", re.I), SourceRole.OPENGOV, [ContentRole.FINANCIAL, ContentRole.PROJECT_INVENTORY], SourcePriority.ANCHOR),
    (re.compile(r"demandstar", re.I), SourceRole.DEMANDSTAR, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"bonfire", re.I), SourceRole.BONFIRE, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"planetbids", re.I), SourceRole.PLANETBIDS, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"ionwave", re.I), SourceRole.IONWAVE, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"bidnet", re.I), SourceRole.BIDNET, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"municode", re.I), SourceRole.MUNICODE, [ContentRole.REGULATORY], SourcePriority.MEDIUM),
]

_CONTENT_HINTS: list[tuple[re.Pattern[str], SourceRole, list[ContentRole], SourcePriority]] = [
    (
        re.compile(r"cipweb|display_project\.php|project_search\.php", re.I),
        SourceRole.LIVE_PROJECT_REGISTRY,
        [ContentRole.PROJECT_INVENTORY, ContentRole.FINANCIAL],
        SourcePriority.ANCHOR,
    ),
    (re.compile(r"capital improvement|\bcip\b|capital projects", re.I), SourceRole.CIP_PORTAL, [ContentRole.PROJECT_INVENTORY, ContentRole.FINANCIAL], SourcePriority.ANCHOR),
    (re.compile(r"\bbudget\b|financial reports|acfr", re.I), SourceRole.BUDGET_PORTAL, [ContentRole.FINANCIAL], SourcePriority.HIGH),
    (re.compile(r"\bbids?\b|rfp|rfq|procurement|purchasing|solicit", re.I), SourceRole.PROCUREMENT_PAGE, [ContentRole.PROCUREMENT], SourcePriority.HIGH),
    (re.compile(r"agenda|minutes|council|board meetings", re.I), SourceRole.BOARD_AGENDA, [ContentRole.APPROVAL], SourcePriority.HIGH),
    (re.compile(r"master plan|facilities plan", re.I), SourceRole.MASTER_PLAN_ARCHIVE, [ContentRole.TECHNICAL_PLANNING], SourcePriority.MEDIUM),
    # Avoid matching generic "registration" pages; require capital/project tracker language.
    (
        re.compile(
            r"(capital|cip).{0,40}(project (tracker|map|status|registry|search))"
            r"|project (tracker|status dashboard)|capital projects dashboard|\bgis\b.{0,20}project",
            re.I,
        ),
        SourceRole.LIVE_PROJECT_REGISTRY,
        [ContentRole.PROJECT_INVENTORY],
        SourcePriority.ANCHOR,
    ),
    (re.compile(r"bond|official statement|disclosure", re.I), SourceRole.BOND_DISCLOSURE, [ContentRole.FINANCING], SourcePriority.MEDIUM),
    (re.compile(r"public (notice|engagement|hearing)", re.I), SourceRole.PUBLIC_ENGAGEMENT, [ContentRole.PUBLIC_ENGAGEMENT], SourcePriority.LOW),
]

# Field authority preference order (source roles)
FIELD_AUTHORITY: dict[str, list[SourceRole]] = {
    "current_stage": [SourceRole.LIVE_PROJECT_REGISTRY, SourceRole.CIP_PORTAL, SourceRole.BUDGET_PORTAL],
    "exact_project_budget": [SourceRole.BUDGET_PORTAL, SourceRole.CIP_PORTAL, SourceRole.LIVE_PROJECT_REGISTRY],
    "total_project_cost": [SourceRole.CIP_PORTAL, SourceRole.BUDGET_PORTAL, SourceRole.MASTER_PLAN_ARCHIVE],
    "annual_appropriation": [SourceRole.BUDGET_PORTAL, SourceRole.CIP_PORTAL],
    "technical_scope": [SourceRole.MASTER_PLAN_ARCHIVE, SourceRole.PROJECT_WEBSITE, SourceRole.DOCUMENT_LIBRARY],
    "consultant_selection": [SourceRole.BOARD_AGENDA, SourceRole.LEGISTAR, SourceRole.BOARDDOCS],
    "solicitation_status": [
        SourceRole.BID_PORTAL,
        SourceRole.DEMANDSTAR,
        SourceRole.BONFIRE,
        SourceRole.PLANETBIDS,
        SourceRole.PROCUREMENT_PAGE,
    ],
    "contract_award": [SourceRole.BOARD_AGENDA, SourceRole.LEGISTAR, SourceRole.BID_PORTAL],
    "contact": [SourceRole.MAIN_WEBSITE, SourceRole.PROJECT_WEBSITE, SourceRole.DOCUMENT_LIBRARY],
    "funding_authorization": [SourceRole.BOARD_AGENDA, SourceRole.BUDGET_PORTAL, SourceRole.BOND_DISCLOSURE],
}


def classify_source(
    name: str,
    url: str,
    text_sample: str = "",
    router: LLMRouter | None = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    blob = f"{name} {url} {text_sample[:1500]}"
    for pattern, role, roles, priority in _PORTAL_HINTS:
        if pattern.search(blob):
            return {
                "source_role": role,
                "content_roles": roles,
                "priority": priority,
                "expected_content": [role.value],
                "confidence": 0.85,
                "official_status": OfficialStatus.OFFICIAL_THIRD_PARTY_HOST
                if role
                not in {
                    SourceRole.CIP_PORTAL,
                    SourceRole.BUDGET_PORTAL,
                    SourceRole.MAIN_WEBSITE,
                    SourceRole.PROCUREMENT_PAGE,
                    SourceRole.BOARD_AGENDA,
                }
                else OfficialStatus.OFFICIAL,
                "access_method": SourceAccessMethod.JAVASCRIPT
                if role
                in {
                    SourceRole.LEGISTAR,
                    SourceRole.BOARDDOCS,
                    SourceRole.OPENGOV,
                    SourceRole.DEMANDSTAR,
                    SourceRole.BONFIRE,
                    SourceRole.PLANETBIDS,
                }
                else SourceAccessMethod.HTML,
            }
    for pattern, role, roles, priority in _CONTENT_HINTS:
        if pattern.search(blob):
            return {
                "source_role": role,
                "content_roles": roles,
                "priority": priority,
                "expected_content": [r.value for r in roles],
                "confidence": 0.75,
                "official_status": OfficialStatus.OFFICIAL,
                "access_method": SourceAccessMethod.HTML,
            }

    result = {
        "source_role": SourceRole.OTHER,
        "content_roles": [],
        "priority": SourcePriority.LOW,
        "expected_content": [],
        "confidence": 0.35,
        "official_status": OfficialStatus.OFFICIAL,
        "access_method": SourceAccessMethod.HTML,
    }
    if use_llm and router is not None:
        try:
            llm = router.complete_json(
                ModelRole.CHEAP_CLASSIFIER,
                SOURCE_CLASSIFY,
                f"Name: {name}\nURL: {url}\nSample:\n{text_sample[:2500]}",
                task_type="source_classify",
            )
            if isinstance(llm, dict) and llm.get("source_role"):
                result.update({k: v for k, v in llm.items() if v is not None})
        except Exception:
            pass
    return result


def apply_source_classification(source: SourceRecord, classification: dict[str, Any]) -> SourceRecord:
    role = classification.get("source_role") or SourceRole.OTHER
    source.source_role = SourceRole(role) if not isinstance(role, SourceRole) else role
    roles = classification.get("content_roles") or []
    source.content_roles = [ContentRole(r) if not isinstance(r, ContentRole) else r for r in roles]
    priority = classification.get("priority") or SourcePriority.MEDIUM
    source.priority = SourcePriority(priority) if not isinstance(priority, SourcePriority) else priority
    status = classification.get("official_status") or OfficialStatus.OFFICIAL
    source.official_status = (
        OfficialStatus(status) if not isinstance(status, OfficialStatus) else status
    )
    access = classification.get("access_method") or SourceAccessMethod.HTML
    source.access_method = (
        SourceAccessMethod(access) if not isinstance(access, SourceAccessMethod) else access
    )
    source.expected_content = list(classification.get("expected_content") or [])
    source.confidence = float(classification.get("confidence") or source.confidence)
    source.authority_fields = [
        field
        for field, roles in FIELD_AUTHORITY.items()
        if source.source_role in roles
    ]
    return source


def build_field_authority_map(sources: list[SourceRecord]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for field, preferred_roles in FIELD_AUTHORITY.items():
        ordered: list[str] = []
        for role in preferred_roles:
            for src in sources:
                if src.source_role == role and src.source_id not in ordered:
                    ordered.append(src.source_id)
        mapping[field] = ordered
    return mapping
