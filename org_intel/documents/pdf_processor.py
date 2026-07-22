"""PDF text extraction and page indexing with PyMuPDF."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from org_intel.utils.logging import get_logger

logger = get_logger(__name__)

MIN_TEXT_CHARS_PER_PAGE = 40


@dataclass
class PdfPage:
    page_number: int  # 1-based original page number
    text: str
    char_count: int
    is_low_text: bool
    needs_ocr: bool
    sha256: str


@dataclass
class PdfDocument:
    path: Path
    page_count: int
    pages: list[PdfPage] = field(default_factory=list)
    sha256: str = ""


def process_pdf(path: Path | str, *, ocr_pages: set[int] | None = None) -> PdfDocument:
    path = Path(path)
    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    doc = fitz.open(path)
    pages: list[PdfPage] = []
    ocr_pages = ocr_pages or set()

    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text("text") or ""
        char_count = len(text.strip())
        is_low = char_count < MIN_TEXT_CHARS_PER_PAGE
        needs_ocr = is_low
        if needs_ocr and (i + 1) in ocr_pages:
            # OCR hook — placeholder text marker; real OCR via llm/ocr module
            text = text or f"[OCR_REQUIRED page={i + 1}]"
        page_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        pages.append(
            PdfPage(
                page_number=i + 1,
                text=text,
                char_count=char_count,
                is_low_text=is_low,
                needs_ocr=needs_ocr,
                sha256=page_hash,
            )
        )
    count = doc.page_count
    doc.close()
    return PdfDocument(path=path, page_count=count, pages=pages, sha256=file_hash)


def render_page_windows(pages: list[PdfPage], page_numbers: list[int], window: int = 1) -> str:
    """Render evidence windows with explicit page boundaries."""
    wanted: set[int] = set()
    max_page = max((p.page_number for p in pages), default=0)
    for num in page_numbers:
        for p in range(max(1, num - window), min(max_page, num + window) + 1):
            wanted.add(p)
    by_num = {p.page_number: p for p in pages}
    chunks: list[str] = []
    for num in sorted(wanted):
        page = by_num.get(num)
        if not page:
            continue
        chunks.append(f"<<<PDF_PAGE_{num}>>>\n{page.text.strip()}")
    return "\n\n".join(chunks)
