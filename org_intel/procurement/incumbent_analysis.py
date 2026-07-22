"""Organization-level incumbent and vendor relationship analysis."""

from __future__ import annotations

from collections import defaultdict

from org_intel.schemas.enums import FieldProvenance
from org_intel.schemas.procurement import (
    DisciplineCoverage,
    IncumbentVendorAnalysis,
    ProcurementEvent,
    VendorRecord,
)
from org_intel.schemas.project import ProjectRecord
from org_intel.utils.names import company_similarity, normalize_company_name


def build_incumbent_analysis(
    organization_id: str,
    projects: list[ProjectRecord],
    events: list[ProcurementEvent],
) -> IncumbentVendorAnalysis:
    buckets: dict[str, VendorRecord] = {}

    def upsert(name: str, **kwargs) -> VendorRecord:
        key = normalize_company_name(name)
        if not key:
            key = name.lower()
        # link to existing by similarity
        for existing_key, vendor in buckets.items():
            if company_similarity(name, vendor.canonical_name) >= 92:
                key = existing_key
                break
        vendor = buckets.get(key)
        if not vendor:
            vendor = VendorRecord(canonical_name=name, source_names=[name])
            buckets[key] = vendor
        if name not in vendor.source_names:
            vendor.source_names.append(name)
        discipline = kwargs.get("discipline")
        if discipline and discipline not in vendor.disciplines:
            vendor.disciplines.append(discipline)
        dept = kwargs.get("department")
        if dept and dept not in vendor.departments_served:
            vendor.departments_served.append(dept)
        amount = kwargs.get("amount")
        if amount:
            vendor.total_known_award_value = (vendor.total_known_award_value or 0) + amount
            vendor.award_count += 1
        date = kwargs.get("date")
        if date and (not vendor.most_recent_award or date > vendor.most_recent_award):
            vendor.most_recent_award = date
        if kwargs.get("on_call"):
            vendor.on_call_status = "possible_on_call"
        vendor.relationship_strength = "confirmed" if kwargs.get("confirmed") else "calculated"
        vendor.provenance_notes.append(
            "Metrics are calculated from researched awards; absence of a firm does not prove no incumbent exists."
        )
        return vendor

    for project in projects:
        for firm in project.consultants + project.contractors:
            upsert(
                firm.company_name,
                discipline=firm.discipline or project.category,
                department=project.department,
                amount=firm.contract_amount,
                date=firm.award_date,
                on_call=firm.on_call,
                confirmed=True,
            )
    for event in events:
        if event.firm_name:
            upsert(
                event.firm_name,
                amount=event.amount,
                date=event.date,
                confirmed=True,
            )

    # Discipline coverage — never claim "no incumbent exists"
    discipline_map: dict[str, list[str]] = defaultdict(list)
    for vendor in buckets.values():
        for d in vendor.disciplines or ["unspecified"]:
            discipline_map[d].append(vendor.canonical_name)

    common_disciplines = [
        "civil_engineering",
        "water_engineering",
        "wastewater_engineering",
        "architecture",
        "construction_management",
        "environmental",
    ]
    coverage: list[DisciplineCoverage] = []
    for disc in common_disciplines:
        vendors = []
        for key, names in discipline_map.items():
            if disc.split("_")[0] in key.lower() or key.lower() in disc:
                vendors.extend(names)
        if vendors:
            coverage.append(
                DisciplineCoverage(
                    discipline=disc,
                    status="incumbent_identified",
                    vendors=list(dict.fromkeys(vendors)),
                    provenance=FieldProvenance.STATED,
                )
            )
        else:
            coverage.append(
                DisciplineCoverage(
                    discipline=disc,
                    status="no_incumbent_identified_in_researched_sources",
                    vendors=[],
                    provenance=FieldProvenance.INFERRED,
                )
            )

    notes = []
    ranked = sorted(
        buckets.values(),
        key=lambda v: (v.award_count, v.total_known_award_value or 0),
        reverse=True,
    )
    if ranked:
        top = ranked[0]
        notes.append(
            f"Highest observed award concentration: {top.canonical_name} "
            f"({top.award_count} awards in researched sources)."
        )

    return IncumbentVendorAnalysis(
        organization_id=organization_id,
        vendors=list(buckets.values()),
        discipline_coverage=coverage,
        concentration_notes=notes,
    )
