"""Deterministic + optional LLM document classification."""

from __future__ import annotations

import re
from typing import Any

from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import DOCUMENT_CLASSIFY
from org_intel.llm.router import LLMRouter
from org_intel.schemas.document import DocumentRecord
from org_intel.schemas.enums import ContentRole, DocumentStatus, DocumentType

_RULES: list[tuple[re.Pattern[str], DocumentType, list[ContentRole], float, float, float]] = [
    (
        re.compile(r"capital improvement (program|plan)|\bcip\b", re.I),
        DocumentType.CAPITAL_IMPROVEMENT_PLAN,
        [ContentRole.PROJECT_INVENTORY, ContentRole.FINANCIAL],
        0.95,
        0.85,
        0.2,
    ),
    (
        re.compile(r"adopted budget|annual budget", re.I),
        DocumentType.ADOPTED_BUDGET,
        [ContentRole.FINANCIAL, ContentRole.PROJECT_INVENTORY],
        0.7,
        0.95,
        0.15,
    ),
    (
        re.compile(r"proposed budget", re.I),
        DocumentType.PROPOSED_BUDGET,
        [ContentRole.FINANCIAL],
        0.55,
        0.9,
        0.1,
    ),
    (
        re.compile(r"\bacfr\b|comprehensive annual financial|annual comprehensive financial", re.I),
        DocumentType.ACFR,
        [ContentRole.FINANCIAL, ContentRole.FINANCING, ContentRole.HISTORICAL],
        0.2,
        0.9,
        0.1,
    ),
    (
        re.compile(r"official statement|bond (offering|disclosure)", re.I),
        DocumentType.OFFICIAL_STATEMENT,
        [ContentRole.FINANCING],
        0.45,
        0.7,
        0.1,
    ),
    (
        re.compile(r"master plan", re.I),
        DocumentType.MASTER_PLAN,
        [ContentRole.TECHNICAL_PLANNING],
        0.75,
        0.35,
        0.15,
    ),
    (
        re.compile(r"airport master plan", re.I),
        DocumentType.AIRPORT_MASTER_PLAN,
        [ContentRole.TECHNICAL_PLANNING, ContentRole.PROJECT_INVENTORY],
        0.85,
        0.4,
        0.2,
    ),
    (
        re.compile(r"agenda|packet|boarddocs|legistar", re.I),
        DocumentType.COUNCIL_PACKET,
        [ContentRole.APPROVAL, ContentRole.PROCUREMENT],
        0.45,
        0.25,
        0.7,
    ),
    (
        re.compile(r"\brfq\b|\brfp\b|invitation to bid|\bifb\b|solicitation", re.I),
        DocumentType.BID_SOLICITATION,
        [ContentRole.PROCUREMENT],
        0.4,
        0.1,
        0.95,
    ),
    (
        re.compile(r"award (notice|of contract)|notice of award", re.I),
        DocumentType.AWARD_NOTICE,
        [ContentRole.AWARD, ContentRole.PROCUREMENT],
        0.35,
        0.15,
        0.9,
    ),
    (
        re.compile(r"professional services agreement|consultant agreement", re.I),
        DocumentType.PROFESSIONAL_SERVICES_AGREEMENT,
        [ContentRole.AWARD, ContentRole.PROCUREMENT],
        0.4,
        0.1,
        0.85,
    ),
    (
        re.compile(r"feasibility study", re.I),
        DocumentType.FEASIBILITY_STUDY,
        [ContentRole.TECHNICAL_PLANNING],
        0.7,
        0.3,
        0.25,
    ),
]


def classify_document_heuristic(title: str, url: str = "", text_sample: str = "") -> dict[str, Any]:
    blob = f"{title} {url} {text_sample[:2000]}"
    for pattern, dtype, roles, proj, fin, proc in _RULES:
        if pattern.search(blob):
            status = DocumentStatus.UNKNOWN
            if re.search(r"adopted|approved", blob, re.I):
                status = DocumentStatus.ADOPTED
            elif re.search(r"proposed|draft", blob, re.I):
                status = DocumentStatus.PROPOSED
            fy = None
            fy_match = re.search(r"(fy\s*20\d{2}|20\d{2}\s*[-/]\s*20\d{2}|20\d{2})", blob, re.I)
            if fy_match:
                fy = fy_match.group(1)
            return {
                "document_type": dtype,
                "content_roles": roles,
                "likely_project_relevance": proj,
                "likely_financial_relevance": fin,
                "likely_procurement_relevance": proc,
                "status": status,
                "fiscal_year": fy,
                "confidence": 0.75,
            }
    return {
        "document_type": DocumentType.OTHER,
        "content_roles": [],
        "likely_project_relevance": 0.2,
        "likely_financial_relevance": 0.2,
        "likely_procurement_relevance": 0.2,
        "status": DocumentStatus.UNKNOWN,
        "fiscal_year": None,
        "confidence": 0.3,
    }


def apply_classification(doc: DocumentRecord, classification: dict[str, Any]) -> DocumentRecord:
    doc.document_type = DocumentType(classification["document_type"])
    roles = classification.get("content_roles") or []
    doc.content_roles = [ContentRole(r) if not isinstance(r, ContentRole) else r for r in roles]
    doc.likely_project_relevance = float(classification.get("likely_project_relevance") or 0)
    doc.likely_financial_relevance = float(classification.get("likely_financial_relevance") or 0)
    doc.likely_procurement_relevance = float(
        classification.get("likely_procurement_relevance") or 0
    )
    status = classification.get("status") or DocumentStatus.UNKNOWN
    doc.status = DocumentStatus(status) if not isinstance(status, DocumentStatus) else status
    doc.fiscal_year = classification.get("fiscal_year")
    doc.confidence = float(classification.get("confidence") or doc.confidence)
    return doc


def classify_document(
    doc: DocumentRecord,
    text_sample: str = "",
    router: LLMRouter | None = None,
    use_llm: bool = False,
) -> DocumentRecord:
    heuristic = classify_document_heuristic(doc.title, doc.url, text_sample)
    if use_llm and router is not None and heuristic["confidence"] < 0.7:
        try:
            llm = router.complete_json(
                ModelRole.CHEAP_CLASSIFIER,
                DOCUMENT_CLASSIFY,
                f"Title: {doc.title}\nURL: {doc.url}\nSample:\n{text_sample[:3000]}",
                task_type="document_classify",
                document_id=doc.document_id,
            )
            if isinstance(llm, dict) and llm.get("document_type"):
                heuristic.update({k: v for k, v in llm.items() if v is not None})
        except Exception:
            pass
    return apply_classification(doc, heuristic)
