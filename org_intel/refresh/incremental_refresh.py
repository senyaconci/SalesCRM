"""Incremental refresh orchestration helpers."""

from __future__ import annotations

from org_intel.refresh.change_detector import detect_project_changes, document_changed
from org_intel.retrieval.http_client import HttpClient
from org_intel.schemas.document import DocumentInventory, DocumentRecord
from org_intel.schemas.evidence import ChangeRecord
from org_intel.schemas.project import ProjectRecord


def refresh_documents(
    inventory: DocumentInventory,
    http: HttpClient,
) -> tuple[list[DocumentRecord], list[str]]:
    """Re-fetch known docs; return changed documents and change notes."""
    changed: list[DocumentRecord] = []
    notes: list[str] = []
    for doc in inventory.documents:
        old_sha = doc.sha256
        try:
            result = http.fetch(doc.url, force=True, as_binary=True)
            if document_changed(old_sha, result.sha256):
                doc.sha256 = result.sha256 or ""
                doc.local_path = result.local_path
                doc.processed = False
                doc.indexed = False
                changed.append(doc)
                notes.append(f"Changed document: {doc.title or doc.url}")
        except Exception as exc:
            notes.append(f"Failed to refresh {doc.url}: {exc}")
    return changed, notes


def affected_projects_from_changes(
    changes: list[ChangeRecord],
    projects: list[ProjectRecord],
) -> list[ProjectRecord]:
    ids = {c.project_id or c.entity_id for c in changes}
    return [p for p in projects if (p.project_id or p.record_id) in ids]


def compute_refresh_changes(
    previous_projects: list[ProjectRecord],
    current_projects: list[ProjectRecord],
) -> list[ChangeRecord]:
    return detect_project_changes(previous_projects, current_projects)
