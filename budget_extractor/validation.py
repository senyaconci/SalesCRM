"""JSON parsing, local cleanup, Pydantic validation, and quality flags."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from budget_extractor.schemas import (
    ChunkExtractionResult,
    ChunkValidationIssue,
    ProjectPhase,
    ProjectRecord,
    PreRfpStatus,
    ValidationIssue,
    generate_record_id,
)


def strip_markdown_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def conservative_json_cleanup(text: str) -> str:
    """Apply conservative fixes for common model JSON issues."""
    cleaned = strip_markdown_fences(text)
    # Trim leading junk before first object/array.
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    starts = [idx for idx in (start_obj, start_arr) if idx >= 0]
    if starts:
        cleaned = cleaned[min(starts) :]
    # Trim trailing junk after last brace/bracket.
    end_obj = cleaned.rfind("}")
    end_arr = cleaned.rfind("]")
    end = max(end_obj, end_arr)
    if end >= 0:
        cleaned = cleaned[: end + 1]
    # Remove trailing commas before } or ].
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned.strip()


def parse_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = conservative_json_cleanup(text)
        return json.loads(cleaned)


def validate_chunk_payload(
    payload: Any,
    *,
    chunk_id: str,
    start_page: int,
    end_page: int,
    document_hash: str,
    total_pages: int,
) -> tuple[ChunkExtractionResult | None, list[str], list[ProjectRecord]]:
    """Validate chunk JSON.

    Returns (validated_result_or_none, error_messages, accepted_projects).
    Invalid individual projects are not silently discarded; they become issues.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, ["Root JSON value must be an object"], []

    projects_raw = payload.get("projects", [])
    if projects_raw is None:
        projects_raw = []
    if not isinstance(projects_raw, list):
        return None, ["projects must be an array"], []

    accepted: list[ProjectRecord] = []
    issues: list[ChunkValidationIssue] = []

    for raw_issue in payload.get("chunk_validation_issues") or []:
        try:
            issues.append(ChunkValidationIssue.model_validate(raw_issue))
        except ValidationError as exc:
            issues.append(
                ChunkValidationIssue(
                    severity="warning",
                    issue_type="invalid_chunk_issue",
                    description=f"Could not parse chunk_validation_issue: {exc}",
                )
            )

    for index, raw_project in enumerate(projects_raw):
        try:
            project = coerce_and_validate_project(
                raw_project,
                chunk_id=chunk_id,
                document_hash=document_hash,
                total_pages=total_pages,
                chunk_start=start_page,
                chunk_end=end_page,
            )
            accepted.append(project)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Project[{index}] invalid: {exc}")
            issues.append(
                ChunkValidationIssue(
                    severity="error",
                    issue_type="invalid_project_record",
                    description=str(exc),
                    project_name=_safe_name(raw_project),
                    pages=_safe_pages(raw_project),
                    recommended_review="Inspect raw model output for this project and correct manually if needed.",
                )
            )

    metadata = payload.get("chunk_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.setdefault("chunk_id", chunk_id)
    metadata.setdefault("start_page", start_page)
    metadata.setdefault("end_page", end_page)

    try:
        result = ChunkExtractionResult(
            chunk_metadata=metadata,
            projects=accepted,
            chunk_validation_issues=issues,
        )
    except ValidationError as exc:
        return None, [str(exc)] + errors, accepted

    # Treat as structurally valid even if some projects failed, as long as root shape is OK.
    return result, errors, accepted


def coerce_and_validate_project(
    raw: Any,
    *,
    chunk_id: str,
    document_hash: str,
    total_pages: int,
    chunk_start: int,
    chunk_end: int,
) -> ProjectRecord:
    if not isinstance(raw, dict):
        raise ValueError("project must be an object")

    data = _normalize_project_dict(raw, chunk_id=chunk_id, chunk_start=chunk_start, chunk_end=chunk_end)
    project = ProjectRecord.model_validate(data)

    # Evidence pages must fall within document range.
    for evidence in project.evidence:
        if evidence.page > total_pages:
            raise ValueError(
                f"evidence page {evidence.page} exceeds document page count {total_pages}"
            )

    for page in project.source_pages:
        if page > total_pages:
            raise ValueError(
                f"source page {page} exceeds document page count {total_pages}"
            )

    if not project.record_id:
        project.record_id = generate_record_id(
            document_hash=document_hash,
            project_id=project.project_id,
            project_name=project.project_name,
            location=project.project_location or project.address_or_site,
        )

    project.quality_flags = compute_quality_flags(project)
    return project


def _normalize_project_dict(
    raw: dict[str, Any],
    *,
    chunk_id: str,
    chunk_start: int,
    chunk_end: int,
) -> dict[str, Any]:
    """Normalize common GLM field aliases into the canonical schema."""
    from budget_extractor.utils import parse_currency

    data = dict(raw)

    alias_map = {
        "project_number": "project_id",
        "project_no": "project_id",
        "cip_number": "project_id",
        "department": "department_or_agency",
        "agency": "department_or_agency",
        "location": "project_location",
        "site": "address_or_site",
        "address": "address_or_site",
        "description": "project_description",
        "scope": "proposed_scope",
        "anticipated_completion_date": "estimated_completion_date",
        "completion_date": "estimated_completion_date",
        "start_date": "estimated_start_date",
        "total_project_cost": "total_project_budget",
        "actual_budget": "total_project_budget",
        "current_year_appropriation": "current_year_budget",
        "prior_expenditures": "prior_year_spending",
        "future_planned_funding": "future_year_funding",
        "remaining_balance": "remaining_budget",
        "requested_amount": "requested_funding",
        "approved_amount": "approved_funding",
        "total_budget_raw": "total_project_budget_raw",
        "budget_raw_text": "total_project_budget_raw",
    }
    for src, dst in alias_map.items():
        if data.get(dst) in (None, "", []) and data.get(src) not in (None, "", []):
            data[dst] = data[src]

    # Prefer actual_budget / total_project_cost style totals when multiple aliases exist.
    if data.get("total_project_budget") in (None, ""):
        for key in ("actual_budget", "total_project_cost", "total_appropriated"):
            if raw.get(key) not in (None, ""):
                data["total_project_budget"] = raw.get(key)
                break

    if data.get("unfunded_amount") in (None, "") and raw.get("needs_appropriated") not in (None, ""):
        data["unfunded_amount"] = raw.get("needs_appropriated")
    if data.get("requested_funding") in (None, "") and raw.get("needs_appropriated") not in (None, ""):
        data["requested_funding"] = raw.get("needs_appropriated")
    if data.get("approved_funding") in (None, "") and raw.get("total_appropriated") not in (None, ""):
        data["approved_funding"] = raw.get("total_appropriated")

    # Numeric coercion for budget-like fields that may arrive as strings.
    for field_name in (
        "total_project_budget",
        "current_year_budget",
        "prior_year_spending",
        "future_year_funding",
        "remaining_budget",
        "requested_funding",
        "approved_funding",
        "unfunded_amount",
        "bond_funding",
        "grant_funding",
        "local_funding",
        "state_funding",
        "federal_funding",
        "other_funding",
    ):
        if isinstance(data.get(field_name), str):
            parsed = parse_currency(data[field_name])
            if parsed is not None:
                if not data.get(f"{field_name}_raw"):
                    data[f"{field_name}_raw"] = data[field_name]
                data[field_name] = parsed

    if data.get("ward") and not data.get("project_location"):
        data["project_location"] = f"Ward {data['ward']}"
    elif data.get("ward") and data.get("project_location"):
        note = f"Ward: {data['ward']}"
        existing = data.get("extraction_notes") or ""
        data["extraction_notes"] = f"{existing}; {note}".strip("; ")

    data["current_phase"] = _coerce_phase(data.get("current_phase"))
    data["pre_rfp_status"] = _coerce_pre_rfp(data.get("pre_rfp_status"))
    data["first_seen_chunk"] = data.get("first_seen_chunk") or chunk_id
    seen = list(data.get("seen_in_chunks") or [])
    if data["first_seen_chunk"] not in seen:
        seen.append(data["first_seen_chunk"])
    data["seen_in_chunks"] = seen

    source_pages = _coerce_page_list(data.get("source_pages"))
    data["evidence"] = _coerce_evidence(data.get("evidence"), fallback_pages=source_pages or [chunk_start])
    data["funding_sources"] = _coerce_funding_sources(data.get("funding_sources"), fallback_pages=source_pages)
    data["annual_funding_schedule"] = _coerce_annual_funding(
        data.get("annual_funding_schedule"), fallback_pages=source_pages
    )
    data["responsible_contacts"] = _coerce_contacts(data.get("responsible_contacts"))
    data["budget_conflicts"] = _coerce_budget_conflicts(data.get("budget_conflicts"))

    if not source_pages:
        inferred = [int(item["page"]) for item in data["evidence"] if item.get("page")]
        source_pages = sorted(set(inferred)) if inferred else [chunk_start]
    data["source_pages"] = source_pages

    if data.get("confidence_score") is None:
        data["confidence_score"] = 0.5

    # Drop unknown helper aliases that are not part of the model.
    for key in list(data.keys()):
        if key in {
            "project_number",
            "department",
            "location",
            "description",
            "ward",
            "total_project_cost",
            "actual_budget",
            "total_appropriated",
            "needs_appropriated",
            "prior_year_ending_balance",
            "current_year_appropriation",
            "budget_raw_text",
            "anticipated_completion_date",
        }:
            # Keep only if already mapped; remove alias key to avoid extras confusion.
            # ProjectRecord uses extra="ignore", so this is optional cleanup.
            pass

    return data


def _coerce_page_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value] if value >= 1 else []
    if isinstance(value, str):
        parts = re.split(r"[,\s;]+", value.strip())
        pages: list[int] = []
        for part in parts:
            if not part:
                continue
            try:
                page = int(part)
            except ValueError:
                continue
            if page >= 1 and page not in pages:
                pages.append(page)
        return sorted(pages)
    if isinstance(value, list):
        pages = []
        for item in value:
            try:
                page = int(item)
            except (TypeError, ValueError):
                continue
            if page >= 1 and page not in pages:
                pages.append(page)
        return sorted(pages)
    return []


