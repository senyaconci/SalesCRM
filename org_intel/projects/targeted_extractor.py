"""Phase — targeted project extraction from evidence windows only."""

from __future__ import annotations

from datetime import datetime, timezone

from org_intel.documents.page_index import PageIndex
from org_intel.documents.pdf_processor import render_page_windows
from org_intel.llm.base import ModelRole
from org_intel.llm.prompts import PROJECT_EXTRACT
from org_intel.llm.router import LLMRouter
from org_intel.projects.phase import normalize_phase
from org_intel.projects.record_type_classifier import classify_record_type
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.enums import PreRfqClassification, ProcurementStatus, ProjectPhase
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.project import (
    ProjectRecord,
    ProjectSourceLink,
    ShallowProjectIndexRecord,
)
from org_intel.utils.money import parse_money
from org_intel.utils.text import excerpt


def enrich_projects(
    shallow: list[ShallowProjectIndexRecord],
    links: list[ProjectSourceLink],
    indexes: dict[str, PageIndex],
    inventory: DocumentInventory,
    *,
    router: LLMRouter | None = None,
    organization_id: str,
    include_completed: bool = False,
    min_project_value: float | None = None,
    project_ids: list[str] | None = None,
    max_projects: int = 100,
) -> list[ProjectRecord]:
    docs = {d.document_id: d for d in inventory.documents}
    links_by_project: dict[str, list[ProjectSourceLink]] = {}
    for link in links:
        links_by_project.setdefault(link.project_id, []).append(link)

    out: list[ProjectRecord] = []
    for item in shallow:
        key = item.project_id or item.record_id
        if project_ids and key not in project_ids and item.project_id not in project_ids:
            continue
        if min_project_value is not None and (item.total_project_cost or 0) < min_project_value:
            continue

        rtype, eligible, reason = classify_record_type(
            item.project_name, item.category, item.published_stage
        )
        phase, phase_inferred, phase_ev = normalize_phase(item.published_stage or "")
        if not include_completed and phase in {
            ProjectPhase.COMPLETED,
            ProjectPhase.CANCELLED,
            ProjectPhase.CONSTRUCTION,
        }:
            # Still include in portfolio but mark; deep enrichment skipped later
            pass

        evidence_windows = _collect_windows(key, links_by_project.get(key, []), indexes)
        record = ProjectRecord(
            organization_id=organization_id,
            project_id=item.project_id,
            project_name=item.project_name,
            alternative_names=list(item.alternative_names),
            record_type=rtype,
            lead_eligible=eligible,
            lead_exclusion_reason=reason,
            department=item.department,
            division=item.division,
            category=item.category,
            location=item.location,
            published_status=item.published_stage,
            normalized_phase=phase,
            phase_evidence=phase_ev,
            phase_is_inferred=phase_inferred,
            total_project_cost=item.total_project_cost,
            construction_year=item.construction_year,
            source_links=links_by_project.get(key, []),
            evidence=list(item.evidence),
            confidence_score=item.confidence,
            first_seen_at=datetime.now(timezone.utc),
            last_verified_at=datetime.now(timezone.utc),
        )
        if evidence_windows:
            record.evidence.append(
                Evidence(
                    url=item.source_url,
                    quote=excerpt(evidence_windows, 500),
                    supports_fields=["project_name"],
                    confidence=0.6,
                )
            )
            # Deterministic money/phase pulls from windows
            money = parse_money(evidence_windows)
            if money and not record.total_project_cost:
                record.total_project_cost = money
            phase2, inf2, ev2 = normalize_phase(evidence_windows)
            if phase2 != ProjectPhase.UNKNOWN and record.normalized_phase == ProjectPhase.UNKNOWN:
                record.normalized_phase = phase2
                record.phase_is_inferred = inf2
                record.phase_evidence = ev2

        if (
            router is not None
            and evidence_windows
            and eligible
            and record.normalized_phase
            not in {ProjectPhase.COMPLETED, ProjectPhase.CANCELLED, ProjectPhase.CONSTRUCTION}
        ):
            record = _llm_enrich(record, evidence_windows, router)

        if not include_completed and record.normalized_phase in {
            ProjectPhase.COMPLETED,
            ProjectPhase.CANCELLED,
        }:
            record.lead_eligible = False
            record.lead_exclusion_reason = record.lead_exclusion_reason or "Completed or cancelled"
            record.pre_rfq_classification = PreRfqClassification.COMPLETED

        out.append(record)
        if len(out) >= max_projects:
            break
    return out


def _collect_windows(
    project_key: str,
    links: list[ProjectSourceLink],
    indexes: dict[str, PageIndex],
) -> str:
    chunks: list[str] = []
    for link in sorted(links, key=lambda l: -l.match_score)[:5]:
        index = indexes.get(link.document_id)
        if not index:
            continue
        pages = link.matching_pages or []
        if not pages:
            continue
        chunks.append(render_page_windows(index.pages, pages, window=1))
    return "\n\n".join(chunks)


def _llm_enrich(record: ProjectRecord, windows: str, router: LLMRouter) -> ProjectRecord:
    data = router.complete_json(
        ModelRole.STRUCTURED_EXTRACTOR,
        PROJECT_EXTRACT,
        f"Project: {record.project_name} ({record.project_id})\n\nEvidence windows:\n{windows[:12000]}",
        task_type="project_extract",
        organization_id=record.organization_id,
        project_id=record.project_id,
    )
    if not isinstance(data, dict):
        return record
    for field in (
        "project_description",
        "problem_or_need",
        "proposed_scope",
        "delivery_method",
        "estimated_design_date",
        "estimated_procurement_date",
        "estimated_bid_date",
        "estimated_construction_start",
        "estimated_completion_date",
    ):
        if data.get(field) and not getattr(record, field):
            setattr(record, field, data[field])
    for field in ("major_components", "deliverables", "infrastructure_domains"):
        if data.get(field):
            setattr(record, field, list(data[field]))
    for field in (
        "total_project_cost",
        "current_year_appropriation",
        "prior_expenditures",
        "future_funding",
        "remaining_balance",
        "requested_funding",
        "approved_funding",
        "unfunded_amount",
    ):
        if data.get(field) is not None and getattr(record, field) is None:
            setattr(record, field, parse_money(data[field]))
    if data.get("normalized_phase"):
        try:
            record.normalized_phase = ProjectPhase(data["normalized_phase"])
            record.phase_is_inferred = bool(data.get("phase_is_inferred"))
            record.phase_evidence = data.get("phase_evidence") or record.phase_evidence
        except ValueError:
            pass
    if data.get("procurement_status"):
        try:
            record.procurement_status = ProcurementStatus(data["procurement_status"])
        except ValueError:
            pass
    return record
