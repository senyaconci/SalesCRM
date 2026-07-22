"""Phase 7 — inexpensive project index from the anchor source."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from bs4 import BeautifulSoup

from org_intel.documents.pdf_processor import process_pdf
from org_intel.projects.record_type_classifier import classify_record_type
from org_intel.retrieval.http_client import HttpClient
from org_intel.schemas.document import DocumentRecord
from org_intel.schemas.evidence import Evidence
from org_intel.schemas.project import ShallowProjectIndexRecord
from org_intel.utils.money import parse_money
from org_intel.utils.text import clean_whitespace

_PROJECT_ID_RE = re.compile(r"\b([A-Z]{1,4}[- ]?\d{2,5})\b")
_MONEY_LINE = re.compile(r"(\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+\s*[kmbKMB]?)")


def extract_project_index(
    organization_id: str,
    anchor: DocumentRecord,
    http: HttpClient,
    *,
    local_path: str | None = None,
) -> list[ShallowProjectIndexRecord]:
    path = local_path
    if not path:
        result = http.fetch(anchor.url, as_binary=anchor.file_type == "pdf")
        path = result.local_path

    if not path:
        return []

    file_type = (anchor.file_type or "").lower()
    if file_type in {"csv", "xlsx", "xls"} or path.endswith((".csv", ".xlsx", ".xls")):
        return _from_tabular(organization_id, anchor, Path(path))
    if file_type == "pdf" or path.endswith(".pdf"):
        return _from_pdf(organization_id, anchor, Path(path))
    return _from_html(organization_id, anchor, Path(path))


def _from_html(
    organization_id: str,
    anchor: DocumentRecord,
    path: Path,
) -> list[ShallowProjectIndexRecord]:
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    records: list[ShallowProjectIndexRecord] = []

    # Prefer structured CIP search tables with per-row detail links.
    cip_records = _from_cip_search_table(organization_id, anchor, soup)
    if cip_records:
        return _dedupe_index(cip_records)

    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [clean_whitespace(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        if len(rows) < 2:
            continue
        header = [c.lower() for c in rows[0]]
        if not _looks_like_project_header(header):
            # still try if enough columns
            if len(rows[0]) < 2:
                continue
        for row in rows[1:]:
            rec = _row_to_record(organization_id, anchor, header, row)
            if rec:
                records.append(rec)

    if records:
        return _dedupe_index(records)

    # Fallback: list items / headings that look like projects
    for li in soup.find_all(["li", "h2", "h3", "h4"]):
        text = clean_whitespace(li.get_text(" ", strip=True))
        if not text or len(text) < 8 or len(text) > 160:
            continue
        if not (_PROJECT_ID_RE.search(text) or re.search(r"\b(project|improvement|replacement|extension)\b", text, re.I)):
            continue
        pid = None
        m = _PROJECT_ID_RE.search(text)
        if m:
            pid = m.group(1).replace(" ", "-")
        rtype, eligible, reason = classify_record_type(text)
        records.append(
            ShallowProjectIndexRecord(
                organization_id=organization_id,
                project_id=pid,
                project_name=text,
                source_url=anchor.url,
                record_type=rtype,
                confidence=0.45,
                evidence=[
                    Evidence(url=anchor.url, title=anchor.title, quote=text, supports_fields=["project_name"], confidence=0.45)
                ],
            )
        )
    return _dedupe_index(records)


def _from_pdf(
    organization_id: str,
    anchor: DocumentRecord,
    path: Path,
) -> list[ShallowProjectIndexRecord]:
    pdf = process_pdf(path)
    records: list[ShallowProjectIndexRecord] = []
    # Scan pages for tabular-ish lines with project IDs or capital keywords
    for page in pdf.pages:
        lines = [clean_whitespace(l) for l in page.text.splitlines() if clean_whitespace(l)]
        for line in lines:
            if len(line) < 8 or len(line) > 200:
                continue
            pid_match = _PROJECT_ID_RE.search(line)
            has_money = bool(_MONEY_LINE.search(line))
            has_keyword = bool(
                re.search(r"\b(project|improvement|replacement|reconstruction|extension|facility)\b", line, re.I)
            )
            if not (pid_match or (has_money and has_keyword)):
                continue
            pid = pid_match.group(1).replace(" ", "-") if pid_match else None
            name = line
            if pid:
                name = clean_whitespace(line.replace(pid_match.group(0), "")).strip(" -–|:;")
            if not name:
                name = line
            money = parse_money(_MONEY_LINE.search(line).group(0)) if has_money else None
            rtype, _, _ = classify_record_type(name)
            records.append(
                ShallowProjectIndexRecord(
                    organization_id=organization_id,
                    project_id=pid,
                    project_name=name[:240],
                    total_project_cost=money,
                    source_url=anchor.url,
                    source_page=page.page_number,
                    record_type=rtype,
                    confidence=0.55 if pid else 0.4,
                    evidence=[
                        Evidence(
                            document_id=anchor.document_id,
                            url=anchor.url,
                            title=anchor.title,
                            page=page.page_number,
                            quote=line[:400],
                            supports_fields=["project_name", "project_id", "total_project_cost"],
                            confidence=0.55 if pid else 0.4,
                        )
                    ],
                )
            )
    return _dedupe_index(records)


def _from_tabular(
    organization_id: str,
    anchor: DocumentRecord,
    path: Path,
) -> list[ShallowProjectIndexRecord]:
    records: list[ShallowProjectIndexRecord] = []
    if path.suffix.lower() == ".csv":
        text = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    else:
        try:
            import pandas as pd

            df = pd.read_excel(path)
            rows = [list(map(str, df.columns))] + df.astype(str).values.tolist()
        except Exception:
            return []
    if len(rows) < 2:
        return []
    header = [clean_whitespace(str(c)).lower() for c in rows[0]]
    for row in rows[1:]:
        row = [clean_whitespace(str(c)) for c in row]
        rec = _row_to_record(organization_id, anchor, header, row)
        if rec:
            records.append(rec)
    return _dedupe_index(records)


def _from_cip_search_table(
    organization_id: str,
    anchor: DocumentRecord,
    soup: BeautifulSoup,
) -> list[ShallowProjectIndexRecord]:
    """Parse live CIP registries such as Columbia's cipweb project_search table."""
    records: list[ShallowProjectIndexRecord] = []
    for table in soup.find_all("table"):
        header_cells = table.find("tr")
        if not header_cells:
            continue
        header = [
            clean_whitespace(c.get_text(" ", strip=True)).lower()
            for c in header_cells.find_all(["th", "td"])
        ]
        joined = " ".join(header)
        if not (
            "project" in joined
            and ("status" in joined or "year" in joined or "division" in joined)
        ):
            continue
        for tr in table.find_all("tr")[1:]:
            cells = [clean_whitespace(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            name = cells[0]
            if not name or name.lower() in {"project", "total", "nan"}:
                continue
            link = tr.find("a", href=True)
            detail_url = None
            if link:
                from urllib.parse import urljoin

                detail_url = urljoin(anchor.url, link["href"])
            pid_match = _PROJECT_ID_RE.search(name)
            pid = pid_match.group(1).replace(" ", "") if pid_match else None
            # Common CIP columns: Project | Status | Const. Year | Ballot | Ward | Division
            stage = cells[1] if len(cells) > 1 else None
            year = cells[2] if len(cells) > 2 else None
            ballot = cells[3] if len(cells) > 3 else None
            division = cells[5] if len(cells) > 5 else (cells[4] if len(cells) > 4 else None)
            rtype, _, _ = classify_record_type(name, division, stage)
            records.append(
                ShallowProjectIndexRecord(
                    organization_id=organization_id,
                    project_id=pid,
                    project_name=name[:240],
                    department=division,
                    category=division,
                    published_stage=stage,
                    construction_year=year if year and year.lower() not in {"none", "none..."} else None,
                    ballot_label=ballot or None,
                    project_detail_url=detail_url,
                    source_url=anchor.url,
                    record_type=rtype,
                    confidence=0.85,
                    evidence=[
                        Evidence(
                            document_id=anchor.document_id,
                            url=detail_url or anchor.url,
                            title=anchor.title,
                            quote=" | ".join(cells)[:400],
                            supports_fields=[
                                "project_name",
                                "project_id",
                                "published_stage",
                                "construction_year",
                            ],
                            confidence=0.85,
                        )
                    ],
                )
            )
    return records


def _looks_like_project_header(header: list[str]) -> bool:
    joined = " ".join(header)
    return bool(
        re.search(r"project|name|description|department|cost|budget|phase|status|year", joined, re.I)
    )


def _row_to_record(
    organization_id: str,
    anchor: DocumentRecord,
    header: list[str],
    row: list[str],
) -> ShallowProjectIndexRecord | None:
    data = {}
    for i, col in enumerate(header):
        if i < len(row):
            data[col] = row[i]
    if not header or len(header) != len(row):
        # positional fallback
        if len(row) < 2:
            return None
        name = row[1] if _PROJECT_ID_RE.search(row[0] or "") else row[0]
        pid = row[0] if _PROJECT_ID_RE.search(row[0] or "") else None
    else:
        name = _pick(data, ["project name", "name", "project", "title", "description"]) or ""
        pid = _pick(data, ["project id", "project #", "project no", "id", "number", "cip #"])
        if not pid:
            m = _PROJECT_ID_RE.search(" ".join(row))
            pid = m.group(1).replace(" ", "-") if m else None
        if not name:
            # use longest cell
            name = max(row, key=len)
    name = clean_whitespace(name)
    if not name or name.lower() in {"nan", "none", "total", "subtotal"}:
        return None

    dept = _pick(data, ["department", "dept", "division", "agency"])
    category = _pick(data, ["category", "type", "fund", "program"])
    location = _pick(data, ["location", "address", "site"])
    stage = _pick(data, ["stage", "phase", "status", "project status"])
    year = _pick(data, ["construction year", "year", "fy", "fiscal year"])
    funding = _pick(data, ["funding", "fund source", "funding source"])
    cost_raw = _pick(data, ["total cost", "project cost", "budget", "amount", "total"])
    cost = parse_money(cost_raw)
    detail = _pick(data, ["url", "link", "detail", "project url"])

    rtype, _, _ = classify_record_type(name, category, stage)
    return ShallowProjectIndexRecord(
        organization_id=organization_id,
        project_id=pid,
        project_name=name[:240],
        department=dept,
        category=category,
        location=location,
        published_stage=stage,
        construction_year=year,
        funding_label=funding,
        project_detail_url=detail,
        source_url=anchor.url,
        total_project_cost=cost,
        record_type=rtype,
        confidence=0.7,
        evidence=[
            Evidence(
                document_id=anchor.document_id,
                url=anchor.url,
                title=anchor.title,
                quote=" | ".join(row)[:400],
                supports_fields=["project_name", "project_id"],
                confidence=0.7,
            )
        ],
    )


def _pick(data: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        for col, val in data.items():
            if key == col or key in col:
                if val and val.lower() not in {"nan", "none", ""}:
                    return val
    return None


def _dedupe_index(records: list[ShallowProjectIndexRecord]) -> list[ShallowProjectIndexRecord]:
    seen: set[str] = set()
    out: list[ShallowProjectIndexRecord] = []
    for rec in records:
        key = (rec.project_id or "").upper() + "|" + rec.project_name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out