def _coerce_evidence(value: Any, *, fallback_pages: list[int]) -> list[dict[str, Any]]:
    if not value:
        return []
    page_fallback = fallback_pages[0] if fallback_pages else 1
    result: list[dict[str, Any]] = []
    if not isinstance(value, list):
        value = [value]
    for item in value:
        if isinstance(item, str):
            quote = item.strip()
            if quote:
                result.append({"page": page_fallback, "quote": quote, "evidence_type": "excerpt"})
            continue
        if isinstance(item, dict):
            quote = str(item.get("quote") or item.get("text") or item.get("excerpt") or "").strip()
            if not quote:
                continue
            page = item.get("page") or item.get("source_page") or page_fallback
            try:
                page_int = int(page)
            except (TypeError, ValueError):
                page_int = page_fallback
            result.append(
                {
                    "page": page_int,
                    "quote": quote,
                    "evidence_type": item.get("evidence_type") or item.get("type"),
                }
            )
    return result


def _coerce_funding_sources(value: Any, *, fallback_pages: list[int]) -> list[dict[str, Any]]:
    from budget_extractor.utils import parse_currency

    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
            if name:
                result.append(
                    {
                        "source_name": name,
                        "source_pages": list(fallback_pages),
                    }
                )
            continue
        if isinstance(item, dict):
            name = (
                item.get("source_name")
                or item.get("name")
                or item.get("funding_source")
                or item.get("source")
            )
            if not name:
                continue
            amount = item.get("amount")
            if isinstance(amount, str):
                amount = parse_currency(amount)
            result.append(
                {
                    "source_name": str(name),
                    "source_type": item.get("source_type") or item.get("type"),
                    "amount": amount,
                    "amount_raw": item.get("amount_raw") or item.get("raw_amount"),
                    "fiscal_year": item.get("fiscal_year") or item.get("year"),
                    "source_pages": _coerce_page_list(item.get("source_pages")) or list(fallback_pages),
                }
            )
    return result


