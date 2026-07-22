"""Contact validation rules — never manufacture emails."""

from __future__ import annotations

from org_intel.schemas.contact import ContactRecord
from org_intel.schemas.enums import EmailStatus


def validate_contact(contact: ContactRecord) -> ContactRecord:
    if not contact.email:
        contact.email_status = EmailStatus.NONE
        return contact
    if contact.email_status == EmailStatus.PATTERN_INFERRED:
        # Pattern-inferred emails must not be treated as confirmed
        contact.confidence = min(contact.confidence, 0.4)
        contact.evidence = [
            e for e in contact.evidence if "manufactured" not in (e.quote or "").lower()
        ]
    return contact


def strip_manufactured_emails(contacts: list[ContactRecord]) -> list[ContactRecord]:
    cleaned: list[ContactRecord] = []
    for c in contacts:
        if c.email_status == EmailStatus.PATTERN_INFERRED:
            # Keep pattern note separately; clear individual email
            c.email = None
            c.email_status = EmailStatus.NONE
        cleaned.append(validate_contact(c))
    return cleaned
