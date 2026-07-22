"""Content download cache keyed by URL and content hash."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select

from org_intel.database import Database, DocumentCacheRow
from org_intel.utils.io import ensure_dir
from org_intel.utils.urls import normalize_url


class ContentCache:
    def __init__(self, db: Database, cache_dir: Path) -> None:
        self.db = db
        self.cache_dir = ensure_dir(cache_dir)
        self.files_dir = ensure_dir(self.cache_dir / "files")

    def get(self, url: str) -> DocumentCacheRow | None:
        norm = normalize_url(url)
        with self.db.session() as session:
            return session.scalar(
                select(DocumentCacheRow).where(DocumentCacheRow.url == norm)
            )

    def put(
        self,
        url: str,
        content: bytes,
        content_type: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        page_count: int | None = None,
        suffix: str | None = None,
    ) -> DocumentCacheRow:
        norm = normalize_url(url)
        digest = hashlib.sha256(content).hexdigest()
        ext = suffix or _guess_ext(content_type, norm)
        path = self.files_dir / f"{digest}{ext}"
        if not path.exists():
            path.write_bytes(content)
        with self.db.session() as session:
            existing = session.scalar(
                select(DocumentCacheRow).where(DocumentCacheRow.url == norm)
            )
            if existing:
                existing.sha256 = digest
                existing.local_path = str(path)
                existing.content_type = content_type
                existing.page_count = page_count
                existing.etag = etag
                existing.last_modified = last_modified
                row = existing
            else:
                row = DocumentCacheRow(
                    url=norm,
                    sha256=digest,
                    local_path=str(path),
                    content_type=content_type,
                    page_count=page_count,
                    etag=etag,
                    last_modified=last_modified,
                )
                session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def path_for_hash(self, sha256: str, suffix: str = "") -> Path:
        return self.files_dir / f"{sha256}{suffix}"


def _guess_ext(content_type: str | None, url: str) -> str:
    if content_type:
        ct = content_type.lower()
        if "pdf" in ct:
            return ".pdf"
        if "html" in ct:
            return ".html"
        if "json" in ct:
            return ".json"
        if "csv" in ct:
            return ".csv"
        if "spreadsheet" in ct or "excel" in ct:
            return ".xlsx"
    lower = url.lower()
    for ext in (".pdf", ".html", ".htm", ".csv", ".xlsx", ".xls", ".json"):
        if lower.endswith(ext):
            return ext if ext != ".htm" else ".html"
    return ".bin"
