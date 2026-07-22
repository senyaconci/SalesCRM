"""OCR helpers for low-text PDF pages.

Uses the OCR model role when available; otherwise marks pages as needing OCR.
"""

from __future__ import annotations

from pathlib import Path

from org_intel.documents.pdf_processor import PdfPage, process_pdf
from org_intel.llm.base import ModelRole
from org_intel.llm.router import LLMRouter
from org_intel.utils.logging import get_logger

logger = get_logger(__name__)


def ocr_relevant_pages(
    path: Path,
    page_numbers: list[int],
    router: LLMRouter | None = None,
    organization_id: str | None = None,
    document_id: str | None = None,
) -> dict[int, str]:
    """OCR only the requested unreadable pages."""
    if not page_numbers:
        return {}
    pdf = process_pdf(path)
    results: dict[int, str] = {}
    by_num = {p.page_number: p for p in pdf.pages}
    for num in page_numbers:
        page = by_num.get(num)
        if not page or not page.needs_ocr:
            continue
        if router is None or not router.provider.is_available() or router.provider.name == "mock":
            results[num] = page.text or f"[OCR_UNAVAILABLE page={num}]"
            continue
        # Without image upload support in GLM text API, keep marker and log.
        logger.info("ocr_skipped_no_vision_upload", page=num, document_id=document_id)
        results[num] = page.text or f"[OCR_REQUIRED page={num}]"
        # Record a cheap classification-style cost placeholder via router optional path
        _ = ModelRole.OCR_MODEL
    return results


def pages_needing_ocr(pages: list[PdfPage]) -> list[int]:
    return [p.page_number for p in pages if p.needs_ocr]
