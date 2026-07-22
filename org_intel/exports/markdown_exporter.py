"""Markdown organization intelligence report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from org_intel.utils.io import atomic_write_text, ensure_dir
from org_intel.utils.text import excerpt


def export_markdown_report(output_dir: Path, artifacts: dict[str, Any]) -> Path:
    ensure_dir(output_dir)
    identity = artifacts.get("organization_profile")
    graph = artifacts.get("organization_relationships")
    registry = artifacts.get("source_registry")
    inventory = artifacts.get("document_inventory")
    financial = artifacts.get("financial_capital_profile")
    projects = artifacts.get("projects_full") or []
    opportunities = artifacts.get("opportunities") or []
    vendors = artifacts.get("incumbent_vendor_analysis")
    contacts = artifacts.get("contacts")
    validation = artifacts.get("validation_plan") or []
    gaps = artifacts.get("research_gaps") or []
    solicitations = artifacts.get("solicitations") or []

    lines: list[str] = []
    name = _get(identity, "canonical_name", "Organization")
    lines.append(f"# Organization Capital Intelligence — {name}")
    lines.append("")
    lines.append(
        "_Confirmed facts are drawn from cited official sources. "
        "Inferences are labeled explicitly and must not be treated as confirmed._"
    )
    lines.append("")

    # 1
    lines.append("## 1. Canonical Organization Identity")
    if identity:
        lines.append(f"- **Canonical name:** {_get(identity, 'canonical_name')}")
        lines.append(f"- **Type:** {_get(identity, 'organization_type')}")
        lines.append(f"- **Official domain:** {_get(identity, 'official_domain')}")
        lines.append(f"- **State:** {_get(identity, 'state') or 'unknown'}")
        lines.append(f"- **Address:** {_get(identity, 'main_address') or 'unknown'}")
        lines.append(f"- **Phone:** {_get(identity, 'main_phone') or 'unknown'}")
        lines.append(f"- **Governance:** {_get(identity, 'governance_model') or 'unknown'}")
        for note in _get(identity, "ambiguity_notes", []) or []:
            lines.append(f"- Ambiguity note: {note}")
        for fe in (_get(identity, "field_evidence", []) or [])[:8]:
            lines.append(
                f"  - Evidence `{_get(fe, 'field')}`: \"{excerpt(_get(fe, 'quote'), 160)}\" "
                f"({_get(fe, 'source_url')}) [{_get(fe, 'provenance')}]"
            )
    lines.append("")

    # 2
    lines.append("## 2. Organization and Responsibility Map")
    if graph:
        for node in _get(graph, "nodes", []) or []:
            lines.append(
                f"- **{_get(node, 'name')}** ({_get(node, 'entity_type')}) — "
                f"{_get(node, 'function') or 'n/a'}; "
                f"capital: {', '.join(_get(node, 'capital_responsibilities', []) or []) or 'n/a'}"
            )
        summary = _get(graph, "capital_responsibility_summary", {}) or {}
        if summary:
            lines.append("")
            lines.append("Responsibility summary:")
            for resp, names in summary.items():
                lines.append(f"- {resp}: {', '.join(names)}")
    lines.append("")

    # 3
    lines.append("## 3. Official Source Registry")
    if registry:
        for src in _get(registry, "sources", []) or []:
            lines.append(
                f"- [{_get(src, 'source_name')}]({_get(src, 'url')}) — "
                f"{_get(src, 'source_role')}; priority={_get(src, 'priority')}; "
                f"status={_get(src, 'official_status')}"
            )
    lines.append("")

    # 4
    lines.append("## 4. Document Inventory")
    if inventory:
        for doc in (_get(inventory, "documents", []) or [])[:40]:
            lines.append(
                f"- [{_get(doc, 'title')}]({_get(doc, 'url')}) — {_get(doc, 'document_type')}; "
                f"project_rel={_get(doc, 'likely_project_relevance')}"
            )
    lines.append("")

    # 5
    lines.append("## 5. Financial and Capital Profile")
    if financial:
        lines.append(_metric_line("Total annual budget", _get(financial, "total_annual_budget")))
        lines.append(_metric_line("CIP value", _get(financial, "cip_value")))
        lines.append(
            f"- Capital planning period: {_get(financial, 'capital_planning_period') or 'unknown'}"
        )
        for note in _get(financial, "notes", []) or []:
            lines.append(f"- Note: {note}")
    lines.append("")

    # 6
    lines.append("## 6. Capital-Project Portfolio")
    lines.append(f"Projects in portfolio: {len(projects)}")
    for p in projects[:50]:
        phase = _get(p, "normalized_phase")
        inferred = _get(p, "phase_is_inferred")
        phase_label = f"{phase} _(inferred)_" if inferred else str(phase)
        lines.append(
            f"- **{_get(p, 'project_name')}** (`{_get(p, 'project_id') or 'n/a'}`) — "
            f"{_get(p, 'record_type')}; phase={phase_label}; "
            f"cost={_get(p, 'total_project_cost')}; class={_get(p, 'pre_rfq_classification')}"
        )
    lines.append("")

    # 7
    lines.append("## 7. Procurement Process")
    if registry:
        proc = [
            s
            for s in _get(registry, "sources", []) or []
            if "procur" in str(_get(s, "source_role")).lower()
            or "bid" in str(_get(s, "source_role")).lower()
        ]
        if proc:
            for s in proc:
                lines.append(f"- [{_get(s, 'source_name')}]({_get(s, 'url')})")
        else:
            lines.append("- No dedicated procurement portal confirmed in researched sources.")
    lines.append("")

    # 8
    lines.append("## 8. Historical Engineering Solicitations and Awards")
    if solicitations:
        for s in solicitations[:30]:
            lines.append(
                f"- {_get(s, 'solicitation_type')} {_get(s, 'solicitation_number') or ''} — "
                f"{_get(s, 'title')}"
            )
    else:
        lines.append("- No solicitations/awards extracted from researched sources yet.")
    lines.append("")

    # 9
    lines.append("## 9. Incumbent and Vendor Relationship Analysis")
    if vendors:
        for v in _get(vendors, "vendors", []) or []:
            lines.append(
                f"- **{_get(v, 'canonical_name')}** — awards={_get(v, 'award_count')}; "
                f"value={_get(v, 'total_known_award_value')}; "
                f"strength={_get(v, 'relationship_strength')} _(calculated/confirmed as labeled)_"
            )
        for d in _get(vendors, "discipline_coverage", []) or []:
            lines.append(f"- Discipline `{_get(d, 'discipline')}`: {_get(d, 'status')}")
        for n in _get(vendors, "concentration_notes", []) or []:
            lines.append(f"- {n}")
    lines.append("")

    # 10
    lines.append("## 10. Contact and Stakeholder Map")
    if contacts:
        for c in _get(contacts, "contacts", []) or []:
            email = _get(c, "email") or "not confirmed"
            status = _get(c, "email_status")
            lines.append(
                f"- **{_get(c, 'name')}** — {_get(c, 'title') or 'n/a'}; "
                f"email={email} [{status}]; role={_get(c, 'functional_role')}"
            )
        pattern = _get(contacts, "email_pattern")
        if pattern:
            lines.append(
                f"- Org email pattern _(not a confirmed individual email)_: {_get(pattern, 'pattern')}"
            )
    lines.append("")

    # 11
    lines.append("## 11. Pre-RFQ Opportunity Assessment")
    for o in opportunities:
        lines.append(
            f"- **{_get(o, 'project_name')}** — `{_get(o, 'classification')}`; "
            f"next={_get(o, 'likely_next_procurement')}; window={_get(o, 'pursuit_window')}"
        )
        for e in (_get(o, "evidence_for", []) or [])[:2]:
            lines.append(f"  - For: {excerpt(_get(e, 'quote'), 160)}")
        for e in (_get(o, "evidence_against", []) or [])[:2]:
            lines.append(f"  - Against: {excerpt(_get(e, 'quote'), 160)}")
    lines.append("")

    # 12
    lines.append("## 12. Validation Plan")
    for v in validation[:40]:
        lines.append(
            f"- ({_get(v, 'priority')}) {_get(v, 'question')} — project={_get(v, 'affected_project')}"
        )
    lines.append("")

    # 13
    lines.append("## 13. Research Gaps and Conflicts")
    for g in gaps:
        lines.append(f"- [{_get(g, 'priority')}] `{_get(g, 'gap_type')}` — {_get(g, 'description')}")
    lines.append("")

    # 14
    lines.append("## 14. Executive Account Summary")
    strong = [
        o
        for o in opportunities
        if str(_get(o, "classification")) in {"strong_pre_rfq", "PreRfqClassification.STRONG_PRE_RFQ"}
        or _enum_val(_get(o, "classification")) == "strong_pre_rfq"
    ]
    possible = [
        o
        for o in opportunities
        if _enum_val(_get(o, "classification")) == "possible_pre_rfq"
    ]
    lines.append(f"- Organization: {name}")
    lines.append(f"- Projects indexed: {len(artifacts.get('project_index') or [])}")
    lines.append(f"- Projects enriched: {len(projects)}")
    lines.append(f"- Strong pre-RFQ: {len(strong)}")
    lines.append(f"- Possible pre-RFQ: {len(possible)}")
    lines.append(f"- Open research gaps: {len(gaps)}")
    lines.append(
        "- This summary is evidence-scoped; absence of an incumbent/vendor means "
        "`no_incumbent_identified_in_researched_sources`, not that none exists."
    )
    lines.append("")

    path = output_dir / "organization_intelligence.md"
    atomic_write_text(path, "\n".join(lines))
    return path


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _enum_val(value: Any) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _metric_line(label: str, metric: Any) -> str:
    if not metric:
        return f"- {label}: unknown"
    value = _get(metric, "value")
    conf = _get(metric, "confidence")
    exact = _get(metric, "exactness")
    prov = _get(metric, "provenance")
    return f"- {label}: {value} (confidence={conf}, {exact}, {prov})"
