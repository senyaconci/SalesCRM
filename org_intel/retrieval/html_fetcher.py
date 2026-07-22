"""HTML fetching and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from org_intel.retrieval.http_client import FetchResult, HttpClient
from org_intel.utils.text import clean_whitespace
from org_intel.utils.urls import absolutize, domain_of, normalize_url


@dataclass
class ParsedPage:
    url: str
    title: str
    text: str
    links: list[dict[str, str]] = field(default_factory=list)
    headings: list[dict[str, str]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)


class HtmlFetcher:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def fetch_and_parse(self, url: str, *, force: bool = False) -> tuple[FetchResult, ParsedPage]:
        result = self.http.fetch(url, force=force)
        page = parse_html(result.text, result.final_url or result.url)
        return result, page


def parse_html(html: str, url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = clean_whitespace(soup.title.get_text() if soup.title else "")
    text = clean_whitespace(soup.get_text(" ", strip=True))

    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        abs_url = absolutize(url, a.get("href"))
        if not abs_url or abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(
            {
                "url": abs_url,
                "text": clean_whitespace(a.get_text(" ", strip=True))[:300],
                "domain": domain_of(abs_url),
            }
        )

    headings = []
    for level in range(1, 5):
        for h in soup.find_all(f"h{level}"):
            headings.append(
                {"level": str(level), "text": clean_whitespace(h.get_text(" ", strip=True))}
            )

    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [
                clean_whitespace(td.get_text(" ", strip=True))
                for td in tr.find_all(["th", "td"])
            ]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    meta: dict[str, str] = {}
    for m in soup.find_all("meta"):
        key = m.get("name") or m.get("property")
        if key and m.get("content"):
            meta[str(key)] = str(m.get("content"))

    return ParsedPage(
        url=normalize_url(url),
        title=title,
        text=text,
        links=links,
        headings=headings,
        tables=tables,
        meta=meta,
    )