def _coerce_annual_funding(value: Any, *, fallback_pages: list[int]) -> list[dict[str, Any]]:
    from budget_extractor.utils import parse_currency

    if not value:
        return []
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        if isinstance(amount, str):
            amount = parse_currency(amount)
        result.append(
            {
                "fiscal_year": item.get("fiscal_year") or item.get("year"),
                "amount": amount,
                "amount_raw": item.get("amount_raw") or item.get("raw_amount"),
                "funding_status": item.get("funding_status") or item.get("status"),
                "source_pages": _coerce_page_list(item.get("source_pages")) or list(fallback_pages),
            }
        )
    return result


def _coerce_contacts(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
            if name:
                result.append({"name": name})
            continue
        if isinstance(item, dict):
            result.append(
                {
                    "name": item.get("name"),
                    "title": item.get("title"),
                    "department": item.get("department"),
                    "email": item.get("email"),
                    "phone": item.get("phone"),
                    "source_pages": _coerce_page_list(item.get("source_pages")),
                }
            )
    return result


def _coerce_budget_conflicts(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field_name = item.get("field_name") or item.get("field") or "unknown"
        result.append(
            {
                "field_name": str(field_name),
                "values": list(item.get("values") or []),
                "source_pages": _coerce_page_list(item.get("source_pages")),
                "explanation": item.get("explanation") or item.get("reason"),
            }
        )
    return result


def compute_quality_flags(project: ProjectRecord) -> list[str]:
    flags: list[str] = []
    if not project.project_name.strip():
        flags.append("missing_project_name")
    if project.total_project_budget is None and project.current_year_budget is None:
        flags.append("missing_budget")
    if project.current_phase == ProjectPhase.UNKNOWN:
        flags.append("missing_phase")
    if not project.evidence:
        flags.append("missing_evidence")
    if project.confidence_score < 0.55:
        flags.append("low_confidence")
    if project.budget_conflicts:
        flags.append("conflicting_budgets")
    if project.incomplete_at_chunk_boundary:
        flags.append("incomplete_chunk_boundary")
    if project.total_project_budget is not None:
        if project.total_project_budget > 5_000_000_000:
            flags.append("suspiciously_large_budget")
        if 0 < project.total_project_budget < 100:
            flags.append("suspiciously_small_budget")
    return flags


def projects_to_validation_issues(
    chunk_id: str,
    issues: list[ChunkValidationIssue],
) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            severity=issue.severity,
            issue_type=issue.issue_type,
            record_id=issue.record_id,
            project_name=issue.project_name,
            chunk_id=chunk_id,
            pages=issue.pages,
            description=issue.description,
            recommended_review=issue.recommended_review,
        )
        for issue in issues
    ]


