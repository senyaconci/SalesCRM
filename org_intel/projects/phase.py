"""Project phase normalization with evidence requirements."""

from __future__ import annotations

import re

from org_intel.schemas.enums import ProjectPhase

_PHASE_PATTERNS: list[tuple[re.Pattern[str], ProjectPhase, bool]] = [
    (re.compile(r"\bcancel+ed\b", re.I), ProjectPhase.CANCELLED, False),
    (re.compile(r"\bdefer+ed\b|on hold", re.I), ProjectPhase.DEFERRED, False),
    (re.compile(r"\b(completed|complete|closeout|closed)\b", re.I), ProjectPhase.COMPLETED, False),
    (re.compile(r"\bcommissioning\b", re.I), ProjectPhase.COMMISSIONING, False),
    (re.compile(r"\b(under )?construction\b|construction underway", re.I), ProjectPhase.CONSTRUCTION, False),
    (re.compile(r"\bcontract awarded\b|notice to proceed", re.I), ProjectPhase.CONTRACT_AWARDED, False),
    (re.compile(r"\bbid evaluation\b|proposals? under review", re.I), ProjectPhase.BID_EVALUATION, False),
    (re.compile(r"\b(rfq|rfp)\s+(issued|released|advertised|open)\b", re.I), ProjectPhase.RFQ_RFP_ISSUED, False),
    (re.compile(r"\b(rfq|rfp)\s+preparation\b|preparing (rfq|rfp)", re.I), ProjectPhase.RFQ_RFP_PREPARATION, False),
    (re.compile(r"\bpre[- ]?procurement\b", re.I), ProjectPhase.PRE_PROCUREMENT, False),
    (re.compile(r"\b(permitting|environmental review|nepa|ceqa)\b", re.I), ProjectPhase.PERMITTING_ENVIRONMENTAL_REVIEW, False),
    (re.compile(r"\bfinal design\b|design complete", re.I), ProjectPhase.FINAL_DESIGN, False),
    (re.compile(r"\bpreliminary design\b|schematic design|30%\s*design", re.I), ProjectPhase.PRELIMINARY_DESIGN, False),
    (re.compile(r"\bconsultant selection\b|select(ing)? consultant", re.I), ProjectPhase.CONSULTANT_SELECTION, False),
    (re.compile(r"\bfunding approved\b|appropriated|budget adopted", re.I), ProjectPhase.FUNDING_APPROVED, True),
    (re.compile(r"\bfunding requested\b|budget request", re.I), ProjectPhase.FUNDING_REQUESTED, True),
    (re.compile(r"\bmaster plan(ning)?\b", re.I), ProjectPhase.MASTER_PLANNING, False),
    (re.compile(r"\bfeasibility\b", re.I), ProjectPhase.FEASIBILITY_STUDY, False),
    (re.compile(r"\bearly planning\b|planning phase", re.I), ProjectPhase.EARLY_PLANNING, False),
    (re.compile(r"\bconcept\b|identified need|needs assessment", re.I), ProjectPhase.CONCEPT_IDENTIFIED_NEED, False),
]


def normalize_phase(text: str | None) -> tuple[ProjectPhase, bool, str | None]:
    """Return (phase, is_inferred, evidence_snippet)."""
    if not text:
        return ProjectPhase.UNKNOWN, False, None
    for pattern, phase, inferred in _PHASE_PATTERNS:
        match = pattern.search(text)
        if match:
            return phase, inferred, match.group(0)
    return ProjectPhase.UNKNOWN, False, None
