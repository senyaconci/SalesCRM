"""Synthesize an Account Intelligence Profile matching the product report format."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from org_intel.llm.base import ModelRole
from org_intel.llm.router import LLMRouter
from org_intel.utils.text import excerpt


PROFILE_SYSTEM = """You are a senior public-sector infrastructure research analyst.
Write an Account Intelligence Profile section using ONLY the provided evidence.
Rules:
- Distinguish confirmed fact from analyst inference.
- Never invent contacts, vendors, emails, or financial figures.
- If unknown, say "unknown" or "not confirmed in researched sources".
- Prefer concise professional prose and markdown tables.
- Do not dump raw navigation link lists.
- For organization map, include only real departments, divisions, utilities, boards.
- Return markdown for the requested section only, no preamble.
"""


def synthesize_account_profile(
    artifacts: dict[str, Any],
    router: LLMRouter | None = None,
) -> str:
    """Build a full Account Intelligence Profile markdown document."""
    identity = _sanitize_identity(_as_dict(artifacts.get("organization_profile")))
    graph = _as_dict(artifacts.get("organization_relationships"))
    registry = _as_dict(artifacts.get("source_registry"))
    inventory = _as_dict(artifacts.get("document_inventory"))
    financial = _as_dict(artifacts.get("financial_capital_profile"))
    projects = [_as_dict(p) for p in artifacts.get("projects_full") or []]
    opportunities = [_as_dict(o) for o in artifacts.get("opportunities") or []]
    contacts = _sanitize_contacts(_as_dict(artifacts.get("contacts")))
    vendors = _as_dict(artifacts.get("incumbent_vendor_analysis"))
    validation = [_as_dict(v) for v in artifacts.get("validation_plan") or []]
    gaps = [_as_dict(g) for g in artifacts.get("research_gaps") or []]
    solicitations = [_as_dict(s) for s in artifacts.get("solicitations") or []]

    name = identity.get("canonical_name") or "Organization"
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    strong = sum(1 for o in opportunities if o.get("classification") == "strong_pre_rfq")
    possible = sum(1 for o in opportunities if o.get("classification") == "possible_pre_rfq")

    sections: list[str] = [
        f"# Account Intelligence Profile: {name}",
        "",
        f"_Research date: {today}. Evidence-backed profile. Inferences are labeled._",
        "",
        f"**Account snapshot:** {len(projects)} indexed capital projects; "
        f"{strong} strong / {possible} possible pre-RFQ opportunities from researched official sources.",
        "",
    ]

    # Deterministic structured sections first; LLM polish for narrative-heavy parts.
    sections.append(_section_identity(identity, router))
    sections.append(_section_org_map(identity, graph, contacts, router))
    sections.append(_section_sources(registry))
    sections.append(_section_documents(inventory))
    sections.append(_section_financial(financial, projects, router))
    sections.append(_section_portfolio(projects))
    sections.append(_section_procurement(registry, solicitations))
    sections.append(_section_historical(solicitations, vendors))
    sections.append(_section_incumbents(vendors, router))
    sections.append(_section_contacts(contacts))
    sections.append(_section_opportunities(opportunities, projects))
    sections.append(_section_validation(validation))
    sections.append(_section_gaps(gaps))
    sections.append(_section_executive(identity, financial, projects, opportunities, vendors, router))

    return "\n".join(sections).strip() + "\n"


def _section_identity(identity: dict[str, Any], router: LLMRouter | None) -> str:
    rows = [
        ("Canonical legal name", identity.get("canonical_name"), _conf(identity, "canonical_name")),
        ("Government / organization type", identity.get("organization_type"), _conf(identity, "organization_type")),
        ("State", identity.get("state"), _conf(identity, "state")),
        ("County", identity.get("county"), _conf(identity, "county")),
        ("Official website", identity.get("official_url"), _conf(identity, "official_domain")),
        ("Official domain", identity.get("official_domain"), _conf(identity, "official_domain")),
        ("Main address", identity.get("main_address"), _conf(identity, "main_address")),
        ("Main telephone", identity.get("main_phone"), _conf(identity, "main_phone")),
        ("Population / customer base", identity.get("population_or_customer_base"), _conf(identity, "population_or_customer_base")),
        ("Service area", identity.get("service_area"), _conf(identity, "service_area")),
        ("Fiscal year", identity.get("fiscal_year"), _conf(identity, "fiscal_year")),
        ("Governance model", identity.get("governance_model"), _conf(identity, "governance_model")),
        ("Active/inactive status", identity.get("active_status") or "active", "High"),
        ("Aliases", ", ".join(identity.get("common_names") or identity.get("aliases") or []) or "n/a", "Medium"),
    ]
    lines = [
        "## SECTION 1 — Canonical Organization Identity",
        "",
        "| Field | Value | Confidence |",
        "|---|---|---|",
    ]
    for field, value, conf in rows:
        lines.append(f"| {field} | {_cell(value)} | {conf} |")
    notes = identity.get("ambiguity_notes") or []
    if notes:
        lines.append("")
        lines.append("**Ambiguity notes**")
        for note in notes:
            lines.append(f"- {note}")
    evidence = identity.get("field_evidence") or []
    if evidence:
        lines.append("")
        lines.append("**Selected evidence**")
        for fe in evidence[:8]:
            lines.append(
                f"- `{fe.get('field')}`: \"{excerpt(fe.get('quote'), 160)}\" "
                f"({fe.get('source_url')}) [{fe.get('provenance')}]"
            )

    if router is not None:
        polished = _llm_section(
            router,
            "SECTION 1 narrative supplement",
            "Add a short 1-paragraph identity narrative and fill only clearly supported "
            "missing fields as bullet clarifications. Do not invent FIPS/population/phone.",
            {"identity": identity},
        )
        if polished:
            lines.extend(["", polished])
    return "\n".join(lines) + "\n"


def _section_org_map(
    identity: dict[str, Any],
    graph: dict[str, Any],
    contacts: dict[str, Any],
    router: LLMRouter | None,
) -> str:
    nodes = _curate_org_nodes(graph.get("nodes") or [])
    lines = [
        "## SECTION 2 — Organization and Responsibility Map",
        "",
        f"{identity.get('canonical_name') or 'The organization'} capital delivery structure "
        "as evidenced from official pages:",
        "",
        "| Entity | Type | Function / capital role | Official URL | Confidence |",
        "|---|---|---|---|---|",
    ]
    for node in nodes[:40]:
        lines.append(
            f"| {_cell(node.get('name'))} | {_cell(node.get('entity_type'))} | "
            f"{_cell(node.get('function') or ', '.join(node.get('capital_responsibilities') or []) or 'n/a')} | "
            f"{_cell(node.get('official_url'))} | {_pct(node.get('confidence'))} |"
        )

    summary = graph.get("capital_responsibility_summary") or {}
    if summary:
        lines.append("")
        lines.append("**Capital responsibility summary**")
        for resp, names in list(summary.items())[:20]:
            curated = [n for n in names if _is_real_entity_name(n)]
            if curated:
                lines.append(f"- **{resp}:** {', '.join(curated[:8])}")

    contact_names = [
        f"{c.get('name')} ({c.get('title')})"
        for c in (contacts.get("contacts") or [])[:12]
        if c.get("name")
    ]
    if contact_names:
        lines.append("")
        lines.append("**Named leadership / stakeholders observed**")
        for item in contact_names:
            lines.append(f"- {item}")

    if router is not None:
        polished = _llm_section(
            router,
            "SECTION 2 narrative",
            "Write a concise responsibility-map narrative: governance body, executive, "
            "finance/procurement, public works/utilities/facilities, and how CIP projects "
            "are approved and procured. Use only provided entities/contacts. "
            "Omit navigation junk.",
            {"nodes": nodes[:30], "contacts": contacts.get("contacts") or []},
        )
        if polished:
            lines.extend(["", polished])
    return "\n".join(lines) + "\n"


def _section_sources(registry: dict[str, Any]) -> str:
    sources = sorted(
        registry.get("sources") or [],
        key=lambda s: (
            {"anchor": 0, "high": 1, "medium": 2, "low": 3}.get(str(s.get("priority")), 9),
            -(float(s.get("confidence") or 0)),
        ),
    )
    # Prefer real portals over noisy low-value pages.
    curated = []
    seen = set()
    for src in sources:
        url = (src.get("url") or "").rstrip("/")
        role = str(src.get("source_role") or "")
        name = src.get("source_name") or url
        if not url or url in seen:
            continue
        if role in {"other"} and float(src.get("confidence") or 0) < 0.6:
            if not any(k in url for k in ("cipweb", "budget", "bid", "legistar", "opengov", "demandstar")):
                continue
        if any(
            bad in (name or "").lower() or bad in url.lower()
            for bad in (
                "clear filters",
                "register-online",
                "bow hunter",
                "activity registration",
                "apply-and-register",
                "register-online-activities",
            )
        ):
            continue
        seen.add(url)
        curated.append(src)
        if len(curated) >= 25:
            break

    lines = [
        "## SECTION 3 — Official Source Registry",
        "",
        "| # | Source | URL | Role | Priority | Official status | Confidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, src in enumerate(curated, start=1):
        lines.append(
            f"| {i} | {_cell(src.get('source_name'))} | {_cell(src.get('url'))} | "
            f"{_cell(src.get('source_role'))} | {_cell(src.get('priority'))} | "
            f"{_cell(src.get('official_status'))} | {_pct(src.get('confidence'))} |"
        )
    if registry.get("field_authority_map"):
        lines.append("")
        lines.append("**Field authority preferences** (source IDs ordered strongest-first)")
        for field, ids in list((registry.get("field_authority_map") or {}).items())[:12]:
            if ids:
                lines.append(f"- `{field}`: {', '.join(ids[:5])}")
    return "\n".join(lines) + "\n"


def _section_documents(inventory: dict[str, Any]) -> str:
    docs = []
    for d in inventory.get("documents") or []:
        blob = f"{d.get('title') or ''} {d.get('url') or ''}".lower()
        if any(
            bad in blob
            for bad in (
                "register-online",
                "activity registration",
                "apply-and-register",
                "facility rental availability",
            )
        ):
            continue
        docs.append(d)
    docs = sorted(
        docs,
        key=lambda d: -(
            float(d.get("likely_project_relevance") or 0) * 0.5
            + float(d.get("likely_financial_relevance") or 0) * 0.3
            + float(d.get("likely_procurement_relevance") or 0) * 0.2
        ),
    )[:30]
    lines = [
        "## SECTION 4 — Document Inventory",
        "",
        "| Document | Type | FY / period | Status | Project rel. | Financial rel. | URL |",
        "|---|---|---|---|---|---|---|",
    ]
    for doc in docs:
        lines.append(
            f"| {_cell(doc.get('title'))} | {_cell(doc.get('document_type'))} | "
            f"{_cell(doc.get('fiscal_year') or doc.get('planning_period'))} | "
            f"{_cell(doc.get('status'))} | {float(doc.get('likely_project_relevance') or 0):.2f} | "
            f"{float(doc.get('likely_financial_relevance') or 0):.2f} | {_cell(doc.get('url'))} |"
        )
    return "\n".join(lines) + "\n"


def _section_financial(
    financial: dict[str, Any],
    projects: list[dict[str, Any]],
    router: LLMRouter | None,
) -> str:
    lines = [
        "## SECTION 5 — Financial and Capital Profile",
        "",
        "| Metric | Value | Period | Exactness | Provenance | Confidence | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, label in (
        ("total_annual_budget", "Total annual budget"),
        ("total_operating_expenditure", "Total operating expenditure"),
        ("total_capital_expenditure", "Total capital expenditure"),
        ("cip_value", "CIP / capital program value"),
        ("enterprise_fund_capital", "Enterprise-fund capital"),
        ("general_fund_position", "General-fund position"),
        ("debt_capacity", "Debt capacity"),
    ):
        metric = financial.get(key)
        if not metric:
            lines.append(f"| {label} | unknown |  |  |  |  |  |")
            continue
        lines.append(
            f"| {label} | {_money(metric.get('value'))} | {_cell(metric.get('fiscal_year') or metric.get('period'))} | "
            f"{_cell(metric.get('exactness'))} | {_cell(metric.get('provenance'))} | "
            f"{_pct(metric.get('confidence'))} | {_cell(metric.get('source_url'))} |"
        )
    lines.append("")
    lines.append(f"- Capital planning period: {_cell(financial.get('capital_planning_period'))}")
    lines.append(f"- CIP update cycle: {_cell(financial.get('cip_update_cycle'))}")
    lines.append(
        f"- Portfolio project cost sum (calculated from indexed projects, not an official total): "
        f"{_money(sum(p.get('total_project_cost') or 0 for p in projects))}"
    )
    for note in financial.get("notes") or []:
        lines.append(f"- Note: {note}")
    lines.append(
        "- Do not combine annual appropriation totals with multi-year CIP project-cost totals."
    )
    if router is not None:
        polished = _llm_section(
            router,
            "SECTION 5 narrative",
            "Write a short financial/capital narrative from the metrics only. "
            "If metrics are sparse, say what is missing and which official source should fill it.",
            {"financial": financial, "project_count": len(projects)},
        )
        if polished:
            lines.extend(["", polished])
    return "\n".join(lines) + "\n"


def _section_portfolio(projects: list[dict[str, Any]]) -> str:
    active = [
        p
        for p in projects
        if str(p.get("normalized_phase")) not in {"cancelled", "completed"}
        and not str(p.get("published_status") or "").lower().startswith("cancel")
    ]
    phase_counts = Counter(str(p.get("normalized_phase")) for p in projects)
    lines = [
        "## SECTION 6 — Capital-Project Portfolio",
        "",
        f"Indexed projects: **{len(projects)}** (active/planned non-cancelled in view: **{len(active)}**).",
        "",
        "**Phase distribution**",
    ]
    for phase, count in phase_counts.most_common():
        lines.append(f"- `{phase}`: {count}")
    lines.extend(
        [
            "",
            "| Project ID | Project | Department | Phase | Status | Const. year | Cost | Pre-RFQ class |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    ranked = sorted(
        active,
        key=lambda p: (-(p.get("total_project_cost") or 0), p.get("project_name") or ""),
    )[:60]
    for p in ranked:
        lines.append(
            f"| {_cell(p.get('project_id'))} | {_cell(p.get('project_name'))} | {_cell(p.get('department'))} | "
            f"{_cell(p.get('normalized_phase'))} | {_cell(p.get('published_status'))} | "
            f"{_cell(p.get('construction_year'))} | {_money(p.get('total_project_cost'))} | "
            f"{_cell(p.get('pre_rfq_classification'))} |"
        )
    return "\n".join(lines) + "\n"


def _section_procurement(registry: dict[str, Any], solicitations: list[dict[str, Any]]) -> str:
    proc = [
        s
        for s in registry.get("sources") or []
        if any(
            k in str(s.get("source_role") or "").lower() or k in (s.get("url") or "").lower()
            for k in ("procur", "bid", "demandstar", "missouribuys", "purchasing", "bonfire", "planetbids")
        )
    ]
    lines = [
        "## SECTION 7 — Procurement Process",
        "",
        "Official procurement-related sources identified:",
        "",
    ]
    if proc:
        for s in proc[:15]:
            lines.append(
                f"- [{s.get('source_name')}]({s.get('url')}) — `{s.get('source_role')}` "
                f"({s.get('official_status')})"
            )
    else:
        lines.append("- No dedicated procurement portal confirmed in researched sources.")
    lines.append("")
    lines.append(f"Solicitations extracted from researched documents: **{len(solicitations)}**")
    for s in solicitations[:20]:
        lines.append(
            f"- {_cell(s.get('solicitation_type'))} {_cell(s.get('solicitation_number'))} — "
            f"{_cell(s.get('title'))}"
        )
    return "\n".join(lines) + "\n"


def _section_historical(solicitations: list[dict[str, Any]], vendors: dict[str, Any]) -> str:
    lines = [
        "## SECTION 8 — Historical Engineering Solicitations and Awards",
        "",
    ]
    if solicitations:
        lines.append("| Solicitation | Type | Related projects | URL | Confidence |")
        lines.append("|---|---|---|---|---|")
        for s in solicitations[:30]:
            lines.append(
                f"| {_cell(s.get('title'))} | {_cell(s.get('solicitation_type'))} | "
                f"{_cell(', '.join(s.get('related_project_ids') or []))} | {_cell(s.get('url'))} | "
                f"{_pct(s.get('confidence'))} |"
            )
    else:
        lines.append(
            "- No historical solicitations/awards were extracted from the researched official pages "
            "in this run. Council packets, DemandStar, and award notices remain priority sources."
        )
    vendor_count = len(vendors.get("vendors") or [])
    lines.append("")
    lines.append(
        f"Vendor records currently linked from researched awards/agreements: **{vendor_count}**."
    )
    return "\n".join(lines) + "\n"


def _section_incumbents(vendors: dict[str, Any], router: LLMRouter | None) -> str:
    lines = [
        "## SECTION 9 — Incumbent and Vendor Relationship Analysis",
        "",
        "| Vendor | Awards (researched) | Known award value | Disciplines | Relationship strength |",
        "|---|---|---|---|---|",
    ]
    for v in vendors.get("vendors") or []:
        lines.append(
            f"| {_cell(v.get('canonical_name'))} | {v.get('award_count')} | "
            f"{_money(v.get('total_known_award_value'))} | "
            f"{_cell(', '.join(v.get('disciplines') or []))} | {_cell(v.get('relationship_strength'))} |"
        )
    if not vendors.get("vendors"):
        lines.append("| _none identified in researched sources_ |  |  |  |  |")
    lines.append("")
    lines.append("**Discipline coverage**")
    for d in vendors.get("discipline_coverage") or []:
        lines.append(
            f"- `{d.get('discipline')}`: **{d.get('status')}**"
            + (f" — {', '.join(d.get('vendors') or [])}" if d.get("vendors") else "")
        )
    for note in vendors.get("concentration_notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    lines.append(
        "_Absence of a firm means `no_incumbent_identified_in_researched_sources`, "
        "not that no incumbent exists._"
    )
    if router is not None and (vendors.get("vendors") or vendors.get("discipline_coverage")):
        polished = _llm_section(
            router,
            "SECTION 9 narrative",
            "Summarize incumbent concentration and open disciplines cautiously from the table only.",
            vendors,
        )
        if polished:
            lines.extend(["", polished])
    return "\n".join(lines) + "\n"


def _section_contacts(contacts: dict[str, Any]) -> str:
    lines = [
        "## SECTION 10 — Contact and Stakeholder Map",
        "",
        "| Name | Title | Department | Functional role | Email | Email status | Phone | Confidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in contacts.get("contacts") or []:
        lines.append(
            f"| {_cell(c.get('name'))} | {_cell(c.get('title'))} | {_cell(c.get('department'))} | "
            f"{_cell(c.get('functional_role'))} | {_cell(c.get('email') or 'not confirmed')} | "
            f"{_cell(c.get('email_status'))} | {_cell(c.get('phone'))} | {_pct(c.get('confidence'))} |"
        )
    if not contacts.get("contacts"):
        lines.append("| _none confirmed_ |  |  |  |  |  |  |  |")
    pattern = contacts.get("email_pattern")
    if pattern:
        lines.append("")
        lines.append(
            f"- Organization email pattern _(not a confirmed individual email)_: "
            f"`{pattern.get('pattern')}`"
        )
    return "\n".join(lines) + "\n"


def _section_opportunities(
    opportunities: list[dict[str, Any]],
    projects: list[dict[str, Any]],
) -> str:
    projects_by_record = {p.get("record_id"): p for p in projects}
    keep = [
        o
        for o in opportunities
        if o.get("classification")
        in {"strong_pre_rfq", "possible_pre_rfq", "monitor"}
    ]
    keep = sorted(
        keep,
        key=lambda o: (
            {"strong_pre_rfq": 0, "possible_pre_rfq": 1, "monitor": 2}.get(o.get("classification"), 9),
            -(projects_by_record.get(o.get("project_record_id"), {}).get("total_project_cost") or 0),
        ),
    )
    lines = [
        "## SECTION 11 — Pre-RFQ Opportunity Assessment",
        "",
        "Filtered to opportunities that are not cancelled, completed, under construction, "
        "or already in active procurement / consultant-selected status (based on researched evidence).",
        "",
        "| # | Project | Discipline | Stage | Likely next step | Pursuit window | Classification | Confidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(keep[:40], start=1):
        p = projects_by_record.get(o.get("project_record_id"), {})
        lines.append(
            f"| {i} | {_cell(o.get('project_id'))} {_cell(o.get('project_name'))} | "
            f"{_cell(o.get('likely_discipline'))} | {_cell(p.get('normalized_phase') or p.get('published_status'))} | "
            f"{_cell(o.get('likely_next_procurement'))} | {_cell(o.get('pursuit_window'))} | "
            f"{_cell(o.get('classification'))} | {_pct(o.get('confidence'))} |"
        )
    if not keep:
        lines.append("|  | _none classified as strong/possible/monitor_ |  |  |  |  |  |  |")
    # Add evidence notes for top opportunities
    if keep:
        lines.append("")
        lines.append("**Evidence notes (top opportunities)**")
        for o in keep[:10]:
            lines.append(f"- **{o.get('project_name')}**")
            for e in (o.get("evidence_for") or [])[:2]:
                lines.append(f"  - For: {excerpt(e.get('quote'), 180)}")
            for e in (o.get("evidence_against") or [])[:2]:
                lines.append(f"  - Against: {excerpt(e.get('quote'), 180)}")
            for q in (o.get("validation_questions") or [])[:2]:
                lines.append(f"  - Validate: {q}")
    return "\n".join(lines) + "\n"


def _section_validation(validation: list[dict[str, Any]]) -> str:
    lines = [
        "## SECTION 12 — Validation Plan",
        "",
        "| Priority | Question | Why it matters | Best contact | Best official source | Affected project |",
        "|---|---|---|---|---|---|",
    ]
    for v in validation[:40]:
        lines.append(
            f"| {_cell(v.get('priority'))} | {_cell(v.get('question'))} | {_cell(v.get('why_it_matters'))} | "
            f"{_cell(v.get('best_contact'))} | {_cell(v.get('best_official_source'))} | "
            f"{_cell(v.get('affected_project'))} |"
        )
    if not validation:
        lines.append("|  | _No validation questions generated_ |  |  |  |  |")
    return "\n".join(lines) + "\n"


def _section_gaps(gaps: list[dict[str, Any]]) -> str:
    lines = [
        "## SECTION 13 — Research Gaps and Conflicts",
        "",
        "| Priority | Gap type | Description | Affected entity | Suggested source |",
        "|---|---|---|---|---|",
    ]
    for g in gaps[:50]:
        lines.append(
            f"| {_cell(g.get('priority'))} | `{_cell(g.get('gap_type'))}` | {_cell(g.get('description'))} | "
            f"{_cell(g.get('affected_entity_id') or g.get('affected_entity_type'))} | "
            f"{_cell(g.get('suggested_source'))} |"
        )
    if not gaps:
        lines.append("|  |  | _No open gaps recorded_ |  |  |")
    return "\n".join(lines) + "\n"


def _section_executive(
    identity: dict[str, Any],
    financial: dict[str, Any],
    projects: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    vendors: dict[str, Any],
    router: LLMRouter | None,
) -> str:
    strong = sum(1 for o in opportunities if o.get("classification") == "strong_pre_rfq")
    possible = sum(1 for o in opportunities if o.get("classification") == "possible_pre_rfq")
    active = [
        p
        for p in projects
        if str(p.get("normalized_phase")) not in {"cancelled", "completed"}
    ]
    lines = [
        "## SECTION 14 — Executive Account Summary",
        "",
        f"1. **Organization overview.** {_cell(identity.get('canonical_name'))} "
        f"({_cell(identity.get('organization_type'))}) — domain `{_cell(identity.get('official_domain'))}`, "
        f"state {_cell(identity.get('state'))}, governance {_cell(identity.get('governance_model') or 'unknown')}.",
        f"2. **Visible capital pipeline.** Indexed projects: {len(projects)} "
        f"({len(active)} non-cancelled/non-completed in current extract). "
        f"CIP/capital metric: {_money((financial.get('cip_value') or {}).get('value'))}; "
        f"annual budget metric: {_money((financial.get('total_annual_budget') or {}).get('value'))}.",
        f"3. **Pre-RFQ opportunity count.** Strong: {strong}; Possible: {possible}.",
        f"4. **Incumbent coverage.** Vendors identified in researched sources: "
        f"{len(vendors.get('vendors') or [])}.",
        "5. **Research posture.** This profile is limited to official researched sources in this run; "
        "gaps remain where budgets/ACFRs/award packets were not fully extracted.",
    ]
    if router is not None:
        polished = _llm_section(
            router,
            "SECTION 14 narrative",
            "Write an executive account summary with up to 6 short numbered points covering: "
            "municipality overview, capital pipeline, priorities by infrastructure domain, "
            "credible pre-RFQ count, incumbent posture, and next validation actions. "
            "Use only provided facts; label inference.",
            {
                "identity": {
                    k: identity.get(k)
                    for k in (
                        "canonical_name",
                        "organization_type",
                        "state",
                        "county",
                        "governance_model",
                        "population_or_customer_base",
                        "service_area",
                        "official_url",
                    )
                },
                "financial": financial,
                "project_count": len(projects),
                "active_count": len(active),
                "strong": strong,
                "possible": possible,
                "top_opportunities": [
                    {
                        "name": o.get("project_name"),
                        "class": o.get("classification"),
                        "next": o.get("likely_next_procurement"),
                        "discipline": o.get("likely_discipline"),
                    }
                    for o in opportunities
                    if o.get("classification") in {"strong_pre_rfq", "possible_pre_rfq"}
                ][:15],
                "vendors": [v.get("canonical_name") for v in (vendors.get("vendors") or [])][:10],
            },
        )
        if polished:
            lines.extend(["", polished])
    return "\n".join(lines) + "\n"


def _llm_section(
    router: LLMRouter,
    title: str,
    instruction: str,
    payload: Any,
) -> str | None:
    try:
        response = router.complete(
            ModelRole.REASONING_MODEL,
            PROFILE_SYSTEM,
            f"{instruction}\n\nSection: {title}\n\nEvidence JSON:\n"
            f"{json.dumps(payload, default=str)[:14000]}",
            task_type="account_profile_section",
            require_json=False,
            max_tokens=1800,
        )
        text = (response.content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("markdown"):
                text = text[len("markdown") :].lstrip()
        return text or None
    except Exception:
        return None


def _curate_org_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    curated = [n for n in nodes if _is_real_entity_name(n.get("name") or "")]
    # Prefer higher confidence / capital-relevant
    curated.sort(
        key=lambda n: (
            0 if n.get("capital_responsibilities") else 1,
            -float(n.get("confidence") or 0),
            n.get("name") or "",
        )
    )
    return curated


def _is_real_entity_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n or len(n) < 3 or len(n) > 80:
        return False
    banned = (
        "opens in a new window",
        "faq",
        "news",
        "browse",
        "report an issue",
        "register",
        "pay ",
        "arrest",
        "shooting",
        "holiday",
        "newsletter",
        "featured",
        "click",
        "application for",
        "form",
        "rebates",
        "let's talk",
        "responds to",
        "invited to",
    )
    if any(b in n for b in banned):
        return False
    # Keep likely org units
    keep_words = (
        "council",
        "manager",
        "finance",
        "public works",
        "utilities",
        "water",
        "electric",
        "sewer",
        "storm",
        "airport",
        "transit",
        "parks",
        "police",
        "fire",
        "procurement",
        "purchasing",
        "engineering",
        "planning",
        "community development",
        "board",
        "authority",
        "department",
        "division",
        "clerk",
        "budget",
        "cip",
        "solid waste",
        "parking",
        "railroad",
    )
    return any(w in n for w in keep_words)


def _sanitize_identity(identity: dict[str, Any]) -> dict[str, Any]:
    address = str(identity.get("main_address") or "")
    lower = address.lower()
    if address and any(
        bad in lower
        for bad in ("newsletter", "featured", "project city", "click", "menu", "july 20")
    ):
        identity["main_address"] = None
        conf = identity.setdefault("field_confidence", {})
        conf["main_address"] = 0.0
    # Normalize enum-ish org type for report readability.
    org_type = identity.get("organization_type")
    if isinstance(org_type, str) and org_type.startswith("OrganizationType."):
        identity["organization_type"] = org_type.split(".", 1)[-1].lower()
    elif isinstance(org_type, str) and "." in org_type and org_type.isupper():
        identity["organization_type"] = org_type.split(".")[-1].lower()
    return identity


def _sanitize_contacts(contacts: dict[str, Any]) -> dict[str, Any]:
    kept = []
    for c in contacts.get("contacts") or []:
        name = str(c.get("name") or "")
        parts = [p for p in name.split() if p]
        if len(parts) < 2 or len(parts) > 4:
            continue
        if any(
            p.lower()
            in {
                "city",
                "clerk",
                "department",
                "departments",
                "accreditation",
                "manager",
                "menu",
                "june",
                "airport",
                "history",
                "all",
                "press",
                "releases",
            }
            for p in parts
        ):
            continue
        kept.append(c)
    contacts["contacts"] = kept
    return contacts


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    text = str(value).replace("|", "/").replace("\n", " ").strip()
    return text[:180] if text else "unknown"


def _pct(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if v >= 0.85:
        return "High"
    if v >= 0.6:
        return "Medium"
    if v > 0:
        return "Low"
    return "unknown"


def _conf(identity: dict[str, Any], field: str) -> str:
    return _pct((identity.get("field_confidence") or {}).get(field))


def _money(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)
