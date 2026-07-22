"""OrganizationStrategy abstraction — guides discovery without restricting it."""

from __future__ import annotations

from dataclasses import dataclass, field

from org_intel.schemas.enums import OrganizationType


@dataclass
class OrganizationStrategy:
    organization_type: OrganizationType
    display_name: str
    department_terms: list[str] = field(default_factory=list)
    capital_source_terms: list[str] = field(default_factory=list)
    governance_terms: list[str] = field(default_factory=list)
    procurement_terms: list[str] = field(default_factory=list)
    master_plan_terms: list[str] = field(default_factory=list)
    financial_doc_terms: list[str] = field(default_factory=list)
    project_categories: list[str] = field(default_factory=list)
    path_hints: list[str] = field(default_factory=list)

    def all_discovery_terms(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for group in (
            self.capital_source_terms,
            self.financial_doc_terms,
            self.procurement_terms,
            self.master_plan_terms,
            self.governance_terms,
            self.department_terms,
        ):
            for term in group:
                key = term.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(term)
        return out


def get_strategy(org_type: OrganizationType | str) -> OrganizationStrategy:
    from org_intel.strategies.registry import STRATEGY_REGISTRY

    if isinstance(org_type, str):
        try:
            org_type = OrganizationType(org_type)
        except ValueError:
            org_type = OrganizationType.UNKNOWN
    return STRATEGY_REGISTRY.get(org_type, STRATEGY_REGISTRY[OrganizationType.OTHER_PUBLIC])
