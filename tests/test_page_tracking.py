from __future__ import annotations

from pathlib import Path

import fitz

from budget_extractor.pdf_processor import (
    acquire_pdf,
    analyze_page_text,
    chunk_pages,
    extract_native_text,
    extract_page_markers,
)


def test_page_marker_preservation(tmp_path: Path):
    pdf_path = tmp_path / "synthetic.pdf"
    doc = fitz.open()
    for idx in range(1, 6):
        page = doc.new_page()
        page.insert_text((72, 72), f"Project Alpha page {idx}. Capital improvement budget $100,000.")
    doc.save(pdf_path)
    doc.close()

    info = acquire_pdf(str(pdf_path), tmp_path / "work")
    extracted = extract_native_text(info)
    markers = extract_page_markers(extracted.full_text)
    assert markers == [1, 2, 3, 4, 5]
    assert "<<<PDF_PAGE_3>>>" in extracted.full_text
    assert "Project Alpha page 3" in extracted.full_text


def test_analyze_page_flags_empty_for_ocr():
    info = analyze_page_text(1, "")
    assert info.needs_ocr is True
    assert info.is_empty is True


def test_chunk_pages_overlap():
    pages = [analyze_page_text(i, f"content {i} " * 20) for i in range(1, 11)]
    chunks = chunk_pages(pages, chunk_pages=4, overlap_pages=1)
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 4
    assert chunks[1].start_page == 4  # overlap
    assert "<<<PDF_PAGE_4>>>" in chunks[0].text
    assert "<<<PDF_PAGE_4>>>" in chunks[1].text
