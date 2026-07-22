"""Central prompt templates."""

from __future__ import annotations

ORG_TYPE_CLASSIFY = """You classify public/quasi-public organizations.
Return JSON: {"organization_type": "<enum>", "confidence": 0-1, "rationale": "..."}
Allowed types: city, county, water_district, utility_authority, airport, port_authority,
transit_agency, school_district, university, hospital, state_agency, housing_authority,
park_district, transportation_authority, joint_powers_authority, other_public, unknown.
Use only evidence from the provided page text. Do not invent identity.
"""

SOURCE_CLASSIFY = """Classify an official source page for capital/procurement intelligence.
Return JSON with keys: source_role, content_roles (list), priority (anchor|high|medium|low),
expected_content (list), confidence, rationale.
"""

DOCUMENT_CLASSIFY = """Classify a document for capital project intelligence.
Return JSON: document_type, content_roles, likely_project_relevance (0-1),
likely_financial_relevance (0-1), likely_procurement_relevance (0-1),
status (draft|proposed|adopted|approved|active|superseded|archived|unknown),
fiscal_year, confidence.
"""

RECORD_TYPE_CLASSIFY = """Classify a capital inventory row.
Return JSON: record_type, lead_eligible (bool), lead_exclusion_reason, confidence.
Types: specific_capital_project, capital_program, budget_line_item, major_equipment_purchase,
study_or_plan, debt_financing_record, fund_or_transfer, maintenance_program,
completed_historical_project, unknown.
"""

PROJECT_EXTRACT = """Extract structured capital project fields from the evidence windows only.
Return JSON matching the project extraction schema. Use null when unavailable.
Never invent facts. Include evidence quotes for extracted fields where possible.
"""

PHASE_CLASSIFY = """Normalize project phase from evidence.
Return JSON: normalized_phase, phase_is_inferred (bool), phase_evidence, confidence.
Do not assume funded means design started, or CIP listing means pre-RFQ.
"""

OPPORTUNITY_ASSESS = """Assess pre-RFQ / pre-RFP opportunity using evidence only.
Return JSON: classification, likely_next_procurement, likely_discipline, pursuit_window,
evidence_for, evidence_against, unknowns, validation_questions, confidence, notes.
A project cannot be strong_pre_rfq if consultant selected, RFQ/RFP active, awarded,
under construction, completed/cancelled, or mere budget line without external scope.
"""

IDENTITY_EXTRACT = """Extract canonical organization identity from official page evidence.
Return JSON with canonical_name, common_names, organization_type, state, county,
main_address, main_phone, official_domain, service_area, governance_model,
population_or_customer_base, fiscal_year, ambiguity_notes, field_confidence.
Never infer legal identity solely from search-result snippets.
"""
