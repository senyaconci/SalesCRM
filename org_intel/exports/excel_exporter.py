"""Excel workbook exporter with formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from org_intel.utils.io import ensure_dir


HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True)
INFERRED_FILL = PatternFill("solid", fgColor="FFF2CC")
CONFIRMED_FILL = PatternFill("solid", fgColor="E2EFDA")


def export_excel_workbook(output_dir: Path, artifacts: dict[str, Any]) -> Path:
    ensure_dir(output_dir)
    wb = Workbook()
    # Remove default sheet after creating first
    default = wb.active
    wb.remove(default)

    identity = _as_dict(artifacts.get("organization_profile"))
    graph = _as_dict(artifacts.get("organization_relationships"))
    registry = _as_dict(artifacts.get("source_registry"))
    inventory = _as_dict(artifacts.get("document_inventory"))
    financial = _as_dict(artifacts.get("financial_capital_profile"))
    project_index = [_as_dict(x) for x in artifacts.get("project_index") or []]
    projects = [_as_dict(x) for x in artifacts.get("projects_full") or []]
    links = [_as_dict(x) for x in artifacts.get("project_source_map") or []]
    opportunities = [_as_dict(x) for x in artifacts.get("opportunities") or []]
    vendors = _as_dict(artifacts.get("incumbent_vendor_analysis"))
    contacts = _as_dict(artifacts.get("contacts"))
    validation = [_as_dict(x) for x in artifacts.get("validation_plan") or []]
    gaps = [_as_dict(x) for x in artifacts.get("research_gaps") or []]
    changes = [_as_dict(x) for x in artifacts.get("change_history") or []]
    costs = [_as_dict(x) for x in artifacts.get("cost_ledger") or []]
    solicitations = [_as_dict(x) for x in artifacts.get("solicitations") or []]
    manifest = _as_dict(artifacts.get("run_manifest"))

    _sheet(
        wb,
        "Executive Summary",
        [
            "Metric",
            "Value",
        ],
        [
            ["Organization", identity.get("canonical_name")],
            ["Type", identity.get("organization_type")],
            ["Domain", identity.get("official_domain")],
            ["Sources", len((registry or {}).get("sources") or [])],
            ["Documents", len((inventory or {}).get("documents") or [])],
            ["Project index", len(project_index)],
            ["Full projects", len(projects)],
            [
                "Strong pre-RFQ",
                sum(1 for o in opportunities if o.get("classification") == "strong_pre_rfq"),
            ],
            [
                "Possible pre-RFQ",
                sum(1 for o in opportunities if o.get("classification") == "possible_pre_rfq"),
            ],
            ["Research gaps", len(gaps)],
            ["Total cost USD", sum(float(c.get("actual_cost") or 0) for c in costs)],
        ],
    )

    _sheet(
        wb,
        "Organization",
        [
            "Field",
            "Value",
            "Confidence",
        ],
        [
            ["canonical_name", identity.get("canonical_name"), (identity.get("field_confidence") or {}).get("canonical_name")],
            ["organization_type", identity.get("organization_type"), (identity.get("field_confidence") or {}).get("organization_type")],
            ["state", identity.get("state"), (identity.get("field_confidence") or {}).get("state")],
            ["county", identity.get("county")],
            ["main_address", identity.get("main_address")],
            ["main_phone", identity.get("main_phone")],
            ["official_domain", identity.get("official_domain")],
            ["official_url", identity.get("official_url")],
            ["governance_model", identity.get("governance_model")],
            ["fiscal_year", identity.get("fiscal_year")],
            ["service_area", identity.get("service_area")],
            ["ambiguity_notes", "; ".join(identity.get("ambiguity_notes") or [])],
        ],
    )

    _sheet(
        wb,
        "Organization Map",
        ["node_id", "name", "entity_type", "function", "capital_responsibilities", "official_url", "confidence"],
        [
            [
                n.get("node_id"),
                n.get("name"),
                n.get("entity_type"),
                n.get("function"),
                ", ".join(n.get("capital_responsibilities") or []),
                n.get("official_url"),
                n.get("confidence"),
            ]
            for n in (graph or {}).get("nodes") or []
        ],
    )

    _sheet(
        wb,
        "Source Registry",
        [
            "source_id",
            "source_name",
            "source_role",
            "url",
            "official_status",
            "priority",
            "access_method",
            "confidence",
        ],
        [
            [
                s.get("source_id"),
                s.get("source_name"),
                s.get("source_role"),
                s.get("url"),
                s.get("official_status"),
                s.get("priority"),
                s.get("access_method"),
                s.get("confidence"),
            ]
            for s in (registry or {}).get("sources") or []
        ],
        hyperlink_cols={3},
    )

    _sheet(
        wb,
        "Document Inventory",
        [
            "document_id",
            "title",
            "document_type",
            "url",
            "fiscal_year",
            "status",
            "file_type",
            "project_relevance",
            "financial_relevance",
            "procurement_relevance",
            "confidence",
        ],
        [
            [
                d.get("document_id"),
                d.get("title"),
                d.get("document_type"),
                d.get("url"),
                d.get("fiscal_year"),
                d.get("status"),
                d.get("file_type"),
                d.get("likely_project_relevance"),
                d.get("likely_financial_relevance"),
                d.get("likely_procurement_relevance"),
                d.get("confidence"),
            ]
            for d in (inventory or {}).get("documents") or []
        ],
        hyperlink_cols={3},
    )

    _sheet(
        wb,
        "Financial Profile",
        ["metric", "value", "fiscal_year", "exactness", "provenance", "confidence", "source_url"],
        _financial_rows(financial),
        hyperlink_cols={6},
    )

    _sheet(
        wb,
        "Project Index",
        [
            "record_id",
            "project_id",
            "project_name",
            "department",
            "category",
            "published_stage",
            "construction_year",
            "total_project_cost",
            "record_type",
            "source_url",
            "confidence",
        ],
        [
            [
                p.get("record_id"),
                p.get("project_id"),
                p.get("project_name"),
                p.get("department"),
                p.get("category"),
                p.get("published_stage"),
                p.get("construction_year"),
                p.get("total_project_cost"),
                p.get("record_type"),
                p.get("source_url"),
                p.get("confidence"),
            ]
            for p in project_index
        ],
        currency_cols={7},
        hyperlink_cols={9},
    )

    _sheet(
        wb,
        "Full Projects",
        [
            "record_id",
            "project_id",
            "project_name",
            "record_type",
            "department",
            "normalized_phase",
            "phase_is_inferred",
            "total_project_cost",
            "current_year_appropriation",
            "procurement_status",
            "consultant_status",
            "pre_rfq_classification",
            "confidence_score",
            "quality_flags",
        ],
        [
            [
                p.get("record_id"),
                p.get("project_id"),
                p.get("project_name"),
                p.get("record_type"),
                p.get("department"),
                p.get("normalized_phase"),
                p.get("phase_is_inferred"),
                p.get("total_project_cost"),
                p.get("current_year_appropriation"),
                p.get("procurement_status"),
                p.get("consultant_status"),
                p.get("pre_rfq_classification"),
                p.get("confidence_score"),
                ", ".join(p.get("quality_flags") or []),
            ]
            for p in projects
        ],
        currency_cols={7, 8},
        inferred_flag_col=6,
    )

    _sheet(
        wb,
        "Project Source Map",
        [
            "project_id",
            "document_id",
            "match_method",
            "match_score",
            "matching_pages",
            "matched_terms",
            "likely_fields",
            "requires_llm_review",
        ],
        [
            [
                l.get("project_id"),
                l.get("document_id"),
                l.get("match_method"),
                l.get("match_score"),
                ",".join(str(x) for x in (l.get("matching_pages") or [])),
                ",".join(l.get("matched_terms") or []),
                ",".join(l.get("likely_fields") or []),
                l.get("requires_llm_review"),
            ]
            for l in links
        ],
    )

    annual_rows = []
    funding_rows = []
    for p in projects:
        for a in p.get("funding_schedule") or []:
            annual_rows.append(
                [
                    p.get("project_id") or p.get("record_id"),
                    p.get("project_name"),
                    a.get("fiscal_year"),
                    a.get("amount"),
                    a.get("fund"),
                    a.get("source_label"),
                ]
            )
        for f in p.get("funding_sources") or []:
            funding_rows.append(
                [
                    p.get("project_id") or p.get("record_id"),
                    p.get("project_name"),
                    f.get("name"),
                    f.get("amount"),
                    f.get("fund_type"),
                    f.get("status"),
                ]
            )

    _sheet(
        wb,
        "Annual Funding",
        ["project_id", "project_name", "fiscal_year", "amount", "fund", "source_label"],
        annual_rows,
        currency_cols={3},
    )
    _sheet(
        wb,
        "Funding Sources",
        ["project_id", "project_name", "name", "amount", "fund_type", "status"],
        funding_rows,
        currency_cols={3},
    )

    _sheet(
        wb,
        "Procurement",
        ["project_id", "project_name", "procurement_status", "consultant_status", "delivery_method", "solicitation_ids"],
        [
            [
                p.get("project_id"),
                p.get("project_name"),
                p.get("procurement_status"),
                p.get("consultant_status"),
                p.get("delivery_method"),
                ",".join(p.get("solicitation_ids") or []),
            ]
            for p in projects
        ],
    )

    _sheet(
        wb,
        "Solicitations and Awards",
        ["solicitation_id", "type", "number", "title", "status", "related_projects", "url", "confidence"],
        [
            [
                s.get("solicitation_id"),
                s.get("solicitation_type"),
                s.get("solicitation_number"),
                s.get("title"),
                s.get("status"),
                ",".join(s.get("related_project_ids") or []),
                s.get("url"),
                s.get("confidence"),
            ]
            for s in solicitations
        ],
        hyperlink_cols={6},
    )

    _sheet(
        wb,
        "Vendors and Incumbents",
        [
            "vendor_id",
            "canonical_name",
            "source_names",
            "disciplines",
            "award_count",
            "total_known_award_value",
            "most_recent_award",
            "relationship_strength",
            "on_call_status",
        ],
        [
            [
                v.get("vendor_id"),
                v.get("canonical_name"),
                "; ".join(v.get("source_names") or []),
                "; ".join(v.get("disciplines") or []),
                v.get("award_count"),
                v.get("total_known_award_value"),
                v.get("most_recent_award"),
                v.get("relationship_strength"),
                v.get("on_call_status"),
            ]
            for v in (vendors or {}).get("vendors") or []
        ],
        currency_cols={5},
    )

    _sheet(
        wb,
        "Contacts",
        [
            "contact_id",
            "name",
            "title",
            "department",
            "functional_role",
            "email",
            "email_status",
            "phone",
            "confidence",
        ],
        [
            [
                c.get("contact_id"),
                c.get("name"),
                c.get("title"),
                c.get("department"),
                c.get("functional_role"),
                c.get("email"),
                c.get("email_status"),
                c.get("phone"),
                c.get("confidence"),
            ]
            for c in (contacts or {}).get("contacts") or []
        ],
    )

    _sheet(
        wb,
        "Opportunities",
        [
            "opportunity_id",
            "project_id",
            "project_name",
            "classification",
            "likely_next_procurement",
            "likely_discipline",
            "pursuit_window",
            "known_incumbent",
            "confidence",
        ],
        [
            [
                o.get("opportunity_id"),
                o.get("project_id"),
                o.get("project_name"),
                o.get("classification"),
                o.get("likely_next_procurement"),
                o.get("likely_discipline"),
                o.get("pursuit_window"),
                o.get("known_incumbent"),
                o.get("confidence"),
            ]
            for o in opportunities
        ],
    )

    evidence_rows = []
    for p in projects:
        for e in p.get("evidence") or []:
            evidence_rows.append(
                [
                    p.get("project_id") or p.get("record_id"),
                    e.get("evidence_id"),
                    e.get("url"),
                    e.get("page"),
                    e.get("quote"),
                    ",".join(e.get("supports_fields") or []),
                    e.get("provenance"),
                    e.get("confidence"),
                ]
            )
    _sheet(
        wb,
        "Evidence",
        ["project_id", "evidence_id", "url", "page", "quote", "supports_fields", "provenance", "confidence"],
        evidence_rows,
        hyperlink_cols={2},
    )

    _sheet(
        wb,
        "Validation Plan",
        ["question_id", "question", "why_it_matters", "priority", "affected_project", "best_contact", "best_official_source"],
        [
            [
                v.get("question_id"),
                v.get("question"),
                v.get("why_it_matters"),
                v.get("priority"),
                v.get("affected_project"),
                v.get("best_contact"),
                v.get("best_official_source"),
            ]
            for v in validation
        ],
    )

    _sheet(
        wb,
        "Research Gaps",
        ["gap_id", "gap_type", "description", "priority", "affected_entity_type", "affected_entity_id", "status"],
        [
            [
                g.get("gap_id"),
                g.get("gap_type"),
                g.get("description"),
                g.get("priority"),
                g.get("affected_entity_type"),
                g.get("affected_entity_id"),
                g.get("status"),
            ]
            for g in gaps
        ],
    )

    quality_rows = []
    for p in projects:
        for flag in p.get("quality_flags") or []:
            quality_rows.append([p.get("project_id") or p.get("record_id"), p.get("project_name"), flag])
        for c in p.get("source_conflicts") or []:
            quality_rows.append(
                [p.get("project_id") or p.get("record_id"), p.get("project_name"), f"conflict:{c.get('field')}"]
            )
    _sheet(wb, "Quality Issues", ["project_id", "project_name", "issue"], quality_rows)

    _sheet(
        wb,
        "Change History",
        ["change_id", "project_id", "field", "old_value", "new_value", "detected_at"],
        [
            [
                c.get("change_id"),
                c.get("project_id"),
                c.get("field"),
                str(c.get("old_value")),
                str(c.get("new_value")),
                c.get("detected_at"),
            ]
            for c in changes
        ],
    )

    _sheet(
        wb,
        "Cost Ledger",
        [
            "task_id",
            "task_type",
            "model",
            "input_tokens",
            "output_tokens",
            "estimated_cost",
            "actual_cost",
            "cache_hit",
            "project_id",
        ],
        [
            [
                c.get("task_id"),
                c.get("task_type"),
                c.get("model"),
                c.get("input_tokens"),
                c.get("output_tokens"),
                c.get("estimated_cost"),
                c.get("actual_cost"),
                c.get("cache_hit"),
                c.get("project_id"),
            ]
            for c in costs
        ],
        currency_cols={5, 6},
    )

    _sheet(
        wb,
        "Run Log",
        ["key", "value"],
        [[k, str(v)] for k, v in (manifest or {}).items()],
    )

    path = output_dir / "capital_projects.xlsx"
    wb.save(path)
    return path


def _financial_rows(financial: dict[str, Any] | None) -> list[list[Any]]:
    if not financial:
        return []
    rows = []
    for key in (
        "total_annual_budget",
        "total_operating_expenditure",
        "total_capital_expenditure",
        "cip_value",
        "enterprise_fund_capital",
        "general_fund_position",
        "debt_capacity",
    ):
        metric = financial.get(key)
        if not metric:
            continue
        rows.append(
            [
                key,
                metric.get("value"),
                metric.get("fiscal_year"),
                metric.get("exactness"),
                metric.get("provenance"),
                metric.get("confidence"),
                metric.get("source_url"),
            ]
        )
    return rows


def _sheet(
    wb: Workbook,
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    *,
    currency_cols: set[int] | None = None,
    hyperlink_cols: set[int] | None = None,
    inferred_flag_col: int | None = None,
) -> None:
    ws = wb.create_sheet(title[:31])
    ws.append(headers)
    for col, _ in enumerate(headers, start=1):
        cell = ws.cell(1, col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(len(rows) + 1, 1)}"

    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(r_idx, c_idx, value)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if currency_cols and (c_idx - 1) in currency_cols and isinstance(value, (int, float)):
                cell.number_format = '"$"#,##0.00'
            if hyperlink_cols and (c_idx - 1) in hyperlink_cols and isinstance(value, str) and value.startswith("http"):
                cell.hyperlink = value
                cell.font = Font(color="0563C1", underline="single")
            if inferred_flag_col is not None and c_idx - 1 == inferred_flag_col:
                if value is True:
                    cell.fill = INFERRED_FILL
                elif value is False:
                    cell.fill = CONFIRMED_FILL

    # Confidence color scale if a confidence-like header exists
    for idx, header in enumerate(headers):
        if "confidence" in header.lower():
            col = get_column_letter(idx + 1)
            ws.conditional_formatting.add(
                f"{col}2:{col}{max(len(rows) + 1, 2)}",
                ColorScaleRule(
                    start_type="num",
                    start_value=0,
                    start_color="F8696B",
                    mid_type="num",
                    mid_value=0.5,
                    mid_color="FFEB84",
                    end_type="num",
                    end_value=1,
                    end_color="63BE7B",
                ),
            )

    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        max_len = len(str(headers[col - 1]))
        for row in rows[:50]:
            if col - 1 < len(row) and row[col - 1] is not None:
                max_len = max(max_len, min(60, len(str(row[col - 1]))))
        ws.column_dimensions[letter].width = max(12, min(48, max_len + 2))


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}
