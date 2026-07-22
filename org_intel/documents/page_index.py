"""Local full-text page index for project matching without LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from org_intel.documents.pdf_processor import PdfDocument, PdfPage
from org_intel.utils.names import normalize_project_name


@dataclass
class PageHit:
    page_number: int
    score: float
    match_method: str
    matched_terms: list[str] = field(default_factory=list)
    snippet: str = ""


@dataclass
class PageIndex:
    document_id: str
    pages: list[PdfPage]
    _normalized: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for page in self.pages:
            self._normalized[page.page_number] = normalize_project_name(page.text)

    @classmethod
    def from_pdf(cls, document_id: str, pdf: PdfDocument) -> "PageIndex":
        return cls(document_id=document_id, pages=pdf.pages)

    def search_project_id(self, project_id: str) -> list[PageHit]:
        if not project_id:
            return []
        pattern = re.compile(rf"\b{re.escape(project_id)}\b", re.I)
        hits: list[PageHit] = []
        for page in self.pages:
            if pattern.search(page.text):
                hits.append(
                    PageHit(
                        page_number=page.page_number,
                        score=100.0,
                        match_method="project_id",
                        matched_terms=[project_id],
                        snippet=_snippet(page.text, project_id),
                    )
                )
        return hits

    def search_name(self, name: str, *, threshold: float = 85.0) -> list[PageHit]:
        norm = normalize_project_name(name)
        if not norm or len(norm) < 4:
            return []
        hits: list[PageHit] = []
        for page in self.pages:
            page_norm = self._normalized[page.page_number]
            if norm in page_norm:
                hits.append(
                    PageHit(
                        page_number=page.page_number,
                        score=100.0,
                        match_method="exact_name",
                        matched_terms=[name],
                        snippet=_snippet(page.text, name),
                    )
                )
                continue
            # Fuzzy against sliding windows of words
            score = float(fuzz.partial_ratio(norm, page_norm))
            if score >= threshold:
                hits.append(
                    PageHit(
                        page_number=page.page_number,
                        score=score,
                        match_method="fuzzy_name",
                        matched_terms=[name],
                        snippet=_snippet(page.text, name.split()[0] if name.split() else name),
                    )
                )
        return sorted(hits, key=lambda h: (-h.score, h.page_number))


def _snippet(text: str, term: str, radius: int = 120) -> str:
    lower = text.lower()
    idx = lower.find(term.lower())
    if idx < 0:
        return text[: radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(term) + radius)
    return text[start:end].strip()
