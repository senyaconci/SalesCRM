from pathlib import Path

import fitz

from org_intel.documents.page_index import PageIndex
from org_intel.documents.pdf_processor import process_pdf, render_page_windows
from org_intel.projects.deduplication import find_merge_candidates
from org_intel.schemas.enums import RecordType
from org_intel.schemas.project import ProjectRecord


def test_pdf_page_indexing(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Project W0280 Westside Water Main Replacement budget $4,500,000")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Unrelated parks content")
    doc.save(path)
    doc.close()

    pdf = process_pdf(path)
    assert pdf.page_count == 2
    index = PageIndex.from_pdf("DOC-1", pdf)
    hits = index.search_project_id("W0280")
    assert hits and hits[0].page_number == 1
    name_hits = index.search_name("Westside Water Main Replacement")
    assert name_hits
    windows = render_page_windows(pdf.pages, [1], window=0)
    assert "<<<PDF_PAGE_1>>>" in windows


def test_generic_name_merge_prevention():
    a = ProjectRecord(
        organization_id="ORG-1",
        project_name="Water Improvements",
        record_type=RecordType.BUDGET_LINE_ITEM,
    )
    b = ProjectRecord(
        organization_id="ORG-1",
        project_name="Water Improvements",
        record_type=RecordType.BUDGET_LINE_ITEM,
    )
    decisions = find_merge_candidates([a, b])
    assert decisions
    assert decisions[0].decision == "keep_separate"


def test_project_id_merge():
    a = ProjectRecord(
        organization_id="ORG-1",
        project_id="W0280",
        project_name="Westside Water Main Replacement",
        location="Westside",
        department="Utilities",
        total_project_cost=4500000,
        construction_year="2027",
    )
    b = ProjectRecord(
        organization_id="ORG-1",
        project_id="W0280",
        project_name="Westside Water Main Replacement Project",
        location="Westside",
        department="Utilities",
        total_project_cost=4500000,
        construction_year="2027",
    )
    decisions = find_merge_candidates([a, b])
    assert decisions
    assert decisions[0].decision == "merge"