def _coerce_phase(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return ProjectPhase.UNKNOWN.value
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    for phase in ProjectPhase:
        if text == phase.value:
            return phase.value
    # Common aliases
    aliases = {
        "planning": ProjectPhase.EARLY_PLANNING.value,
        "design": ProjectPhase.PRELIMINARY_DESIGN.value,
        "construction_underway": ProjectPhase.CONSTRUCTION.value,
        "in_construction": ProjectPhase.CONSTRUCTION.value,
        "funded": ProjectPhase.FUNDING_APPROVED.value,
    }
    if text in aliases:
        return aliases[text]
    raise ValueError(f"invalid current_phase: {value!r}")


def _coerce_pre_rfp(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return PreRfpStatus.INSUFFICIENT_INFORMATION.value
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    for status in PreRfpStatus:
        if text == status.value:
            return status.value
    aliases = {
        "pre_rfp": PreRfpStatus.POSSIBLE_PRE_RFP.value,
        "rfp_issued": PreRfpStatus.PROCUREMENT_ACTIVE.value,
        "rfq_issued": PreRfpStatus.PROCUREMENT_ACTIVE.value,
    }
    if text in aliases:
        return aliases[text]
    raise ValueError(f"invalid pre_rfp_status: {value!r}")


def _safe_name(raw: Any) -> str | None:
    if isinstance(raw, dict):
        name = raw.get("project_name")
        return str(name) if name else None
    return None


def _safe_pages(raw: Any) -> list[int]:
    if not isinstance(raw, dict):
        return []
    pages = raw.get("source_pages") or []
    result: list[int] = []
    for page in pages:
        try:
            result.append(int(page))
        except (TypeError, ValueError):
            continue
    return result
