"""PDF acquisition, inspection, native text extraction, and chunking."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import fitz  # PyMuPDF
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from budget_extractor.utils import (
    chunk_id_for_index,
    document_stem,
    ensure_dir,
    is_url,
    safe_filename,
    sha256_file,
)

LOGGER = logging.getLogger(__name__)

PAGE_MARKER_RE = re.compile(r"<<<PDF_PAGE_(\d+)>>>")
PROJECT_BOUNDARY_HINTS = re.compile(
    r"(?im)^(project\s*(name|title|number|#)|capital\s+project|cip\s+project|"
    r"project\s+description|estimated\s+cost|total\s+project\s+cost)\b"
)


@dataclass
class PageTextInfo:
    page_number: int
    text: str
    char_count: int
    word_count: int
    printable_ratio: float
    is_empty: bool
    appears_corrupted: bool
    needs_ocr: bool
    used_ocr: bool = False
    ocr_failed: bool = False


@dataclass
class PdfDocumentInfo:
    local_path: Path
    source_path: str
    source_url: str | None
    filename: str
    file_size: int
    sha256: str
    total_pages: int
    metadata: dict[str, Any] = field(default_factory=dict)
    acquired_at: str = ""


@dataclass
class TextChunk:
    chunk_id: str
    start_page: int
    end_page: int
    text: str
    page_numbers: list[int]


@dataclass
class ExtractedDocumentText:
    document: PdfDocumentInfo
    pages: list[PageTextInfo]
    full_text: str

    @property
    def page_map(self) -> dict[int, PageTextInfo]:
        return {page.page_number: page for page in self.pages}


class PdfProcessingError(Exception):
    """Raised for unrecoverable PDF problems."""


def acquire_pdf(input_path: str, work_dir: str | Path) -> PdfDocumentInfo:
    """Download or copy a PDF into the working directory and inspect it."""
    work_dir = ensure_dir(work_dir)
    acquired_at = datetime.now(timezone.utc).isoformat()

    if is_url(input_path):
        local_path = _download_pdf(input_path, work_dir)
        source_url = input_path
        source_path = input_path
    else:
        src = Path(input_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"PDF not found: {src}")
        if not src.is_file():
            raise PdfProcessingError(f"Input path is not a file: {src}")
        local_path = work_dir / safe_filename(src.name)
        if src.resolve() != local_path.resolve():
            local_path.write_bytes(src.read_bytes())
        source_url = None
        source_path = str(src)

    if local_path.stat().st_size == 0:
        raise PdfProcessingError("PDF file is empty")

    header = local_path.read_bytes()[:5]
    if header != b"%PDF-":
        raise PdfProcessingError("Input does not appear to be a valid PDF (missing %PDF- header)")

    try:
        doc = fitz.open(local_path)
    except Exception as exc:  # noqa: BLE001
        raise PdfProcessingError(f"Unable to open PDF: {exc}") from exc

    try:
        if doc.is_encrypted and not doc.authenticate(""):
            raise PdfProcessingError("PDF is encrypted and cannot be opened without a password")
        if doc.page_count < 1:
            raise PdfProcessingError("PDF contains no pages")

        metadata = dict(doc.metadata or {})
        info = PdfDocumentInfo(
            local_path=local_path,
            source_path=source_path,
            source_url=source_url,
            filename=local_path.name,
            file_size=local_path.stat().st_size,
            sha256=sha256_file(local_path),
            total_pages=doc.page_count,
            metadata=metadata,
            acquired_at=acquired_at,
        )
    finally:
        doc.close()

    LOGGER.info(
        "Acquired PDF %s (%s pages, %.1f MB)",
        info.filename,
        info.total_pages,
        info.file_size / (1024 * 1024),
    )
    return info


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((requests.RequestException,)),
)
def _download_pdf(url: str, work_dir: Path) -> Path:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "downloaded_budget.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{safe_filename(name)}.pdf"
    target = work_dir / safe_filename(name)

    LOGGER.info("Downloading PDF from URL")
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        first_chunk = next(response.iter_content(chunk_size=8192), b"")
        if not first_chunk.startswith(b"%PDF-") and "pdf" not in content_type:
            raise PdfProcessingError(
                f"Downloaded content does not look like a PDF (content-type={content_type!r})"
            )
        with open(target, "wb") as handle:
            handle.write(first_chunk)
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)
    return target


def analyze_page_text(page_number: int, text: str) -> PageTextInfo:
    raw = text or ""
    char_count = len(raw)
    words = re.findall(r"\S+", raw)
    word_count = len(words)
    if char_count == 0:
        printable_ratio = 0.0
    else:
        printable = sum(1 for ch in raw if ch.isprintable() or ch.isspace())
        printable_ratio = printable / char_count

    is_empty = char_count < 20 or word_count < 3
    appears_corrupted = printable_ratio < 0.75 and char_count > 40
    # Very low text density often indicates scanned pages.
    needs_ocr = is_empty or appears_corrupted or (char_count < 80 and word_count < 12)

    return PageTextInfo(
        page_number=page_number,
        text=raw,
        char_count=char_count,
        word_count=word_count,
        printable_ratio=printable_ratio,
        is_empty=is_empty,
        appears_corrupted=appears_corrupted,
        needs_ocr=needs_ocr,
    )


def extract_native_text(
    document: PdfDocumentInfo,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> ExtractedDocumentText:
    """Extract native text page-by-page with explicit page markers."""
    doc = fitz.open(document.local_path)
    pages: list[PageTextInfo] = []
    parts: list[str] = []

    first = start_page or 1
    last = end_page or document.total_pages
    first = max(1, first)
    last = min(document.total_pages, last)

    try:
        for page_number in range(first, last + 1):
            page = doc.load_page(page_number - 1)
            text = page.get_text("text") or ""
            info = analyze_page_text(page_number, text)
            pages.append(info)
            parts.append(f"<<<PDF_PAGE_{page_number}>>>\n{text.strip()}")
    finally:
        doc.close()

    full_text = "\n\n".join(parts).strip() + "\n"
    return ExtractedDocumentText(document=document, pages=pages, full_text=full_text)


def apply_ocr_text(
    extracted: ExtractedDocumentText,
    ocr_page_texts: dict[int, str],
) -> ExtractedDocumentText:
    """Replace/supplement page text with OCR results while preserving markers."""
    updated_pages: list[PageTextInfo] = []
    parts: list[str] = []
    for page in extracted.pages:
        if page.page_number in ocr_page_texts:
            ocr_text = ocr_page_texts[page.page_number] or ""
            info = analyze_page_text(page.page_number, ocr_text)
            info.used_ocr = True
            info.needs_ocr = False
            updated_pages.append(info)
            parts.append(f"<<<PDF_PAGE_{page.page_number}>>>\n{ocr_text.strip()}")
        else:
            updated_pages.append(page)
            parts.append(f"<<<PDF_PAGE_{page.page_number}>>>\n{page.text.strip()}")

    full_text = "\n\n".join(parts).strip() + "\n"
    return ExtractedDocumentText(
        document=extracted.document,
        pages=updated_pages,
        full_text=full_text,
    )


def mark_ocr_failures(
    extracted: ExtractedDocumentText,
    failed_pages: list[int],
) -> ExtractedDocumentText:
    failed = set(failed_pages)
    pages: list[PageTextInfo] = []
    for page in extracted.pages:
        if page.page_number in failed:
            page.ocr_failed = True
        pages.append(page)
    return ExtractedDocumentText(
        document=extracted.document,
        pages=pages,
        full_text=extracted.full_text,
    )


def split_pdf_pages(
    source_pdf: str | Path,
    page_numbers: list[int],
    output_path: str | Path,
) -> Path:
    """Create a temporary PDF containing the selected 1-based pages."""
    source_pdf = Path(source_pdf)
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    src = fitz.open(source_pdf)
    out = fitz.open()
    try:
        for page_number in page_numbers:
            out.insert_pdf(src, from_page=page_number - 1, to_page=page_number - 1)
        out.save(output_path)
    finally:
        out.close()
        src.close()
    return output_path


def build_page_delimited_text(pages: list[PageTextInfo], page_numbers: list[int]) -> str:
    page_map = {page.page_number: page for page in pages}
    parts: list[str] = []
    for page_number in page_numbers:
        page = page_map[page_number]
        parts.append(f"<<<PDF_PAGE_{page_number}>>>\n{(page.text or '').strip()}")
    return "\n\n".join(parts).strip() + "\n"


def _find_boundary_shift(pages: list[PageTextInfo], candidate: int, hard_end: int) -> int:
    """Prefer ending a chunk on an obvious project-sheet boundary when feasible."""
    page_map = {page.page_number: page for page in pages}
    # Look a few pages forward/back for a heading-like boundary.
    for offset in range(0, 3):
        for page_number in (candidate - offset, candidate + offset):
            if page_number < 1 or page_number > hard_end:
                continue
            text = page_map.get(page_number).text if page_number in page_map else ""
            if text and PROJECT_BOUNDARY_HINTS.search(text[:800]):
                return min(max(page_number, candidate - 2), hard_end)
    return candidate


def chunk_pages(
    pages: list[PageTextInfo],
    *,
    chunk_pages: int = 20,
    overlap_pages: int = 2,
) -> list[TextChunk]:
    if not pages:
        return []
    page_numbers = [page.page_number for page in pages]
    first = page_numbers[0]
    last = page_numbers[-1]
    chunks: list[TextChunk] = []
    index = 1
    start = first

    while start <= last:
        nominal_end = min(start + chunk_pages - 1, last)
        end = _find_boundary_shift(pages, nominal_end, last) if nominal_end < last else nominal_end
        selected = [p for p in page_numbers if start <= p <= end]
        text = build_page_delimited_text(pages, selected)
        chunks.append(
            TextChunk(
                chunk_id=chunk_id_for_index(index),
                start_page=start,
                end_page=end,
                text=text,
                page_numbers=selected,
            )
        )
        if end >= last:
            break
        start = max(end - overlap_pages + 1, start + 1)
        index += 1

    return chunks


def extract_page_markers(text: str) -> list[int]:
    return [int(match) for match in PAGE_MARKER_RE.findall(text or "")]


def default_work_dirs(output_dir: str | Path) -> dict[str, Path]:
    output_dir = ensure_dir(output_dir)
    return {
        "output": output_dir,
        "work": ensure_dir(output_dir / "work"),
        "ocr": ensure_dir(output_dir / "work" / "ocr"),
        "downloads": ensure_dir(output_dir / "work" / "downloads"),
        "checkpoints": ensure_dir(output_dir / "checkpoints"),
        "intermediate": ensure_dir(output_dir / "intermediate"),
    }


def suggest_document_title(document: PdfDocumentInfo) -> str:
    title = (document.metadata.get("title") or "").strip()
    if title:
        return title
    return document_stem(document.filename).replace("_", " ").replace("-", " ").strip()
