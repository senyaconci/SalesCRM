"""Markdown → PDF exporter for the organization intelligence report."""

from __future__ import annotations

from pathlib import Path

import markdown
from xhtml2pdf import pisa

from org_intel.utils.io import ensure_dir
from org_intel.utils.logging import get_logger

logger = get_logger(__name__)

_CSS = """
@page { size: letter; margin: 0.7in; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.35; color: #111; }
h1 { font-size: 18pt; margin: 0 0 12pt 0; color: #1F4E79; }
h2 { font-size: 13pt; margin: 16pt 0 6pt 0; color: #1F4E79; border-bottom: 1px solid #ccc; padding-bottom: 3pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt 0; }
p, li { margin: 0 0 6pt 0; }
ul { margin: 0 0 8pt 18pt; }
code, pre { font-family: Courier, monospace; font-size: 8.5pt; }
a { color: #0563C1; text-decoration: none; }
"""


def export_pdf_report(output_dir: Path, markdown_path: Path | None = None) -> Path:
    """Render organization_intelligence.md to organization_intelligence.pdf."""
    ensure_dir(output_dir)
    md_path = markdown_path or (output_dir / "organization_intelligence.md")
    pdf_path = output_dir / "organization_intelligence.pdf"
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown report not found: {md_path}")

    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
    )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        f"<style>{_CSS}</style></head><body>{body}</body></html>"
    )
    with pdf_path.open("wb") as handle:
        result = pisa.CreatePDF(html, dest=handle, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} errors")
    logger.info("pdf_exported", path=str(pdf_path), bytes=pdf_path.stat().st_size)
    return pdf_path
