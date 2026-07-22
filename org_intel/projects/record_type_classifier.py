"""Classify shallow inventory rows into record types."""

from __future__ import annotations

import re

from org_intel.schemas.enums import RecordType
from org_intel.utils.names import is_generic_project_name

_PATTERNS: list[tuple[re.Pattern[str], RecordType]] = [
    (re.compile(r"\b(debt|bond issuance|refunding|certificate of participation)\b", re.I), RecordType.DEBT_FINANCING_RECORD),
    (re.compile(r"\b(transfer|fund balance|contingency|reserve)\b", re.I), RecordType.FUND_OR_TRANSFER),
    (re.compile(r"\b(annual|ongoing|preventive)\b.*\b(maintenance|repair)\b|\bmaintenance program\b", re.I), RecordType.MAINTENANCE_PROGRAM),
    (re.compile(r"\b(study|plan|assessment|analysis|feasibility)\b", re.I), RecordType.STUDY_OR_PLAN),
    (re.compile(r"\b(vehicle|truck|equipment|fleet)\b", re.I), RecordType.MAJOR_EQUIPMENT_PURCHASE),
    (re.compile(r"\b(program|citywide|systemwide)\b", re.I), RecordType.CAPITAL_PROGRAM),
    (re.compile(r"\b(completed|closeout|closed)\b", re.I), RecordType.COMPLETED_HISTORICAL_PROJECT),
]


def classify_record_type(
    name: str,
    category: str | None = None,
    stage: str | None = None,
    description: str | None = None,
) -> tuple[RecordType, bool, str | None]:
    blob = " ".join(x for x in [name, category or "", stage or "", description or ""] if x)
    for pattern, rtype in _PATTERNS:
        if pattern.search(blob):
            eligible, reason = _eligibility(rtype, name)
            return rtype, eligible, reason

    if is_generic_project_name(name) and not re.search(r"[A-Z]{0,3}\d{2,}", name):
        return RecordType.BUDGET_LINE_ITEM, False, "Generic budget-style name without specific scope"

    # Default: specific project if name looks concrete
    if re.search(r"\b(street|road|bridge|plant|facility|park|school|terminal|runway|pump|sewer|water main)\b", name, re.I):
        return RecordType.SPECIFIC_CAPITAL_PROJECT, True, None
    if re.search(r"[A-Z]{1,4}[- ]?\d{2,}", name):
        return RecordType.SPECIFIC_CAPITAL_PROJECT, True, None

    return RecordType.UNKNOWN, False, "Insufficient specificity for opportunity candidacy"


def _eligibility(rtype: RecordType, name: str) -> tuple[bool, str | None]:
    if rtype in {
        RecordType.SPECIFIC_CAPITAL_PROJECT,
        RecordType.MAJOR_EQUIPMENT_PURCHASE,
        RecordType.STUDY_OR_PLAN,
    }:
        return True, None
    if rtype == RecordType.CAPITAL_PROGRAM:
        return True, None  # certain external capital programs may be candidates
    reasons = {
        RecordType.BUDGET_LINE_ITEM: "Budget line item without defined external scope",
        RecordType.DEBT_FINANCING_RECORD: "Debt/financing record, not a project opportunity",
        RecordType.FUND_OR_TRANSFER: "Fund or transfer record",
        RecordType.MAINTENANCE_PROGRAM: "Maintenance program typically not a discrete external opportunity",
        RecordType.COMPLETED_HISTORICAL_PROJECT: "Completed/historical project",
        RecordType.UNKNOWN: "Unknown record type",
    }
    return False, reasons.get(rtype, "Not lead-eligible")
